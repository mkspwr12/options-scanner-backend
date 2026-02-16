"""Yahoo Finance market data provider.

Uses the ``yfinance`` library to fetch real options chain data
and current quotes.  Greeks are computed via the Black-Scholes
calculator in ``app.providers.greeks``.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import yfinance as yf

from .base import MarketDataProvider, OptionContract, Quote

logger = logging.getLogger(__name__)

# Polite inter-request delay (seconds) to avoid throttling
_REQUEST_DELAY = 0.5


class YahooFinanceProvider:
    """Live options data via Yahoo Finance (``yfinance``)."""

    def __init__(self) -> None:
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # MarketDataProvider interface
    # ------------------------------------------------------------------

    def get_options_chain(
        self, symbol: str, expiration: str | None = None
    ) -> list[OptionContract]:
        """Fetch options chain for *symbol*.

        When *expiration* is ``None`` the nearest available expiration
        is used automatically.
        """
        self._throttle()
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                logger.warning("No expirations available for %s", symbol)
                return []

            if expiration and expiration in expirations:
                target_exp = expiration
            else:
                target_exp = expirations[0]

            chain = ticker.option_chain(target_exp)
            contracts: list[OptionContract] = []

            for _, row in chain.calls.iterrows():
                contracts.append(self._row_to_contract(symbol, target_exp, "CALL", row))

            for _, row in chain.puts.iterrows():
                contracts.append(self._row_to_contract(symbol, target_exp, "PUT", row))

            logger.info(
                "Fetched %d contracts for %s (exp=%s)", len(contracts), symbol, target_exp,
            )
            return contracts
        except Exception:
            logger.exception("Failed to fetch options chain for %s", symbol)
            raise

    def get_quote(self, symbol: str) -> Quote:
        """Fetch current quote for *symbol*."""
        self._throttle()
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            return Quote(
                symbol=symbol.upper(),
                price=float(getattr(info, "last_price", 0) or 0),
                day_high=float(getattr(info, "day_high", 0) or 0),
                day_low=float(getattr(info, "day_low", 0) or 0),
                volume=int(getattr(info, "last_volume", 0) or 0),
                previous_close=float(getattr(info, "previous_close", 0) or 0),
            )
        except Exception:
            logger.exception("Failed to fetch quote for %s", symbol)
            raise

    def is_available(self) -> bool:
        """Probe Yahoo Finance by fetching a lightweight quote."""
        try:
            self._throttle()
            ticker = yf.Ticker("SPY")
            price = getattr(ticker.fast_info, "last_price", None)
            return price is not None and price > 0
        except Exception:
            return False

    def get_expiration_dates(self, symbol: str) -> list[str]:
        """Return available expiration dates from Yahoo Finance."""
        self._throttle()
        try:
            ticker = yf.Ticker(symbol)
            return list(ticker.options)
        except Exception:
            logger.exception("Failed to fetch expirations for %s", symbol)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Enforce minimum inter-request delay."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < _REQUEST_DELAY:
            time.sleep(_REQUEST_DELAY - elapsed)
        self._last_request_time = time.monotonic()

    @staticmethod
    def _row_to_contract(
        symbol: str, expiration: str, option_type: str, row: object
    ) -> OptionContract:
        return OptionContract(
            symbol=symbol.upper(),
            strike=float(getattr(row, "strike", 0)),
            expiration=expiration,
            option_type=option_type,
            bid=float(getattr(row, "bid", 0) or 0),
            ask=float(getattr(row, "ask", 0) or 0),
            last_price=float(getattr(row, "lastPrice", 0) or 0),
            volume=int(getattr(row, "volume", 0) or 0),
            open_interest=int(getattr(row, "openInterest", 0) or 0),
            implied_volatility=float(getattr(row, "impliedVolatility", 0) or 0),
        )
