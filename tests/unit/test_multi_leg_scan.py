"""Unit tests for Issue #11 — multi-leg scan service."""
from __future__ import annotations

from app.providers.mock_provider import MockProvider
from app.schemas import MultiLegScanFilters, MultiLegScanRequest
from app.services.multi_leg_scan_service import MultiLegScanService


class TestMultiLegScanService:
    def setup_method(self) -> None:
        self.svc = MultiLegScanService(provider=MockProvider())

    def test_iron_condor_scan(self) -> None:
        req = MultiLegScanRequest(ticker="AAPL", strategyType="iron_condor")
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert len(result["results"]) > 0
        r = result["results"][0]
        assert r["strategyType"] == "iron_condor"
        assert len(r["legs"]) == 4
        assert r["maxProfit"] > 0
        assert r["maxLoss"] < 0
        assert len(r["breakevens"]) == 2
        assert "payoutChart" in r
        # Issue #17 — new fields
        assert r["id"].startswith("strategy-")
        assert r["ticker"] == "AAPL"
        assert r["buyingPower"] > 0
        # Legs should have enriched fields
        leg = r["legs"][0]
        assert leg["type"] in ("put", "call")
        assert leg["position"] in ("long", "short")
        assert leg["quantity"] == 1
        assert leg["expiration"] != ""

    def test_vertical_spread_scan(self) -> None:
        req = MultiLegScanRequest(ticker="SPY", strategyType="vertical_spread")
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert len(result["results"]) == 2  # bull + bear

    def test_calendar_spread_scan(self) -> None:
        req = MultiLegScanRequest(ticker="META", strategyType="calendar_spread")
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert len(result["results"]) >= 1

    def test_butterfly_scan(self) -> None:
        req = MultiLegScanRequest(ticker="NVDA", strategyType="butterfly")
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert len(result["results"]) >= 1
        r = result["results"][0]
        assert len(r["legs"]) == 4

    def test_diagonal_spread_scan(self) -> None:
        req = MultiLegScanRequest(ticker="TSLA", strategyType="diagonal_spread")
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert len(result["results"]) >= 1

    def test_unsupported_strategy_type(self) -> None:
        req = MultiLegScanRequest(ticker="AAPL", strategyType="straddle")
        result = self.svc.scan(req)
        assert result["status"] == "error"
        assert result["results"] == []

    def test_filter_min_probability(self) -> None:
        req = MultiLegScanRequest(
            ticker="AAPL",
            strategyType="iron_condor",
            filters=MultiLegScanFilters(minProbability=99),
        )
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        # Very high threshold should filter out all results
        assert len(result["results"]) == 0

    def test_filter_max_buying_power(self) -> None:
        req = MultiLegScanRequest(
            ticker="AAPL",
            strategyType="iron_condor",
            filters=MultiLegScanFilters(maxBuyingPower=10),
        )
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        # Very low buying power should filter out all results
        assert len(result["results"]) == 0

    def test_payout_chart_structure(self) -> None:
        req = MultiLegScanRequest(ticker="AAPL", strategyType="iron_condor")
        result = self.svc.scan(req)
        chart = result["results"][0]["payoutChart"]
        assert "pricePoints" in chart
        assert "profitPoints" in chart
        assert len(chart["pricePoints"]) == len(chart["profitPoints"])

    def test_ticker_uppercased(self) -> None:
        req = MultiLegScanRequest(ticker="aapl", strategyType="iron_condor")
        assert req.ticker == "AAPL"
