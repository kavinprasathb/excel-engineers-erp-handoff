"""technical offer format

A quotation may be printed as the technical offer sheet instead of the item
list: one column per item, one row per technical parameter. The quotation
keeps the rows ([{section, label}]) and the scope of supply; each line keeps
its column heading (service) and one value per row. Existing quotations are
the standard format and have none of these.

Revision ID: d4a8c2e6f1b9
Revises: c7e3a9d1f5b8
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4a8c2e6f1b9"
down_revision: str | None = "c7e3a9d1f5b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotations",
        sa.Column("format", sa.String(length=20), server_default="standard", nullable=False),
    )
    op.add_column(
        "quotations",
        sa.Column(
            "tech_rows",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("quotations", sa.Column("scope", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "quotation_lines",
        sa.Column("service", sa.String(length=150), server_default="", nullable=False),
    )
    op.add_column(
        "quotation_lines",
        sa.Column(
            "tech_values",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("quotation_lines", "tech_values")
    op.drop_column("quotation_lines", "service")
    op.drop_column("quotations", "scope")
    op.drop_column("quotations", "tech_rows")
    op.drop_column("quotations", "format")
