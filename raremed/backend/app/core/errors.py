"""One error envelope for every API failure."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx

logger = logging.getLogger("raremed.errors")


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id_ctx.get(),
    }
    if details:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message))

    @app.exception_handler(HTTPException)
    async def handle_fastapi_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for item in exc.errors():
            location = [str(part) for part in item.get("loc", []) if part != "body"]
            details.append({"location": location, "message": item.get("msg", "Invalid value.")})
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "The request is not valid.", details),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.warning("database request failed", extra={"error_type": exc.__class__.__name__})
        return JSONResponse(
            status_code=503,
            content=error_body(
                "database_unavailable",
                "The workspace database is not available. Conversations cannot be saved right now.",
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error", extra={"error_type": exc.__class__.__name__})
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "RareMed AI hit an unexpected error."),
        )
