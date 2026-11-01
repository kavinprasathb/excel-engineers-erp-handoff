"""Orders and purchase orders.

An order is made from an accepted quotation, one per quotation, and holds
(reserves) stock item by item as it becomes available. A purchase order is
drafted to a supplier for whatever an order could not be given from stock.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..constants import OrderStatus, PurchaseOrderStatus
from .base import Base, TimestampMixin
from .customer import Customer
from .product import Product
from .supplier import Supplier, SupplierBranch
from .types import StrEnumType


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "ORD-ESQSP-26-2": the quote it came from, so nobody needs a lookup table.
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        StrEnumType(OrderStatus), nullable=False, server_default=OrderStatus.WAITING_STOCK
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    customer: Mapped[Customer] = relationship(lazy="raise")
    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderLine.position",
        lazy="raise",
    )

    __table_args__ = (
        # One order per quotation: accepting twice must not double-reserve.
        UniqueConstraint("quotation_id", name="uq_orders_quotation_id"),
        UniqueConstraint("number", name="uq_orders_number"),
        Index("ix_orders_status", "status"),
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # How many of `quantity` are held in stock for this order right now.
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    # Which quotation line this came from (its index among the product lines).
    # A line made of several items gives one order line per item, all with
    # the same source; an ordinary line gives one.
    source_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # For an item of such a set: the set's description, as quoted.
    set_description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # For an item of a set, the set's value is carried whole on its first item
    # and 0 on the rest, so totals match the quote exactly. NULL: an ordinary
    # line, worth quantity x rate.
    amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    order: Mapped[Order] = relationship(back_populates="lines", lazy="raise")
    product: Mapped[Product] = relationship(lazy="raise")

    __table_args__ = (
        UniqueConstraint("order_id", "position", name="uq_order_lines_position"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("reserved >= 0 AND reserved <= quantity", name="reserved_in_range"),
    )

    @property
    def value_paise(self) -> int:
        return (
            self.amount_paise if self.amount_paise is not None else self.quantity * self.rate_paise
        )


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    # NULL when the product has no supplier on record; the draft asks for one.
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True
    )
    # The supplier's branch the order goes to, if any: its GST number and
    # address print instead of the head office's.
    supplier_branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_branches.id", ondelete="RESTRICT"), nullable=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        StrEnumType(PurchaseOrderStatus), nullable=False, server_default=PurchaseOrderStatus.DRAFT
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    supplier: Mapped[Supplier | None] = relationship(lazy="raise")
    supplier_branch: Mapped[SupplierBranch | None] = relationship(lazy="raise")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.position",
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint("number", name="uq_purchase_orders_number"),
        Index("ix_purchase_orders_order_id", "order_id"),
        Index("ix_purchase_orders_status", "status"),
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # What we expect to pay: the product's purchase cost when drafted.
    rate_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=sql_text("0")
    )
    # The product's GST rate when drafted, in basis points (1800 = 18%).
    gst_rate_bp: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines", lazy="raise")

    __table_args__ = (
        UniqueConstraint("purchase_order_id", "position", name="uq_purchase_order_lines_position"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("gst_rate_bp BETWEEN 0 AND 10000", name="gst_rate_bp_range"),
    )
