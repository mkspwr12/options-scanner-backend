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
        assert result["totalResults"] >= 10
        assert result["page"] == 1
        assert result["totalPages"] >= 1

    def test_pagination(self) -> None:
        req = StockScanRequest(page=1, pageSize=5)
        result = self.svc.scan(req)
        assert len(result["results"]) == 5
        assert result["page"] == 1
        assert result["totalPages"] >= 2

    def test_pagination_page_2(self) -> None:
        req = StockScanRequest(page=2, pageSize=5)
        result = self.svc.scan(req)
        assert result["page"] == 2
        assert len(result["results"]) == 5

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
        assert result["totalResults"] == 20  # 20 sample stocks
