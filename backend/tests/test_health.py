from unittest.mock import MagicMock

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from api_client import send
from app.config import Settings
from app.main import create_app


def make_app(engine: Engine) -> FastAPI:
    settings = Settings(_env_file=None)
    return create_app(settings=settings, engine=engine)


def get(app: FastAPI, path: str):
    return send(app, "GET", path)


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
