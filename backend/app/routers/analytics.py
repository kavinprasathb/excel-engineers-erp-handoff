"""Analytics: quote conversion, sales, customers, products, pipeline."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..constants import DECLINE_REASONS
from ..db import get_db
from ..deps import get_current_user, owner_only
from ..errors import NotFound
from ..models import AppSettings, User
from ..services import analytics as service
from ..services.analytics_pdf import render_analytics_pdf

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(owner_only)])


@router.get("")
def analytics_report(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return service.report(db, date_from=date_from, date_to=date_to)


@router.get("/decline-reasons")
def decline_reasons(_user: User = Depends(get_current_user)) -> list[str]:
    return list(DECLINE_REASONS)


@router.get("/pdf")
def analytics_pdf(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    """The Analytics page for the same period, as a PDF to print or share."""
    settings = db.get(AppSettings, 1)
    if settings is None:
        raise NotFound("Application settings row is missing; the database needs repair.")
    report = service.report(db, date_from=date_from, date_to=date_to)
    name = f"analytics-{date_from or 'start'}-to-{date_to or 'today'}.pdf"
    return Response(
        content=render_analytics_pdf(report, settings),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
