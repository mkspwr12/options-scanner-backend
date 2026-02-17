"""Provider metrics service — recording and aggregation."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..repositories.metrics_repository import MetricsRepository

logger = logging.getLogger(__name__)


class MetricsService:
    """Record, aggregate, and query provider metrics."""

    def __init__(self, repo: MetricsRepository | None = None) -> None:
        self._repo = repo or MetricsRepository()

    def record(
        self,
        provider_id: str,
        endpoint: str,
        latency_ms: int,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """Record a single provider call metric."""
        row = {
            "id": f"met-{uuid.uuid4().hex[:12]}",
            "provider_id": provider_id,
            "endpoint": endpoint,
            "latency_ms": latency_ms,
            "success": 1 if success else 0,
            "error_message": error_message,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._repo.record(row)
        except Exception:
            logger.warning("Failed to record metric for %s", provider_id)

    def get_metrics(
        self,
        provider_id: str,
        time_range: str = "day",
    ) -> dict[str, Any]:
        """Get aggregated metrics for a provider."""
        agg = self._repo.get_aggregated(provider_id, time_range=time_range)
        return {
            "providerId": provider_id,
            "timeRange": time_range,
            "totalCalls": agg.get("totalCalls", 0),
            "successCount": agg.get("successCount", 0),
            "errorCount": agg.get("errorCount", 0),
            "avgLatencyMs": round(agg.get("avgLatencyMs", 0), 1),
            "errorRate": round(agg.get("errorRatePercent", 0) / 100, 4) if agg.get("errorRatePercent") else 0.0,
        }

    def get_top_errors(
        self,
        provider_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return the most frequent errors for a provider."""
        return self._repo.get_top_errors(provider_id, limit=limit)

    def get_all_providers_summary(self) -> list[dict[str, Any]]:
        """Return aggregated metrics for every provider."""
        return self._repo.get_all_providers_summary()
