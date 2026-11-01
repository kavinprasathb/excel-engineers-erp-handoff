"""many emails and phones on customers and suppliers

Revision ID: d8a3f5c1e6b2
Revises: c4d1e7a2b9f3
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d8a3f5c1e6b2"
down_revision: str | None = "c4d1e7a2b9f3"
branch_labels = None
depends_on = None

TABLES = ("customers", "suppliers")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "emails",
                postgresql.ARRAY(sa.String(length=255)),
                server_default="{}",
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "phones",
                postgresql.ARRAY(sa.String(length=30)),
                server_default="{}",
                nullable=False,
            ),
        )
        # Backfill: the single value becomes the first (only) list entry, so
        # nothing typed before this migration is lost.
        op.execute(f"UPDATE {table} SET emails = ARRAY[btrim(email)] WHERE btrim(email) <> ''")
        op.execute(f"UPDATE {table} SET phones = ARRAY[btrim(phone)] WHERE btrim(phone) <> ''")


def downgrade() -> None:
    for table in TABLES:
        # The single columns are kept in sync on every write; this only covers
        # a row whose single value was somehow blank while the list was not.
        op.execute(
            f"UPDATE {table} SET email = emails[1] WHERE email = '' AND cardinality(emails) > 0"
        )
        op.execute(
            f"UPDATE {table} SET phone = phones[1] WHERE phone = '' AND cardinality(phones) > 0"
        )
        op.drop_column(table, "phones")
        op.drop_column(table, "emails")
