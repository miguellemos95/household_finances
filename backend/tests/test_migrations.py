from io import StringIO
import sqlite3

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def test_clean_database_is_migrated_to_the_latest_revision(
    migrated_database_url: str,
    alembic_config: Config,
) -> None:
    engine = create_engine(migrated_database_url)
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    engine.dispose()

    assert revision == ScriptDirectory.from_config(alembic_config).get_current_head()
    assert {
        "members",
        "categories",
        "subcategories",
        "expenses",
        "incomes",
        "category_budgets",
        "bills",
        "bill_occurrences",
    } <= tables


def test_models_do_not_drift_from_migrations(
    migrated_database_url: str,
    alembic_config: Config,
) -> None:
    command.check(alembic_config)


def test_bill_category_migration_preserves_data_and_enforces_uniqueness(
    tmp_path, monkeypatch, alembic_config: Config
) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'upgrade.db').as_posix()}"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    command.upgrade(alembic_config, "0004_bills")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO expenses (transaction_date, amount, category_id, subcategory_id) "
            "SELECT '2025-11-03', 30.33, id, NULL FROM categories WHERE name = 'Bills'"
        )
        original_expenses = connection.exec_driver_sql(
            "SELECT amount, category_id, subcategory_id FROM expenses"
        ).all()

    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        categories = connection.exec_driver_sql(
            "SELECT name, is_bill_category FROM categories ORDER BY position"
        ).all()
        expenses = connection.exec_driver_sql(
            "SELECT amount, category_id, subcategory_id FROM expenses"
        ).all()
    assert [name for name, flagged in categories if flagged] == ["Bills"]
    assert len(original_expenses) == 1
    assert expenses == original_expenses

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE categories SET is_bill_category = true WHERE name = 'Groceries'"
            )

    command.downgrade(alembic_config, "0004_bills")
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT amount, category_id, subcategory_id FROM expenses"
        ).all() == expenses
    engine.dispose()


def test_bill_category_migration_reports_missing_seed_before_altering_schema(
    tmp_path, monkeypatch, alembic_config: Config
) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'missing.db').as_posix()}"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    command.upgrade(alembic_config, "0004_bills")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "DELETE FROM subcategories WHERE category_id = "
            "(SELECT id FROM categories WHERE name = 'Bills')"
        )
        connection.exec_driver_sql("DELETE FROM categories WHERE name = 'Bills'")
    with pytest.raises(RuntimeError, match="existing Bills category is missing"):
        command.upgrade(alembic_config, "head")
    assert "is_bill_category" not in {
        column["name"] for column in inspect(engine).get_columns("categories")
    }
    engine.dispose()


@pytest.mark.parametrize("missing", [False, True])
def test_offline_bill_category_migration_checks_for_missing_seed(
    tmp_path, monkeypatch, alembic_config: Config, missing: bool
) -> None:
    database_path = tmp_path / "offline.db"
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite+pysqlite:///{database_path.as_posix()}")
    command.upgrade(alembic_config, "0004_bills")
    if missing:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "DELETE FROM subcategories WHERE category_id = "
                "(SELECT id FROM categories WHERE name = 'Bills')"
            )
            connection.execute("DELETE FROM categories WHERE name = 'Bills'")

    output = StringIO()
    offline_config = Config("alembic.ini", output_buffer=output)
    command.upgrade(offline_config, "0004_bills:head", sql=True)
    with sqlite3.connect(database_path) as connection:
        if not missing:
            connection.executescript(output.getvalue())
            assert connection.execute(
                "SELECT name FROM categories WHERE is_bill_category"
            ).fetchall() == [("Bills",)]
        else:
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                connection.executescript(output.getvalue())
            assert "is_bill_category" not in {
                column[1] for column in connection.execute("PRAGMA table_info(categories)")
            }
