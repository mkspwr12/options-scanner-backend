"""Massive market data provider.

Implements the ``MarketDataProvider`` protocol for quotes, options chains,
and expiration dates using Massive REST APIs.

Rate limiting: Implements exponential backoff with configurable request delays
to prevent hitting API rate limits.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from .base import OptionContract, Quote

logger = logging.getLogger(__name__)


class MassiveProvider:
    """Live options/quote data via Massive with rate limiting.
    
    Rate limiting strategy:
    - Minimum delay between requests: 3s (~20 req/min) with retry/backoff on 429
    - Exponential backoff on 429 errors (15s, 30s, 45s, 60s)
    - Max retries: 4
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        min_request_interval: float = 3.0,  # 3s between requests with retry on 429
        max_retries: int = 4,
    ) -> None:
        self._api_key = (api_key or os.getenv("MASSIVE_API_KEY") or "").strip()
        self._base_url = (base_url or os.getenv("MASSIVE_BASE_URL") or "https://api.massive.com").rstrip("/")
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries
        self._last_request_time: float = 0.0

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            quote = self.get_quote("SPY")
            return quote.price > 0
        except Exception:
            return False

    def get_quote(self, symbol: str) -> Quote:
        sym = symbol.upper()
        payload = self._get_json(f"/v2/aggs/ticker/{sym}/prev", {"adjusted": "true"})
        rows = payload.get("results") or []
        if not rows:
            raise RuntimeError(f"No quote data for {sym}")
        row = rows[0]
        price = self._safe_float(row.get("c"))
        return Quote(
            symbol=sym,
            price=price,
            day_high=self._safe_float(row.get("h"), price),
            day_low=self._safe_float(row.get("l"), price),
            volume=self._safe_int(row.get("v"), 0),
            previous_close=price,
        )

    def get_expiration_dates(self, symbol: str) -> list[str]:
        sym = symbol.upper()
        params = {
            "underlying_ticker": sym,
            "expired": "false",
            "limit": "1000",
            "sort": "expiration_date",
            "order": "asc",
        }
        payloads = self._paginate_json("/v3/reference/options/contracts", params)
        expirations: set[str] = set()
        for payload in payloads:
            for item in payload.get("results") or []:
                exp = item.get("expiration_date")
                if exp:
                    expirations.add(str(exp))
        return sorted(expirations)

    def get_options_chain(self, symbol: str, expiration: str | None = None, underlying_price: float | None = None) -> list[OptionContract]:
        """Fetch options chain using free-tier endpoints.

        Uses /v3/reference/options/contracts for contract metadata and
        /v2/aggs/ticker/{contract}/prev for pricing (since /v3/snapshot/options
        requires a paid plan and returns 403 on free tier).

        To stay within rate limits, limits to ATM contracts (3 calls + 3 puts)
        near the underlying price.
        """
        sym = symbol.upper()
        target_exp = expiration
        if not target_exp:
            dates = self.get_expiration_dates(sym)
            if not dates:
                return []
            target_exp = dates[0]

        # Get all contracts for this expiration
        params = {
            "underlying_ticker": sym,
            "expiration_date": target_exp,
            "expired": "false",
            "limit": "250",
            "sort": "strike_price",
            "order": "asc",
        }
        payloads = self._paginate_json("/v3/reference/options/contracts", params)
        all_contracts: list[dict] = []
        for payload in payloads:
            for item in payload.get("results") or []:
                ctype = str(item.get("contract_type") or "").upper()
                if ctype in ("CALL", "PUT"):
                    all_contracts.append(item)

        if not all_contracts:
            return []

        # Filter to ATM contracts near the underlying price
        # to minimize API calls for pricing
        atm_contracts = self._filter_atm_contracts(all_contracts, underlying_price or 0, max_per_type=5)

        logger.info(
            "Options chain for %s exp=%s: %d total contracts, %d ATM selected for pricing",
            sym, target_exp, len(all_contracts), len(atm_contracts),
        )

        # Fetch pricing for each selected contract via /v2/aggs/ticker/{ticker}/prev
        contracts: list[OptionContract] = []
        for ref in atm_contracts:
            contract_ticker = ref.get("ticker", "")
            ctype = str(ref.get("contract_type") or "").upper()
            strike = self._safe_float(ref.get("strike_price"))
            exp_date = str(ref.get("expiration_date") or target_exp)

            # Get prev-day pricing for the contract
            try:
                pricing = self._get_json(f"/v2/aggs/ticker/{contract_ticker}/prev", {"adjusted": "true"})
                rows = pricing.get("results") or []
                if rows:
                    row = rows[0]
                    close_price = self._safe_float(row.get("c"))
                    high = self._safe_float(row.get("h"))
                    low = self._safe_float(row.get("l"))
                    # Estimate bid/ask from high/low
                    bid = low if low > 0 else close_price * 0.95
                    ask = high if high > 0 else close_price * 1.05
                    volume = self._safe_int(row.get("v"))
                else:
                    close_price = 0.0
                    bid = 0.0
                    ask = 0.0
                    volume = 0
            except Exception:
                logger.debug("Could not get pricing for %s", contract_ticker)
                close_price = 0.0
                bid = 0.0
                ask = 0.0
                volume = 0

            last_price = close_price if close_price > 0 else ((bid + ask) / 2 if (bid > 0 or ask > 0) else 0.0)

            contracts.append(
                OptionContract(
                    symbol=sym,
                    strike=strike,
                    expiration=exp_date,
                    option_type=ctype,
                    bid=bid,
                    ask=ask,
                    last_price=last_price,
                    volume=volume,
                    open_interest=0,
                    implied_volatility=0.0,
                )
            )

        return contracts

    @staticmethod
    def _filter_atm_contracts(contracts: list[dict], underlying_price: float, max_per_type: int = 5) -> list[dict]:
        """Select contracts nearest to the underlying price, up to max_per_type calls + puts."""
        if underlying_price <= 0:
            # No price info — take the middle contracts
            mid = len(contracts) // 2
            start = max(0, mid - max_per_type)
            end = min(len(contracts), mid + max_per_type)
            return contracts[start:end]

        calls = [c for c in contracts if str(c.get("contract_type", "")).upper() == "CALL"]
        puts = [c for c in contracts if str(c.get("contract_type", "")).upper() == "PUT"]

        def nearest(items: list[dict], n: int) -> list[dict]:
            scored = sorted(items, key=lambda c: abs(float(c.get("strike_price", 0)) - underlying_price))
            return scored[:n]

        return nearest(calls, max_per_type) + nearest(puts, max_per_type)

    def get_stock_scan_data(self, symbol: str, days: int = 90) -> dict[str, Any] | None:
        sym = symbol.upper()
        end_date = date.today()
        start_date = end_date - timedelta(days=max(days, 30))

        bars_payload = self._get_json(
            f"/v2/aggs/ticker/{sym}/range/1/day/{start_date.isoformat()}/{end_date.isoformat()}",
            {"adjusted": "true", "sort": "asc", "limit": "200"},
        )
        bars = bars_payload.get("results") or []
        if len(bars) < 14:
            return None

        closes = [self._safe_float(b.get("c")) for b in bars if self._safe_float(b.get("c")) > 0]
        if len(closes) < 14:
            return None

        last = bars[-1]
        prev_close = closes[-2] if len(closes) >= 2 else closes[-1]

        name = sym
        market_cap = 0
        pe_ratio = 0.0
        try:
            ref_payload = self._get_json(f"/v3/reference/tickers/{sym}", {})
            ref = ref_payload.get("results") or {}
            name = str(ref.get("name") or sym)
            market_cap = self._safe_int(ref.get("market_cap"), 0)
            pe_ratio = self._safe_float(ref.get("pe_ratio"), 0.0)
        except Exception:
            logger.debug("Reference lookup unavailable for %s", sym)

        return {
            "symbol": sym,
            "name": name,
            "price": self._safe_float(last.get("c")),
            "prev_close": self._safe_float(prev_close),
            "volume": self._safe_int(last.get("v")),
            "closes": closes,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
        }

    def _paginate_json(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        next_path: str | None = path
        next_params = dict(params or {})

        while next_path:
            payload = self._get_json(next_path, next_params)
            payloads.append(payload)
            next_url = payload.get("next_url")
            if not next_url:
                break
            parsed = urlparse(str(next_url))
            next_path = parsed.path
            qs = parse_qs(parsed.query)
            next_params = {k: v[-1] for k, v in qs.items() if v}
        return payloads

    def _rate_limit_delay(self) -> None:
        """Enforce minimum delay between API requests."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                sleep_time = self._min_request_interval - elapsed
                logger.debug("Rate limiting: sleeping %.3fs", sleep_time)
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        """Fetch JSON from Massive API with rate limiting and retry logic."""
        if not self._api_key:
            raise RuntimeError("MASSIVE_API_KEY is not configured")

        query = dict(params or {})
        query["apiKey"] = self._api_key
        url = f"{self._base_url}{path}?{urlencode(query)}"

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                # Enforce rate limiting
                self._rate_limit_delay()

                with urlopen(url, timeout=20) as resp:  # noqa: S310
                    raw = resp.read().decode("utf-8")
                    payload: dict[str, Any] = json.loads(raw)
                    return payload

            except HTTPError as exc:
                if exc.code == 429:
                    # Rate limit hit - longer backoff for free-tier limits
                    backoff_time = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s
                    logger.warning(
                        "Massive rate limit hit (429) for %s, attempt %d/%d - backing off %ds",
                        path,
                        attempt + 1,
                        self._max_retries,
                        backoff_time,
                    )
                    if attempt < self._max_retries - 1:
                        time.sleep(backoff_time)
                        last_error = exc
                        continue
                    raise RuntimeError(f"Massive rate limit exceeded after {self._max_retries} retries") from exc
                else:
                    # Other HTTP errors are not retryable
                    raise RuntimeError(f"Massive HTTP {exc.code} for {path}") from exc

            except URLError as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    logger.warning("Massive connection error for %s, retrying... (%s)", path, exc.reason)
                    time.sleep(1)
                    continue
                raise RuntimeError(f"Massive connection error for {path}: {exc.reason}") from exc

        # Should not reach here, but handle it gracefully
        raise RuntimeError(f"Max retries exceeded for {path}") from last_error

    @staticmethod
    def _safe_float(val: object, default: float = 0.0) -> float:
        try:
            if val is None:
                return default
            return float(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(val: object, default: int = 0) -> int:
        try:
            if val is None:
                return default
            return int(float(val))
        except (TypeError, ValueError):
            return default
