"""Simple circuit breaker for external provider calls.

States:
    CLOSED  — requests pass through normally.
    OPEN    — requests are short-circuited (raise ``CircuitOpenError``).
    HALF_OPEN — one probe request is allowed; success → CLOSED, failure → OPEN.
"""
from __future__ import annotations

import logging
import time
from enum import Enum, auto

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and calls are blocked."""


class CircuitBreaker:
    """Lightweight circuit breaker with configurable threshold and timeout."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 300.0,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current state, lazily transitioning OPEN → HALF_OPEN on timeout."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(
                    "Circuit '%s' transitioning OPEN → HALF_OPEN after %.0fs",
                    self.name, elapsed,
                )
                self._state = CircuitState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        """Return *True* if a request should be attempted."""
        return self.state != CircuitState.OPEN

    def record_success(self) -> None:
        """Record a successful call — reset to CLOSED."""
        if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — may trip to OPEN."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            logger.warning(
                "Circuit '%s' OPEN after %d consecutive failures",
                self.name, self._failure_count,
            )
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Force-reset to CLOSED (useful for testing)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
