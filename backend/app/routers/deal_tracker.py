"""Deal Tracker: each quoted item from first quote to delivery, with downloads."""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import owner_only
from ..models import AppSettings
from ..services import deal_tracker as service

# Owner-only: every row carries the deal's value and margin history.
router = APIRouter(
    prefix="/deal-tracker", tags=["deal-tracker"], dependencies=[Depends(owner_only)]
)


def _filters(
    q: str | None = Query(default=None, max_length=200),
    stage: str | None = Query(default=None, max_length=40),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
) -> dict[str, Any]:
    return {"q": q, "stage": stage, "date_from": date_from, "date_to": date_to}


@router.get("")
def deal_tracker(
    f: dict[str, Any] = Depends(_filters), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    return service.rows(db, **f)


@router.get("/export")
def deal_tracker_export(
    format: Literal["xlsx", "pdf"] = "xlsx",
    f: dict[str, Any] = Depends(_filters),
    db: Session = Depends(get_db),
) -> Response:
    """The same rows as the screen, under the same filters, as a file."""
    data = service.rows(db, **f)
    start = f["date_from"].isoformat() if f["date_from"] else "start"
    end = f["date_to"].isoformat() if f["date_to"] else "today"
    name = f"deal-tracker-{start}-to-{end}"
    label = f"{start} to {end}" + (f" · {f['stage']}" if f["stage"] else "")
    if format == "pdf":
        settings = db.get(AppSettings, 1)
        company = settings.company_name if settings else "Excel Engineers"
        return Response(
            content=service.to_pdf(data, company=company, filters=label),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
        )
    return Response(
        content=service.to_xlsx(data, filters=label),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
    )
