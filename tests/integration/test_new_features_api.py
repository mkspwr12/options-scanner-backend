"""Integration tests for new scan endpoints (Issues #10, #11, #12)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestScanPayoutChart:
    """Issue #10 — payout chart data in /api/scan response."""

    def test_scan_results_have_payout_chart(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        assert resp.status_code == 200
        opps = resp.json()["opportunities"]
        assert len(opps) > 0
        for opp in opps:
            assert "payoutChart" in opp
            assert "probability" in opp
            assert "breakeven" in opp
            assert "maxProfit" in opp
            assert "maxLoss" in opp
            assert "position" in opp

    def test_payout_chart_structure(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        chart = resp.json()["opportunities"][0]["payoutChart"]
        assert "pricePoints" in chart
        assert "profitPoints" in chart
        assert len(chart["pricePoints"]) >= 5
        assert len(chart["profitPoints"]) >= 5

    def test_probability_range(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        for opp in resp.json()["opportunities"]:
            assert 0 <= opp["probability"] <= 100

    def test_breakeven_reasonable(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        for opp in resp.json()["opportunities"]:
            assert opp["breakeven"] > 0


class TestMultiLegScan:
    """Issue #11 — POST /api/multi-leg-scan endpoint."""

    def test_iron_condor_scan(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "AAPL", "strategyType": "iron_condor"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["results"]) > 0

    def test_vertical_spread_scan(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "SPY", "strategyType": "vertical_spread"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) > 0

    def test_butterfly_scan(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "META", "strategyType": "butterfly"},
        )
        assert resp.status_code == 200

    def test_calendar_spread_scan(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "NVDA", "strategyType": "calendar_spread"},
        )
        assert resp.status_code == 200

    def test_diagonal_spread_scan(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "TSLA", "strategyType": "diagonal_spread"},
        )
        assert resp.status_code == 200

    def test_unsupported_strategy(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "AAPL", "strategyType": "straddle"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_with_filters(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={
                "ticker": "AAPL",
                "strategyType": "iron_condor",
                "filters": {
                    "minProbability": 60,
                    "maxBuyingPower": 5000,
                },
            },
        )
        assert resp.status_code == 200

    def test_missing_ticker(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"strategyType": "iron_condor"},
        )
        assert resp.status_code == 422

    def test_result_structure(self, client: TestClient) -> None:
        resp = client.post(
            "/api/multi-leg-scan",
            json={"ticker": "AAPL", "strategyType": "iron_condor"},
        )
        result = resp.json()["results"][0]
        assert "strategyType" in result
        assert "legs" in result
        assert "netCredit" in result
        assert "maxProfit" in result
        assert "maxLoss" in result
        assert "breakevens" in result
        assert "probability" in result
        assert "payoutChart" in result
        # Issue #17 — new fields
        assert "id" in result
        assert "ticker" in result
        assert "buyingPower" in result
        # Check leg structure
        leg = result["legs"][0]
        assert leg["type"] in ("put", "call")
        assert "position" in leg
        assert "quantity" in leg
        assert "expiration" in leg


class TestStockScan:
    """Issue #12 — POST /api/stock-scan endpoint."""

    def test_stock_scan_no_filters(self, client: TestClient) -> None:
        resp = client.post("/api/stock-scan", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["totalResults"] > 0
        assert data["page"] == 1

    def test_stock_scan_pagination(self, client: TestClient) -> None:
        resp = client.post("/api/stock-scan", json={"page": 1, "pageSize": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 5
        assert data["totalPages"] >= 2

    def test_stock_scan_page_2(self, client: TestClient) -> None:
        resp = client.post("/api/stock-scan", json={"page": 2, "pageSize": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2

    def test_result_shape(self, client: TestClient) -> None:
        resp = client.post("/api/stock-scan", json={"pageSize": 1})
        stock = resp.json()["results"][0]
        assert "ticker" in stock
        assert "name" in stock
        assert "price" in stock
        assert "macd" in stock
        assert "rsi" in stock

    def test_technical_filter(self, client: TestClient) -> None:
        resp = client.post(
            "/api/stock-scan",
            json={
                "filters": {
                    "technical": {
                        "rsi": {"min": 40, "max": 60},
                    }
                }
            },
        )
        assert resp.status_code == 200
        for stock in resp.json()["results"]:
            assert 40 <= stock["rsi"] <= 60

    def test_fundamental_filter(self, client: TestClient) -> None:
        resp = client.post(
            "/api/stock-scan",
            json={
                "filters": {
                    "fundamental": {
                        "peRatio": {"min": 10, "max": 40},
                    }
                }
            },
        )
        assert resp.status_code == 200
        for stock in resp.json()["results"]:
            assert 10 <= stock["pe"] <= 40


class TestPortfolioActions:
    """Issue #14, #16 — position action endpoints with frontend-aligned responses."""

    def test_close_position(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/close-position",
            json={"positionId": "pos-123", "closePrice": 180.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "closedPosition" in data
        assert "closedAt" in data["closedPosition"]
        assert "realizedPnL" in data["closedPosition"]

    def test_roll_position(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/roll-position",
            json={"positionId": "pos-123", "newExpiration": "2026-03-21"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "oldPositionId" in data
        assert "newPositionId" in data
        assert "rollCredit" in data

    def test_adjust_position_protective_put(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/adjust-position",
            json={
                "positionId": "pos-123",
                "adjustmentType": "add_protective_put",
                "strike": 160.0,
                "quantity": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "adjustedPosition" in data
        legs = data["adjustedPosition"]["newLegs"]
        assert len(legs) == 1
        assert legs[0]["optionType"] == "put"

    def test_adjust_position_reduce_size(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/adjust-position",
            json={
                "positionId": "pos-456",
                "adjustmentType": "reduce_size",
                "quantity": 2,
            },
        )
        assert resp.status_code == 200

    def test_close_position_missing_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/close-position",
            json={"positionId": "pos-123"},
        )
        assert resp.status_code == 422

    def test_invalid_adjustment_type(self, client: TestClient) -> None:
        resp = client.post(
            "/api/portfolio/adjust-position",
            json={
                "positionId": "pos-123",
                "adjustmentType": "invalid_type",
            },
        )
        assert resp.status_code == 422
