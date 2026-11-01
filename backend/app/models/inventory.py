from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .product import Product


class Inventory(Base, TimestampMixin):
    """Live stock counters — exactly one row per product.

    Nothing outside app.services.stock may write quantity_on_hand or
    quantity_reserved; a session guard enforces it and CI greps for bypasses.
    """

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    quantity_reserved: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    # Derived by Postgres, never by Python or TypeScript. v2 recomputed this in
    # three places and they were free to disagree; here the database owns the
    # definition and physically rejects writes to it.
    quantity_available: Mapped[int] = mapped_column(
        Integer,
        Computed("quantity_on_hand - quantity_reserved", persisted=True),
        nullable=False,
    )

    product: Mapped["Product"] = relationship(back_populates="inventory", lazy="raise")

    # So INSERT ... RETURNING brings back the generated column instead of
    # leaving a stale None on the instance.
    # RUF012 is suppressed rather than obeyed: SQLAlchemy declares
    # __mapper_args__ as an instance variable, so ClassVar is a mypy error.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("quantity_reserved <= quantity_on_hand", name="reserved_within_on_hand"),
        Index("ix_inventory_available", "quantity_available"),
    )
