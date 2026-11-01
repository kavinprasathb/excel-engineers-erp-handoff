"""Items from offers sent before the app, for suggestions while quoting.

One row per priced item read from the client's past offer letters (Word):
what was quoted, at what rate, to whom and when. Read-only reference data,
loaded by `scripts/import_past_offers.py`; nothing in the app writes it, and
nothing reads it but the description suggestions.
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PastOfferItem(Base):
    __tablename__ = "past_offer_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Context printed with it: the pump model group, or a pump's scope of supply.
    details: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    part_no: Mapped[str] = mapped_column(String(60), nullable=False, server_default="")
    moc: Mapped[str] = mapped_column(String(60), nullable=False, server_default="")
    unit: Mapped[str] = mapped_column(String(30), nullable=False, server_default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    rate_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hsn_code: Mapped[str] = mapped_column(String(15), nullable=False, server_default="")
    offer_no: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    offer_date: Mapped[date | None] = mapped_column(Date)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(300), nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_past_offer_items_description_trgm",
            description,
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        Index("ix_past_offer_items_customer_id", "customer_id"),
    )
