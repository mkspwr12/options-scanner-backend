"""Custom exceptions and global error handler for the Options Scanner API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 500, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    """Resource not found (404)."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} '{identifier}' not found",
            status_code=404,
        )


class DatabaseError(AppError):
    """Database connection or query error (503)."""

    def __init__(self, message: str = "Database unavailable") -> None:
        super().__init__(message=message, status_code=503)


class ConflictError(AppError):
    """Duplicate / conflict error (409)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=409)


# ---------------------------------------------------------------------------
# Global Error Handlers — register on the FastAPI app
# ---------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    """Attach consistent error handlers to the FastAPI application."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError: %s (status=%d)", exc.message, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "detail": exc.message,
                "code": exc.status_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        messages = []
        for err in errors:
            loc = " → ".join(str(l) for l in err.get("loc", []))
            messages.append(f"{loc}: {err.get('msg', 'invalid')}")
        detail = "; ".join(messages)
        logger.warning("Validation error: %s", detail)
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "detail": detail,
                "code": 422,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "detail": "Internal server error",
                "code": 500,
            },
        )
