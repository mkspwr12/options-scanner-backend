"""In-memory sliding-window rate limiter middleware.

Limits requests per client (by IP) to avoid abuse.  When ``rate_limit``
is 0 or negative, rate limiting is disabled.

Uses a simple dict of deques — acceptable for single-process deployments.
For multi-process, swap to Redis-based counting.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter.

    Args:
        app: ASGI application.
        max_requests: Maximum requests allowed per *window_seconds*.
        window_seconds: Length of the sliding window.
    """

    def __init__(
        self,
        app: object,  # noqa: ANN001
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._enabled = max_requests > 0
        if self._enabled:
            logger.info(
                "Rate limiting enabled: %d req / %ds window",
                max_requests, window_seconds,
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[type-arg]
        if not self._enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        # Prune expired entries
        window = self._requests[client_ip]
        while window and window[0] <= now - self._window:
            window.popleft()

        if len(window) >= self._max_requests:
            retry_after = int(self._window - (now - window[0])) + 1
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "detail": "Rate limit exceeded. Try again later.",
                    "code": 429,
                },
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)
