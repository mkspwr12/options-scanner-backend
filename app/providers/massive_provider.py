"""Massive market data provider.

Implements the ``MarketDataProvider`` protocol for quotes, options chains,
and expiration dates using Massive REST APIs.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from .base import OptionContract, Quote

logger = logging.getLogger(__name__)


class MassiveProvider:
    """Live options/quote data via Massive."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = (api_key or os.getenv("MASSIVE_API_KEY") or "").strip()
        self._base_url = (base_url or os.getenv("MASSIVE_BASE_URL") or "https://api.massive.com").rstrip("/")

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

    def get_options_chain(self, symbol: str, expiration: str | None = None) -> list[OptionContract]:
        sym = symbol.upper()
        target_exp = expiration
        if not target_exp:
            dates = self.get_expiration_dates(sym)
            if not dates:
                return []
            target_exp = dates[0]

        params = {
            "expiration_date": target_exp,
            "limit": "250",
            "sort": "strike_price",
            "order": "asc",
        }
        payloads = self._paginate_json(f"/v3/snapshot/options/{sym}", params)
        contracts: list[OptionContract] = []

        for payload in payloads:
            for item in payload.get("results") or []:
                details = item.get("details") or {}
                last_quote = item.get("last_quote") or {}
                day = item.get("day") or {}

                ctype = str(details.get("contract_type") or "").upper()
                if ctype not in ("CALL", "PUT"):
                    continue

                bid = self._safe_float(last_quote.get("bid"))
                ask = self._safe_float(last_quote.get("ask"))
                close_price = self._safe_float(day.get("close"))
                last_price = close_price if close_price > 0 else ((bid + ask) / 2 if (bid > 0 or ask > 0) else 0.0)

                contracts.append(
                    OptionContract(
                        symbol=sym,
                        strike=self._safe_float(details.get("strike_price")),
                        expiration=str(details.get("expiration_date") or target_exp),
                        option_type=ctype,
                        bid=bid,
                        ask=ask,
                        last_price=last_price,
                        volume=self._safe_int(day.get("volume")),
                        open_interest=self._safe_int(item.get("open_interest")),
                        implied_volatility=self._safe_float(item.get("implied_volatility")),
                    )
                )

        return contracts

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

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("MASSIVE_API_KEY is not configured")

        query = dict(params or {})
        query["apiKey"] = self._api_key
        url = f"{self._base_url}{path}?{urlencode(query)}"

        try:
            with urlopen(url, timeout=20) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
                payload: dict[str, Any] = json.loads(raw)
                return payload
        except HTTPError as exc:
            raise RuntimeError(f"Massive HTTP {exc.code} for {path}") from exc
        except URLError as exc:
            raise RuntimeError(f"Massive connection error for {path}: {exc.reason}") from exc

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
