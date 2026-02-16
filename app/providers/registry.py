"""Runtime provider registry with ordered failover and rate-limit tracking.

Manages multiple ``MarketDataProvider`` instances, each with its own
``CircuitBreaker``.  Supports priority-based failover and per-provider
rate-limit counters.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .base import MarketDataProvider
from .circuit_breaker import CircuitBreaker
from ..exceptions import ProviderError

logger = logging.getLogger(__name__)


@dataclass
class ProviderEntry:
    """Internal bookkeeping for a single registered provider."""

    config: dict[str, Any]
    provider: MarketDataProvider | None
    circuit_breaker: CircuitBreaker


class ProviderRegistry:
    """Thread-safe* registry of market data providers with failover.

    *Note: thread-safe for single-process async (FastAPI/uvicorn).
    """

    def __init__(self) -> None:
        self._entries: dict[str, ProviderEntry] = {}
        self._rate_counters: dict[str, deque[float]] = defaultdict(deque)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, provider_id: str, config: dict[str, Any]) -> None:
        """Register (or re-register) a provider."""
        provider = self._create_provider(config.get("type", ""))
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=300.0,
            name=provider_id,
        )
        self._entries[provider_id] = ProviderEntry(
            config=config, provider=provider, circuit_breaker=cb,
        )
        logger.info("Registered provider '%s' (type=%s, priority=%s)",
                     provider_id, config.get("type"), config.get("priority"))

    def unregister(self, provider_id: str) -> None:
        self._entries.pop(provider_id, None)
        self._rate_counters.pop(provider_id, None)

    def clear(self) -> None:
        self._entries.clear()
        self._rate_counters.clear()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_provider(self, provider_id: str) -> MarketDataProvider | None:
        """Return the ``MarketDataProvider`` for *provider_id*,
        or ``None`` if not found / unsupported type.
        """
        entry = self._entries.get(provider_id)
        if entry is None or entry.provider is None:
            return None
        return entry.provider

    def get_entry(self, provider_id: str) -> ProviderEntry | None:
        return self._entries.get(provider_id)

    def get_best_provider(self) -> tuple[str, MarketDataProvider]:
        """Return *(provider_id, provider)* for the highest-priority
        enabled provider whose circuit breaker is not OPEN.

        Raises ``RuntimeError`` when no provider is available.
        """
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda item: item[1].config.get("priority", 999),
        )
        for pid, entry in sorted_entries:
            if (
                entry.config.get("enabled", True)
                and entry.provider is not None
                and entry.circuit_breaker.allow_request()
            ):
                return pid, entry.provider

        raise ProviderError("No providers available")

    @property
    def provider_ids(self) -> list[str]:
        return list(self._entries.keys())

    def __len__(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Circuit-breaker delegation
    # ------------------------------------------------------------------

    def record_success(self, provider_id: str) -> None:
        entry = self._entries.get(provider_id)
        if entry:
            entry.circuit_breaker.record_success()

    def record_failure(self, provider_id: str) -> None:
        entry = self._entries.get(provider_id)
        if entry:
            entry.circuit_breaker.record_failure()

    # ------------------------------------------------------------------
    # Rate-limit tracking (in-memory sliding window)
    # ------------------------------------------------------------------

    def record_call(self, provider_id: str) -> None:
        """Record that a call was made to *provider_id*."""
        self._rate_counters[provider_id].append(time.monotonic())

    def get_rate_limit_info(self, provider_id: str) -> dict[str, Any]:
        """Return rate-limit info dict for response headers."""
        entry = self._entries.get(provider_id)
        max_per_hour = 2000
        if entry:
            max_per_hour = entry.config.get("rate_limit_max_per_hour", 2000)

        now = time.monotonic()
        window = self._rate_counters[provider_id]
        while window and window[0] < now - 3600:
            window.popleft()

        remaining = max(0, max_per_hour - len(window))
        reset_seconds = 3600 - int(now % 3600) if window else 3600

        return {
            "limit": max_per_hour,
            "remaining": remaining,
            "reset": reset_seconds,
            "window": "hour",
        }

    def is_rate_limited(self, provider_id: str) -> bool:
        info = self.get_rate_limit_info(provider_id)
        return info["remaining"] <= 0

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def _create_provider(provider_type: str) -> MarketDataProvider | None:
        """Instantiate the correct provider for *provider_type*.

        Returns ``None`` for unsupported types (ALPACA, TRADIER, CUSTOM)
        — the infrastructure is ready but the implementations don't exist yet.
        """
        pt = provider_type.upper()
        if pt in ("YAHOO_FINANCE", "YAHOO"):
            from .yahoo_provider import YahooFinanceProvider
            return YahooFinanceProvider()
        if pt == "MOCK":
            from .mock_provider import MockProvider
            return MockProvider()
        logger.warning("Unsupported provider type '%s' — proxy calls will fail", provider_type)
        return None
