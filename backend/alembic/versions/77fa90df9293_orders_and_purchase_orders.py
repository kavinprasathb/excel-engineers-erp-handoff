"""orders and purchase orders

An order per accepted quotation, holding stock item by item; draft purchase
orders for what it is short of, one per supplier.

Revision ID: 77fa90df9293
Revises: eb9feb9358bb
Create Date: 2026-09-26 20:34:00.663955
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "77fa90df9293"
down_revision: str | None = "eb9feb9358bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=40), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="waiting_stock", nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_orders_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_orders_quotation_id_quotations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("number", name="uq_orders_number"),
        sa.UniqueConstraint("quotation_id", name="uq_orders_quotation_id"),
    )
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_table(
        "order_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("rate_paise", sa.BigInteger(), nullable=False),
        sa.Column("reserved", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_lines_quantity_positive")),
        sa.CheckConstraint(
            "reserved >= 0 AND reserved <= quantity", name=op.f("ck_order_lines_reserved_in_range")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_lines_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_lines")),
        sa.UniqueConstraint("order_id", "position", name="uq_order_lines_position"),
    )
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=40), server_default="", nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
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
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_purchase_orders_order_id_orders"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_purchase_orders_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders")),
    )
    op.create_index("ix_purchase_orders_order_id", "purchase_orders", ["order_id"], unique=False)
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"], unique=False)
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("rate_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_purchase_order_lines_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_purchase_order_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_purchase_order_lines_purchase_order_id_purchase_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_order_lines")),
        sa.UniqueConstraint(
            "purchase_order_id", "position", name="uq_purchase_order_lines_position"
        ),
    )


def downgrade() -> None:
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_order_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_table("order_lines")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_table("orders")
