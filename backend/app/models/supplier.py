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


class Supplier(Base, TimestampMixin):
    """A company we buy from (KSB, Lovejoy, Goodluck…).

    Called "supplier" in the table, the API and the UI alike. v2 said
    "manufacturer" in the database and "Supplier" on screen, and the mismatch
    never went away.
    """

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # SUP-0001: issued by the database on insert from the `supplier_code_seq`
    # sequence, so every path that adds one (the form, the importer, tests)
    # gets a code, and a number is never handed out twice, not even after a
    # delete. Read-only everywhere.
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("party_code('SUP'::text, nextval('supplier_code_seq'::regclass))"),
    )
    # The last branch number issued here. Branch codes count up from it and
    # are never reused, whatever happens to the branch.
    branch_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    contact_person: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
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
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    address_line2: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    state: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    pincode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    branches: Mapped[list["SupplierBranch"]] = relationship(
        back_populates="supplier", order_by="SupplierBranch.seq", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_suppliers_code"),
        Index("uq_suppliers_name_lower", func.lower(name), unique=True),
        Index(
            "ix_suppliers_name_trgm",
            name,
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class SupplierBranch(Base, TimestampMixin):
    """An optional branch of a supplier, with its own GST number and address.

    A purchase order may name one; it then prints the branch's GST number and
    address instead of the head office's. Removing a branch only hides it
    (`is_active`), so a document that named it still prints it.
    """

    __tablename__ = "supplier_branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    # 1, 2, 3... within the supplier; the code is "SUP-0001-BR01".
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
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

    supplier: Mapped[Supplier] = relationship(back_populates="branches", lazy="raise")

    __table_args__ = (
        UniqueConstraint("code", name="uq_supplier_branches_code"),
        UniqueConstraint("supplier_id", "seq", name="uq_supplier_branches_supplier_id_seq"),
        Index("ix_supplier_branches_supplier_id", "supplier_id"),
    )
