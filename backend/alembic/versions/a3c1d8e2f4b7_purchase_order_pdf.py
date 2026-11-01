"""purchase order pdf: GST per line, ESPO numbers

Each purchase order line keeps the GST rate it was drafted with, so the
printed SGST/CGST does not move when a product's rate is edited later.
Purchase orders are numbered like quotations: ESPO-26-1, ESPO-26-2, ...

Revision ID: a3c1d8e2f4b7
Revises: 77fa90df9293
Create Date: 2026-09-26 22:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c1d8e2f4b7"
down_revision: str | None = "77fa90df9293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_order_lines",
        sa.Column("gst_rate_bp", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_purchase_order_lines_gst_rate_bp_range"),
        "purchase_order_lines",
        "gst_rate_bp BETWEEN 0 AND 10000",
    )
    op.execute(
        "UPDATE purchase_order_lines l SET gst_rate_bp = p.gst_rate_bp "
        "FROM products p WHERE p.id = l.product_id"
    )
    op.execute(
        "UPDATE purchase_orders po SET number = n.number FROM ("
        "  SELECT id, 'ESPO-' || to_char(created_at AT TIME ZONE 'Asia/Kolkata', 'YY') || '-' ||"
        "    row_number() OVER (PARTITION BY to_char(created_at AT TIME ZONE 'Asia/Kolkata', 'YY')"
        "    ORDER BY id) AS number FROM purchase_orders"
        ") n WHERE n.id = po.id"
    )
    op.create_unique_constraint(op.f("uq_purchase_orders_number"), "purchase_orders", ["number"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_purchase_orders_number"), "purchase_orders", type_="unique")
    op.execute("UPDATE purchase_orders SET number = 'PO-' || lpad(id::text, 4, '0')")
    op.drop_constraint(
        op.f("ck_purchase_order_lines_gst_rate_bp_range"), "purchase_order_lines", type_="check"
    )
    op.drop_column("purchase_order_lines", "gst_rate_bp")
