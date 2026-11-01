"""past offer items, for description suggestions

Items read from the client's past offer letters (description, rate, HSN,
MOC, offer no, date, customer), so typing a description in a quotation can
offer what was quoted before. Reference data only: a new table, nothing
existing changes.

Revision ID: b2d6f8a1c3e5
Revises: a9e4c7b2d8f1
"""

import sqlalchemy as sa

from alembic import op

revision: str = "b2d6f8a1c3e5"
down_revision: str | None = "a9e4c7b2d8f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "past_offer_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), server_default="", nullable=False),
        sa.Column("part_no", sa.String(length=60), server_default="", nullable=False),
        sa.Column("moc", sa.String(length=60), server_default="", nullable=False),
        sa.Column("unit", sa.String(length=30), server_default="", nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("rate_paise", sa.BigInteger(), nullable=False),
        sa.Column("hsn_code", sa.String(length=15), server_default="", nullable=False),
        sa.Column("offer_no", sa.String(length=40), server_default="", nullable=False),
        sa.Column("offer_date", sa.Date(), nullable=True),
        sa.Column("customer_name", sa.String(length=200), server_default="", nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=300), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_past_offer_items_customer_id_customers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_past_offer_items")),
    )
    op.create_index(
        "ix_past_offer_items_description_trgm",
        "past_offer_items",
        ["description"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.create_index("ix_past_offer_items_customer_id", "past_offer_items", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_past_offer_items_customer_id", table_name="past_offer_items")
    op.drop_index("ix_past_offer_items_description_trgm", table_name="past_offer_items")
    op.drop_table("past_offer_items")
