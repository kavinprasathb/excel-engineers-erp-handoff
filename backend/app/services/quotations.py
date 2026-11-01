"""Quotation queries, numbering, revisions and status.

Rules, all enforced here and nowhere else:

* A number is `<PREFIX>-<YY>-<seq>`, sequence per (type, year), restarting
  each year, issued under a row lock so two people saving at once never share
  one. Revisions append `R<n>` and keep the sequence.
* Only the latest revision of a number may change, and only while pending.
  Revising marks the old row superseded and copies everything into a new one.
* Lines and terms are replaced wholesale on every save — the editor is one
  form, so the API is one body.
"""

from datetime import date
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased, selectinload

from ..constants import (
    DEFAULT_QUOTATION_SPECS,
    DEFAULT_QUOTATION_TERMS,
    QUOTATION_PREFIXES,
    LineKind,
    QuotationStatus,
    QuotationType,
    VersionKind,
)
from ..errors import Conflict, NotFound, QuotationLocked, ValidationFailed
from ..models import (
    AppSettings,
    Customer,
    CustomerBranch,
    Product,
    Quotation,
    QuotationCounter,
    QuotationLine,
    QuotationTerm,
)
from ..schemas.quotation import (
    Deviation,
    LineIn,
    QuotationCreate,
    QuotationUpdate,
    TechRow,
    TermIn,
)
from .like import LIKE_ESCAPE, contains

_newer = aliased(Quotation)

SORTS: dict[str, Any] = {
    "-updated_at": Quotation.updated_at.desc(),
    "updated_at": Quotation.updated_at.asc(),
    "-quote_date": Quotation.quote_date.desc(),
    "quote_date": Quotation.quote_date.asc(),
    "number": (Quotation.year.asc(), Quotation.seq.asc(), Quotation.revision.asc()),
    "-number": (Quotation.year.desc(), Quotation.seq.desc(), Quotation.revision.desc()),
}


def format_number(
    type_: QuotationType, year: int, seq: int, rev_no: int = 0, neg_no: int = 0
) -> str:
    """ESQSP-26-70, ESQSP-26-70-R2 (second revised quotation), ESQSP-26-70N1
    (first negotiation of the original), ESQSP-26-70-R2N1 (first negotiation
    of R2). The original number always leads, so every version is found by it.
    """
    number = f"{QUOTATION_PREFIXES[type_]}-{year:02d}-{seq}"
    if rev_no:
        number += f"-R{rev_no}"
    if neg_no:
        number += f"N{neg_no}"
    return number


# Which list a number is on, by its latest version: the original quotation,
# a revised quotation (R, no negotiation yet), or a negotiation (N).
STAGES = ("quotation", "revised", "negotiation")


def _next_seq(db: Session, type_: QuotationType, year: int) -> int:
    """Take the next sequence number under a row lock.

    The counter row for a (type, year) is created on first use with an
    idempotent insert, then locked FOR UPDATE, so concurrent creates serialise
    on it and each gets a distinct number. The unique constraint on the
    quotation itself is the backstop should that ever fail.
    """
    db.execute(
        pg_insert(QuotationCounter)
        .values(type=type_.value, year=year, last_seq=0)
        .on_conflict_do_nothing()
    )
    counter = db.execute(
        select(QuotationCounter)
        .where(QuotationCounter.type == type_, QuotationCounter.year == year)
        .with_for_update()
    ).scalar_one()
    counter.last_seq += 1
    db.flush()
    return counter.last_seq


def _load_options(stmt: Select[tuple[Quotation]]) -> Select[tuple[Quotation]]:
    return stmt.options(
        selectinload(Quotation.customer),
        selectinload(Quotation.customer_branch),
        selectinload(Quotation.lines),
        selectinload(Quotation.terms),
    )


def _is_latest_clause() -> Any:
    """True for rows with no higher revision of the same number."""
    newer = select(1).where(
        # Correlated: `Quotation` outside, `_newer` inside.
        _newer.type == Quotation.type,
        _newer.year == Quotation.year,
        _newer.seq == Quotation.seq,
        _newer.revision > Quotation.revision,
    )
    return ~newer.exists()


