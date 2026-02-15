"""Integration tests for scan endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestScan:
    def test_scan_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "opportunities" in data
        assert len(data["opportunities"]) >= 1

    def test_scan_with_filters(self, client: TestClient) -> None:
        resp = client.get("/api/scan?symbol=META&optionType=CALL&minConfidence=70")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_scan_limit_parameter(self, client: TestClient) -> None:
        resp = client.get("/api/scan?limit=1")
        assert resp.status_code == 200

    def test_scan_invalid_limit(self, client: TestClient) -> None:
        resp = client.get("/api/scan?limit=0")
        assert resp.status_code == 422

    def test_scan_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/scan?limit=999")
        assert resp.status_code == 422

    def test_scan_includes_source_field(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        data = resp.json()
        assert "source" in data
        assert data["source"] in ("database", "sample")

    def test_scan_opportunities_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        data = resp.json()
        for opp in data["opportunities"]:
            assert "id" in opp
            assert "symbol" in opp
            assert "strikePrice" in opp
            assert "optionType" in opp
            assert "greeks" in opp
            assert "confidenceScore" in opp
            assert "riskRewardRatio" in opp

    def test_scan_greeks_have_all_fields(self, client: TestClient) -> None:
        resp = client.get("/api/scan")
        opp = resp.json()["opportunities"][0]
        greeks = opp["greeks"]
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "theta" in greeks
        assert "vega" in greeks

    def test_scan_min_risk_reward_filter(self, client: TestClient) -> None:
        resp = client.get("/api/scan?minRiskReward=1.5")
        assert resp.status_code == 200

    def test_scan_sort_by_parameter(self, client: TestClient) -> None:
        resp = client.get("/api/scan?sortBy=riskRewardRatio")
        assert resp.status_code == 200

    def test_scan_symbol_filter(self, client: TestClient) -> None:
        resp = client.get("/api/scan?symbol=SPY")
        assert resp.status_code == 200

    def test_scan_option_type_filter(self, client: TestClient) -> None:
        resp = client.get("/api/scan?optionType=PUT")
        assert resp.status_code == 200

    def test_scan_multiple_filters_combined(self, client: TestClient) -> None:
        resp = client.get(
            "/api/scan?symbol=META&optionType=CALL&minConfidence=50&minRiskReward=1.0&limit=10"
        )
        assert resp.status_code == 200


class TestMultiLegOpportunities:
    def test_returns_strategies(self, client: TestClient) -> None:
        resp = client.get("/api/multi-leg-opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["opportunities"]) >= 1

    def test_strategies_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/api/multi-leg-opportunities")
        for strategy in resp.json()["opportunities"]:
            assert "id" in strategy
            assert "symbol" in strategy
            assert "strategyType" in strategy
            assert "legs" in strategy
            assert "maxProfit" in strategy
            assert "maxLoss" in strategy
            assert "breakeven" in strategy

    def test_strategies_have_legs(self, client: TestClient) -> None:
        resp = client.get("/api/multi-leg-opportunities")
        strategy = resp.json()["opportunities"][0]
        assert len(strategy["legs"]) >= 2

    def test_strategy_types_present(self, client: TestClient) -> None:
        resp = client.get("/api/multi-leg-opportunities")
        types = {s["strategyType"] for s in resp.json()["opportunities"]}
        assert len(types) >= 1
        # At least one of the known strategy types
        assert types & {"BULL_CALL_SPREAD", "IRON_CONDOR", "BEAR_PUT_SPREAD"}
