"""Quotations: offer letters to customers."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ..constants import QuotationStatus, QuotationType, VersionKind
from ..db import get_db
from ..deps import Pagination, get_current_user, get_pagination, owner_only
from ..errors import NotFound
from ..models import AppSettings, Quotation, User
from ..schemas.common import Page
from ..schemas.quotation import (
    ChangeOut,
    CompareOut,
    DashboardOut,
    HistoryRow,
    ItemSuggestion,
    LineChangeOut,
    QuotationCreate,
    QuotationOut,
    QuotationSummary,
    QuotationUpdate,
    ReviseIn,
    StatusChange,
)
from ..services import item_suggestions as item_suggestions_service
from ..services import quotations as service
from ..services.history_export import to_pdf, to_xlsx
from ..services.quotation_pdf import render_quotation_pdf

router = APIRouter(prefix="/quotations", tags=["quotations"])

# Which list: original quotations, revised quotations, or negotiations.
QuotationStage = Literal["quotation", "revised", "negotiation"]

QuotationSort = Literal[
    "-updated_at", "updated_at", "-quote_date", "quote_date", "number", "-number"
]


def _out(db: Session, q: Quotation) -> QuotationOut:
    return QuotationOut.model_validate(
        {
            **q.__dict__,
            "customer": q.customer,
            "customer_branch": q.customer_branch,
            "lines": q.lines,
            "terms": q.terms,
            "tech_rows": q.tech_rows,
            "print_columns": q.print_columns,
            "total_paise": q.total_paise,
            "base_number": q.base_number,
            "stage_label": q.stage_label,
            "is_latest": service.is_latest(db, q),
        }
    )


@router.get("", response_model=Page[QuotationSummary])
def list_quotations(
    q: str | None = Query(default=None, max_length=200),
    type: QuotationType | None = None,
    status_: QuotationStatus | None = Query(default=None, alias="status"),
    customer_id: int | None = None,
    all_revisions: bool = False,
    negotiated: bool | None = None,
    stage: QuotationStage | None = None,
    sort: QuotationSort = "-updated_at",
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[QuotationSummary]:
    rows, total = service.list_quotations(
        db,
        q=q,
        type_=type,
        status=status_,
        customer_id=customer_id,
        latest_only=not all_revisions,
        negotiated=negotiated,
        stage=stage,
        sort=sort,
        offset=page.offset,
        limit=page.limit,
    )
    return Page.build(
        [QuotationSummary.model_validate(r) for r in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{quotation_id}/revisions", response_model=list[QuotationSummary])
def list_revisions(
    quotation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[QuotationSummary]:
    """Every revision of the same number, oldest first, this one included."""
    quotation = service.get_quotation(db, quotation_id)
    return [QuotationSummary.model_validate(r) for r in service.list_revisions(db, quotation)]


@router.get("/history", response_model=list[HistoryRow])
def quotation_history(
    q: str | None = Query(default=None, max_length=200),
    status_: QuotationStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[HistoryRow]:
    """End to end, one row per item. Declared before /{quotation_id}."""
    rows = service.history_matrix(db, q=q, status=status_, date_from=date_from, date_to=date_to)
    return [HistoryRow.model_validate(r) for r in rows]


def _period(date_from: date | None, date_to: date | None) -> str:
    """-2026-07-01-to-2026-09-30 in the file name, so downloads do not overwrite."""
    if not date_from and not date_to:
        return ""
    return f"-{date_from or 'start'}-to-{date_to or 'today'}"


@router.get("/history/export")
def quotation_history_export(
    format: Literal["xlsx", "pdf"] = "xlsx",
    q: str | None = Query(default=None, max_length=200),
    status_: QuotationStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    """The Quote History table as a file, under the same search and filter."""
    rows = service.history_matrix(db, q=q, status=status_, date_from=date_from, date_to=date_to)
    bits = []
    if q:
        bits.append(f'Search "{q}".')
    if status_:
        bits.append(f"Result: {status_.value}.")
    if date_from or date_to:
        a = date_from.strftime("%d.%m.%Y") if date_from else "the start"
        b = date_to.strftime("%d.%m.%Y") if date_to else "today"
        bits.append(f"Quoted {a} to {b}.")
    filters = " ".join(bits) or "All quotations."
    if format == "pdf":
        settings = db.get(AppSettings, 1)
        company = settings.company_name if settings else "Excel Engineers"
        body = to_pdf(rows, company=company, filters=filters)
        media, ext = "application/pdf", "pdf"
    else:
        body = to_xlsx(rows, filters=filters)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    name = f"quote-history{_period(date_from, date_to)}.{ext}"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/item-suggestions", response_model=list[ItemSuggestion])
def item_suggestions(
    q: str = Query(min_length=1, max_length=200),
    customer_id: int | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ItemSuggestion]:
    """What was quoted before, for the description box. Declared before /{quotation_id}."""
    return [
        ItemSuggestion.model_validate(s)
        for s in item_suggestions_service.suggest(db, q, customer_id=customer_id)
    ]


@router.get("/dashboard", response_model=DashboardOut)
def quotation_dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DashboardOut:
    """Declared before /{quotation_id}, or "dashboard" is read as an id."""
    return DashboardOut.model_validate(service.dashboard(db))


@router.get("/{quotation_id}/changes", response_model=list[ChangeOut])
def quotation_changes(
    quotation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ChangeOut]:
    quotation = service.get_quotation(db, quotation_id)
    return [ChangeOut.model_validate(c) for c in service.changes_since_source(db, quotation)]


@router.get("/{quotation_id}/line-changes", response_model=list[LineChangeOut])
def quotation_line_changes(
    quotation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[LineChangeOut]:
    quotation = service.get_quotation(db, quotation_id)
    return [LineChangeOut.model_validate(c) for c in service.line_changes(db, quotation)]


@router.post("", response_model=QuotationOut, status_code=status.HTTP_201_CREATED)
def create_quotation(
    body: QuotationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuotationOut:
    return _out(db, service.create_quotation(db, body, actor_id=user.id))


@router.get("/{quotation_id}", response_model=QuotationOut)
def get_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> QuotationOut:
    return _out(db, service.get_quotation(db, quotation_id))


@router.delete("/{quotation_id}", status_code=204, dependencies=[Depends(owner_only)])
def delete_quotation(
    quotation_id: int,
    whole: bool = Query(default=True),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    """whole=true: the number with all its negotiations; false: just this negotiation."""
    service.delete_quotation(db, quotation_id, whole=whole)
    return Response(status_code=204)


@router.patch("/{quotation_id}", response_model=QuotationOut)
def update_quotation(
    quotation_id: int,
    body: QuotationUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> QuotationOut:
    return _out(db, service.update_quotation(db, quotation_id, body))


@router.post("/{quotation_id}/revise", response_model=QuotationOut, status_code=201)
def revise_quotation(
    quotation_id: int,
    body: ReviseIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuotationOut:
    """Start the next version: a revised quotation (R) or a negotiation (N, the default)."""
    kind = body.kind if body is not None else VersionKind.NEGOTIATION
    return _out(db, service.revise_quotation(db, quotation_id, actor_id=user.id, kind=kind))


@router.get("/{quotation_id}/compare", response_model=CompareOut)
def compare_versions(
    quotation_id: int,
    against: int = Query(..., description="The version to compare this one with."),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CompareOut:
    """What changed from `against` to this version: any two versions of one number."""
    return CompareOut.model_validate(service.compare_versions(db, quotation_id, against))


@router.post("/{quotation_id}/status", response_model=QuotationOut)
def set_status(
    quotation_id: int,
    body: StatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuotationOut:
    return _out(
        db,
        service.set_status(db, quotation_id, body.status, reason=body.reason, actor_id=user.id),
    )


@router.get("/{quotation_id}/pdf")
def quotation_pdf(
    quotation_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    quotation = service.get_quotation(db, quotation_id)
    settings = db.get(AppSettings, 1)
    if settings is None:
        raise NotFound("Application settings row is missing; the database needs repair.")
    # Old and new rates print only on a negotiation: a revised quotation is a
    # new offer, and its items may not be the old ones at all.
    changes = service.line_changes(db, quotation) if quotation.neg_no else None
    pdf = render_quotation_pdf(quotation, settings, changes)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{quotation.number}.pdf"'},
    )
