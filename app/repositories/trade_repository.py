"""Trade repository — SQL data access for the trades table."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import pyodbc

from ..db import get_connection
from ..exceptions import DatabaseError, NotFoundError
from ..models import ClosedTrade, Greeks, TrackedTrade

logger = logging.getLogger(__name__)


class TradeRepository:
    """Encapsulates all SQL operations on the ``trades`` table."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, trade_id: str) -> TrackedTrade | ClosedTrade:
        """Return a single trade by ID.  Raises NotFoundError if missing."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
                row = cursor.fetchone()
                if row is None:
                    raise NotFoundError("Trade", trade_id)
                return self._row_to_model(row, cursor.description)
        except NotFoundError:
            raise
        except Exception as exc:
            logger.exception("Failed to get trade %s", trade_id)
            raise DatabaseError(f"Failed to get trade: {exc}") from exc

    def get_active_trades(self) -> list[TrackedTrade]:
        """Return all trades with status = 'active'."""
        return self._get_by_status("active")

    def get_closed_trades(self) -> list[ClosedTrade]:
        """Return all trades with status = 'closed'."""
        return self._get_by_status("closed")  # type: ignore[return-value]

    def get_all(self) -> list[TrackedTrade | ClosedTrade]:
        """Return every trade row."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades ORDER BY created_at DESC")
                return [self._row_to_model(r, cursor.description) for r in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to list trades")
            raise DatabaseError(f"Failed to list trades: {exc}") from exc

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert(self, data: dict[str, Any]) -> str:
        """Insert a new trade row.  Returns the generated trade ID."""
        trade_id = f"trade-{uuid.uuid4().hex[:12]}"
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO trades
                        (id, opportunity_id, symbol, strike_price, expiration_date,
                         option_type, entry_price, current_price, quantity,
                         underlying_price, delta, gamma, theta, vega,
                         entry_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    """,
                    (
                        trade_id,
                        data["opportunityId"],
                        data["symbol"],
                        data["strikePrice"],
                        data["expirationDate"],
                        data["optionType"],
                        data["entryPrice"],
                        data["currentPrice"],
                        data["quantity"],
                        data["underlyingPrice"],
                        data["greeks"]["delta"],
                        data["greeks"]["gamma"],
                        data["greeks"]["theta"],
                        data["greeks"]["vega"],
                        now_ms,
                    ),
                )
                conn.commit()
            return trade_id
        except Exception as exc:
            logger.exception("Failed to insert trade")
            raise DatabaseError(f"Failed to insert trade: {exc}") from exc

    def close_trade(self, trade_id: str, exit_price: float) -> dict[str, Any]:
        """Mark a trade as closed, compute realized P/L, return summary."""
        trade = self.get_by_id(trade_id)  # raises NotFoundError if missing
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        realized_pl = (exit_price - trade.entryPrice) * trade.quantity * 100
        realized_pl_pct = ((exit_price - trade.entryPrice) / trade.entryPrice) * 100 if trade.entryPrice else 0.0
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE trades
                    SET status = 'closed',
                        exit_price = ?,
                        exit_date = ?,
                        current_price = ?,
                        updated_at = GETUTCDATE()
                    WHERE id = ?
                    """,
                    (exit_price, now_ms, exit_price, trade_id),
                )
                conn.commit()
            return {
                "tradeId": trade_id,
                "realizedPL": round(realized_pl, 2),
                "realizedPLPercent": round(realized_pl_pct, 2),
            }
        except Exception as exc:
            logger.exception("Failed to close trade %s", trade_id)
            raise DatabaseError(f"Failed to close trade: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_by_status(self, status: str) -> list[Any]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM trades WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
                return [self._row_to_model(r, cursor.description) for r in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to list trades (status=%s)", status)
            raise DatabaseError(f"Failed to list trades: {exc}") from exc

    @staticmethod
    def _row_to_model(
        row: pyodbc.Row, description: list[tuple[str, ...]]
    ) -> TrackedTrade | ClosedTrade:
        """Convert a pyodbc row into the appropriate Pydantic model."""
        cols = [col[0] for col in description]
        d = dict(zip(cols, row))

        greeks = Greeks(
            delta=float(d.get("delta") or 0),
            gamma=float(d.get("gamma") or 0),
            theta=float(d.get("theta") or 0),
            vega=float(d.get("vega") or 0),
        )

        entry_price = float(d["entry_price"])
        current_price = float(d["current_price"])
        quantity = int(d["quantity"])
        unrealized_pl = (current_price - entry_price) * quantity * 100
        unrealized_pl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price else 0.0

        base = dict(
            id=d["id"],
            opportunityId=d["opportunity_id"],
            symbol=d["symbol"],
            strikePrice=float(d["strike_price"]),
            expirationDate=str(d["expiration_date"]),
            optionType=d["option_type"],
            entryPrice=entry_price,
            currentPrice=current_price,
            quantity=quantity,
            underlyingPrice=float(d["underlying_price"]),
            greeks=greeks,
            entryDate=int(d["entry_date"]),
            unrealizedPL=round(unrealized_pl, 2),
            unrealizedPLPercent=round(unrealized_pl_pct, 2),
            status=d["status"],
        )

        if d["status"] == "closed":
            return ClosedTrade(
                **base,
                exitPrice=float(d.get("exit_price") or 0),
                exitDate=int(d.get("exit_date") or 0),
                realizedPL=round(
                    (float(d.get("exit_price") or 0) - entry_price) * quantity * 100, 2
                ),
                realizedPLPercent=round(
                    ((float(d.get("exit_price") or 0) - entry_price) / entry_price) * 100
                    if entry_price
                    else 0.0,
                    2,
                ),
            )
        return TrackedTrade(**base)
