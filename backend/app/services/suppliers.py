"""Supplier queries and mutations.

The recurring theme in this module — and in `products` and `inventory` beside
it — is that `product_count` is a correlated subquery inside the same statement
that fetches the rows. v2 counted products per supplier in a loop, so a page of
25 suppliers cost 26 round-trips and the list got slower as the catalogue grew.
"""

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..errors import Conflict, NotFound
from ..models import Product, Supplier, SupplierBranch
from ..schemas.contacts import splice_first
from ..schemas.party import PARTY_REQUIRED
from ..schemas.supplier import (
    SupplierBranchCreate,
    SupplierBranchUpdate,
    SupplierCreate,
    SupplierUpdate,
)
from .like import LIKE_ESCAPE, contains
from .party import validate_party

# The sort keys the contract names. Anything else is a client bug, and falling
# back silently would hide it, so the router validates against these.
SORTS: dict[str, Any] = {
    "name": Supplier.name.asc(),
    "-name": Supplier.name.desc(),
    "created_at": Supplier.created_at.asc(),
    "-created_at": Supplier.created_at.desc(),
}

_product_count = (
    select(func.count(Product.id))
    .where(Product.supplier_id == Supplier.id)
    .correlate(Supplier)
    .scalar_subquery()
)


def _filtered(q: str | None, is_active: bool | None) -> Select[tuple[Supplier, int]]:
    stmt = select(Supplier, _product_count.label("product_count")).options(
        selectinload(Supplier.branches)
    )
    if q:
        # ilike with a leading % is answered by the gin_trgm index on name; a
        # Python-side filter would have to materialise the whole table.
        pattern = contains(q)
        stmt = stmt.where(
            or_(
                Supplier.name.ilike(pattern, escape=LIKE_ESCAPE),
                Supplier.code.ilike(pattern, escape=LIKE_ESCAPE),
                Supplier.city.ilike(pattern, escape=LIKE_ESCAPE),
                func.array_to_string(Supplier.emails, " ").ilike(pattern, escape=LIKE_ESCAPE),
                func.array_to_string(Supplier.phones, " ").ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Supplier.is_active.is_(is_active))
    return stmt


def list_suppliers(
    db: Session,
    *,
    q: str | None = None,
    is_active: bool | None = None,
    sort: str = "name",
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[tuple[Supplier, int]], int]:
    stmt = _filtered(q, is_active)
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(Supplier.id).subquery())
    ).scalar_one()
    # id as a tiebreak: without it two suppliers sharing a sort key can swap
    # places between page 1 and page 2, and the operator sees one of them twice.
    rows = db.execute(
        stmt.order_by(SORTS[sort], Supplier.id.asc()).offset(offset).limit(limit)
    ).all()
    return [(row[0], row[1]) for row in rows], total


def list_options(db: Session) -> list[Supplier]:
    """Every active supplier, unpaginated.

    Not a page_size=200 call: the inventory page's inline dropdown must offer
    every supplier regardless of how the list beside it happens to be paged.
    """
    return list(
        db.execute(
            select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.name.asc())
        )
        .scalars()
        .all()
    )


def get_supplier(db: Session, supplier_id: int) -> tuple[Supplier, int]:
    row = db.execute(
        select(Supplier, _product_count.label("product_count"))
        .where(Supplier.id == supplier_id)
        .options(selectinload(Supplier.branches))
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFound(f"Supplier {supplier_id} was not found.", supplier_id=supplier_id)
    return row[0], row[1]


def _reject_duplicate_name(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    """Check before the insert as well as catching the IntegrityError after it.

    The check produces a message naming the supplier; the unique index is what
    makes it correct under concurrency. Both, not either.
    """
    stmt = select(Supplier.id).where(func.lower(Supplier.name) == name.strip().lower())
    if exclude_id is not None:
        stmt = stmt.where(Supplier.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise Conflict(f"A supplier named '{name.strip()}' already exists.", name=name.strip())


def create_supplier(db: Session, body: SupplierCreate) -> tuple[Supplier, int]:
    _reject_duplicate_name(db, body.name)
    values = validate_party(body.model_dump(), PARTY_REQUIRED)
    supplier = Supplier(**{**values, "name": body.name.strip()})
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"A supplier named '{body.name.strip()}' already exists.") from exc
    return get_supplier(db, supplier.id)


def update_supplier(db: Session, supplier_id: int, body: SupplierUpdate) -> tuple[Supplier, int]:
    supplier, _ = get_supplier(db, supplier_id)
    changes = validate_party(body.model_dump(exclude_unset=True), PARTY_REQUIRED, stored=supplier)
    if changes.get("name") is not None:
        changes["name"] = changes["name"].strip()
        _reject_duplicate_name(db, changes["name"], exclude_id=supplier_id)
    # A legacy single email/phone without its list replaces the first entry.
    for plural, single in (("emails", "email"), ("phones", "phone")):
        if changes.get(plural) is None and changes.get(single) is not None:
            changes[plural] = splice_first(list(getattr(supplier, plural) or []), changes[single])
    for field, value in changes.items():
        if value is not None:
            setattr(supplier, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("A supplier with that name already exists.") from exc
    return get_supplier(db, supplier_id)


def deactivate_supplier(db: Session, supplier_id: int) -> None:
    """Soft delete.

    Refused while products point here — the FK is RESTRICT, and purchase
    history that has lost its supplier is worse than a stale row.
    """
    supplier, product_count = get_supplier(db, supplier_id)
    if product_count:
        raise Conflict(
            f"{product_count} product(s) still reference this supplier.",
            product_count=product_count,
        )
    supplier.is_active = False
    db.commit()


# --- branches --------------------------------------------------------------------


def _branch(db: Session, supplier_id: int, branch_id: int) -> SupplierBranch:
    branch = db.get(SupplierBranch, branch_id)
    if branch is None or branch.supplier_id != supplier_id:
        raise NotFound(f"Branch {branch_id} was not found.", branch_id=branch_id)
    return branch


def create_branch(
    db: Session, supplier_id: int, body: SupplierBranchCreate
) -> tuple[Supplier, int]:
    """Add a branch. Its code is the supplier's code plus the next BR number.

    The supplier row is locked while the number is taken, so two branches added
    at once never get the same one; the counter never goes back, so a removed
    branch's number is not issued again.
    """
    parent = db.execute(
        select(Supplier).where(Supplier.id == supplier_id).with_for_update()
    ).scalar_one_or_none()
    if parent is None:
        raise NotFound(f"Supplier {supplier_id} was not found.", supplier_id=supplier_id)
    values = validate_party(body.model_dump(), PARTY_REQUIRED)
    parent.branch_seq += 1
    db.add(
        SupplierBranch(
            supplier_id=parent.id,
            seq=parent.branch_seq,
            code=f"{parent.code}-BR{parent.branch_seq:02d}",
            **values,
        )
    )
    db.commit()
    return get_supplier(db, supplier_id)


def update_branch(
    db: Session, supplier_id: int, branch_id: int, body: SupplierBranchUpdate
) -> tuple[Supplier, int]:
    branch = _branch(db, supplier_id, branch_id)
    changes = validate_party(body.model_dump(exclude_unset=True), PARTY_REQUIRED, stored=branch)
    for field, value in changes.items():
        if value is not None:
            setattr(branch, field, value)
    db.commit()
    return get_supplier(db, supplier_id)


def remove_branch(db: Session, supplier_id: int, branch_id: int) -> None:
    """Soft delete: a purchase order that named the branch still prints it."""
    _branch(db, supplier_id, branch_id).is_active = False
    db.commit()
