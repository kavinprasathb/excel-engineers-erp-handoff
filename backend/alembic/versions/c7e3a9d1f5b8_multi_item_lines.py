"""multi-item quotation lines

A quotation line may hold several inventory items (a pump set: pump, base
frame, coupling), each with its quantity per unit of the line. Accepting it
makes one order line per item, so stock is held and delivered per item; the
order line remembers which quotation line it came from, the set's
description, and (on the set's first item) the set's value.

Existing order lines came one-to-one from quotation lines, so their source
is their position.

Revision ID: c7e3a9d1f5b8
Revises: b5d9f2a7c4e1
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c7e3a9d1f5b8"
down_revision: str | None = "b5d9f2a7c4e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotation_lines",
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("order_lines", sa.Column("source_position", sa.Integer(), nullable=True))
    op.add_column(
        "order_lines",
        sa.Column("set_description", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("order_lines", sa.Column("amount_paise", sa.BigInteger(), nullable=True))
    op.execute("UPDATE order_lines SET source_position = position")


def downgrade() -> None:
    op.drop_column("order_lines", "amount_paise")
    op.drop_column("order_lines", "set_description")
    op.drop_column("order_lines", "source_position")
    op.drop_column("quotation_lines", "components")
