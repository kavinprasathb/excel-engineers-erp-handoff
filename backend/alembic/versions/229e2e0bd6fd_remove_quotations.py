"""remove quotations

The first quotations build is withdrawn wholesale ahead of a redesign. Six
tables and four settings columns go; customers and the letterhead stay,
because both are needed by whatever replaces it.

Data in those tables at the time: one seeded test offer, no client data.

Revision ID: 229e2e0bd6fd
Revises: f5e5c6ec6c46
Create Date: 2026-09-18 22:17:13.795326
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "229e2e0bd6fd"
down_revision: str | None = "f5e5c6ec6c46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Children before parents. Autogenerate emitted `quotations` first, which
    # Postgres refuses while quotation_lines, quotation_terms and
    # quotation_status_events still hold foreign keys to it: it cannot order
    # drops of tables that are no longer in the metadata, because it has no
    # dependency information for them any more. Indexes go with their tables.
    op.drop_index(op.f("ix_quotation_line_items_line_id"), table_name="quotation_line_items")
    op.drop_index(op.f("ix_quotation_line_items_product_id"), table_name="quotation_line_items")
    op.drop_index(op.f("uq_quotation_line_items_position"), table_name="quotation_line_items")
    op.drop_table("quotation_line_items")

    op.drop_index(op.f("ix_quotation_lines_quotation_id"), table_name="quotation_lines")
    op.drop_index(op.f("uq_quotation_lines_position"), table_name="quotation_lines")
    op.drop_table("quotation_lines")

    op.drop_index(op.f("ix_quotation_terms_quotation_id"), table_name="quotation_terms")
    op.drop_index(op.f("uq_quotation_terms_position"), table_name="quotation_terms")
    op.drop_table("quotation_terms")

    op.drop_index(
        op.f("ix_quotation_status_events_quotation_id"), table_name="quotation_status_events"
    )
    op.drop_table("quotation_status_events")

    op.drop_index(op.f("ix_quotations_customer_id"), table_name="quotations")
    op.drop_index(op.f("ix_quotations_next_follow_up_on"), table_name="quotations")
    op.drop_index(
        op.f("ix_quotations_number_trgm"),
        table_name="quotations",
        postgresql_ops={"number": "gin_trgm_ops"},
        postgresql_using="gin",
    )
    op.drop_index(op.f("ix_quotations_status_date"), table_name="quotations")
    op.drop_index(op.f("uq_quotations_number_revision"), table_name="quotations")
    op.drop_table("quotations")

    op.drop_table("quotation_counters")

    op.drop_constraint(
        op.f("ck_app_settings_quotation_terms_is_array"), "app_settings", type_="check"
    )
    op.drop_constraint(
        op.f("ck_app_settings_quotation_validity_non_negative"), "app_settings", type_="check"
    )
    op.drop_column("app_settings", "quotation_prefix")
    op.drop_column("app_settings", "quotation_closing_text")
    op.drop_column("app_settings", "quotation_validity_days")
    op.drop_column("app_settings", "quotation_terms")


def downgrade() -> None:
    # Parents before children, the reverse of upgrade() and for the same reason:
    # autogenerate had quotation_lines being created before the quotations
    # table its foreign key points at.
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_validity_days",
            sa.INTEGER(),
            server_default=sa.text("10"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_closing_text",
            sa.TEXT(),
            server_default=sa.text(
                "'We trust to have made our offer in line with your requirements and in case of any query, please feel free to get in touch with us.'::text"
            ),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_prefix",
            sa.VARCHAR(length=20),
            server_default=sa.text("'ESQP'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_app_settings_quotation_validity_non_negative"),
        "app_settings",
        "quotation_validity_days >= 0",
    )
    op.create_check_constraint(
        op.f("ck_app_settings_quotation_terms_is_array"),
        "app_settings",
        "jsonb_typeof(quotation_terms) = 'array'::text",
    )
    op.create_table(
        "quotation_counters",
        sa.Column("fy", sa.VARCHAR(length=8), autoincrement=False, nullable=False),
        sa.Column(
            "last_seq",
            sa.INTEGER(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            "last_seq >= 0", name=op.f("ck_quotation_counters_last_seq_non_negative")
        ),
        sa.PrimaryKeyConstraint("fy", name=op.f("pk_quotation_counters")),
    )
    op.create_table(
        "quotations",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("number", sa.VARCHAR(length=40), autoincrement=False, nullable=False),
        sa.Column("number_fy", sa.VARCHAR(length=8), autoincrement=False, nullable=False),
        sa.Column("number_seq", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "revision",
            sa.INTEGER(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("customer_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "attention_to",
            sa.VARCHAR(length=150),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "quote_format",
            sa.VARCHAR(length=30),
            server_default=sa.text("'standard'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.VARCHAR(length=30),
            server_default=sa.text("'draft'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "quote_date",
            sa.DATE(),
            server_default=sa.text("CURRENT_DATE"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "validity_days",
            sa.INTEGER(),
            server_default=sa.text("10"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.TEXT(),
            server_default=sa.text("''::text"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "reference",
            sa.VARCHAR(length=200),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "scope_text",
            sa.TEXT(),
            server_default=sa.text("''::text"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.TEXT(),
            server_default=sa.text("''::text"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "hsn_code",
            sa.VARCHAR(length=20),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "sac_code",
            sa.VARCHAR(length=20),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "gst_rate_bp",
            sa.INTEGER(),
            server_default=sa.text("1800"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "tax_inclusive",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "subtotal_paise",
            sa.BIGINT(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "tax_paise",
            sa.BIGINT(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "total_paise",
            sa.BIGINT(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "spec_rows",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "status_changed_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("next_follow_up_on", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("created_by_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            "gst_rate_bp >= 0 AND gst_rate_bp <= 10000",
            name=op.f("ck_quotations_gst_rate_bp_range"),
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
    op.create_index(
        op.f("uq_quotations_number_revision"), "quotations", ["number", "revision"], unique=True
    )
    op.create_index(
        op.f("ix_quotations_status_date"), "quotations", ["status", "quote_date"], unique=False
    )
    op.create_index(
        op.f("ix_quotations_number_trgm"),
        "quotations",
        ["number"],
        unique=False,
        postgresql_ops={"number": "gin_trgm_ops"},
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_quotations_next_follow_up_on"), "quotations", ["next_follow_up_on"], unique=False
    )
    op.create_index(op.f("ix_quotations_customer_id"), "quotations", ["customer_id"], unique=False)
    op.create_table(
        "quotation_lines",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("quotation_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "description",
            sa.TEXT(),
            server_default=sa.text("''::text"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "unit",
            sa.VARCHAR(length=20),
            server_default=sa.text("'piece'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "unit_price_paise",
            sa.BIGINT(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "base_price_paise",
            sa.BIGINT(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "below_base_approved",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "specs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "line_total_paise",
            sa.BIGINT(),
            sa.Computed("(quantity * unit_price_paise)", persisted=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            '"position" >= 0', name=op.f("ck_quotation_lines_position_non_negative")
        ),
        sa.CheckConstraint(
            "base_price_paise >= 0", name=op.f("ck_quotation_lines_base_price_non_negative")
        ),
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
        op.f("uq_quotation_lines_position"),
        "quotation_lines",
        ["quotation_id", "position"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quotation_lines_quotation_id"), "quotation_lines", ["quotation_id"], unique=False
    )
    op.create_table(
        "quotation_line_items",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("line_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("product_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "quantity",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "unit_base_price_paise",
            sa.BIGINT(),
            server_default=sa.text("0"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "product_name",
            sa.VARCHAR(length=255),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.VARCHAR(length=100),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            '"position" >= 0', name=op.f("ck_quotation_line_items_position_non_negative")
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
        op.f("uq_quotation_line_items_position"),
        "quotation_line_items",
        ["line_id", "position"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quotation_line_items_product_id"),
        "quotation_line_items",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quotation_line_items_line_id"), "quotation_line_items", ["line_id"], unique=False
    )
    op.create_table(
        "quotation_terms",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("quotation_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("text_body", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "is_standard",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            '"position" >= 0', name=op.f("ck_quotation_terms_position_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_terms_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_terms")),
    )
    op.create_index(
        op.f("uq_quotation_terms_position"),
        "quotation_terms",
        ["quotation_id", "position"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quotation_terms_quotation_id"), "quotation_terms", ["quotation_id"], unique=False
    )
    op.create_table(
        "quotation_status_events",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("quotation_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("from_status", sa.VARCHAR(length=30), autoincrement=False, nullable=True),
        sa.Column("to_status", sa.VARCHAR(length=30), autoincrement=False, nullable=False),
        sa.Column(
            "note",
            sa.TEXT(),
            server_default=sa.text("''::text"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("created_by_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
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
