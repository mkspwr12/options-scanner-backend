"""Options chain service — fetch options chains via the provider registry."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from ..exceptions import AppError, ProviderError
from ..providers.base import OptionContract
from ..providers.greeks import calculate_greeks
from ..providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)

_TICKER_RE = re.compile(r"^[A-Z]{1,10}$")

# Risk-free rate approximation (US 10-year treasury)
_RISK_FREE_RATE = 0.045


class OptionsChainService:
    """Fetches options chains using the best available provider."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self._registry = registry if registry is not None else ProviderRegistry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_chain(
        self, ticker: str, expiration: str | None = None
    ) -> dict[str, Any]:
        """Fetch the full options chain for *ticker*.

        The registry handles provider selection and failover.
        """
        ticker = ticker.upper()
        if not _TICKER_RE.match(ticker):
            raise AppError(
                f"Invalid ticker symbol: '{ticker}'. "
                "Must be 1-10 uppercase letters.",
                status_code=400,
            )

        provider_id, provider = self._registry.get_best_provider()
        start = time.monotonic()

        try:
            quote = provider.get_quote(ticker)
            contracts = provider.get_options_chain(ticker, expiration)
            latency_ms = int((time.monotonic() - start) * 1000)
            self._registry.record_success(provider_id)
            self._registry.record_call(provider_id)

            enriched = [self._enrich(c, quote.price) for c in contracts]

            # Collect unique expiration dates
            expiration_dates = sorted(
                {c["expiration"] for c in enriched if c.get("expiration")}
            )

            now_utc = datetime.now(timezone.utc).isoformat()

            return {
                "status": "ok",
                "ticker": ticker,
                "underlyingPrice": quote.price,
                "expirationDates": expiration_dates,
                "provider": provider_id,
                "latencyMs": latency_ms,
                "contracts": enriched,
                "contractCount": len(enriched),
                "lastUpdated": now_utc,
                "dataDelayMinutes": 15,
            }
        except AppError:
            raise
        except ProviderError:
            self._registry.record_failure(provider_id)
            raise
        except Exception as exc:
            self._registry.record_failure(provider_id)
            raise AppError(
                f"Upstream provider '{provider_id}' failed: {exc}",
                status_code=502,
            ) from exc

    def get_expirations(self, ticker: str) -> dict[str, Any]:
        """Return available expiration dates for *ticker*."""
        provider_id, provider = self._registry.get_best_provider()
        try:
            expirations = provider.get_expiration_dates(ticker)
            self._registry.record_success(provider_id)
            return {
                "status": "ok",
                "ticker": ticker.upper(),
                "expirations": expirations,
                "provider": provider_id,
            }
        except Exception:
            self._registry.record_failure(provider_id)
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich(c: OptionContract, underlying_price: float) -> dict[str, Any]:
        """Add computed Greeks, DTE, and moneyness to a raw contract."""
        mid = (c.bid + c.ask) / 2.0 if c.bid and c.ask else c.last_price

        try:
            exp_date = datetime.strptime(c.expiration, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            dte = max((exp_date - datetime.now(timezone.utc)).days, 0)
            T = dte / 365.0
        except Exception:
            dte = 30
            T = 30 / 365.0

        greeks = calculate_greeks(
            S=underlying_price,
            K=c.strike,
            T=T,
            r=_RISK_FREE_RATE,
            sigma=c.implied_volatility,
            option_type=c.option_type,
        )

        # Classify moneyness
        moneyness = "ATM"
        if c.strike > 0:
            ratio = underlying_price / c.strike
            if c.option_type == "CALL":
                if ratio > 1.02:
                    moneyness = "ITM"
                elif ratio < 0.98:
                    moneyness = "OTM"
            else:
                if ratio < 0.98:
                    moneyness = "ITM"
                elif ratio > 1.02:
                    moneyness = "OTM"

        return {
            "symbol": c.symbol,
            "strike": c.strike,
            "expiration": c.expiration,
            "optionType": c.option_type,
            "bid": c.bid,
            "ask": c.ask,
            "lastPrice": c.last_price,
            "midPrice": round(mid, 4),
            "volume": c.volume,
            "openInterest": c.open_interest,
            "impliedVolatility": round(c.implied_volatility, 4),
            "greeks": {
                "delta": greeks.delta,
                "gamma": greeks.gamma,
                "theta": greeks.theta,
                "vega": greeks.vega,
            },
            "dte": dte,
            "moneyness": moneyness,
        }
