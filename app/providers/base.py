"""Market data provider protocol (abstract interface)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Quote:
    """Current price and basic data for an underlying asset."""

    symbol: str
    price: float
    day_high: float
    day_low: float
    volume: int
    previous_close: float


@dataclass(frozen=True)
class OptionContract:
    """Raw option contract data from a market data provider."""

    symbol: str
    strike: float
    expiration: str  # YYYY-MM-DD
    option_type: str  # CALL or PUT
    bid: float
    ask: float
    last_price: float
    volume: int
    open_interest: int
    implied_volatility: float


@runtime_checkable
class MarketDataProvider(Protocol):
    """Protocol that all market data providers must implement."""

    def get_options_chain(
        self, symbol: str, expiration: str | None = None, underlying_price: float | None = None
    ) -> list[OptionContract]:
        """Fetch options chain for a symbol.

        Args:
            symbol: Ticker symbol (e.g. ``"META"``).
            expiration: Optional expiration date ``YYYY-MM-DD``.
                        When *None*, return the nearest monthly expiration.
        """
        ...

    def get_quote(self, symbol: str) -> Quote:
        """Fetch current quote for a symbol."""
        ...

    def is_available(self) -> bool:
        """Return *True* when the provider can serve data."""
        ...

    def get_expiration_dates(self, symbol: str) -> list[str]:
        """Return available expiration dates for a symbol.

        Each date is formatted as ``YYYY-MM-DD``.
        """
        ...
