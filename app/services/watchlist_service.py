"""Watchlist service — business logic for watchlist management."""
from __future__ import annotations

import logging
from typing import Any

from ..repositories.watchlist_repository import WatchlistRepository

logger = logging.getLogger(__name__)


class WatchlistService:
    """Manages the user's watchlist of ticker symbols."""

    _DEFAULT_SYMBOLS: list[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY"]

    def __init__(self, repo: WatchlistRepository | None = None) -> None:
        self._repo = repo or WatchlistRepository()

    def get_symbols(self) -> list[str]:
        """Return all symbols on the watchlist.

        Falls back to a default list when the database is unavailable so the
        frontend can still render useful content.
        """
        try:
            symbols = self._repo.get_all_symbols()
            return symbols if symbols else self._DEFAULT_SYMBOLS
        except Exception:
            logger.warning("Watchlist DB unavailable — returning default symbols")
            return list(self._DEFAULT_SYMBOLS)

    def add_symbol(self, symbol: str) -> dict[str, Any]:
        """Add a symbol to the watchlist."""
        self._repo.add_symbol(symbol)
        logger.info("Added to watchlist: %s", symbol)
        return {
            "status": "ok",
            "symbol": symbol,
            "message": f"{symbol} added to watchlist",
        }

    def remove_symbol(self, symbol: str) -> dict[str, Any]:
        """Remove a symbol from the watchlist."""
        self._repo.remove_symbol(symbol)
        logger.info("Removed from watchlist: %s", symbol)
        return {
            "status": "ok",
            "symbol": symbol,
            "message": f"{symbol} removed from watchlist",
        }
