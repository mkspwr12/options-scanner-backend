"""API key authentication middleware.

Protects all ``/api/`` endpoints except health probes.
When ``API_KEY`` is not set, authentication is disabled (open access).
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths that never require authentication
_PUBLIC_PATHS: set[str] = {
    "/",
    "/healthz",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validate ``X-API-Key`` header on protected routes.

    When *api_key* is ``None`` or empty, all requests pass through.
    """

    def __init__(self, app: object, api_key: str | None = None) -> None:  # noqa: ANN001
        super().__init__(app)  # type: ignore[arg-type]
        self._api_key = api_key
        if api_key:
            logger.info("API key authentication enabled")
        else:
            logger.info("API key authentication disabled (no API_KEY set)")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[type-arg]
        # Skip auth when no key is configured
        if not self._api_key:
            return await call_next(request)

        # Public paths are always open
        path = request.url.path.rstrip("/")
        if path in _PUBLIC_PATHS or path == "":
            return await call_next(request)

        # Check header
        provided = request.headers.get("X-API-Key", "")
        if provided != self._api_key:
            logger.warning("Unauthorized request: %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "detail": "Invalid or missing API key",
                    "code": 401,
                },
            )

        return await call_next(request)
