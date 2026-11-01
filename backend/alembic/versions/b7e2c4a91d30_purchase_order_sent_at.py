"""purchase order sent_at

When a purchase order was sent to the supplier, for the Deal Tracker.
Existing sent or received orders take their last change as the best guess.

Revision ID: b7e2c4a91d30
Revises: f01d6d3179ce
Create Date: 2026-09-27 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2c4a91d30"
down_revision: str | None = "f01d6d3179ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE purchase_orders SET sent_at = updated_at WHERE status IN ('sent', 'received')")


def downgrade() -> None:
    op.drop_column("purchase_orders", "sent_at")
