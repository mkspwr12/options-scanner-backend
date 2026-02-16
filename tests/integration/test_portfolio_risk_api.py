"""Integration tests for the Portfolio Risk API."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class TestPortfolioRisk:
    def test_risk_endpoint(self, client: TestClient, mock_strategy_repo: MagicMock) -> None:
        """Should return aggregate Greeks plus trade/strategy counts."""
        mock_strategy_repo.get_all.return_value = []  # no active strategies
        resp = client.get("/api/portfolio/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "aggregateGreeks" in data
        assert "tradeCount" in data
        assert "strategyCount" in data
        assert "alerts" in data
        # Default trade fixture has delta=0.42 * qty=2 = 0.84 total
        assert data["aggregateGreeks"]["delta"] == pytest.approx(0.84, abs=0.01)

    def test_risk_with_group_by(self, client: TestClient, mock_strategy_repo: MagicMock) -> None:
        mock_strategy_repo.get_all.return_value = []
        resp = client.get("/api/portfolio/risk?groupBy=symbol")
        assert resp.status_code == 200
        data = resp.json()
        assert data["groups"] is not None
        assert len(data["groups"]) >= 1
        assert data["groups"][0]["symbol"] == "META"
