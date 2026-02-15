"""Unit tests for ScanService."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.repositories.scan_repository import ScanRepository
from app.services.scan_service import ScanService


class TestGetOpportunities:
    def test_fallback_to_sample_data(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.get_latest.return_value = []  # empty = no persisted data

        svc = ScanService(repo=repo)
        result = svc.get_opportunities()

        assert result["status"] == "ok"
        assert result["source"] == "sample"
        assert len(result["opportunities"]) >= 1

    def test_db_error_falls_back_gracefully(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.get_latest.side_effect = Exception("DB down")

        svc = ScanService(repo=repo)
        result = svc.get_opportunities()

        assert result["status"] == "ok"
        assert result["source"] == "sample"

    def test_db_results_returned_when_available(self) -> None:
        fake_opp = MagicMock()
        repo = MagicMock(spec=ScanRepository)
        repo.get_latest.return_value = [fake_opp]

        svc = ScanService(repo=repo)
        result = svc.get_opportunities()

        assert result["source"] == "database"
        assert result["opportunities"] == [fake_opp]


class TestGetMultiLegOpportunities:
    def test_returns_sample_data(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        svc = ScanService(repo=repo)
        result = svc.get_multi_leg_opportunities()

        assert result["status"] == "ok"
        assert len(result["opportunities"]) >= 1
        # verify strategy types are present
        types = {o.strategyType for o in result["opportunities"]}
        assert "BULL_CALL_SPREAD" in types or "IRON_CONDOR" in types
