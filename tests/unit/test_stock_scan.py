"""Unit tests for Issue #12 — stock scan service."""
from __future__ import annotations

from unittest.mock import patch

from app.models import MACDData, StockScanResult
from app.schemas import (
    FundamentalFilters,
    IntRangeFilter,
    RangeFilter,
    StockScanFilters,
    StockScanRequest,
    TechnicalFilters,
)
from app.services.stock_scan_service import StockScanService
from app.services import stock_scan_service as _ssm


def _test_stocks() -> list[StockScanResult]:
    """Deterministic test stock data for unit tests."""
    samples = [
        ("AAPL", "Apple Inc.", 175.50, 2.5, 85_000_000, 55.0, 1.2, 0.8, 0.4, 22.5, 2_800_000_000_000, "high"),
        ("MSFT", "Microsoft Corp.", 420.30, 3.1, 45_000_000, 48.0, 0.9, 0.7, 0.2, 35.2, 3_100_000_000_000, "high"),
        ("NVDA", "NVIDIA Corp.", 875.20, 8.5, 70_000_000, 72.0, 3.2, 2.5, 0.7, 65.0, 2_100_000_000_000, "high"),
        ("GOOGL", "Alphabet Inc.", 178.80, -1.2, 32_000_000, 62.0, -0.5, -0.3, -0.2, 25.8, 2_200_000_000_000, "high"),
        ("AMZN", "Amazon.com Inc.", 225.40, 4.2, 55_000_000, 42.0, 1.5, 1.1, 0.4, 60.5, 1_900_000_000_000, "high"),
    ]
    return [
        StockScanResult(
            ticker=t, name=n, price=p, change=c, volume=v, rsi=r,
            macd=MACDData(value=mv, signal=ms, histogram=mh),
            pe=pe, marketCap=mc, optionLiquidity=liq,
        )
        for t, n, p, c, v, r, mv, ms, mh, pe, mc, liq in samples
    ]


@patch.object(StockScanService, "_fetch_live_stocks", return_value=_test_stocks())
class TestStockScanService:
    def setup_method(self) -> None:
        _ssm._cache.clear()  # avoid cross-test cache pollution
        self.svc = StockScanService()

    def test_scan_returns_results(self, _mock: object) -> None:
        req = StockScanRequest()
        result = self.svc.scan(req)
        assert result["status"] == "ok"
        assert "results" in result
        assert result["totalResults"] >= 1
        assert result["page"] == 1
        assert result["totalPages"] >= 1

    def test_pagination(self, _mock: object) -> None:
        req = StockScanRequest(page=1, pageSize=2)
        result = self.svc.scan(req)
        assert len(result["results"]) == 2
        assert result["page"] == 1
        assert result["totalPages"] >= 2

    def test_pagination_page_2(self, _mock: object) -> None:
        req = StockScanRequest(page=2, pageSize=2)
        result = self.svc.scan(req)
        assert result["page"] == 2
        assert len(result["results"]) >= 1

    def test_result_shape(self, _mock: object) -> None:
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

    def test_macd_shape(self, _mock: object) -> None:
        req = StockScanRequest(pageSize=1)
        result = self.svc.scan(req)
        macd = result["results"][0]["macd"]
        assert "value" in macd
        assert "signal" in macd
        assert "histogram" in macd

    def test_rsi_filter(self, _mock: object) -> None:
        req = StockScanRequest(
            filters=StockScanFilters(
                technical=TechnicalFilters(rsi=RangeFilter(min=50, max=60)),
            )
        )
        result = self.svc.scan(req)
        for stock in result["results"]:
            assert 50 <= stock["rsi"] <= 60

    def test_pe_filter(self, _mock: object) -> None:
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

    def test_market_cap_filter(self, _mock: object) -> None:
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

    def test_caching(self, _mock: object) -> None:
        """Second request with same filters should come from cache."""
        req = StockScanRequest(pageSize=5)
        result1 = self.svc.scan(req)
        result2 = self.svc.scan(req)
        assert result2["source"] == "cache"
        assert result1["totalResults"] == result2["totalResults"]

    def test_no_filters_returns_all(self, _mock: object) -> None:
        req = StockScanRequest(pageSize=200)
        result = self.svc.scan(req)
        assert result["totalResults"] == 5  # 5 test stocks


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

    def test_provider_none_returns_empty(self) -> None:
        svc = StockScanService(provider=None)
        assert svc._provider is None
        stocks = svc._fetch_live_stocks()
        assert len(stocks) == 0  # no provider = empty results
