"""Quotations: an offer letter to a customer, with its lines and terms.

One row per *version*. A new version inserts a row with the same
(type, year, seq) and revision + 1, and marks the old one superseded — so the
history is just the rows, and "the live one" is the highest revision.

A version is one of two kinds, and carries both counters:

* a **revised quotation** (product, quantity or technical change): R1, R2...
  `rev_no` counts up across the number, `neg_no` starts again at 0;
* a **negotiation** (price only): N1, N2... within the revision it was
  started from; `rev_no` is that revision's.

So ESQSP-26-7 → ESQSP-26-7-R1 → ESQSP-26-7-R2 → ESQSP-26-7-R2N1. `revision`
stays the plain position in the chain (0, 1, 2, 3): it orders the history
and decides which version is the latest.
"""

from datetime import date
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..constants import QUOTATION_PREFIXES, LineKind, QuotationStatus, QuotationType
from .base import Base, TimestampMixin
from .customer import Customer, CustomerBranch
from .types import StrEnumType


class QuotationCounter(Base):
    """last_seq per (type, year). Locked FOR UPDATE when a number is issued."""

    __tablename__ = "quotation_counters"

    type: Mapped[QuotationType] = mapped_column(StrEnumType(QuotationType), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))


class Quotation(Base, TimestampMixin):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[QuotationType] = mapped_column(StrEnumType(QuotationType), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)  # two-digit, e.g. 26
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    # Which revised quotation (R) this version belongs to; 0 is the original.
    rev_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    # Which negotiation round (N) of that revision; 0 is not a negotiation.
    neg_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    # Denormalised "ESQSP-26-70-R1N2" so lists and searches never rebuild it.
    number: Mapped[str] = mapped_column(String(30), nullable=False)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    # The branch the offer is addressed to, if any: its GST number and address
    # print instead of the head office's.
    customer_branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_branches.id", ondelete="RESTRICT"), nullable=True
    )
    quote_date: Mapped[date] = mapped_column(Date, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    reference: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    status: Mapped[QuotationStatus] = mapped_column(
        StrEnumType(QuotationStatus), nullable=False, server_default=QuotationStatus.PENDING
    )
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # How the letter is laid out; the data is the same for all three.
    # "pump": a datasheet and a price line per pump (1-3 new pumps).
    # "spares": tables of parts per pump model, notes as group headings,
    # service at the end. "technical": one column per pump, one row per
    # parameter (`tech_rows`), for 4+ pumps on 1-2 pages.
    format: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pump")
    # Spares layout: which optional columns print (part_no, moc, unit, delivery).
    print_columns: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text('\'["moc", "unit"]\'::jsonb')
    )
    # The technical sheet's rows, in order: [{section, label}]. Every item
    # (column) has one value per row, in `QuotationLine.tech_values`.
    tech_rows: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )
    # The technical sheet's price row label, saying what the price covers
    # ("Pump with accessories (without motor) Unit Price"); blank: "Unit Price".
    price_label: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    # The technical sheet's scope of supply ("Motor not in our scope").
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # Why the customer said no. Required to decline; the sales record is the
    # point of keeping declined offers at all.
    decline_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    customer: Mapped[Customer] = relationship(lazy="raise")
    customer_branch: Mapped[CustomerBranch | None] = relationship(lazy="raise")
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationLine.position",
        lazy="raise",
    )
    terms: Mapped[list["QuotationTerm"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationTerm.position",
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint("type", "year", "seq", "revision", name="uq_quotations_number_parts"),
        # One R1N2 per number: references are never issued twice.
        UniqueConstraint(
            "type", "year", "seq", "rev_no", "neg_no", name="uq_quotations_version_refs"
        ),
        Index("ix_quotations_number", "number"),
        Index("ix_quotations_customer_id", "customer_id"),
        Index("ix_quotations_status", "status"),
        CheckConstraint("revision >= 0", name="revision_non_negative"),
        CheckConstraint("seq > 0", name="seq_positive"),
        CheckConstraint("rev_no >= 0 AND neg_no >= 0", name="version_refs_non_negative"),
    )

    @property
    def total_paise(self) -> int:
        return sum(line.value_paise for line in self.lines)

    @property
    def base_number(self) -> str:
        """The original quotation's number, ESQSP-26-70, whatever this version is."""
        return f"{QUOTATION_PREFIXES[self.type]}-{self.year:02d}-{self.seq}"

    @property
    def stage_label(self) -> str:
        """'Initial quote', 'Revision R2', 'Negotiation N1' or 'Revision R2 · Negotiation N1'."""
        parts = []
        if self.rev_no:
            parts.append(f"Revision R{self.rev_no}")
        if self.neg_no:
            parts.append(f"Negotiation N{self.neg_no}")
        return " · ".join(parts) or "Initial quote"


class QuotationLine(Base):
    __tablename__ = "quotation_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[LineKind] = mapped_column(
        StrEnumType(LineKind, length=10), nullable=False, server_default=LineKind.PRODUCT
    )
    # "Each", "Set"... printed beside the quantity.
    unit_label: Mapped[str] = mapped_column(String(30), nullable=False, server_default="Each")
    # HSN (goods) or SAC (services) code, printed in its own column.
    hsn_code: Mapped[str] = mapped_column(String(15), nullable=False, server_default="")
    # NULL for a free-text line. The description is always stored, so a later
    # rename of the product does not rewrite a sent offer.
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # The item's technical deviation: ordered [{label, value}] rows. Only the
    # rows with a value print, directly under the item. JSONB: the rows are
    # always read and written with their line and nothing queries inside them.
    deviations: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )
    # A line made of several inventory items (a pump set: pump, base frame,
    # coupling): [{product_id, name, quantity}], quantity per one of the line's
    # units. The line prints as one item; stock moves per component, by
    # component quantity x line quantity, and only through its order. Empty:
    # an ordinary line, whose product is `product_id`. The description is for
    # the letter only and is never read for stock.
    components: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )
    # Technical sheet only: the column heading ("UF Feed", "Borewell BH1")
    # and one value per row of the quotation's `tech_rows`, in the same order.
    service: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    # Spares layout columns, printed when switched on for the quotation.
    part_no: Mapped[str] = mapped_column(String(60), nullable=False, server_default="")
    moc: Mapped[str] = mapped_column(String(60), nullable=False, server_default="")
    delivery: Mapped[str] = mapped_column(String(60), nullable=False, server_default="")
    # Pump layout: what the price includes ("with 20 Hp motor, base frame...").
    supply_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tech_values: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )

    quotation: Mapped[Quotation] = relationship(back_populates="lines", lazy="raise")

    __table_args__ = (
        UniqueConstraint("quotation_id", "position", name="uq_quotation_lines_position"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("rate_paise >= 0", name="rate_non_negative"),
    )

    @property
    def value_paise(self) -> int:
        return self.quantity * self.rate_paise


class QuotationTerm(Base):
    __tablename__ = "quotation_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))

    quotation: Mapped[Quotation] = relationship(back_populates="terms", lazy="raise")

    __table_args__ = (
        UniqueConstraint("quotation_id", "position", name="uq_quotation_terms_position"),
    )
