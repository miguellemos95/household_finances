import asyncio
from unittest.mock import MagicMock

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app


def make_app(engine: Engine) -> FastAPI:
    settings = Settings(_env_file=None)
    return create_app(settings=settings, engine=engine)


def get(app: FastAPI, path: str):
    async def send_request():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(send_request())


def test_live_endpoint_does_not_depend_on_database() -> None:
    engine = MagicMock(spec=Engine)
    app = make_app(engine)

    response = get(app, "/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    engine.connect.assert_not_called()


def test_ready_endpoint_checks_database_connection() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = make_app(engine)

    response = get(app, "/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
    engine.dispose()


def test_ready_endpoint_hides_database_error_details() -> None:
    engine = MagicMock(spec=Engine)
    engine.connect.side_effect = SQLAlchemyError("private connection detail")
    app = make_app(engine)

    response = get(app, "/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "database_unavailable",
            "message": "Database is unavailable.",
        }
    }
    assert "private connection detail" not in response.text


def test_clean_database_can_be_initialized_by_migrations(
    tmp_path,
    monkeypatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'household.db').as_posix()}"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    config = Config("alembic.ini")

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert inspect(connection).has_table("alembic_version")
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    engine.dispose()

    assert revision == "0001_initial"
