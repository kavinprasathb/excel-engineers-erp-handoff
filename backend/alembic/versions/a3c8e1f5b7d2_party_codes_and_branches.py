"""customer/supplier codes and branches

Customers and suppliers get a read-only code (CUST-0001, SUP-0001) issued by
the database from a sequence, so a number is never reused; existing rows are
numbered in id order. Each may have branches (CUST-0001-BR01...) with their
own GST number and address, which a quotation or a purchase order may name.

Nothing existing is deleted or rewritten except the new codes.

Revision ID: a3c8e1f5b7d2
Revises: e7b2c9d4a1f6
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a3c8e1f5b7d2"
down_revision: str | None = "e7b2c9d4a1f6"
branch_labels = None
depends_on = None

# (table, prefix, sequence, branch table, branch FK column, has contact fields)
PARTIES = (
    ("customers", "CUST", "customer_code_seq", "customer_branches", "customer_id", True),
    ("suppliers", "SUP", "supplier_code_seq", "supplier_branches", "supplier_id", False),
)


def upgrade() -> None:
    # CUST-0001 ... CUST-9999, then CUST-10000: never truncated, never reused.
    op.execute(
        """
        CREATE FUNCTION party_code(prefix text, n bigint) RETURNS text
        LANGUAGE sql IMMUTABLE AS $$
            SELECT prefix || '-' || CASE WHEN n < 10000 THEN lpad(n::text, 4, '0')
                                         ELSE n::text END
        $$
        """
    )
    for table, prefix, seq, branch_table, fk, contacts in PARTIES:
        op.execute(f"CREATE SEQUENCE {seq}")
        op.add_column(table, sa.Column("code", sa.String(length=20), nullable=True))
        op.add_column(
            table,
            sa.Column("branch_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        )
        # Existing records, oldest first, then the sequence carries on from there.
        op.execute(
            f"""
            UPDATE {table} t SET code = party_code('{prefix}', n.rn)
            FROM (SELECT id, row_number() OVER (ORDER BY id) AS rn FROM {table}) n
            WHERE n.id = t.id
            """
        )
        op.execute(
            f"SELECT setval('{seq}', GREATEST((SELECT count(*) FROM {table}), 1), "
            f"(SELECT count(*) FROM {table}) > 0)"
        )
        op.alter_column(
            table,
            "code",
            nullable=False,
            server_default=sa.text(f"party_code('{prefix}'::text, nextval('{seq}'::regclass))"),
        )
        op.execute(f"ALTER SEQUENCE {seq} OWNED BY {table}.code")
        op.create_unique_constraint(f"uq_{table}_code", table, ["code"])

        extra = (
            [
                sa.Column(
                    "contact_person", sa.String(length=150), server_default="", nullable=False
                ),
                sa.Column("designation", sa.String(length=100), server_default="", nullable=False),
            ]
            if contacts
            else []
        )
        op.create_table(
            branch_table,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(fk, sa.Integer(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=30), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("gstin", sa.String(length=20), server_default="", nullable=False),
            *extra,
            sa.Column(
                "emails",
                postgresql.ARRAY(sa.String(length=255)),
                server_default="{}",
                nullable=False,
            ),
            sa.Column(
                "phones",
                postgresql.ARRAY(sa.String(length=30)),
                server_default="{}",
                nullable=False,
            ),
            sa.Column("address_line1", sa.String(length=255), server_default="", nullable=False),
            sa.Column("city", sa.String(length=100), server_default="", nullable=False),
            sa.Column("state", sa.String(length=100), server_default="", nullable=False),
            sa.Column("pincode", sa.String(length=10), server_default="", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                [fk],
                [f"{table}.id"],
                name=op.f(f"fk_{branch_table}_{fk}_{table}"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{branch_table}")),
            sa.UniqueConstraint("code", name=f"uq_{branch_table}_code"),
            sa.UniqueConstraint(fk, "seq", name=f"uq_{branch_table}_{fk}_seq"),
        )
        op.create_index(f"ix_{branch_table}_{fk}", branch_table, [fk])

    op.add_column("quotations", sa.Column("customer_branch_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_quotations_customer_branch_id_customer_branches"),
        "quotations",
        "customer_branches",
        ["customer_branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("purchase_orders", sa.Column("supplier_branch_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_purchase_orders_supplier_branch_id_supplier_branches"),
        "purchase_orders",
        "supplier_branches",
        ["supplier_branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_purchase_orders_supplier_branch_id_supplier_branches"),
        "purchase_orders",
        type_="foreignkey",
    )
    op.drop_column("purchase_orders", "supplier_branch_id")
    op.drop_constraint(
        op.f("fk_quotations_customer_branch_id_customer_branches"), "quotations", type_="foreignkey"
    )
    op.drop_column("quotations", "customer_branch_id")
    for table, _prefix, _seq, branch_table, fk, _contacts in PARTIES:
        op.drop_index(f"ix_{branch_table}_{fk}", table_name=branch_table)
        op.drop_table(branch_table)
        op.drop_constraint(f"uq_{table}_code", table, type_="unique")
        # Dropping the column drops the sequence it owns.
        op.drop_column(table, "code")
        op.drop_column(table, "branch_seq")
    op.execute("DROP FUNCTION party_code(text, bigint)")
