"""negotiation suffix N

The client calls revisions negotiations, so ESQSP-26-70R2 becomes
ESQSP-26-70N2. Only the denormalised `number` text changes; the revision
column that drives it is untouched.

Revision ID: eb9feb9358bb
Revises: f5e4e26214ac
"""

from collections.abc import Sequence

from alembic import op

revision: str = "eb9feb9358bb"
down_revision: str | None = "f5e4e26214ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(r"UPDATE quotations SET number = regexp_replace(number, 'R(\d+)$', 'N\1')")


def downgrade() -> None:
    op.execute(r"UPDATE quotations SET number = regexp_replace(number, 'N(\d+)$', 'R\1')")
