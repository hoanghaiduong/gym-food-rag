import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import error_response


logger = logging.getLogger(__name__)


def create_error_response(status_code: int, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=error_response(message=message, code=status_code, detail=detail),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return create_error_response(exc.status_code, exc.detail)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return create_error_response(422, "Validation Error", str(exc.errors()))


async def db_connection_handler(request: Request, exc: OperationalError):
    logger.error("DB Connection Failed: %s", exc)
    return create_error_response(503, "Database connection failed. System under maintenance.")


async def db_query_handler(request: Request, exc: SQLAlchemyError):
    logger.error("SQL Error: %s", exc)
    return create_error_response(500, "Database query error.")


async def global_handler(request: Request, exc: Exception):
    logger.error("Unhandled Error: %s", exc, exc_info=True)
    return create_error_response(500, "Internal Server Error", str(exc))


def add_exception_handlers(app):
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(OperationalError, db_connection_handler)
    app.add_exception_handler(SQLAlchemyError, db_query_handler)
    app.add_exception_handler(Exception, global_handler)
