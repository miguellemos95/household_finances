"""Add monthly category budgets."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_category_budgets"
down_revision: Union[str, None] = "0002_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "category_budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("category_id", "month", name="uq_category_budgets_category_month"),
        sa.CheckConstraint("amount > 0", name="ck_category_budgets_amount_positive"),
    )


def downgrade() -> None:
    op.drop_table("category_budgets")
