"""quotation decline reason

Declining an offer now requires the reason, kept on the row.

Revision ID: 9451e2b4f103
Revises: 569547df7a39
Create Date: 2026-09-19 12:32:22.452876
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9451e2b4f103"
down_revision: str | None = "569547df7a39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quotations",
        sa.Column("decline_reason", sa.Text(), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("quotations", "decline_reason")
