"""Stock scan service — server-side stock screening with in-memory caching.

Issue #12: POST /api/stock-scan endpoint.
Uses Yahoo Finance (yfinance) for live market data with TTL-based caching.
Returns empty results when the provider is unavailable.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ..models import MACDData, StockScanResult
from ..providers.base import MarketDataProvider
from ..schemas import StockScanRequest

logger = logging.getLogger(__name__)

# In-memory cache (replaces Redis for initial implementation)
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 900  # 15 minutes for live data

# Default stock universe for screening
_DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "JPM", "V", "JNJ", "UNH", "PG", "DIS", "NFLX", "CRM", "INTC",
    "BA", "COIN", "PLTR",
]

# Company name map (yfinance info can be slow, cache common names)
_COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
    "META": "Meta Platforms",
    "TSLA": "Tesla Inc.",
    "AMD": "Advanced Micro Devices",
    "JPM": "JPMorgan Chase",
    "V": "Visa Inc.",
    "JNJ": "Johnson & Johnson",
    "UNH": "UnitedHealth Group",
    "PG": "Procter & Gamble",
    "DIS": "Walt Disney Co.",
    "NFLX": "Netflix Inc.",
    "CRM": "Salesforce Inc.",
    "INTC": "Intel Corp.",
    "BA": "Boeing Co.",
    "COIN": "Coinbase Global",
    "PLTR": "Palantir Technologies",
}


class StockScanService:
    """Scans and filters stocks with in-memory caching and live data."""

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self._provider = provider

    def scan(self, request: StockScanRequest) -> dict[str, Any]:
        """Execute a stock scan with optional filters and pagination.
        
        If request.tickers is provided, scans those specific symbols.
        Otherwise, scans the default universe.
        """
        cache_key = self._build_cache_key(request)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return self._paginate(cached, request.page, request.pageSize, source="cache")

        # Fetch live data for requested or default symbols
        tickers_to_scan = request.tickers if request.tickers else None
        all_stocks = self._fetch_live_stocks(tickers_to_scan)

        # Apply filters
        filtered = self._apply_filters(all_stocks, request.filters)

        # Cache the filtered results
        self._set_cache(cache_key, filtered)

        return self._paginate(filtered, request.page, request.pageSize, source="live")

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
                # Issue #15 — boolean MACD bullish filter
                if t.macdBullish is True and s.macd.histogram <= 0:
                    continue
                if t.macdBullish is False and s.macd.histogram > 0:
                    continue
                # Issue #15 — unusual volume filter
                if t.unusualVolume is True and s.volume < 50_000_000:
                    continue

            # Fundamental filters
            if filters.fundamental:
                f = filters.fundamental
                if f.peRatio:
                    if f.peRatio.min is not None and s.pe < f.peRatio.min:
                        continue
                    if f.peRatio.max is not None and s.pe > f.peRatio.max:
                        continue
                if f.marketCap is not None:
                    if isinstance(f.marketCap, str):
                        # Issue #15 — string-based market cap categories
                        cap = s.marketCap
                        if f.marketCap == "small" and cap >= 2_000_000_000:
                            continue
                        elif f.marketCap == "mid" and (
                            cap < 2_000_000_000 or cap >= 10_000_000_000
                        ):
                            continue
                        elif f.marketCap == "large" and (
                            cap < 10_000_000_000 or cap >= 200_000_000_000
                        ):
                            continue
                        elif f.marketCap == "mega" and cap < 200_000_000_000:
                            continue
                        # "all" → no filter
                    else:
                        # IntRangeFilter backward compat
                        if f.marketCap.min is not None and s.marketCap < f.marketCap.min:
                            continue
                        if f.marketCap.max is not None and s.marketCap > f.marketCap.max:
                            continue

            # Momentum filters
            if filters.momentum:
                m = filters.momentum
                # Issue #15 — volume spike filter (ratio vs 30M baseline)
                if m.volumeSpike is not None:
                    spike_ratio = s.volume / 30_000_000
                    if m.volumeSpike.min is not None and spike_ratio < m.volumeSpike.min:
                        continue
                    if m.volumeSpike.max is not None and spike_ratio > m.volumeSpike.max:
                        continue

            filtered.append(s)
        return filtered

    # ------------------------------------------------------------------
    # Live data fetching
    # ------------------------------------------------------------------

    def _fetch_live_stocks(self, tickers: list[str] | None = None) -> list[StockScanResult]:
        """Fetch real stock data from Yahoo Finance.
        
        Args:
            tickers: List of specific symbols to fetch. If None, uses _DEFAULT_TICKERS.
        
        Returns empty list if the provider is unavailable.
        """
        if self._provider is None:
            logger.warning("No provider configured — returning empty stock list")
            return []

        try:
            return self._fetch_from_yahoo(tickers or _DEFAULT_TICKERS)
        except Exception:
            logger.exception("Live stock fetch failed — no data available")
            return []

    def _fetch_from_yahoo(self, tickers: list[str]) -> list[StockScanResult]:
        """Fetch live data for specified tickers using yfinance."""
        import yfinance as yf

        results: list[StockScanResult] = []

        for ticker_sym in tickers:
            try:
                ticker = yf.Ticker(ticker_sym)

                # Get price history (60 days for RSI/MACD calculations)
                hist = ticker.history(period="3mo")
                if hist.empty or len(hist) < 14:
                    logger.warning("Insufficient history for %s, skipping", ticker_sym)
                    continue

                close = hist["Close"]
                volume_series = hist["Volume"]

                # Current price and change
                current_price = float(close.iloc[-1])
                prev_close = float(close.iloc[-2]) if len(close) >= 2 else current_price
                change_pct = round(
                    ((current_price - prev_close) / prev_close) * 100, 2
                ) if prev_close > 0 else 0.0

                # Current volume
                current_volume = int(volume_series.iloc[-1])

                # RSI (14-period)
                rsi = self._calculate_rsi(close.tolist(), period=14)

                # MACD (12, 26, 9)
                macd_data = self._calculate_macd(close.tolist())

                # Market cap and PE from fast_info / info
                info = ticker.fast_info
                market_cap = int(getattr(info, "market_cap", 0) or 0)

                # PE ratio — fast_info doesn't always have it, try info dict
                pe_ratio = 0.0
                try:
                    pe_ratio = float(getattr(info, "pe_ratio", 0) or 0)
                except Exception:
                    pass
                if pe_ratio == 0:
                    try:
                        full_info = ticker.info
                        pe_ratio = float(full_info.get("trailingPE", 0) or 0)
                    except Exception:
                        pass

                # Option liquidity — based on options availability and volume
                option_liq = self._assess_option_liquidity(ticker)

                name = _COMPANY_NAMES.get(ticker_sym, ticker_sym)

                results.append(
                    StockScanResult(
                        ticker=ticker_sym,
                        name=name,
                        price=round(current_price, 2),
                        change=change_pct,
                        volume=current_volume,
                        rsi=round(rsi, 1),
                        macd=macd_data,
                        pe=round(pe_ratio, 1),
                        marketCap=market_cap,
                        optionLiquidity=option_liq,
                    )
                )
                logger.info(
                    "Fetched live data for %s: $%.2f (RSI=%.1f)",
                    ticker_sym, current_price, rsi,
                )

            except Exception:
                logger.exception("Failed to fetch data for %s", ticker_sym)
                continue

        if not results:
            logger.warning("No live data fetched — returning empty list")
            return []

        return results

    # ------------------------------------------------------------------
    # Technical indicator calculations
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_rsi(prices: list[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index) from price list."""
        if len(prices) < period + 1:
            return 50.0  # neutral fallback

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]

        # Initial average gain/loss
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Smoothed via Wilder's method
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    @staticmethod
    def _calculate_macd(
        prices: list[float],
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ) -> MACDData:
        """Calculate MACD, Signal, and Histogram from price list."""
        if len(prices) < slow + signal_period:
            return MACDData(value=0.0, signal=0.0, histogram=0.0)

        # EMA helper
        def ema(data: list[float], span: int) -> list[float]:
            multiplier = 2.0 / (span + 1)
            result = [0.0] * len(data)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
            return result

        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_line = ema(macd_line, signal_period)
        histogram = [m - s for m, s in zip(macd_line, signal_line)]

        return MACDData(
            value=round(macd_line[-1], 4),
            signal=round(signal_line[-1], 4),
            histogram=round(histogram[-1], 4),
        )

    @staticmethod
    def _assess_option_liquidity(ticker: object) -> str:
        """Assess option liquidity for a ticker. Returns 'high', 'medium', or 'low'."""
        try:
            expirations = ticker.options  # type: ignore[attr-defined]
            if len(expirations) >= 12:
                return "high"
            elif len(expirations) >= 6:
                return "medium"
            else:
                return "low"
        except Exception:
            return "low"
