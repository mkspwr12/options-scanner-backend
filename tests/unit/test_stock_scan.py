"""Unit tests for Issue #12 — stock scan service."""
from __future__ import annotations

from app.schemas import (
    FundamentalFilters,
    IntRangeFilter,
    RangeFilter,
    StockScanFilters,
    StockScanRequest,
    TechnicalFilters,
)
from app.services.stock_scan_service import StockScanService


class TestStockScanService:
    def setup_method(self) -> None:
        self.svc = StockScanService()

    def test_scan_returns_results(self) -> None:
        req = StockScanRequest()
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert "results" in result
        assert result["totalResults"] >= 1
        assert result["page"] == 1
        assert result["totalPages"] >= 1

    def test_pagination(self) -> None:
        req = StockScanRequest(page=1, pageSize=2)
        result = self.svc.scan(req)
        assert len(result["results"]) == 2
        assert result["page"] == 1
        assert result["totalPages"] >= 2

    def test_pagination_page_2(self) -> None:
        req = StockScanRequest(page=2, pageSize=2)
        result = self.svc.scan(req)
        assert result["page"] == 2
        assert len(result["results"]) >= 1

    def test_result_shape(self) -> None:
        req = StockScanRequest(pageSize=1)
        result = self.svc.scan(req)
        stock = result["results"][0]
        assert "ticker" in stock
        assert "name" in stock
        assert "price" in stock
        assert "change" in stock
        assert "volume" in stock
        assert "rsi" in stock
        assert "macd" in stock
        assert "pe" in stock
        assert "marketCap" in stock
        assert "optionLiquidity" in stock

    def test_macd_shape(self) -> None:
        req = StockScanRequest(pageSize=1)
        result = self.svc.scan(req)
        macd = result["results"][0]["macd"]
        assert "value" in macd
        assert "signal" in macd
        assert "histogram" in macd

    def test_rsi_filter(self) -> None:
        req = StockScanRequest(
            filters=StockScanFilters(
                technical=TechnicalFilters(rsi=RangeFilter(min=50, max=60)),
            )
        )
        result = self.svc.scan(req)
        for stock in result["results"]:
            assert 50 <= stock["rsi"] <= 60

    def test_pe_filter(self) -> None:
        req = StockScanRequest(
            filters=StockScanFilters(
                fundamental=FundamentalFilters(
                    peRatio=RangeFilter(min=10, max=30),
                ),
            )
        )
        result = self.svc.scan(req)
        for stock in result["results"]:
            assert 10 <= stock["pe"] <= 30

    def test_market_cap_filter(self) -> None:
        req = StockScanRequest(
            filters=StockScanFilters(
                fundamental=FundamentalFilters(
                    marketCap=IntRangeFilter(min=1_000_000_000_000),
                ),
            )
        )
        result = self.svc.scan(req)
        for stock in result["results"]:
            assert stock["marketCap"] >= 1_000_000_000_000

    def test_caching(self) -> None:
        """Second request with same filters should come from cache."""
        req = StockScanRequest(pageSize=5)
        result1 = self.svc.scan(req)
        result2 = self.svc.scan(req)
        assert result2["source"] == "cache"
        assert result1["totalResults"] == result2["totalResults"]

    def test_no_filters_returns_all(self) -> None:
        req = StockScanRequest(pageSize=200)
        result = self.svc.scan(req)
        assert result["totalResults"] == 5  # 5 fallback stocks (no provider)


class TestTechnicalIndicators:
    """Tests for RSI and MACD calculation functions."""

    def test_rsi_basic(self) -> None:
        # Alternating up/down should give RSI ~50
        prices = [100 + (i % 2) * 2 for i in range(30)]
        rsi = StockScanService._calculate_rsi(prices)
        assert 40 <= rsi <= 60

    def test_rsi_all_up(self) -> None:
        prices = [100 + i for i in range(30)]
        rsi = StockScanService._calculate_rsi(prices)
        assert rsi == 100.0

    def test_rsi_all_down(self) -> None:
        prices = [200 - i for i in range(30)]
        rsi = StockScanService._calculate_rsi(prices)
        assert rsi < 5.0

    def test_rsi_insufficient_data(self) -> None:
        prices = [100, 101, 102]
        rsi = StockScanService._calculate_rsi(prices)
        assert rsi == 50.0  # neutral fallback

    def test_macd_basic(self) -> None:
        prices = [100 + i * 0.5 for i in range(60)]
        macd = StockScanService._calculate_macd(prices)
        assert macd.value != 0
        assert macd.signal != 0
        assert macd.histogram == round(macd.value - macd.signal, 4)

    def test_macd_insufficient_data(self) -> None:
        prices = [100, 101, 102]
        macd = StockScanService._calculate_macd(prices)
        assert macd.value == 0.0
        assert macd.signal == 0.0
        assert macd.histogram == 0.0

    def test_provider_none_uses_fallback(self) -> None:
        svc = StockScanService(provider=None)
        assert svc._provider is None
        stocks = svc._fetch_live_stocks()
        assert len(stocks) == 5  # fallback mock data
