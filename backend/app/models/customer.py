from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    """A company we sell to (Chemplast Sanmar, IE-Emmvee…).

    Deliberately the same shape as `Supplier`, because they are the same kind
    of thing pointed the other way and two divergent address models would mean
    two of every form, validator and formatter.

    The one addition is a separate *shipping* address. A real offer is billed
    to a head office and delivered to a plant — the Chemplast offer is
    addressed to Mettur while the company is registered elsewhere — and the
    delivery challan module will need the distinction. Blank shipping fields
    mean "same as billing"; nothing in the app copies one into the other.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # CUST-0001: issued by the database on insert from the `customer_code_seq`
    # sequence, so every path that adds one (the form, the importer, tests)
    # gets a code, and a number is never handed out twice, not even after a
    # delete. Read-only everywhere.
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("party_code('CUST'::text, nextval('customer_code_seq'::regclass))"),
    )
    # The last branch number issued here. Branch codes count up from it and
    # are never reused, whatever happens to the branch.
    branch_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # "Kind Attn. Mr. B.Prathap" on the real offers. Prints under the address.
    contact_person: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    designation: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, server_default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    # Every email / phone, first one first. `email` / `phone` above always
    # equal the first entry: the PDFs and older clients read those.
    emails: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), nullable=False, default=list, server_default="{}"
    )
    phones: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), nullable=False, default=list, server_default="{}"
    )
    gstin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")

    billing_address_line1: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    billing_address_line2: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    billing_city: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    billing_state: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    billing_pincode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="")

    shipping_address_line1: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    shipping_address_line2: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    shipping_city: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    shipping_state: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    shipping_pincode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="")

    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    branches: Mapped[list["CustomerBranch"]] = relationship(
        back_populates="customer", order_by="CustomerBranch.seq", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_customers_code"),
        Index("uq_customers_name_lower", func.lower(name), unique=True),
        Index(
            "ix_customers_name_trgm",
            name,
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class CustomerBranch(Base, TimestampMixin):
    """An optional branch of a customer, with its own GST number and address.

    A quotation may name one; it then prints the branch's GST number and
    address instead of the head office's. Removing a branch only hides it
    (`is_active`), so a document that named it still prints it.
    """

    __tablename__ = "customer_branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    # 1, 2, 3... within the customer; the code is "CUST-0001-BR01".
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
    contact_person: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    designation: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    emails: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), nullable=False, default=list, server_default="{}"
    )
    phones: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), nullable=False, default=list, server_default="{}"
    )
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    state: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    pincode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    customer: Mapped[Customer] = relationship(back_populates="branches", lazy="raise")

    __table_args__ = (
        UniqueConstraint("code", name="uq_customer_branches_code"),
        UniqueConstraint("customer_id", "seq", name="uq_customer_branches_customer_id_seq"),
        Index("ix_customer_branches_customer_id", "customer_id"),
    )
