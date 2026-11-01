"""customers and quotations

Revision ID: f5e5c6ec6c46
Revises: 95b0c71a4a0d
Create Date: 2026-09-16 10:01:39.224060
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# Inlined rather than imported from app.constants: a migration that imports
# application code breaks the moment that code is refactored — and this one
# did, the day the constant was deleted. A migration describes what happened
# to the database on the day it ran, and must keep saying so verbatim.
_STANDARD_TERMS = (
    "Price quoted are FOR Salem, exclusive of GST and certificates.",
    "GST @ 18% extra.",
    "Packing & Forwarding Nil. If pump with motor is needed in wooden packing, "
    "₹4,000/- per pumpset will be extra.",
    "Freight extra.",
    "Delivery 16 weeks from the technically cleared PO along with document approvals.",
    "Payment: 100% within 90 days from the invoice date.",
    "Offer valid for 10 days.",
    "Warranty 12 months from supply.",
    "Being standard range of pumps, inspection is not applicable.",
    "LD clause not applicable.",
)

revision: str = "f5e5c6ec6c46"
down_revision: str | None = "95b0c71a4a0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("contact_person", sa.String(length=150), server_default="", nullable=False),
        sa.Column("designation", sa.String(length=100), server_default="", nullable=False),
        sa.Column("phone", sa.String(length=30), server_default="", nullable=False),
        sa.Column("email", sa.String(length=255), server_default="", nullable=False),
        sa.Column("gstin", sa.String(length=20), server_default="", nullable=False),
        sa.Column(
            "billing_address_line1", sa.String(length=255), server_default="", nullable=False
        ),
        sa.Column(
            "billing_address_line2", sa.String(length=255), server_default="", nullable=False
        ),
        sa.Column("billing_city", sa.String(length=100), server_default="", nullable=False),
        sa.Column("billing_state", sa.String(length=100), server_default="", nullable=False),
        sa.Column("billing_pincode", sa.String(length=10), server_default="", nullable=False),
        sa.Column(
            "shipping_address_line1", sa.String(length=255), server_default="", nullable=False
        ),
        sa.Column(
            "shipping_address_line2", sa.String(length=255), server_default="", nullable=False
        ),
        sa.Column("shipping_city", sa.String(length=100), server_default="", nullable=False),
        sa.Column("shipping_state", sa.String(length=100), server_default="", nullable=False),
        sa.Column("shipping_pincode", sa.String(length=10), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(
        "ix_customers_name_trgm",
        "customers",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "uq_customers_name_lower", "customers", [sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "quotation_counters",
        sa.Column("fy", sa.String(length=8), nullable=False),
        sa.Column("last_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "last_seq >= 0", name=op.f("ck_quotation_counters_last_seq_non_negative")
        ),
        sa.PrimaryKeyConstraint("fy", name=op.f("pk_quotation_counters")),
    )
    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=40), nullable=False),
        sa.Column("number_fy", sa.String(length=8), nullable=False),
        sa.Column("number_seq", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("attention_to", sa.String(length=150), server_default="", nullable=False),
        sa.Column(
            "quote_format",
            sa.String(length=30),
            server_default="standard",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("quote_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("validity_days", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("subject", sa.Text(), server_default="", nullable=False),
        sa.Column("reference", sa.String(length=200), server_default="", nullable=False),
        sa.Column("scope_text", sa.Text(), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("hsn_code", sa.String(length=20), server_default="", nullable=False),
        sa.Column("sac_code", sa.String(length=20), server_default="", nullable=False),
        sa.Column("gst_rate_bp", sa.Integer(), server_default=sa.text("1800"), nullable=False),
        sa.Column("tax_inclusive", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("subtotal_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("tax_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "spec_rows",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_follow_up_on", sa.Date(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "gst_rate_bp BETWEEN 0 AND 10000", name=op.f("ck_quotations_gst_rate_bp_range")
        ),
        sa.CheckConstraint("number_seq > 0", name=op.f("ck_quotations_number_seq_positive")),
        sa.CheckConstraint("revision >= 0", name=op.f("ck_quotations_revision_non_negative")),
        sa.CheckConstraint("subtotal_paise >= 0", name=op.f("ck_quotations_subtotal_non_negative")),
        sa.CheckConstraint("tax_paise >= 0", name=op.f("ck_quotations_tax_non_negative")),
        sa.CheckConstraint("total_paise >= 0", name=op.f("ck_quotations_total_non_negative")),
        sa.CheckConstraint(
            "validity_days >= 0", name=op.f("ck_quotations_validity_days_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_quotations_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_quotations_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotations")),
    )
    op.create_index(op.f("ix_quotations_customer_id"), "quotations", ["customer_id"], unique=False)
    op.create_index(
        op.f("ix_quotations_next_follow_up_on"), "quotations", ["next_follow_up_on"], unique=False
    )
    op.create_index(
        "ix_quotations_number_trgm",
        "quotations",
        ["number"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"number": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_quotations_status_date", "quotations", ["status", "quote_date"], unique=False
    )
    op.create_index(
        "uq_quotations_number_revision", "quotations", ["number", "revision"], unique=True
    )
    op.create_table(
        "quotation_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("unit", sa.String(length=20), server_default="piece", nullable=False),
        sa.Column("unit_price_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("base_price_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "below_base_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "specs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "line_total_paise",
            sa.BigInteger(),
            sa.Computed("quantity * unit_price_paise", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "base_price_paise >= 0", name=op.f("ck_quotation_lines_base_price_non_negative")
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_quotation_lines_position_non_negative")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_quotation_lines_quantity_positive")),
        sa.CheckConstraint(
            "unit_price_paise >= 0", name=op.f("ck_quotation_lines_unit_price_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_lines_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_lines")),
    )
    op.create_index(
        op.f("ix_quotation_lines_quotation_id"), "quotation_lines", ["quotation_id"], unique=False
    )
    op.create_index(
        "uq_quotation_lines_position", "quotation_lines", ["quotation_id", "position"], unique=True
    )
    op.create_table(
        "quotation_status_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_quotation_status_events_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_status_events_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_status_events")),
    )
    op.create_index(
        op.f("ix_quotation_status_events_quotation_id"),
        "quotation_status_events",
        ["quotation_id"],
        unique=False,
    )
    op.create_table(
        "quotation_terms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("is_standard", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_quotation_terms_position_non_negative")),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_terms_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_terms")),
    )
    op.create_index(
        op.f("ix_quotation_terms_quotation_id"), "quotation_terms", ["quotation_id"], unique=False
    )
    op.create_index(
        "uq_quotation_terms_position", "quotation_terms", ["quotation_id", "position"], unique=True
    )
    op.create_table(
        "quotation_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "unit_base_price_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("product_name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("product_sku", sa.String(length=100), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_quotation_line_items_position_non_negative")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_quotation_line_items_quantity_positive")),
        sa.CheckConstraint(
            "unit_base_price_paise >= 0",
            name=op.f("ck_quotation_line_items_unit_base_price_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["quotation_lines.id"],
            name=op.f("fk_quotation_line_items_line_id_quotation_lines"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_quotation_line_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_line_items")),
    )
    op.create_index(
        op.f("ix_quotation_line_items_line_id"), "quotation_line_items", ["line_id"], unique=False
    )
    op.create_index(
        op.f("ix_quotation_line_items_product_id"),
        "quotation_line_items",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "uq_quotation_line_items_position",
        "quotation_line_items",
        ["line_id", "position"],
        unique=True,
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_address_line1",
            sa.String(length=255),
            server_default="G2, VKP Residency, 146, Dhayanandhar Street",
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_address_line2",
            sa.String(length=255),
            server_default="New Fairlands",
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("company_city", sa.String(length=100), server_default="Salem", nullable=False),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_state", sa.String(length=100), server_default="Tamil Nadu", nullable=False
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("company_pincode", sa.String(length=10), server_default="636016", nullable=False),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_gstin", sa.String(length=20), server_default="33AAIFE2328P1Z9", nullable=False
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_phone", sa.String(length=30), server_default="0427 244 0808", nullable=False
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_mobile", sa.String(length=30), server_default="94449 15716", nullable=False
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "company_email",
            sa.String(length=255),
            server_default="excelengrs@gmail.com",
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "signatory_name",
            sa.String(length=150),
            server_default="M. Rajamuthaiyah",
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "signatory_designation", sa.String(length=100), server_default="", nullable=False
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("quotation_prefix", sa.String(length=20), server_default="ESQP", nullable=False),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_validity_days", sa.Integer(), server_default=sa.text("10"), nullable=False
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_closing_text",
            sa.Text(),
            server_default="We trust to have made our offer in line with your requirements and in case of any query, please feel free to get in touch with us.",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_app_settings_quotation_terms_is_array"),
        "app_settings",
        "jsonb_typeof(quotation_terms) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_app_settings_quotation_validity_non_negative"),
        "app_settings",
        "quotation_validity_days >= 0",
    )

    # Seed the standard terms onto the existing singleton row. The column's
    # server_default is an empty array, correct for a fresh database but it
    # would leave this deployment blank - and a quotation created with no
    # standard terms prints a commercially useless offer.
    op.execute(
        sa.text(
            "UPDATE app_settings SET quotation_terms = CAST(:terms AS jsonb) "
            "WHERE id = 1 AND quotation_terms = '[]'::jsonb"
        ).bindparams(terms=json.dumps(list(_STANDARD_TERMS)))
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_app_settings_quotation_validity_non_negative"), "app_settings", type_="check"
    )
    op.drop_constraint(
        op.f("ck_app_settings_quotation_terms_is_array"), "app_settings", type_="check"
    )
    op.drop_column("app_settings", "quotation_closing_text")
    op.drop_column("app_settings", "quotation_terms")
    op.drop_column("app_settings", "quotation_validity_days")
    op.drop_column("app_settings", "quotation_prefix")
    op.drop_column("app_settings", "signatory_designation")
    op.drop_column("app_settings", "signatory_name")
    op.drop_column("app_settings", "company_email")
    op.drop_column("app_settings", "company_mobile")
    op.drop_column("app_settings", "company_phone")
    op.drop_column("app_settings", "company_gstin")
    op.drop_column("app_settings", "company_pincode")
    op.drop_column("app_settings", "company_state")
    op.drop_column("app_settings", "company_city")
    op.drop_column("app_settings", "company_address_line2")
    op.drop_column("app_settings", "company_address_line1")
    op.drop_index("uq_quotation_line_items_position", table_name="quotation_line_items")
    op.drop_index(op.f("ix_quotation_line_items_product_id"), table_name="quotation_line_items")
    op.drop_index(op.f("ix_quotation_line_items_line_id"), table_name="quotation_line_items")
    op.drop_table("quotation_line_items")
    op.drop_index("uq_quotation_terms_position", table_name="quotation_terms")
    op.drop_index(op.f("ix_quotation_terms_quotation_id"), table_name="quotation_terms")
    op.drop_table("quotation_terms")
    op.drop_index(
        op.f("ix_quotation_status_events_quotation_id"), table_name="quotation_status_events"
    )
    op.drop_table("quotation_status_events")
    op.drop_index("uq_quotation_lines_position", table_name="quotation_lines")
    op.drop_index(op.f("ix_quotation_lines_quotation_id"), table_name="quotation_lines")
    op.drop_table("quotation_lines")
    op.drop_index("uq_quotations_number_revision", table_name="quotations")
    op.drop_index("ix_quotations_status_date", table_name="quotations")
    op.drop_index(
        "ix_quotations_number_trgm",
        table_name="quotations",
        postgresql_using="gin",
        postgresql_ops={"number": "gin_trgm_ops"},
    )
    op.drop_index(op.f("ix_quotations_next_follow_up_on"), table_name="quotations")
    op.drop_index(op.f("ix_quotations_customer_id"), table_name="quotations")
    op.drop_table("quotations")
    op.drop_table("quotation_counters")
    op.drop_index("uq_customers_name_lower", table_name="customers")
    op.drop_index(
        "ix_customers_name_trgm",
        table_name="customers",
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.drop_table("customers")
