from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

def create_error_response(status_code: int, message: str, detail: str = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "code": status_code,
            "message": message,
            "detail": detail
        },
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return create_error_response(exc.status_code, exc.detail)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = exc.errors()[0].get("msg") if exc.errors() else "Invalid data"
    return create_error_response(422, "Validation Error", str(exc.errors()))

async def db_connection_handler(request: Request, exc: OperationalError):
    logger.error(f"DB Connection Failed: {exc}")
    return create_error_response(503, "Database connection failed. System under maintenance.")

async def db_query_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"SQL Error: {exc}")
    return create_error_response(500, "Database query error.")

async def global_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Error: {exc}", exc_info=True)
    return create_error_response(500, "Internal Server Error", str(exc))

def add_exception_handlers(app):
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(OperationalError, db_connection_handler)
    app.add_exception_handler(SQLAlchemyError, db_query_handler)
    app.add_exception_handler(Exception, global_handler)
