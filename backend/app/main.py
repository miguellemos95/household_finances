from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, text

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.errors import register_error_handlers
from app.ledger_router import router as ledger_router


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Household Finances API", version="0.1.0")
    app.state.database_engine = engine or create_database_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.database_engine)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(ledger_router)

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready(request: Request) -> dict[str, str]:
        with request.app.state.database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"status": "ready", "database": "ok"}

    return app


app = create_app()
