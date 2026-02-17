"""Metrics repository — SQL data access for the provider_metrics table."""
from __future__ import annotations

import logging
from typing import Any

from ..db import get_connection
from ..exceptions import DatabaseError

logger = logging.getLogger(__name__)

_TIME_RANGE_SQL = {
    "hour": "recorded_at >= DATEADD(HOUR, -1, GETUTCDATE())",
    "day": "recorded_at >= DATEADD(DAY, -1, GETUTCDATE())",
    "week": "recorded_at >= DATEADD(WEEK, -1, GETUTCDATE())",
    "month": "recorded_at >= DATEADD(MONTH, -1, GETUTCDATE())",
}


class MetricsRepository:
    """Encapsulates all SQL operations on the ``provider_metrics`` table."""

    def record(self, data: dict[str, Any] | None = None, /, provider_id: str = "",
               latency_ms: int = 0, success: bool = True,
               error: str | None = None, endpoint: str | None = None) -> None:
        # Accept either a dict or keyword args
        if data is not None and isinstance(data, dict):
            provider_id = data.get("provider_id", provider_id)
            latency_ms = data.get("latency_ms", latency_ms)
            success = data.get("success", success)
            if isinstance(success, int):
                success = bool(success)
            error = data.get("error_message") or data.get("error", error)
            endpoint = data.get("endpoint", endpoint)
            row_id = data.get("id") or f"met-{__import__('uuid').uuid4().hex[:12]}"
        else:
            row_id = f"met-{__import__('uuid').uuid4().hex[:12]}"
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO provider_metrics
                        (id, provider_id, latency_ms, success, error_message, endpoint)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (row_id, provider_id, latency_ms, 1 if success else 0, error, endpoint),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to record metric: %s", exc)

    def get_aggregated(self, provider_id: str, time_range: str = "day") -> dict[str, Any]:
        time_filter = _TIME_RANGE_SQL.get(time_range, _TIME_RANGE_SQL["day"])
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_calls,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
                        AVG(latency_ms) as avg_latency_ms,
                        MAX(recorded_at) as last_call_at
                    FROM provider_metrics
                    WHERE provider_id = ? AND {time_filter}
                    """,
                    (provider_id,),
                )
                row = cursor.fetchone()
                if row is None or row[0] == 0:
                    return {
                        "totalCalls": 0, "successCount": 0, "errorCount": 0,
                        "avgLatencyMs": 0, "errorRatePercent": 0.0, "lastCallAt": None,
                    }

                total = row[0]
                success_count = row[1] or 0
                error_count = row[2] or 0
                avg_latency = int(row[3] or 0)
                last_call = str(row[4]) if row[4] else None

                return {
                    "totalCalls": total,
                    "successCount": success_count,
                    "errorCount": error_count,
                    "avgLatencyMs": avg_latency,
                    "errorRatePercent": round((error_count / total) * 100, 2) if total else 0.0,
                    "lastCallAt": last_call,
                }
        except Exception as exc:
            logger.exception("Failed to get metrics for %s", provider_id)
            raise DatabaseError(f"Failed to get metrics: {exc}") from exc

    def get_top_errors(self, provider_id: str, time_range: str = "day",
                       limit: int = 5) -> list[dict[str, Any]]:
        time_filter = _TIME_RANGE_SQL.get(time_range, _TIME_RANGE_SQL["day"])
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT TOP (?) error_message, COUNT(*) as cnt
                    FROM provider_metrics
                    WHERE provider_id = ? AND success = 0
                      AND error_message IS NOT NULL AND {time_filter}
                    GROUP BY error_message
                    ORDER BY cnt DESC
                    """,
                    (limit, provider_id),
                )
                return [{"error": row[0], "count": row[1]} for row in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to get top errors for %s", provider_id)
            raise DatabaseError(f"Failed to get top errors: {exc}") from exc

    def get_all_providers_summary(self, time_range: str = "day") -> list[dict[str, Any]]:
        time_filter = _TIME_RANGE_SQL.get(time_range, _TIME_RANGE_SQL["day"])
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT
                        provider_id,
                        COUNT(*) as total_calls,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
                        AVG(latency_ms) as avg_latency_ms
                    FROM provider_metrics
                    WHERE {time_filter}
                    GROUP BY provider_id
                    ORDER BY total_calls DESC
                    """,
                )
                results = []
                for row in cursor.fetchall():
                    total = row[1]
                    errors = row[2] or 0
                    results.append({
                        "providerId": row[0],
                        "totalCalls": total,
                        "errorRatePercent": round((errors / total) * 100, 2) if total else 0,
                        "avgLatencyMs": int(row[3] or 0),
                    })
                return results
        except Exception as exc:
            logger.exception("Failed to get provider metrics summary")
            raise DatabaseError(f"Failed to get metrics summary: {exc}") from exc
