"""Add the household ledger tables and workbook reference data."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_ledger"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_MEMBER_NAMES = ("Azul", "Pinketa")
WORKBOOK_CATEGORIES = (
    ("Bills", ("Water", "Electricity", "Heating", "Home Internet", "Phone Plan")),
    ("Groceries", ()),
    ("Beauty", ("Hairdresser", "Face", "Body", "Hair")),
    ("Transports", ("Bus", "Spark", "Bolt/Uber")),
    ("Eat out", ("Restaurants", "Cafe")),
    ("Clothes", ()),
)


def upgrade() -> None:
    members = op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
    )
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    subcategories = op.create_table(
        "subcategories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("category_id", "name", name="uq_subcategories_category_name"),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id"), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
    )
    op.create_index("ix_expenses_transaction_date", "expenses", ["transaction_date"])
    op.create_table(
        "incomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("member_id", "month", name="uq_incomes_member_month"),
        sa.CheckConstraint("amount > 0", name="ck_incomes_amount_positive"),
    )

    # Rows are inserted one at a time so identifiers follow the listed order.
    op.bulk_insert(
        members,
        [{"name": name} for name in DEFAULT_MEMBER_NAMES],
        multiinsert=False,
    )
    op.bulk_insert(
        categories,
        [
            {"name": name, "position": position}
            for position, (name, _) in enumerate(WORKBOOK_CATEGORIES, start=1)
        ],
        multiinsert=False,
    )
    for category_name, subcategory_names in WORKBOOK_CATEGORIES:
        for position, subcategory_name in enumerate(subcategory_names, start=1):
            op.execute(
                subcategories.insert().from_select(
                    ["category_id", "name", "position"],
                    sa.select(
                        categories.c.id,
                        sa.literal(subcategory_name),
                        sa.literal(position),
                    ).where(categories.c.name == category_name),
                )
            )


def downgrade() -> None:
    op.drop_table("incomes")
    op.drop_index("ix_expenses_transaction_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("subcategories")
    op.drop_table("categories")
    op.drop_table("members")
