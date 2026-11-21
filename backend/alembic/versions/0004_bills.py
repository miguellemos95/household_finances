"""Add bill tracking."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_bills"
down_revision: Union[str, None] = "0003_category_budgets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recurrence", sa.String(20), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=True),
        sa.Column("default_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id"), nullable=True),
        sa.CheckConstraint(
            "(recurrence = 'one_off' AND due_day IS NULL) OR "
            "(recurrence = 'monthly' AND due_day BETWEEN 1 AND 31)",
            name="ck_bills_recurrence",
        ),
        sa.CheckConstraint("default_amount > 0", name="ck_bills_amount_positive"),
    )
    op.create_table(
        "bill_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("expenses.id"), nullable=True, unique=True),
        sa.UniqueConstraint("bill_id", "due_date", name="uq_bill_occurrences_bill_due"),
        sa.CheckConstraint("amount > 0", name="ck_bill_occurrences_amount_positive"),
        sa.CheckConstraint(
            "paid_amount IS NULL OR paid_amount > 0",
            name="ck_bill_occurrences_paid_amount_positive",
        ),
        sa.CheckConstraint(
            "(status IN ('pending', 'overdue') AND paid_amount IS NULL AND paid_date IS NULL) OR "
            "(status = 'paid' AND paid_amount IS NOT NULL AND paid_date IS NOT NULL)",
            name="ck_bill_occurrences_status",
        ),
    )
    op.create_index("ix_bills_first_due_date", "bills", ["first_due_date"])
    op.create_index("ix_bill_occurrences_due_date", "bill_occurrences", ["due_date"])
    op.create_index("ix_bill_occurrences_paid_date", "bill_occurrences", ["paid_date"])


def downgrade() -> None:
    op.drop_index("ix_bill_occurrences_paid_date", table_name="bill_occurrences")
    op.drop_index("ix_bill_occurrences_due_date", table_name="bill_occurrences")
    op.drop_index("ix_bills_first_due_date", table_name="bills")
    op.drop_table("bill_occurrences")
    op.drop_table("bills")
