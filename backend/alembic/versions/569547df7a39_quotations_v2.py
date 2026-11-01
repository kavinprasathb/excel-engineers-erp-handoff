"""quotations v2

The rebuilt quotation module: one row per revision, lines that may or may not
point at a product, terms as checkboxes, a counter per (type, year). Also
seeds the per-type default terms on app_settings. The literal below is a copy
of app.constants.DEFAULT_QUOTATION_TERMS on the day this ran, and must stay a
copy: a migration never imports application code.

Revision ID: 569547df7a39
Revises: 229e2e0bd6fd
Create Date: 2026-09-19 10:49:03.979276
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "569547df7a39"
down_revision: str | None = "229e2e0bd6fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_TERMS: dict[str, list[dict[str, str]]] = {
    "pumps": [
        {"label": "Price Basis", "text": "The prices quoted are FOR Salem, Exclusive of GST"},
        {"label": "GST", "text": "GST @ 18% will be charged extra to your account"},
        {"label": "Delivery", "text": "2 weeks"},
        {"label": "Packing & Forwarding", "text": "Included on the above price"},
        {"label": "Freight", "text": "Actual to your account."},
        {"label": "Payment terms", "text": "Against Proforma Invoice"},
        {
            "label": "Warranty",
            "text": "12 months from date of commissioning or 18 months from date of despatch, whichever is earlier, as per KSB policy",
        },
        {"label": "Validity", "text": "30 days from date of this offer."},
    ],
    "valves": [
        {"label": "Price Basis", "text": "The prices quoted are FOR Salem, Exclusive of GST"},
        {"label": "GST", "text": "GST @ 18% will be charged extra to your account"},
        {"label": "Delivery", "text": "2 weeks"},
        {"label": "Packing & Forwarding", "text": "Included on the above price"},
        {"label": "Freight", "text": "Actual to your account."},
        {"label": "Payment terms", "text": "Against Proforma Invoice"},
        {"label": "Warranty", "text": "12 months from date of despatch as per manufacturer policy"},
        {"label": "Validity", "text": "30 days from date of this offer."},
    ],
    "spares": [
        {"label": "Price Basis", "text": "The prices quoted are FOR Salem, Exclusive of GST"},
        {"label": "GST", "text": "GST @ 18% will be charged extra to your account"},
        {"label": "Delivery", "text": "2 weeks"},
        {"label": "Packing & Forwarding", "text": "Included on the above price"},
        {"label": "Freight", "text": "Actual to your account."},
        {"label": "Payment terms", "text": "Against Proforma Invoice"},
        {"label": "Warranty", "text": "No Warranty / Guarantee for spares as per KSB Policy"},
        {"label": "Validity", "text": "30 days from date of this offer."},
    ],
}


def upgrade() -> None:
    op.create_table(
        "quotation_counters",
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("type", "year", name=op.f("pk_quotation_counters")),
    )
    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("number", sa.String(length=30), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("subject", sa.String(length=255), server_default="", nullable=False),
        sa.Column("reference", sa.String(length=255), server_default="", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
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
        sa.CheckConstraint("revision >= 0", name=op.f("ck_quotations_revision_non_negative")),
        sa.CheckConstraint("seq > 0", name=op.f("ck_quotations_seq_positive")),
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
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["quotations.id"],
            name=op.f("fk_quotations_supersedes_id_quotations"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotations")),
        sa.UniqueConstraint("type", "year", "seq", "revision", name="uq_quotations_number_parts"),
    )
    op.create_index("ix_quotations_customer_id", "quotations", ["customer_id"], unique=False)
    op.create_index("ix_quotations_number", "quotations", ["number"], unique=False)
    op.create_index("ix_quotations_status", "quotations", ["status"], unique=False)
    op.create_table(
        "quotation_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("rate_paise", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_quotation_lines_quantity_positive")),
        sa.CheckConstraint("rate_paise >= 0", name=op.f("ck_quotation_lines_rate_non_negative")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_quotation_lines_product_id_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_lines_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_lines")),
        sa.UniqueConstraint("quotation_id", "position", name="uq_quotation_lines_position"),
    )
    op.create_table(
        "quotation_terms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("included", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_terms_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_terms")),
        sa.UniqueConstraint("quotation_id", "position", name="uq_quotation_terms_position"),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_terms_defaults",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE app_settings SET quotation_terms_defaults = CAST(:v AS jsonb) WHERE id = 1"
        ).bindparams(v=json.dumps(_DEFAULT_TERMS))
    )


def downgrade() -> None:
    op.drop_column("app_settings", "quotation_terms_defaults")
    op.drop_table("quotation_terms")
    op.drop_table("quotation_lines")
    op.drop_index("ix_quotations_status", table_name="quotations")
    op.drop_index("ix_quotations_number", table_name="quotations")
    op.drop_index("ix_quotations_customer_id", table_name="quotations")
    op.drop_table("quotations")
    op.drop_table("quotation_counters")
