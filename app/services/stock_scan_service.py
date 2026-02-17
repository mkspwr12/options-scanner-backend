"""Stock scan service — server-side stock screening with in-memory caching.

Issue #12: POST /api/stock-scan endpoint.
Uses mock data with TTL-based in-memory caching.
Ready for Yahoo Finance / Alpha Vantage integration.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ..models import MACDData, StockScanResult
from ..schemas import StockScanRequest

logger = logging.getLogger(__name__)

# In-memory cache (replaces Redis for initial implementation)
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 3600  # 60 minutes


class StockScanService:
    """Scans and filters stocks with in-memory caching."""

    def scan(self, request: StockScanRequest) -> dict[str, Any]:
        """Execute a stock scan with optional filters and pagination."""
        cache_key = self._build_cache_key(request)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return self._paginate(cached, request.page, request.pageSize, source="cache")

        # Generate (or fetch from live API in future)
        all_stocks = self._generate_sample_stocks()

        # Apply filters
        filtered = self._apply_filters(all_stocks, request.filters)

        # Cache the filtered results
        self._set_cache(cache_key, filtered)

        return self._paginate(filtered, request.page, request.pageSize, source="scan")

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    @staticmethod
    def _build_cache_key(request: StockScanRequest) -> str:
        """Build a deterministic cache key from the request."""
        import hashlib
        import json

        payload = request.model_dump(exclude={"page", "pageSize"})
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _get_cached(key: str) -> list[StockScanResult] | None:
        global _cache
        entry = _cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.time() - ts > _CACHE_TTL_SECONDS:
            del _cache[key]
            return None
        return data

    @staticmethod
    def _set_cache(key: str, data: list[StockScanResult]) -> None:
        global _cache
        _cache[key] = (time.time(), data)
        # Evict old entries if cache gets too large
        if len(_cache) > 100:
            oldest_key = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest_key]

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    @staticmethod
    def _paginate(
        results: list[StockScanResult],
        page: int,
        page_size: int,
        source: str = "scan",
    ) -> dict[str, Any]:
        total = len(results)
        total_pages = max((total + page_size - 1) // page_size, 1)
        start = (page - 1) * page_size
        end = start + page_size
        page_results = results[start:end]

        return {
            "status": "ok",
            "results": [r.model_dump() for r in page_results],
            "totalResults": total,
            "page": page,
            "totalPages": total_pages,
            "source": source,
        }

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_filters(
        stocks: list[StockScanResult],
        filters: Any | None,
    ) -> list[StockScanResult]:
        if filters is None:
            return stocks

        filtered: list[StockScanResult] = []
        for s in stocks:
            # Technical filters
            if filters.technical:
                t = filters.technical
                if t.rsi:
                    if t.rsi.min is not None and s.rsi < t.rsi.min:
                        continue
                    if t.rsi.max is not None and s.rsi > t.rsi.max:
                        continue
                if t.macd == "bullish_crossover" and s.macd.histogram <= 0:
                    continue
                if t.macd == "bearish_crossover" and s.macd.histogram >= 0:
                    continue

            # Fundamental filters
            if filters.fundamental:
                f = filters.fundamental
                if f.peRatio:
                    if f.peRatio.min is not None and s.pe < f.peRatio.min:
                        continue
                    if f.peRatio.max is not None and s.pe > f.peRatio.max:
                        continue
                if f.marketCap:
                    if f.marketCap.min is not None and s.marketCap < f.marketCap.min:
                        continue
                    if f.marketCap.max is not None and s.marketCap < f.marketCap.max:
                        continue

            # Momentum filters
            if filters.momentum:
                m = filters.momentum
                # volumeIncrease filter: percentage above average
                # (approximate — mock data doesn't have average)
                pass

            filtered.append(s)
        return filtered

    # ------------------------------------------------------------------
    # Sample data
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_sample_stocks() -> list[StockScanResult]:
        """Generate a universe of sample stocks for screening."""
        samples = [
            ("AAPL", "Apple Inc.", 175.50, 2.5, 85_000_000, 55.0, 1.2, 0.8, 0.4, 22.5, 2_800_000_000_000, "high"),
            ("MSFT", "Microsoft Corp.", 420.30, 3.1, 45_000_000, 48.0, 0.9, 0.7, 0.2, 35.2, 3_100_000_000_000, "high"),
            ("GOOGL", "Alphabet Inc.", 178.80, -1.2, 32_000_000, 62.0, -0.5, -0.3, -0.2, 25.8, 2_200_000_000_000, "high"),
            ("AMZN", "Amazon.com Inc.", 225.40, 4.2, 55_000_000, 42.0, 1.5, 1.1, 0.4, 60.5, 1_900_000_000_000, "high"),
            ("NVDA", "NVIDIA Corp.", 875.20, 8.5, 70_000_000, 72.0, 3.2, 2.5, 0.7, 65.0, 2_100_000_000_000, "high"),
            ("META", "Meta Platforms", 610.50, 5.3, 40_000_000, 58.0, 2.1, 1.8, 0.3, 28.0, 1_550_000_000_000, "high"),
            ("TSLA", "Tesla Inc.", 245.80, -3.5, 95_000_000, 38.0, -1.2, -0.8, -0.4, 55.0, 780_000_000_000, "high"),
            ("AMD", "Advanced Micro Devices", 178.60, 2.8, 60_000_000, 52.0, 0.8, 0.5, 0.3, 42.0, 290_000_000_000, "high"),
            ("JPM", "JPMorgan Chase", 245.30, 1.5, 15_000_000, 50.0, 0.6, 0.4, 0.2, 12.5, 715_000_000_000, "medium"),
            ("V", "Visa Inc.", 310.20, 1.8, 12_000_000, 54.0, 0.7, 0.5, 0.2, 32.0, 640_000_000_000, "medium"),
            ("JNJ", "Johnson & Johnson", 158.40, -0.5, 8_000_000, 45.0, -0.3, -0.1, -0.2, 18.5, 380_000_000_000, "medium"),
            ("UNH", "UnitedHealth Group", 520.10, 3.2, 6_000_000, 60.0, 1.1, 0.9, 0.2, 24.0, 480_000_000_000, "medium"),
            ("PG", "Procter & Gamble", 162.80, 0.8, 7_000_000, 47.0, 0.3, 0.2, 0.1, 26.0, 385_000_000_000, "low"),
            ("DIS", "Walt Disney Co.", 115.60, 2.1, 18_000_000, 56.0, 0.9, 0.6, 0.3, 72.0, 210_000_000_000, "medium"),
            ("NFLX", "Netflix Inc.", 890.50, 6.2, 10_000_000, 65.0, 2.5, 2.0, 0.5, 48.0, 390_000_000_000, "medium"),
            ("CRM", "Salesforce Inc.", 325.40, 1.9, 9_000_000, 49.0, 0.5, 0.3, 0.2, 55.0, 315_000_000_000, "medium"),
            ("INTC", "Intel Corp.", 32.50, -1.8, 45_000_000, 35.0, -0.8, -0.5, -0.3, 95.0, 135_000_000_000, "medium"),
            ("BA", "Boeing Co.", 185.20, 3.5, 12_000_000, 58.0, 1.0, 0.7, 0.3, -15.0, 110_000_000_000, "medium"),
            ("COIN", "Coinbase Global", 265.30, 8.9, 25_000_000, 70.0, 3.0, 2.2, 0.8, 35.0, 65_000_000_000, "medium"),
            ("PLTR", "Palantir Technologies", 78.50, 4.2, 55_000_000, 68.0, 1.8, 1.3, 0.5, 180.0, 175_000_000_000, "medium"),
        ]

        results: list[StockScanResult] = []
        for (ticker, name, price, change, vol, rsi,
             macd_v, macd_s, macd_h, pe, mcap, liq) in samples:
            results.append(
                StockScanResult(
                    ticker=ticker,
                    name=name,
                    price=price,
                    change=change,
                    volume=vol,
                    rsi=rsi,
                    macd=MACDData(value=macd_v, signal=macd_s, histogram=macd_h),
                    pe=pe,
                    marketCap=mcap,
                    optionLiquidity=liq,
                )
            )
        return results
