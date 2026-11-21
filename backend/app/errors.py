import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class LedgerError(Exception):
    status_code = 400
    code = "ledger_error"

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class InvalidEntryError(LedgerError):
    status_code = 422
    code = "invalid_input"


class NotFoundError(LedgerError):
    status_code = 404
    code = "not_found"


class ConflictError(LedgerError):
    status_code = 409
    code = "conflict"


def error_response(
    status_code: int,
    code: str,
    message: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    detail: dict[str, object] = {"code": code, "message": message}
    if errors:
        detail["errors"] = errors
    return JSONResponse(status_code=status_code, content={"detail": detail})


def handle_ledger_error(request: Request, error: LedgerError) -> JSONResponse:
    errors = [{"field": error.field, "message": error.message}] if error.field else None
    return error_response(error.status_code, error.code, error.message, errors)


def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(part) for part in issue["loc"][1:]),
            "message": issue["msg"],
        }
        for issue in error.errors()
    ]
    return error_response(
        InvalidEntryError.status_code,
        InvalidEntryError.code,
        "The request contains invalid values.",
        errors,
    )


def handle_database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
    logger.error("Database operation failed.", exc_info=error)
    return error_response(503, "database_unavailable", "Database is unavailable.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LedgerError, handle_ledger_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(SQLAlchemyError, handle_database_error)
