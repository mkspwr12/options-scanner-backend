"""Watchlist service — business logic for watchlist management."""
from __future__ import annotations

import logging
from typing import Any

from ..repositories.watchlist_repository import WatchlistRepository

logger = logging.getLogger(__name__)


class WatchlistService:
    """Manages the user's watchlist of ticker symbols."""

    def __init__(self, repo: WatchlistRepository | None = None) -> None:
        self._repo = repo or WatchlistRepository()

    def get_symbols(self) -> list[str]:
        """Return all symbols on the watchlist."""
        return self._repo.get_all_symbols()

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
