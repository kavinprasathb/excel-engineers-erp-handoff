"""three offer layouts: pump, spares, technical

Every offer the client sends is one of three layouts: a pump offer (a
datasheet and price line per pump), a spares & service offer (tables of
parts per pump model) or the technical sheet (pumps side by side). The old
"standard" item list becomes the pump offer, or the spares offer for a
spares-type quotation, so nothing already saved changes content; "technical"
stays.

Item lines gain the spares columns (part no, MOC, delivery) and the pump
offer's scope of supply; the quotation keeps which optional columns print,
and the technical sheet's price label ("Pump with accessories (without
motor) Unit Price"), which says what the price covers.

Revision ID: a9e4c7b2d8f1
Revises: f3b7d1a9c5e2
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a9e4c7b2d8f1"
down_revision: str | None = "f3b7d1a9c5e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotations",
        sa.Column(
            "print_columns",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("""'["moc", "unit"]'::jsonb"""),
            nullable=False,
        ),
    )
    op.add_column(
        "quotations",
        sa.Column("price_label", sa.String(length=150), server_default="", nullable=False),
    )
    op.alter_column("quotations", "format", server_default="pump")
    op.execute(
        "UPDATE quotations SET format = CASE WHEN type = 'spares' THEN 'spares' ELSE 'pump' END "
        "WHERE format = 'standard'"
    )
    for name, length in (("part_no", 60), ("moc", 60), ("delivery", 60)):
        op.add_column(
            "quotation_lines",
            sa.Column(name, sa.String(length=length), server_default="", nullable=False),
        )
    op.add_column(
        "quotation_lines", sa.Column("supply_scope", sa.Text(), server_default="", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("quotation_lines", "supply_scope")
    for name in ("delivery", "moc", "part_no"):
        op.drop_column("quotation_lines", name)
    op.execute("UPDATE quotations SET format = 'standard' WHERE format IN ('pump', 'spares')")
    op.alter_column("quotations", "format", server_default="standard")
    op.drop_column("quotations", "price_label")
    op.drop_column("quotations", "print_columns")