def _filtered(
    *,
    q: str | None,
    type_: QuotationType | None,
    status: QuotationStatus | None,
    customer_id: int | None,
    latest_only: bool,
    negotiated: bool | None = None,
    stage: str | None = None,
) -> Select[tuple[Quotation]]:
    stmt = select(Quotation)
    if negotiated is not None:
        # Kept for older clients: true is the Negotiations list, false the originals.
        stage = "negotiation" if negotiated else "quotation"
    if stage == "negotiation":
        stmt = stmt.where(Quotation.neg_no > 0)
    elif stage == "revised":
        stmt = stmt.where(Quotation.rev_no > 0, Quotation.neg_no == 0)
    elif stage == "quotation":
        stmt = stmt.where(Quotation.rev_no == 0, Quotation.neg_no == 0)
    if latest_only:
        # One row per number: the list is "what offers are out there", and
        # a superseded R0 beside its R1 is the same offer shown twice.
        stmt = stmt.where(_is_latest_clause())
    if q:
        pattern = contains(q)
        stmt = stmt.join(Quotation.customer).where(
            or_(
                Quotation.number.ilike(pattern, escape=LIKE_ESCAPE),
                Quotation.subject.ilike(pattern, escape=LIKE_ESCAPE),
                Customer.name.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if type_ is not None:
        stmt = stmt.where(Quotation.type == type_)
    if status is not None:
        stmt = stmt.where(Quotation.status == status)
    if customer_id is not None:
        stmt = stmt.where(Quotation.customer_id == customer_id)
    return stmt


def list_quotations(
    db: Session,
    *,
    q: str | None = None,
    type_: QuotationType | None = None,
    status: QuotationStatus | None = None,
    customer_id: int | None = None,
    latest_only: bool = True,
    negotiated: bool | None = None,
    stage: str | None = None,
    sort: str = "-updated_at",
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Quotation], int]:
    stmt = _filtered(
        q=q,
        type_=type_,
        status=status,
        customer_id=customer_id,
        latest_only=latest_only,
        negotiated=negotiated,
        stage=stage,
    )
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(Quotation.id).subquery())
    ).scalar_one()
    order = SORTS[sort]
    order = order if isinstance(order, tuple) else (order,)
    rows = (
        db.execute(
            _load_options(stmt.order_by(*order, Quotation.id.desc()).offset(offset).limit(limit))
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_quotation(db: Session, quotation_id: int) -> Quotation:
    row = db.execute(
        _load_options(select(Quotation).where(Quotation.id == quotation_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"Quotation {quotation_id} was not found.", quotation_id=quotation_id)
    return row


def list_revisions(db: Session, quotation: Quotation) -> list[Quotation]:
    """Every revision of this number, oldest first — the history one screen shows."""
    return list(
        db.execute(
            _load_options(
                select(Quotation)
                .where(
                    Quotation.type == quotation.type,
                    Quotation.year == quotation.year,
                    Quotation.seq == quotation.seq,
                )
                .order_by(Quotation.revision.asc())
            )
        )
        .scalars()
        .all()
    )


def is_latest(db: Session, quotation: Quotation) -> bool:
    newer = db.execute(
        select(Quotation.id).where(
            Quotation.type == quotation.type,
            Quotation.year == quotation.year,
            Quotation.seq == quotation.seq,
            Quotation.revision > quotation.revision,
        )
    ).first()
    return newer is None


def _require_editable(db: Session, quotation: Quotation) -> None:
    if quotation.status != QuotationStatus.PENDING or not is_latest(db, quotation):
        raise QuotationLocked(
            f"{quotation.number} is {quotation.status.value} and cannot be changed. "
            "Revise it to make a new version.",
            status=quotation.status.value,
        )


def _check_customer(db: Session, customer_id: int) -> None:
    if db.get(Customer, customer_id) is None:
        raise NotFound(f"Customer {customer_id} was not found.", customer_id=customer_id)


def _check_branch(db: Session, customer_id: int, branch_id: int | None) -> None:
    """A quotation may only name an active branch of its own customer."""
    if branch_id is None:
        return
    branch = db.get(CustomerBranch, branch_id)
    if branch is None or branch.customer_id != customer_id or not branch.is_active:
        raise ValidationFailed(
            "That branch does not belong to the chosen customer.", branch_id=branch_id
        )


def _components(line: LineIn) -> list[dict[str, Any]]:
    """The line's items, one entry per product (a repeat adds to the quantity)."""
    if line.kind == LineKind.NOTE:
        return []
    merged: dict[int, dict[str, Any]] = {}
    for c in line.components:
        if c.product_id in merged:
            merged[c.product_id]["quantity"] += c.quantity
        else:
            merged[c.product_id] = {
                "product_id": c.product_id,
                "name": c.name.strip(),
                "quantity": c.quantity,
            }
    return list(merged.values())


def _build_lines(db: Session, lines: list[LineIn]) -> list[QuotationLine]:
    product_ids = {line.product_id for line in lines if line.product_id is not None}
    product_ids |= {c.product_id for line in lines for c in line.components}
    if product_ids:
        found = set(
            db.execute(select(Product.id).where(Product.id.in_(product_ids))).scalars().all()
        )
        missing = product_ids - found
        if missing:
            raise NotFound(f"Product {sorted(missing)[0]} was not found.")
    defaults: list[dict[str, str]] | None = None

    def deviations(line: LineIn) -> list[dict[str, str]]:
        nonlocal defaults
        # A note prints as text only; it has no technical deviation.
        if line.kind == LineKind.NOTE:
            return []
        if line.deviations is None:
            if defaults is None:
                defaults = [d.model_dump() for d in default_deviations(db)]
            return [dict(d) for d in defaults]
        return [
            {"label": d.label.strip(), "value": d.value.strip()}
            for d in line.deviations
            if d.label.strip()
        ]

    built = [(line, _components(line)) for line in lines]
    return [
        QuotationLine(
            position=i,
            kind=line.kind,
            unit_label=line.unit_label.strip() or "Each",
            hsn_code="" if line.kind == LineKind.NOTE else line.hsn_code.strip(),
            # A note carries no price; whatever was sent, it prints as text.
            # A multi-item line has no single product: its items carry them.
            product_id=None if line.kind == LineKind.NOTE or comps else line.product_id,
            description=line.description.strip(),
            quantity=1 if line.kind == LineKind.NOTE else line.quantity,
            rate_paise=0 if line.kind == LineKind.NOTE else line.rate_paise,
            deviations=deviations(line),
            components=comps,
            service="" if line.kind == LineKind.NOTE else line.service.strip(),
            part_no="" if line.kind == LineKind.NOTE else line.part_no.strip(),
            moc="" if line.kind == LineKind.NOTE else line.moc.strip(),
            delivery="" if line.kind == LineKind.NOTE else line.delivery.strip(),
            supply_scope="" if line.kind == LineKind.NOTE else line.supply_scope.strip(),
            tech_values=[] if line.kind == LineKind.NOTE else [v.strip() for v in line.tech_values],
        )
        for i, (line, comps) in enumerate(built)
    ]


def default_deviations(db: Session) -> list[Deviation]:
    """The technical deviation rows a new item line starts with (Settings)."""
    settings = db.get(AppSettings, 1)
    stored = settings.quotation_spec_defaults if settings is not None else []
    raw = stored or DEFAULT_QUOTATION_SPECS
    return [Deviation(label=s["label"], value=s.get("value", "")) for s in raw]


def _build_terms(terms: list[TermIn]) -> list[QuotationTerm]:
    return [
        QuotationTerm(position=i, label=t.label.strip(), text=t.text.strip(), included=t.included)
        for i, t in enumerate(terms)
    ]


def default_terms(db: Session, type_: QuotationType) -> list[TermIn]:
    settings = db.get(AppSettings, 1)
    stored = settings.quotation_terms_defaults if settings is not None else {}
    raw = stored.get(type_.value) or DEFAULT_QUOTATION_TERMS[type_.value]
    return [TermIn(label=t["label"], text=t["text"]) for t in raw]


def create_quotation(db: Session, body: QuotationCreate, *, actor_id: int | None) -> Quotation:
    _check_customer(db, body.customer_id)
    _check_branch(db, body.customer_id, body.customer_branch_id)
    year = body.quote_date.year % 100
    seq = _next_seq(db, body.type, year)
    quotation = Quotation(
        type=body.type,
        year=year,
        seq=seq,
        revision=0,
        number=format_number(body.type, year, seq, 0),
        customer_id=body.customer_id,
        customer_branch_id=body.customer_branch_id,
        quote_date=body.quote_date,
        subject=body.subject.strip(),
        reference=body.reference.strip(),
        notes=body.notes,
        format=body.format,
        print_columns=list(dict.fromkeys(body.print_columns)),
        tech_rows=_tech_rows(body.tech_rows),
        scope=body.scope.strip(),
        price_label=body.price_label.strip(),
        status=QuotationStatus.PENDING,
        created_by_id=actor_id,
        lines=_build_lines(db, body.lines),
        terms=_build_terms(body.terms if body.terms is not None else default_terms(db, body.type)),
    )
    db.add(quotation)
    db.commit()
    return get_quotation(db, quotation.id)


def update_quotation(db: Session, quotation_id: int, body: QuotationUpdate) -> Quotation:
    quotation = get_quotation(db, quotation_id)
    _require_editable(db, quotation)
    changes = body.model_dump(exclude_unset=True)
    if "customer_id" in changes and changes["customer_id"] is not None:
        _check_customer(db, changes["customer_id"])
        if changes["customer_id"] != quotation.customer_id:
            # A branch belongs to one customer; a new customer starts at its
            # head office unless a branch of it is sent alongside.
            quotation.customer_branch_id = None
        quotation.customer_id = changes["customer_id"]
    if "customer_branch_id" in changes:
        _check_branch(db, quotation.customer_id, changes["customer_branch_id"])
        quotation.customer_branch_id = changes["customer_branch_id"]
    if changes.get("quote_date") is not None:
        quotation.quote_date = changes["quote_date"]
        # The number carries the year; a date moved across a year boundary
        # keeps its number — renumbering a quote the customer already holds
        # would be worse than a mismatched year.
    if changes.get("subject") is not None:
        quotation.subject = changes["subject"].strip()
    if changes.get("reference") is not None:
        quotation.reference = changes["reference"].strip()
    if changes.get("notes") is not None:
        quotation.notes = changes["notes"]
    fmt = body.format if body.format is not None else quotation.format
    rows = _tech_rows(body.tech_rows) if body.tech_rows is not None else quotation.tech_rows
    scope = body.scope.strip() if body.scope is not None else quotation.scope
    label = body.price_label.strip() if body.price_label is not None else quotation.price_label
    if quotation.neg_no and (fmt, rows, scope, label) != (
        quotation.format,
        quotation.tech_rows,
        quotation.scope,
        quotation.price_label,
    ):
        raise ValidationFailed(
            f"{quotation.number} is a negotiation: only prices can change. To change "
            "the format, technical rows or scope, start a revised quotation."
        )
    quotation.format, quotation.tech_rows, quotation.scope = fmt, rows, scope
    quotation.price_label = label
    # Which columns print is presentation, not content: a negotiation may change it.
    if body.print_columns is not None:
        quotation.print_columns = list(dict.fromkeys(body.print_columns))
    # Clear then flush before assigning: the unit of work would otherwise
    # INSERT the new rows before DELETEing the orphans and trip the unique
    # (quotation_id, position) constraint on the very first line.
    if body.lines is not None:
        new_lines = _build_lines(db, body.lines)
        if quotation.neg_no and _content(new_lines) != _content(quotation.lines):
            raise ValidationFailed(
                f"{quotation.number} is a negotiation: only prices can change. To change "
                "products, quantities or technical details, start a revised quotation."
            )
        quotation.lines.clear()
        db.flush()
        quotation.lines = new_lines
    if body.terms is not None:
        quotation.terms.clear()
        db.flush()
        quotation.terms = _build_terms(body.terms)
    db.commit()
    return get_quotation(db, quotation_id)


_FORMAT_NAMES = {
    "pump": "Pump Offer",
    "spares": "Spares & Service",
    "technical": "Technical Sheet",
}


def _tech_rows(rows: list[TechRow]) -> list[dict[str, str]]:
    return [
        {"section": r.section.strip(), "label": r.label.strip()} for r in rows if r.label.strip()
    ]


def _content(lines: list[QuotationLine]) -> list[tuple[Any, ...]]:
    """Everything about the lines but their prices: what a negotiation may not change."""
    return [
        (
            ln.kind,
            ln.product_id,
            " ".join(ln.description.split()),
            ln.quantity,
            ln.unit_label,
            ln.hsn_code,
            [(d.get("label", ""), d.get("value", "")) for d in ln.deviations],
            [(c["product_id"], c["quantity"]) for c in ln.components],
            ln.service,
            list(ln.tech_values),
            ln.part_no,
            ln.moc,
            ln.delivery,
            " ".join(ln.supply_scope.split()),
        )
        for ln in sorted(lines, key=lambda ln: ln.position)
    ]


def revise_quotation(
    db: Session,
    quotation_id: int,
    *,
    actor_id: int | None,
    kind: VersionKind = VersionKind.NEGOTIATION,
) -> Quotation:
    """Start the next negotiation of this number, copied from *this* revision.

    Two kinds. A *revised quotation* (R) is for a change of product,
    quantity or technical details: it takes the next R of the number and
    starts its negotiations afresh. A *negotiation* (N) is for price only: it
    takes the next N within the revision it is started from, and only its
    prices may then be edited. Either way the customer pushes back, a new
    version goes out, and so on until one is accepted or the customer walks.
    The new row is always the highest revision + 1, but its content comes
    from whichever revision was chosen — the initial quote or any step since —
    so a negotiation that went the wrong way can be restarted from an earlier
    one. `supersedes_id` records that source, and the "what changed" view
    compares against it.

    Any pending revision of the number is superseded. An accepted number is
    final and cannot be negotiated further; a declined one can — a re-quote
    at a better price is exactly the point.
    """
    old = get_quotation(db, quotation_id)
    chain = list_revisions(db, old)
    accepted = next((r for r in chain if r.status == QuotationStatus.ACCEPTED), None)
    if accepted is not None:
        raise QuotationLocked(
            f"{accepted.number} was accepted; an accepted quotation is final.",
            status=accepted.status.value,
        )
    next_rev = max(r.revision for r in chain) + 1
    if kind == VersionKind.REVISION:
        rev_no, neg_no = max(r.rev_no for r in chain) + 1, 0
    else:
        rev_no = old.rev_no
        neg_no = max(r.neg_no for r in chain if r.rev_no == old.rev_no) + 1
    new = Quotation(
        type=old.type,
        year=old.year,
        seq=old.seq,
        revision=next_rev,
        rev_no=rev_no,
        neg_no=neg_no,
        number=format_number(old.type, old.year, old.seq, rev_no, neg_no),
        customer_id=old.customer_id,
        customer_branch_id=old.customer_branch_id,
        quote_date=old.quote_date,
        subject=old.subject,
        reference=old.reference,
        notes=old.notes,
        format=old.format,
        print_columns=list(old.print_columns),
        tech_rows=[dict(r) for r in old.tech_rows],
        scope=old.scope,
        price_label=old.price_label,
        # A revision is a fresh offer; the old refusal stays on the old row.
        status=QuotationStatus.PENDING,
        supersedes_id=old.id,
        created_by_id=actor_id,
        lines=[
            QuotationLine(
                position=line.position,
                kind=line.kind,
                unit_label=line.unit_label,
                hsn_code=line.hsn_code,
                product_id=line.product_id,
                description=line.description,
                quantity=line.quantity,
                rate_paise=line.rate_paise,
                deviations=[dict(d) for d in line.deviations],
                components=[dict(c) for c in line.components],
                service=line.service,
                tech_values=list(line.tech_values),
                part_no=line.part_no,
                moc=line.moc,
                delivery=line.delivery,
                supply_scope=line.supply_scope,
            )
            for line in old.lines
        ],
        terms=[
            QuotationTerm(position=t.position, label=t.label, text=t.text, included=t.included)
            for t in old.terms
        ],
    )
    for r in chain:
        if r.status == QuotationStatus.PENDING:
            r.status = QuotationStatus.SUPERSEDED
    db.add(new)
    db.commit()
    return get_quotation(db, new.id)


def _parts(line: QuotationLine) -> str:
    """'Pump x1, Base Frame x2': a multi-item line's items, for the change list."""
    return ", ".join(
        f"{c.get('name') or c['product_id']} x{c['quantity']}" for c in line.components
    )


def _source(db: Session, quotation: Quotation) -> Quotation | None:
    if quotation.supersedes_id is None:
        return None
    return db.execute(
        _load_options(select(Quotation).where(Quotation.id == quotation.supersedes_id))
    ).scalar_one_or_none()


def compare_versions(db: Session, quotation_id: int, against_id: int) -> dict[str, Any]:
    """Any two versions of one number, side by side: what changed from `against` to this.

    The original against R3, R1 against R2N2, and so on, so the screen can
    compare any pair, not only a version with the one it was copied from.
    """
    quotation = get_quotation(db, quotation_id)
    against = get_quotation(db, against_id)
    if (against.type, against.year, against.seq) != (quotation.type, quotation.year, quotation.seq):
        raise ValidationFailed("Only versions of the same quotation can be compared.")
    return {
        "changes": _diff(against, quotation),
        "lines": _line_diff(against, quotation),
    }


def changes_since_source(db: Session, quotation: Quotation) -> list[dict[str, str]]:
    """What this negotiation changed against the revision it was copied from.

    Plain (section, item, field, before, after) rows, so the screen can say
    "Items · RNS 125/100 Coupling · Rate: 14,760 → 13,500" without knowing
    anything about the model. Lines are matched by position, terms by
    label, and an item's technical deviation rows by label within its line.
    The initial quote has no source and returns nothing.
    """
    src = _source(db, quotation)
    return [] if src is None else _diff(src, quotation)


def _diff(src: Quotation, quotation: Quotation) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def norm(v: object) -> object:
        # Whitespace is not a negotiation: "RNS  125" vs "RNS 125" is the
        # same line, and a diff that lists it would bury the price change.
        return " ".join(v.split()) if isinstance(v, str) else v

    def row(section: str, item: str, field: str, before: object, after: object) -> None:
        if norm(before) != norm(after):
            out.append(
                {
                    "section": section,
                    "item": item,
                    "field": field,
                    "before": "" if before is None else str(before),
                    "after": "" if after is None else str(after),
                }
            )

    row("Header", "", "Customer", src.customer.name, quotation.customer.name)
    row(
        "Header",
        "",
        "Branch",
        src.customer_branch.name if src.customer_branch else "Head office",
        quotation.customer_branch.name if quotation.customer_branch else "Head office",
    )
    row("Header", "", "Date", src.quote_date.isoformat(), quotation.quote_date.isoformat())
    row("Header", "", "Subject", src.subject, quotation.subject)
    row("Header", "", "Reference", src.reference, quotation.reference)
    row(
        "Header",
        "",
        "Format",
        _FORMAT_NAMES.get(src.format, src.format),
        _FORMAT_NAMES.get(quotation.format, quotation.format),
    )
    row("Header", "", "Scope", src.scope, quotation.scope)
    row("Header", "", "Price covers", src.price_label, quotation.price_label)
    labels_a = [r["label"] for r in src.tech_rows]
    labels_b = [r["label"] for r in quotation.tech_rows]
    row("Technical sheet", "", "Rows", ", ".join(labels_a), ", ".join(labels_b))

    for i in range(max(len(src.lines), len(quotation.lines))):
        la = src.lines[i] if i < len(src.lines) else None
        lb = quotation.lines[i] if i < len(quotation.lines) else None
        if la is None or lb is None:
            name = lb.description if lb is not None else la.description if la is not None else ""
            row(
                "Items",
                name,
                "Line",
                "—" if la is None else la.description,
                "—" if lb is None else lb.description,
            )
            continue
        row("Items", lb.description, "Description", la.description, lb.description)
        row("Items", lb.description, "Quantity", la.quantity, lb.quantity)
        row("Items", lb.description, "Rate", la.rate_paise, lb.rate_paise)
        if la.kind != lb.kind:
            row("Items", lb.description, "Kind", la.kind.value, lb.kind.value)
        row("Items", lb.description, "Items in set", _parts(la), _parts(lb))
        row("Items", lb.description, "Service", la.service, lb.service)
        row("Items", lb.description, "Part No", la.part_no, lb.part_no)
        row("Items", lb.description, "MOC", la.moc, lb.moc)
        row("Items", lb.description, "Delivery", la.delivery, lb.delivery)
        row("Items", lb.description, "Scope of supply", la.supply_scope, lb.supply_scope)
        tech_a = dict(zip(labels_a, la.tech_values, strict=False))
        tech_b = dict(zip(labels_b, lb.tech_values, strict=False))
        for label in labels_a + [x for x in labels_b if x not in labels_a]:
            row(
                "Technical sheet",
                lb.service or lb.description,
                label,
                tech_a.get(label, "—"),
                tech_b.get(label, "—"),
            )
        dev_a = {d["label"]: d.get("value", "") for d in la.deviations}
        dev_b = {d["label"]: d.get("value", "") for d in lb.deviations}
        for label in list(dev_a) + [x for x in dev_b if x not in dev_a]:
            row(
                "Technical deviation",
                lb.description,
                label,
                dev_a.get(label, "—"),
                dev_b.get(label, "—"),
            )

    src_terms = {t.label: t for t in src.terms}
    new_terms = {t.label: t for t in quotation.terms}
    for label in list(src_terms) + [x for x in new_terms if x not in src_terms]:
        ta, tb = src_terms.get(label), new_terms.get(label)
        if ta is None or tb is None:
            row(
                "Terms",
                label,
                "Term",
                "—" if ta is None else "present",
                "—" if tb is None else "present",
            )
            continue
        row("Terms", label, "Text", ta.text, tb.text)
        row(
            "Terms",
            label,
            "Included",
            "yes" if ta.included else "no",
            "yes" if tb.included else "no",
        )

    return out


def line_changes(db: Session, quotation: Quotation) -> list[dict[str, Any]]:
    """Item-by-item comparison against the version this one was started from.

    One row per product line, matched by position: old and new quantity and
    rate, so the screen can show the discount given on each item. Notes carry
    no price and are left out. The initial quote has no source: no rows.
    """
    src = _source(db, quotation)
    return [] if src is None else _line_diff(src, quotation)


def _line_diff(src: Quotation, quotation: Quotation) -> list[dict[str, Any]]:
    old = [ln for ln in src.lines if ln.kind == LineKind.PRODUCT]
    new = [ln for ln in quotation.lines if ln.kind == LineKind.PRODUCT]
    out: list[dict[str, Any]] = []
    for i in range(max(len(old), len(new))):
        a = old[i] if i < len(old) else None
        b = new[i] if i < len(new) else None
        ref = b if b is not None else a
        assert ref is not None
        out.append(
            {
                "description": ref.description,
                "old_quantity": a.quantity if a else None,
                "new_quantity": b.quantity if b else None,
                "old_rate_paise": a.rate_paise if a else None,
                "new_rate_paise": b.rate_paise if b else None,
                "change": "added" if a is None else "removed" if b is None else "kept",
            }
        )
    return out


HISTORY_STAGES = 10


def version_ref(q: Quotation) -> str:
    """The short reference of a version after the original: R2, N1 or R2N1."""
    return (f"R{q.rev_no}" if q.rev_no else "") + (f"N{q.neg_no}" if q.neg_no else "")


def history_matrix(
    db: Session,
    *,
    q: str | None = None,
    status: QuotationStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    """End-to-end history, one row per item: quoted rate, then every version.

    `stages` lists each version after the original in the order it was made,
    labelled R (a revised quotation) or N (a negotiation), with the item's
    rate there; `revised_paise` is the latest revised quotation's rate before
    any negotiation of it, and `current_paise` the latest version's. One row
    per item of a *number*, never per version, so nothing is counted twice.
    `negotiations_paise` (the same rates, unlabelled, N1..N10) stays for
    older clients.

    Items are matched across a number's versions by their position among its
    product lines — the same rule as the negotiation table — so row 2 of the
    initial quote and row 2 of N3 are the same item. A blank cell means that
    stage does not exist yet, or the item was not in it. Stages past
    HISTORY_STAGES are left out here by the client's choice; the per-number
    history page still has them.

    Filters apply to the number's *latest* version: its status, and a search
    over number, customer, subject and item description.
    """
    rows = (
        db.execute(
            _load_options(
                select(Quotation).order_by(
                    Quotation.year.desc(), Quotation.seq.desc(), Quotation.revision.asc()
                )
            )
        )
        .scalars()
        .all()
    )
    chains: dict[tuple[str, int, int], list[Quotation]] = {}
    for r in rows:
        chains.setdefault((r.type.value, r.year, r.seq), []).append(r)

    needle = q.strip().lower() if q else ""
    out: list[dict[str, Any]] = []
    for chain in chains.values():
        latest = chain[-1]
        if status is not None and latest.status != status:
            continue
        # The revised quotation the deal now rests on, before its negotiations.
        revised = next(
            (
                v
                for v in reversed(chain)
                if v.rev_no and v.rev_no == latest.rev_no and v.neg_no == 0
            ),
            None,
        )
        # The period is when the quote was first sent: the initial version's date.
        first_date = chain[0].quote_date
        if date_from is not None and first_date < date_from:
            continue
        if date_to is not None and first_date > date_to:
            continue
        by_rev = {v.revision: [ln for ln in v.lines if ln.kind == LineKind.PRODUCT] for v in chain}
        width = max((len(v) for v in by_rev.values()), default=0)
        items = []
        for i in range(width):

            def rate(
                rev: int, i: int = i, by_rev: dict[int, list[QuotationLine]] = by_rev
            ) -> int | None:
                lines = by_rev.get(rev)
                return lines[i].rate_paise if lines is not None and i < len(lines) else None

            def qty(
                rev: int, i: int = i, by_rev: dict[int, list[QuotationLine]] = by_rev
            ) -> int | None:
                lines = by_rev.get(rev)
                return lines[i].quantity if lines is not None and i < len(lines) else None

            # The latest wording of the item, falling back to where it last appeared.
            desc = next(
                (
                    by_rev[v.revision][i].description
                    for v in reversed(chain)
                    if i < len(by_rev[v.revision])
                ),
                "",
            )
            items.append(
                {
                    "quotation_id": latest.id,
                    "number": latest.number,
                    "customer": latest.customer.name,
                    "description": desc,
                    "quantity": next(
                        (qty(v.revision) for v in reversed(chain) if qty(v.revision) is not None),
                        None,
                    ),
                    "quoted_paise": rate(chain[0].revision),
                    "negotiations_paise": [rate(n) for n in range(1, HISTORY_STAGES + 1)],
                    "stages": [
                        {"label": version_ref(v), "rate_paise": rate(v.revision)} for v in chain[1:]
                    ],
                    "revised_paise": rate(revised.revision) if revised else None,
                    "current_paise": rate(latest.revision),
                    "original_number": latest.base_number,
                    "stage": latest.revision,
                    "stage_label": latest.stage_label,
                    "status": latest.status.value,
                    "decline_reason": latest.decline_reason,
                    "quote_date": chain[0].quote_date.isoformat(),
                }
            )
        if needle:
            haystack = " ".join(
                [latest.number, latest.customer.name, latest.subject]
                + [str(it["description"]) for it in items]
            ).lower()
            if needle not in haystack:
                continue
        out.extend(items)
    return out


def dashboard(db: Session) -> dict[str, Any]:
    """The owner's view: every number once, at its latest revision.

    Small enough to compute in Python — a dealer writes hundreds of offers a
    year, not millions — and it keeps the stage rules in one place.
    """
    rows = (
        db.execute(
            _load_options(
                select(Quotation).where(_is_latest_clause()).order_by(Quotation.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )

    def stage(q: Quotation) -> str:
        if q.status == QuotationStatus.PENDING:
            return "awaiting" if q.revision == 0 else "negotiating"
        return q.status.value

    def summary(q: Quotation) -> dict[str, Any]:
        return {
            "id": q.id,
            "number": q.number,
            "customer": q.customer.name,
            "stage": q.revision,
            "stage_label": q.stage_label,
            "status": q.status.value,
            "quote_date": q.quote_date.isoformat(),
            "updated_at": q.updated_at.isoformat(),
            "total_paise": q.total_paise,
            "decline_reason": q.decline_reason,
        }

    buckets: dict[str, dict[str, int]] = {
        k: {"count": 0, "total_paise": 0}
        for k in ("awaiting", "negotiating", "accepted", "declined")
    }
    for q in rows:
        b = buckets[stage(q)]
        b["count"] += 1
        b["total_paise"] += q.total_paise
    return {
        "buckets": buckets,
        "negotiating": [summary(q) for q in rows if stage(q) == "negotiating"][:10],
        "awaiting": [summary(q) for q in rows if stage(q) == "awaiting"][:10],
        "accepted": [summary(q) for q in rows if stage(q) == "accepted"][:10],
        "declined": [summary(q) for q in rows if stage(q) == "declined"][:10],
    }


def set_status(
    db: Session,
    quotation_id: int,
    status: QuotationStatus,
    *,
    reason: str = "",
    actor_id: int | None = None,
) -> Quotation:
    """pending → accepted | declined, on the latest revision only.

    Superseded is never set here — only `revise` produces it — and nothing
    moves back to pending: to reopen a decided offer, revise it.
    """
    quotation = get_quotation(db, quotation_id)
    if status not in (QuotationStatus.ACCEPTED, QuotationStatus.DECLINED):
        raise Conflict(f"A quotation cannot be set to {status.value} directly.")
    if quotation.status != QuotationStatus.PENDING or not is_latest(db, quotation):
        raise QuotationLocked(
            f"{quotation.number} is {quotation.status.value}; only a pending quotation "
            "can be accepted or declined.",
            status=quotation.status.value,
        )
    if status == QuotationStatus.DECLINED and not reason.strip():
        raise ValidationFailed("Enter the reason the customer declined.")
    from . import orders

    # Refuse before changing anything: an item that is not in Products cannot
    # have its stock checked, so the quote cannot become an order.
    if status == QuotationStatus.ACCEPTED:
        orders.ensure_orderable(quotation)
    quotation.status = status
    quotation.decline_reason = reason.strip() if status == QuotationStatus.DECLINED else ""
    if status == QuotationStatus.ACCEPTED:
        # Same transaction: an accepted quote without its order (or an order
        # for a quote that failed to accept) must not be possible.
        try:
            orders.create_from_quotation(db, quotation, actor_id=actor_id)
        except Exception:
            db.rollback()
            raise
    db.commit()
    return get_quotation(db, quotation_id)


def delete_quotation(db: Session, quotation_id: int, *, whole: bool) -> None:
    """Delete a quote.

    `whole=True` (the Quotations page) removes the number with every
    negotiation; `whole=False` (the Negotiations page) removes only this
    latest negotiation, and the version before it becomes pending again.
    An accepted quote has an order and cannot be deleted.
    """
    quotation = get_quotation(db, quotation_id)
    chain = (
        db.execute(
            select(Quotation)
            .where(
                Quotation.type == quotation.type,
                Quotation.year == quotation.year,
                Quotation.seq == quotation.seq,
            )
            .order_by(Quotation.revision)
        )
        .scalars()
        .all()
    )
    targets = list(chain) if whole else [quotation]
    if any(q.status == QuotationStatus.ACCEPTED for q in targets):
        raise Conflict(f"{quotation.number} is accepted and has an order; it cannot be deleted.")
    if not whole:
        if quotation.revision == 0:
            raise Conflict("This is the initial quote; delete it from the Quotations page.")
        if quotation.revision != chain[-1].revision:
            raise Conflict(f"Only the latest negotiation of {quotation.number} can be deleted.")
    for q in targets:
        db.delete(q)
    db.flush()
    if not whole:
        rest = [q for q in chain if q.id != quotation.id]
        # The version it replaced is live again, unless something else is.
        reopen = (
            rest
            and rest[-1].status == QuotationStatus.SUPERSEDED
            and not any(q.status == QuotationStatus.PENDING for q in rest)
        )
        if reopen:
            rest[-1].status = QuotationStatus.PENDING
    db.commit()
