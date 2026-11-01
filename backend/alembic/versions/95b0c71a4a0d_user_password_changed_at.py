"""user password_changed_at and session_epoch

Revision ID: 95b0c71a4a0d
Revises: f068d5d74c7e
Create Date: 2026-08-30 21:53:51.669659
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "95b0c71a4a0d"
down_revision: str | None = "f068d5d74c7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only the column. Autogenerate also proposed dropping and recreating
    # ix_products_search_trgm — that index is over a concatenation expression,
    # which Alembic cannot compare, so it reports a difference on every run.
    # Acting on it would rebuild a GIN index on every deploy for nothing.
    op.add_column(
        "users",
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("session_epoch", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "session_epoch")
    op.drop_column("users", "password_changed_at")
