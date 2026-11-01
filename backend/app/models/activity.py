"""Who did what, and when: one row per change made through the app."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Kept as text too, so the log still reads right after a user is removed.
    user_name: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    area: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, server_default="")
    path: Mapped[str] = mapped_column(String(300), nullable=False, server_default="")
    ip: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")

    __table_args__ = (
        Index("ix_activity_log_created_at", "created_at"),
        Index("ix_activity_log_user_id", "user_id"),
    )
