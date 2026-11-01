from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..constants import UserRole
from .base import Base, TimestampMixin
from .types import StrEnumType


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        StrEnumType(UserRole, 20), nullable=False, server_default=UserRole.ADMIN.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Bumped whenever every existing session must die — today only on a
    # password change. The token carries the epoch it was minted under and
    # must still match, so revocation is exact.
    #
    # A counter rather than comparing the token's `iat` against
    # password_changed_at: `iat` is whole seconds and the timestamp has
    # microseconds, so a session issued in the same second as the change
    # would survive it. That is precisely the session an attacker holds.
    session_epoch: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    __table_args__ = (
        # Case-insensitive uniqueness. Login must query with func.lower(email)
        # to use this index.
        Index("uq_users_email_lower", func.lower(email), unique=True),
    )
