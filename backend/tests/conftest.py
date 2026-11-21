import os
from collections.abc import Callable, Iterator
from datetime import date
from functools import partial

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import Response

from api_client import send
from app.config import Settings
from app.ledger_router import get_today
from app.main import create_app

TODAY = date(2025, 12, 15)


@pytest.fixture
def alembic_config() -> Config:
    return Config("alembic.ini")


@pytest.fixture
def migrated_database_url(tmp_path, monkeypatch, alembic_config: Config) -> Iterator[str]:
    """Migrate a throwaway database; TEST_DATABASE_URL selects a dedicated PostgreSQL one."""
    database_url = os.environ.get("TEST_DATABASE_URL") or (
        f"sqlite+pysqlite:///{(tmp_path / 'ledger.db').as_posix()}"
    )
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    command.upgrade(alembic_config, "head")
    yield database_url
    command.downgrade(alembic_config, "base")


@pytest.fixture
def ledger_app(migrated_database_url: str) -> Iterator[FastAPI]:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_today] = lambda: TODAY
    yield app
    app.state.database_engine.dispose()


@pytest.fixture
def api(ledger_app: FastAPI) -> Callable[..., Response]:
    return partial(send, ledger_app)
