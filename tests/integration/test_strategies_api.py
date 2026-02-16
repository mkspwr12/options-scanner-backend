"""Integration tests for the Strategies API."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def _strategy_row():
    return {
        "id": "strat-abc",
        "strategy_type": "BULL_CALL_SPREAD",
        "name": "Test Spread",
        "ticker": "META",
        "underlying_price": 689.30,
        "status": "active",
        "entry_date": "2025-01-15T00:00:00",
        "exit_date": None,
        "last_updated": "2025-01-15T00:00:00",
        "tags": "earnings",
        "notes": None,
        "legs": [
            {
                "id": "leg-1",
                "type": "CALL",
                "strike": 680.0,
                "expiration": "2025-02-28",
                "action": "BUY",
                "quantity": 1,
                "entry_price": 8.5,
                "current_price": 10.0,
                "delta": 0.6,
                "gamma": 0.04,
                "theta": -0.02,
                "vega": 0.10,
                "implied_volatility": 0.30,
            },
        ],
    }


class TestListStrategies:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["strategies"] == []

    def test_list_with_filters(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio/strategies?ticker=META&status=active")
        assert resp.status_code == 200


class TestCreateStrategy:
    def test_create_valid(self, client: TestClient, mock_strategy_repo: MagicMock) -> None:
        mock_strategy_repo.get_by_id.return_value = _strategy_row()
        resp = client.post("/api/portfolio/strategies", json={
            "strategyType": "BULL_CALL_SPREAD",
            "ticker": "META",
            "legs": [
                {
                    "type": "CALL",
                    "strike": 680.0,
                    "expiration": "2027-02-28",
                    "action": "BUY",
                    "quantity": 1,
                },
                {
                    "type": "CALL",
                    "strike": 700.0,
                    "expiration": "2027-02-28",
                    "action": "SELL",
                    "quantity": 1,
                },
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["strategy"]["strategyType"] == "BULL_CALL_SPREAD"

    def test_create_missing_ticker(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/strategies", json={
            "strategyType": "CUSTOM",
            "legs": [{"type": "CALL", "strike": 100, "expiration": "2027-03-01", "action": "BUY", "quantity": 1}],
        })
        assert resp.status_code == 422

    def test_create_no_legs(self, client: TestClient) -> None:
        resp = client.post("/api/portfolio/strategies", json={
            "strategyType": "CUSTOM",
            "ticker": "META",
            "legs": [],
        })
        assert resp.status_code == 422  # min_length=1 on legs


class TestGetStrategy:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio/strategies/nonexistent")
        assert resp.status_code == 404

    def test_found(self, client: TestClient, mock_strategy_repo: MagicMock) -> None:
        mock_strategy_repo.get_by_id.return_value = _strategy_row()
        resp = client.get("/api/portfolio/strategies/strat-abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"]["id"] == "strat-abc"


class TestUpdateStrategy:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.put("/api/portfolio/strategies/nonexistent", json={"name": "New"})
        assert resp.status_code == 404


class TestDeleteStrategy:
    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/portfolio/strategies/nonexistent")
        assert resp.status_code == 404

    def test_delete_ok(self, client: TestClient, mock_strategy_repo: MagicMock) -> None:
        mock_strategy_repo.get_by_id.return_value = _strategy_row()
        resp = client.delete("/api/portfolio/strategies/strat-abc")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
