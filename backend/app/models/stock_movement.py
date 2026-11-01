from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..constants import MovementType, ReferenceType
from .base import Base
from .types import StrEnumType


class StockMovement(Base):
    """Append-only ledger explaining every change to the stock counters.

    Two deltas, not one. v2 had a single `quantity_delta` documented as the
    change to on-hand, but its reserve path wrote that field while changing
    only `quantity_reserved` — so the ledger could never be reconciled against
    the counters even in principle. Storing the deltas separately makes both
    SUM(on_hand_delta) == quantity_on_hand and
    SUM(reserved_delta) == quantity_reserved true invariants, which is what
    makes reconcile() writable at all.
    """

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    movement_type: Mapped[MovementType] = mapped_column(
        StrEnumType(MovementType, 20), nullable=False
    )

    on_hand_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reserved_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Snapshot after this movement: makes history readable without replaying
    # the whole ledger, and localises any drift to a single row.
    quantity_on_hand_after: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_reserved_after: Mapped[int] = mapped_column(Integer, nullable=False)

    # Structured, so "every movement for order 412" is a query rather than a
    # LIKE scan over a free-text reference string.
    reference_type: Mapped[ReferenceType] = mapped_column(
        StrEnumType(ReferenceType, 30),
        nullable=False,
        server_default=ReferenceType.MANUAL.value,
    )
    reference_id: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
        Index("ix_stock_movements_reference", "reference_type", "reference_id"),
        CheckConstraint("on_hand_delta <> 0 OR reserved_delta <> 0", name="movement_not_empty"),
    )
