"""Company-wide settings — one row, id 1.

`CHECK (id = 1)` and the row inserted by the initial migration together mean
this file never needs a get-or-create. That path is where singletons go wrong:
two concurrent requests each decide the row is missing and one of them loses.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, owner_only
from ..errors import NotFound
from ..models import AppSettings, User
from ..schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

SETTINGS_ID = 1


def _load(db: Session) -> AppSettings:
    row = db.get(AppSettings, SETTINGS_ID)
    if row is None:
        # Only reachable if someone deleted the seeded row by hand. Say so
        # plainly rather than recreating it and hiding the damage.
        raise NotFound("Application settings row is missing; the database needs repair.")
    return row


@router.get("", response_model=SettingsOut)
def read_settings(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SettingsOut:
    return SettingsOut.model_validate(_load(db))


@router.patch("", response_model=SettingsOut, dependencies=[Depends(owner_only)])
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SettingsOut:
    row = _load(db)
    # exclude_unset, not exclude_none: "" and 0 are meaningful values here, and
    # omitting a field must be distinguishable from sending it empty.
    for field, value in body.model_dump(exclude_unset=True, mode="json").items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return SettingsOut.model_validate(row)
