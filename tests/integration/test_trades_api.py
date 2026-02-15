"""Integration tests for trade and portfolio endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def _valid_trade_payload() -> dict:
    return {
        "opportunityId": "opp-001",
        "symbol": "META",
        "strikePrice": 690.0,
        "expirationDate": "2025-03-01",
        "optionType": "CALL",
        "entryPrice": 5.8,
        "currentPrice": 6.9,
        "quantity": 2,
        "underlyingPrice": 689.3,
        "greeks": {"delta": 0.42, "gamma": 0.06, "theta": -0.03, "vega": 0.12},
    }


class TestTrackTrade:
    def test_track_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/trades/track", json=_valid_trade_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ok"
        assert "tradeId" in data

    def test_track_invalid_body_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/trades/track", json={"symbol": "META"})
        assert resp.status_code == 422

    def test_track_bad_date_returns_422(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["expirationDate"] = "not-a-date"
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 422

    def test_track_bad_option_type_returns_422(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["optionType"] = "STRADDLE"
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 422


class TestCloseTrade:
    def test_close_returns_ok(self, client: TestClient) -> None:
        resp = client.post(
            "/api/trades/close",
            json={"tradeId": "trade-abc123", "exitPrice": 7.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "realizedPL" in data

    def test_close_missing_fields_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/trades/close", json={})
        assert resp.status_code == 422


class TestPortfolio:
    def test_portfolio_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "portfolio" in data
        portfolio = data["portfolio"]
        assert "metrics" in portfolio
        assert "activeTrades" in portfolio
        assert "closedTrades" in portfolio
