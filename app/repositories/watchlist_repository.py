"""Watchlist repository — SQL data access for the watchlist_items table."""
from __future__ import annotations

import logging

from ..db import get_connection
from ..exceptions import ConflictError, DatabaseError, NotFoundError

logger = logging.getLogger(__name__)


class WatchlistRepository:
    """Encapsulates all SQL operations on the ``watchlist_items`` table."""

    def get_all_symbols(self) -> list[str]:
        """Return all watchlist symbols, ordered alphabetically."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT symbol FROM watchlist_items ORDER BY symbol")
                return [row[0] for row in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to list watchlist")
            raise DatabaseError(f"Failed to list watchlist: {exc}") from exc

    def add_symbol(self, symbol: str) -> None:
        """Add a symbol.  Raises ConflictError if already present."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Check for duplicate first
                cursor.execute(
                    "SELECT COUNT(*) FROM watchlist_items WHERE symbol = ?", (symbol,)
                )
                if cursor.fetchone()[0] > 0:
                    raise ConflictError(f"Symbol '{symbol}' is already in the watchlist")
                cursor.execute(
                    "INSERT INTO watchlist_items (symbol) VALUES (?)", (symbol,)
                )
                conn.commit()
        except ConflictError:
            raise
        except Exception as exc:
            logger.exception("Failed to add symbol %s", symbol)
            raise DatabaseError(f"Failed to add symbol: {exc}") from exc

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol.  Raises NotFoundError if not present."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM watchlist_items WHERE symbol = ?", (symbol,)
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Watchlist symbol", symbol)
                conn.commit()
        except NotFoundError:
            raise
        except Exception as exc:
            logger.exception("Failed to remove symbol %s", symbol)
            raise DatabaseError(f"Failed to remove symbol: {exc}") from exc
