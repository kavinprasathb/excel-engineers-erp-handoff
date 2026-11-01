"""purchase order received

When the goods on a purchase order arrive: stock goes in, and the PO
records when.

Revision ID: ffa52613cff0
Revises: a3c1d8e2f4b7
Create Date: 2026-09-26 23:09:27.064145
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ffa52613cff0"
down_revision: str | None = "a3c1d8e2f4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.execute("UPDATE purchase_orders SET status = 'sent' WHERE status = 'received'")
    op.drop_column("purchase_orders", "received_at")
