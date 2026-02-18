"""Position repository — SQL data access for the positions table (Issue #18)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import pyodbc

from ..db import get_connection
from ..exceptions import DatabaseError, NotFoundError
from ..models import PortfolioPositionRecord

logger = logging.getLogger(__name__)


class PositionRepository:
    """Encapsulates SQL operations on the ``positions`` table."""

    def insert(self, data: dict[str, Any]) -> str:
        """Insert a new position row. Returns the generated position ID."""
        position_id = f"pos-{uuid.uuid4().hex[:8]}"
        current_value = round(data["premium"] * data["quantity"] * 100, 2)
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO positions
                        (id, symbol, strike, expiration, option_type,
                         quantity, premium, entry_date, current_value, pnl, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'open')
                    """,
                    (
                        position_id,
                        data["symbol"],
                        data["strike"],
                        data["expiration"],
                        data["type"],
                        data["quantity"],
                        data["premium"],
                        data["entryDate"],
                        current_value,
                    ),
                )
                conn.commit()
            return position_id
        except Exception as exc:
            logger.exception("Failed to insert position")
            raise DatabaseError(f"Failed to insert position: {exc}") from exc

    def get_by_id(self, position_id: str) -> PortfolioPositionRecord:
        """Return a single position by ID. Raises NotFoundError if missing."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
                row = cursor.fetchone()
                if row is None:
                    raise NotFoundError("Position", position_id)
                return self._row_to_model(row, cursor.description)
        except NotFoundError:
            raise
        except Exception as exc:
            logger.exception("Failed to get position %s", position_id)
            raise DatabaseError(f"Failed to get position: {exc}") from exc

    def get_all_open(self) -> list[PortfolioPositionRecord]:
        """Return all positions with status = 'open'."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM positions WHERE status = 'open' ORDER BY created_at DESC"
                )
                return [self._row_to_model(r, cursor.description) for r in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to list open positions")
            raise DatabaseError(f"Failed to list positions: {exc}") from exc

    def get_all(self) -> list[PortfolioPositionRecord]:
        """Return every position row."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM positions ORDER BY created_at DESC")
                return [self._row_to_model(r, cursor.description) for r in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to list positions")
            raise DatabaseError(f"Failed to list positions: {exc}") from exc

    @staticmethod
    def _row_to_model(
        row: pyodbc.Row, description: list[tuple[str, ...]],
    ) -> PortfolioPositionRecord:
        """Convert a pyodbc row into a PortfolioPositionRecord."""
        cols = [col[0] for col in description]
        d = dict(zip(cols, row))

        return PortfolioPositionRecord(
            id=d["id"],
            symbol=d["symbol"],
            strike=float(d["strike"]),
            expiration=str(d["expiration"]),
            type=d["option_type"],
            quantity=int(d["quantity"]),
            premium=float(d["premium"]),
            entryDate=str(d["entry_date"]),
            currentValue=float(d.get("current_value") or 0),
            pnl=float(d.get("pnl") or 0),
            status=d["status"],
            createdAt=str(d.get("created_at", "")),
        )
