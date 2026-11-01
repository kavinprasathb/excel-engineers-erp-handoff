"""product stock type

A product is stocked (held on the shelf), to_order (quoted and bought in when
an order needs it) or a service (never stocked). Every existing product is
stocked, so nothing about current stock, alerts or orders changes.

Revision ID: f3b7d1a9c5e2
Revises: d4a8c2e6f1b9
"""

import sqlalchemy as sa

from alembic import op

revision: str = "f3b7d1a9c5e2"
down_revision: str | None = "d4a8c2e6f1b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("stock_type", sa.String(length=20), server_default="stocked", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("products", "stock_type")
