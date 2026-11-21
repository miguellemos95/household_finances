"""Mark the existing bill category independently of its display name."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0005_bill_category"
down_revision: Union[str, None] = "0004_bills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        # Offline SQL cannot inspect query results while it is being generated.
        op.execute(
            "CREATE TEMPORARY TABLE migration_0005_bill_category_check "
            "(matches INTEGER NOT NULL CHECK (matches = 1))"
        )
        op.execute(
            "INSERT INTO migration_0005_bill_category_check "
            "SELECT COUNT(*) FROM categories WHERE name = 'Bills'"
        )
        op.execute("DROP TABLE migration_0005_bill_category_check")
    else:
        count = op.get_bind().scalar(
            sa.text("SELECT COUNT(*) FROM categories WHERE name = 'Bills'")
        )
        if count != 1:
            raise RuntimeError("Cannot migrate: the existing Bills category is missing.")

    op.add_column(
        "categories",
        sa.Column("is_bill_category", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE categories SET is_bill_category = true WHERE name = 'Bills'")
    op.create_index(
        "uq_categories_one_bill_category",
        "categories",
        ["is_bill_category"],
        unique=True,
        postgresql_where=sa.text("is_bill_category"),
        sqlite_where=sa.text("is_bill_category"),
    )


def downgrade() -> None:
    op.drop_index("uq_categories_one_bill_category", table_name="categories")
    op.drop_column("categories", "is_bill_category")
