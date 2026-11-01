"""quotation format 2

The technical offer: a format flag on the quote, a specs table for its
label/value rows, note-or-product kind and a unit label on lines, and the
default spec rows on app_settings (a copy of DEFAULT_QUOTATION_SPECS on the
day this ran; a migration never imports application code).

Revision ID: f5e4e26214ac
Revises: 9451e2b4f103
Create Date: 2026-09-19 15:08:15.925991
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f5e4e26214ac"
down_revision: str | None = "9451e2b4f103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotation_specs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotations.id"],
            name=op.f("fk_quotation_specs_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_specs")),
        sa.UniqueConstraint("quotation_id", "position", name="uq_quotation_specs_position"),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "quotation_spec_defaults",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "quotation_lines",
        sa.Column("kind", sa.String(length=10), server_default="product", nullable=False),
    )
    op.add_column(
        "quotation_lines",
        sa.Column("unit_label", sa.String(length=30), server_default="Each", nullable=False),
    )
    op.add_column(
        "quotations", sa.Column("format", sa.String(length=2), server_default="1", nullable=False)
    )
    op.execute(
        sa.text(
            "UPDATE app_settings SET quotation_spec_defaults = CAST(:v AS jsonb) WHERE id = 1"
        ).bindparams(
            v='[{"label": "Pump Model", "value": ""}, {"label": "Liquid Handled", "value": ""}, {"label": "Capacity (Cub.M/hr)", "value": ""}, {"label": "Total Head (Mtrs)", "value": ""}, {"label": "Shaft Seal", "value": ""}, {"label": "Recommended Motor (kW)", "value": ""}]'
        )
    )


def downgrade() -> None:
    op.drop_column("quotations", "format")
    op.drop_column("quotation_lines", "unit_label")
    op.drop_column("quotation_lines", "kind")
    op.drop_column("app_settings", "quotation_spec_defaults")
    op.drop_table("quotation_specs")
