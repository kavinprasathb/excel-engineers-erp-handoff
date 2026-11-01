"""The activity log: who changed what, and when. Owner only."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Pagination, get_pagination, owner_only
from ..schemas.common import Page
from ..services.activity import list_activity

router = APIRouter(prefix="/activity", tags=["activity"], dependencies=[Depends(owner_only)])


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_id: int | None
    user_name: str
    action: str
    area: str
    link: str
    ip: str


@router.get("", response_model=Page[ActivityOut])
def activity(
    q: str | None = Query(default=None, max_length=200),
    user_id: int | None = None,
    area: str | None = Query(default=None, max_length=40),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
) -> Page[ActivityOut]:
    rows, total = list_activity(
        db,
        q=q,
        user_id=user_id,
        area=area,
        date_from=date_from,
        date_to=date_to,
        offset=page.offset,
        limit=page.limit,
    )
    return Page.build(
        [ActivityOut.model_validate(r) for r in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )
