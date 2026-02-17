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

    def test_track_returns_message(self, client: TestClient) -> None:
        resp = client.post("/api/trades/track", json=_valid_trade_payload())
        data = resp.json()
        assert "message" in data
        assert "META" in data["message"]

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

    def test_track_negative_strike_returns_422(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["strikePrice"] = -100
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 422

    def test_track_zero_quantity_returns_422(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["quantity"] = 0
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 422

    def test_track_empty_symbol_returns_422(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["symbol"] = ""
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 422

    def test_track_empty_body_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/trades/track", json={})
        assert resp.status_code == 422

    def test_track_missing_greeks_returns_422(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        del payload["greeks"]
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 422

    def test_track_put_option(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["optionType"] = "PUT"
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 201

    def test_track_lowercase_symbol_uppercased(self, client: TestClient) -> None:
        payload = _valid_trade_payload()
        payload["symbol"] = "meta"
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 201
        assert "META" in resp.json()["message"]

    def test_track_zero_current_price_allowed(self, client: TestClient) -> None:
        """A worthless option should be trackable."""
        payload = _valid_trade_payload()
        payload["currentPrice"] = 0.0
        resp = client.post("/api/trades/track", json=payload)
        assert resp.status_code == 201


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

    def test_close_returns_message(self, client: TestClient) -> None:
        resp = client.post(
            "/api/trades/close",
            json={"tradeId": "trade-abc123", "exitPrice": 7.5},
        )
        data = resp.json()
        assert "message" in data
        assert "P/L" in data["message"]

    def test_close_missing_fields_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/trades/close", json={})
        assert resp.status_code == 422

    def test_close_empty_trade_id_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/trades/close",
            json={"tradeId": "", "exitPrice": 5.0},
        )
        assert resp.status_code == 422

    def test_close_zero_exit_price_allowed(self, client: TestClient) -> None:
        """Option expired worthless — exit at $0."""
        resp = client.post(
            "/api/trades/close",
            json={"tradeId": "trade-abc123", "exitPrice": 0.0},
        )
        assert resp.status_code == 200


class TestPortfolio:
    def test_portfolio_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "portfolio" in data
        portfolio = data["portfolio"]
        assert "summary" in portfolio
        assert "positions" in portfolio
        assert "aggregatePayoutChart" in portfolio

    def test_portfolio_summary_fields(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio")
        summary = resp.json()["portfolio"]["summary"]
        assert "totalValue" in summary
        assert "totalPL" in summary
        assert "totalPLPercent" in summary
        assert "maxProfit" in summary
        assert "maxLoss" in summary
        assert "netDelta" in summary
        assert "netTheta" in summary

    def test_portfolio_aggregate_payout_chart(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio")
        chart = resp.json()["portfolio"]["aggregatePayoutChart"]
        assert "pricePoints" in chart
        assert "profitPoints" in chart

    def test_portfolio_positions_shape(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio")
        positions = resp.json()["portfolio"]["positions"]
        if positions:
            pos = positions[0]
            assert "id" in pos
            assert "ticker" in pos
            assert "entryPrice" in pos
            assert "currentValue" in pos
            assert "unrealizedPL" in pos
            assert "plHistory" in pos

    def test_portfolio_positions_empty(self, client: TestClient) -> None:
        resp = client.get("/api/portfolio")
        positions = resp.json()["portfolio"]["positions"]
        assert isinstance(positions, list)
