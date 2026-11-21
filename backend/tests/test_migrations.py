from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect


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
