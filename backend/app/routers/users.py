"""Staff logins: the owner adds, edits, deactivates and resets passwords."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import UserRole
from ..db import get_db
from ..deps import owner_only
from ..errors import Conflict, NotFound, ValidationFailed
from ..models import User
from ..security import MIN_PASSWORD_LENGTH, hash_password

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(owner_only)])


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    role: UserRole = UserRole.STAFF
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role: UserRole | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound(f"User {user_id} was not found.", user_id=user_id)
    return user


def _active_owners(db: Session) -> int:
    """Counted under row locks: two owners demoting each other at once would
    otherwise both see "2" and leave nobody able to sign in as owner."""
    ids = db.execute(
        select(User.id)
        .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        .with_for_update()
    ).all()
    return len(ids)


@router.get("", response_model=list[StaffOut])
def list_users(db: Session = Depends(get_db)) -> list[StaffOut]:
    rows = db.execute(select(User).order_by(User.role, User.full_name, User.email)).scalars()
    return [StaffOut.model_validate(u) for u in rows]


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def create_user(body: StaffCreate, db: Session = Depends(get_db)) -> StaffOut:
    email = body.email.lower()
    if db.execute(select(User.id).where(func.lower(User.email) == email)).first():
        raise Conflict("A login with this email already exists.")
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    return StaffOut.model_validate(user)


@router.patch("/{user_id}", response_model=StaffOut)
def update_user(user_id: int, body: StaffUpdate, db: Session = Depends(get_db)) -> StaffOut:
    user = _get(db, user_id)
    losing_owner = (
        str(user.role) == UserRole.ADMIN.value
        and user.is_active
        and ((body.role is not None and body.role != UserRole.ADMIN) or body.is_active is False)
    )
    if losing_owner and _active_owners(db) <= 1:
        raise ValidationFailed("There must always be at least one active owner.")
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
        if not body.is_active:
            user.session_epoch += 1  # signs them out everywhere, now
    db.commit()
    return StaffOut.model_validate(user)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, body: PasswordReset, db: Session = Depends(get_db)) -> None:
    user = _get(db, user_id)
    user.password_hash = hash_password(body.password)
    user.password_changed_at = datetime.now(UTC)
    user.session_epoch += 1
    db.commit()
