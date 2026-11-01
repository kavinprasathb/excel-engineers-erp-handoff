"""revised quotations alongside negotiations

Each quotation version now records which revised quotation (R) it belongs
to and which negotiation round (N) of it, so a number can go
ESQSP-26-7 → -R1 → -R2 → -R2N1. Every existing version was a negotiation
of the original, so it becomes rev_no 0, neg_no = its revision: its number
(ESQSP-26-7N2) is unchanged.

Revision ID: b5d9f2a7c4e1
Revises: a3c8e1f5b7d2
"""

import sqlalchemy as sa

from alembic import op

revision: str = "b5d9f2a7c4e1"
down_revision: str | None = "a3c8e1f5b7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotations", sa.Column("rev_no", sa.Integer(), server_default=sa.text("0"), nullable=False)
    )
    op.add_column(
        "quotations", sa.Column("neg_no", sa.Integer(), server_default=sa.text("0"), nullable=False)
    )
    op.execute("UPDATE quotations SET neg_no = revision")
    op.create_unique_constraint(
        "uq_quotations_version_refs", "quotations", ["type", "year", "seq", "rev_no", "neg_no"]
    )
    op.create_check_constraint(
        op.f("ck_quotations_version_refs_non_negative"),
        "quotations",
        "rev_no >= 0 AND neg_no >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_quotations_version_refs_non_negative"), "quotations", type_="check")
    op.drop_constraint("uq_quotations_version_refs", "quotations", type_="unique")
    op.drop_column("quotations", "neg_no")
    op.drop_column("quotations", "rev_no")
