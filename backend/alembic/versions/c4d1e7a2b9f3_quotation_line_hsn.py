"""quotation line hsn/sac code

Revision ID: c4d1e7a2b9f3
Revises: b7e2c4a91d30
"""

import sqlalchemy as sa

from alembic import op

revision: str = "c4d1e7a2b9f3"
down_revision: str | None = "b7e2c4a91d30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotation_lines",
        sa.Column("hsn_code", sa.String(length=15), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("quotation_lines", "hsn_code")
