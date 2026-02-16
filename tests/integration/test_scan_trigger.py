"""Integration tests for the scan trigger endpoint and MockProvider-based scan."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_scan_service, get_watchlist_service
from app.main import app
from app.providers.mock_provider import MockProvider
from app.repositories.scan_repository import ScanRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.scan_service import ScanService
from app.services.watchlist_service import WatchlistService


@pytest.fixture()
def mock_scan_repo_no_results() -> MagicMock:
    repo = MagicMock(spec=ScanRepository)
    repo.get_latest.return_value = []
    repo.save_results.return_value = None
    return repo


@pytest.fixture()
def mock_wl_repo() -> MagicMock:
    repo = MagicMock(spec=WatchlistRepository)
    repo.get_all_symbols.return_value = ["META", "SPY"]
    return repo


@pytest.fixture()
def trigger_client(
    mock_scan_repo_no_results: MagicMock,
    mock_wl_repo: MagicMock,
) -> TestClient:
    """TestClient with MockProvider wired into the scan service."""

    def _scan_svc() -> ScanService:
        return ScanService(
            repo=mock_scan_repo_no_results,
            provider=MockProvider(),
        )

    def _wl_svc() -> WatchlistService:
        return WatchlistService(repo=mock_wl_repo)

    app.dependency_overrides[get_scan_service] = _scan_svc
    app.dependency_overrides[get_watchlist_service] = _wl_svc

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestScanTrigger:
    """Integration tests for POST /api/scan/trigger."""

    def test_trigger_no_provider(self, client: TestClient) -> None:
        """Default conftest has no provider → returns 'no provider' message."""
        resp = client.post("/api/scan/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["source"] == "none"
        assert data["resultsCount"] == 0

    def test_trigger_with_mock_provider(self, trigger_client: TestClient) -> None:
        resp = trigger_client.post("/api/scan/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["source"] == "live"
        assert data["resultsCount"] > 0
        assert "scanTimestamp" in data

    def test_trigger_persists_results(
        self,
        mock_scan_repo_no_results: MagicMock,
        mock_wl_repo: MagicMock,
    ) -> None:
        """Verify scan results are saved to the repository."""

        def _scan_svc() -> ScanService:
            return ScanService(
                repo=mock_scan_repo_no_results,
                provider=MockProvider(),
            )

        def _wl_svc() -> WatchlistService:
            return WatchlistService(repo=mock_wl_repo)

        app.dependency_overrides[get_scan_service] = _scan_svc
        app.dependency_overrides[get_watchlist_service] = _wl_svc

        try:
            client = TestClient(app)
            client.post("/api/scan/trigger")
            mock_scan_repo_no_results.save_results.assert_called_once()
        finally:
            app.dependency_overrides.clear()


class TestScanServiceRunScan:
    """Unit tests for ScanService.run_scan() with MockProvider."""

    def test_run_scan_returns_results(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.save_results.return_value = None
        svc = ScanService(repo=repo, provider=MockProvider())
        result = svc.run_scan(["META"])
        assert result["status"] == "ok"
        assert result["resultsCount"] > 0

    def test_run_scan_no_symbols(self) -> None:
        svc = ScanService(provider=MockProvider())
        result = svc.run_scan([])
        assert result["resultsCount"] == 0

    def test_run_scan_none_symbols(self) -> None:
        svc = ScanService(provider=MockProvider())
        result = svc.run_scan(None)
        assert result["resultsCount"] == 0

    def test_run_scan_multiple_symbols(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.save_results.return_value = None
        svc = ScanService(repo=repo, provider=MockProvider())
        result = svc.run_scan(["META", "SPY", "AAPL"])
        # 10 contracts per symbol × 3 symbols = 30
        assert result["resultsCount"] == 30

    def test_run_scan_sorted_by_confidence(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.save_results.return_value = None
        svc = ScanService(repo=repo, provider=MockProvider())
        result = svc.run_scan(["META"])

        # Verify results were persisted in order
        saved = repo.save_results.call_args[0][0]
        scores = [o["confidenceScore"] for o in saved]
        assert scores == sorted(scores, reverse=True)
