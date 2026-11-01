"""one quotation format; technical deviation per item line

The two quotation formats become one. The quote-level technical block
(quotation_specs) is replaced by a technical deviation on each item line:
ordered [{label, value}] rows, printed under the item when filled. The
format flag goes. Existing quote-level rows are kept: each quotation's rows
move, in order, onto its first item line, so they still print on the letter
(under that item) and nothing already sent is lost.

Revision ID: e7b2c9d4a1f6
Revises: d8a3f5c1e6b2
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e7b2c9d4a1f6"
down_revision: str | None = "d8a3f5c1e6b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotation_lines",
        sa.Column(
            "deviations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    # Keep what was written: a quotation's rows go to its first item line
    # (a note only if it has no item), in their order.
    op.execute(
        """
        UPDATE quotation_lines ql
        SET deviations = s.rows
        FROM (
            SELECT quotation_id,
                   jsonb_agg(jsonb_build_object('label', label, 'value', value)
                             ORDER BY position) AS rows
            FROM quotation_specs
            WHERE btrim(label) <> ''
            GROUP BY quotation_id
        ) s
        WHERE ql.quotation_id = s.quotation_id
          AND ql.id = (
              SELECT x.id FROM quotation_lines x
              WHERE x.quotation_id = ql.quotation_id
              ORDER BY (x.kind = 'note'), x.position
              LIMIT 1
          )
        """
    )
    op.drop_table("quotation_specs")
    op.drop_column("quotations", "format")


def downgrade() -> None:
    op.add_column(
        "quotations", sa.Column("format", sa.String(length=2), server_default="1", nullable=False)
    )
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
    # Back to quote-level rows: each quotation's first item line's rows.
    op.execute(
        """
        INSERT INTO quotation_specs (quotation_id, position, label, value)
        SELECT ql.quotation_id, d.ord - 1, left(d.row->>'label', 100), coalesce(d.row->>'value', '')
        FROM quotation_lines ql
        CROSS JOIN LATERAL jsonb_array_elements(ql.deviations) WITH ORDINALITY AS d(row, ord)
        WHERE ql.id = (
            SELECT x.id FROM quotation_lines x
            WHERE x.quotation_id = ql.quotation_id
            ORDER BY (x.kind = 'note'), x.position
            LIMIT 1
        )
        """
    )
    op.drop_column("quotation_lines", "deviations")
