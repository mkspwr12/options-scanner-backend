"""Unit tests for MetricsService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.repositories.metrics_repository import MetricsRepository
from app.services.metrics_service import MetricsService


@pytest.fixture()
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=MetricsRepository)
    repo.record.return_value = None
    repo.get_aggregated.return_value = {
        "total_calls": 100,
        "success_count": 95,
        "error_count": 5,
        "avg_latency": 123.4,
        "error_rate": 0.05,
    }
    repo.get_top_errors.return_value = [
        {"error_message": "timeout", "count": 3},
    ]
    repo.get_all_providers_summary.return_value = [
        {"provider_id": "p1", "total_calls": 50},
    ]
    return repo


@pytest.fixture()
def svc(mock_repo: MagicMock) -> MetricsService:
    return MetricsService(repo=mock_repo)


class TestRecord:
    def test_record_success(self, svc: MetricsService, mock_repo: MagicMock) -> None:
        svc.record("p1", "/options-chain", 120, True)
        mock_repo.record.assert_called_once()

    def test_record_failure_logged(self, svc: MetricsService, mock_repo: MagicMock) -> None:
        mock_repo.record.side_effect = RuntimeError("db down")
        svc.record("p1", "/options-chain", 120, True)  # should not raise


class TestGetMetrics:
    def test_returns_aggregated(self, svc: MetricsService) -> None:
        result = svc.get_metrics("p1", time_range="day")
        assert result["totalCalls"] == 100
        assert result["successCount"] == 95
        assert result["errorCount"] == 5
        assert result["avgLatencyMs"] == 123.4
        assert result["errorRate"] == 0.05
        assert result["timeRange"] == "day"


class TestGetTopErrors:
    def test_returns_errors(self, svc: MetricsService) -> None:
        result = svc.get_top_errors("p1", limit=5)
        assert len(result) == 1
        assert result[0]["error_message"] == "timeout"


class TestGetAllProvidersSummary:
    def test_returns_summary(self, svc: MetricsService) -> None:
        result = svc.get_all_providers_summary()
        assert len(result) == 1
        assert result[0]["provider_id"] == "p1"
