from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..constants import DEFAULT_UNIT
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .category import Category
    from .inventory import Inventory
    from .supplier import Supplier


class Product(Base, TimestampMixin):
    """A sellable item in the catalogue.

    Money is integer paise in BigInteger. v2 used Integer, which caps at about
    ₹21.4 lakh — a single industrial pump line can exceed that, and the failure
    would be a silent overflow.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_number: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default=DEFAULT_UNIT)
    hsn_code: Mapped[str] = mapped_column(String(15), nullable=False, server_default="")

    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )

    purchase_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    sell_price: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    # Basis points: 1800 == 18%. Integer percent cannot express the 0.25% slab.
    gst_rate_bp: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Per-product override of the global low-stock threshold. Not exposed in
    # slice 1 (always NULL); present so enabling it later is a field, not a
    # migration plus backfill plus query rewrite.
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # stocked / to_order / service (constants.StockType). Existing products
    # are stocked; the type decides low-stock alerts and whether an order
    # holds and delivers stock for it.
    stock_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="stocked")

    # lazy="raise": an accidental lazy load is a hard error, not 25 silent
    # extra round-trips. Every list query must state its loader options.
    supplier: Mapped["Supplier | None"] = relationship(lazy="raise")
    category: Mapped["Category | None"] = relationship(lazy="raise")
    inventory: Mapped["Inventory"] = relationship(
        back_populates="product", uselist=False, lazy="raise", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_products_sku_lower", func.lower(sku), unique=True),
        # The operator class goes in postgresql_ops, NOT inline in the
        # expression: inline, Alembic cannot compare the index and the
        # models-match-migrations test has to exempt it.
        Index(
            "ix_products_search_trgm",
            text("(name || ' ' || sku || ' ' || model_number)"),
            postgresql_using="gin",
            postgresql_ops={"(name || ' ' || sku || ' ' || model_number)": "gin_trgm_ops"},
        ),
        CheckConstraint("purchase_cost >= 0", name="purchase_cost_non_negative"),
        CheckConstraint("sell_price >= 0", name="sell_price_non_negative"),
        CheckConstraint("gst_rate_bp BETWEEN 0 AND 10000", name="gst_rate_bp_range"),
        CheckConstraint(
            "low_stock_threshold IS NULL OR low_stock_threshold >= 0",
            name="low_stock_threshold_non_negative",
        ),
    )
