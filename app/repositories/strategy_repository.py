"""Strategy repository — SQL data access for strategies and strategy_legs tables."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection
from ..exceptions import DatabaseError, NotFoundError

logger = logging.getLogger(__name__)


class StrategyRepository:
    """Encapsulates all SQL operations on the ``strategies`` / ``strategy_legs`` tables."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all(
        self,
        *,
        ticker: str | None = None,
        status: str | None = None,
        strategy_type: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if ticker:
            conditions.append("s.ticker = ?")
            params.append(ticker.upper())
        if status:
            conditions.append("s.status = ?")
            params.append(status)
        if strategy_type:
            conditions.append("s.strategy_type = ?")
            params.append(strategy_type)

        where = " AND ".join(conditions)
        where_clause = f"WHERE {where}" if where else ""

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT * FROM strategies s
                    {where_clause}
                    ORDER BY s.entry_date DESC
                    """,
                    params,
                )
                cols = [c[0] for c in cursor.description]
                strategies = [dict(zip(cols, row)) for row in cursor.fetchall()]

                # Fetch legs for each strategy
                for strat in strategies:
                    cursor.execute(
                        "SELECT * FROM strategy_legs WHERE strategy_id = ? ORDER BY leg_order",
                        (strat["id"],),
                    )
                    leg_cols = [c[0] for c in cursor.description]
                    strat["legs"] = [dict(zip(leg_cols, r)) for r in cursor.fetchall()]

                return strategies
        except Exception as exc:
            logger.exception("Failed to list strategies")
            raise DatabaseError(f"Failed to list strategies: {exc}") from exc

    def get_by_id(self, strategy_id: str) -> dict[str, Any]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,))
                row = cursor.fetchone()
                if row is None:
                    raise NotFoundError("Strategy", strategy_id)
                cols = [c[0] for c in cursor.description]
                strat = dict(zip(cols, row))

                cursor.execute(
                    "SELECT * FROM strategy_legs WHERE strategy_id = ? ORDER BY leg_order",
                    (strategy_id,),
                )
                leg_cols = [c[0] for c in cursor.description]
                strat["legs"] = [dict(zip(leg_cols, r)) for r in cursor.fetchall()]
                return strat
        except NotFoundError:
            raise
        except Exception as exc:
            logger.exception("Failed to get strategy %s", strategy_id)
            raise DatabaseError(f"Failed to get strategy: {exc}") from exc

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert(self, data: dict[str, Any]) -> str:
        strategy_id = data.get("id") or f"strat-{uuid.uuid4().hex[:12]}"
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO strategies
                        (id, strategy_type, name, ticker, underlying_price,
                         max_profit, max_loss, breakevens, risk_reward,
                         net_debit, net_credit, unrealized_pl, unrealized_pl_pct,
                         status, tags, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        strategy_id,
                        data["strategy_type"],
                        data.get("name"),
                        data["ticker"],
                        data.get("underlying_price"),
                        data.get("max_profit"),
                        data.get("max_loss"),
                        json.dumps(data.get("breakevens")) if data.get("breakevens") else None,
                        data.get("risk_reward"),
                        data.get("net_debit"),
                        data.get("net_credit"),
                        data.get("unrealized_pl", 0),
                        data.get("unrealized_pl_pct", 0),
                        data.get("status", "active"),
                        json.dumps(data.get("tags")) if data.get("tags") else None,
                        data.get("notes"),
                    ),
                )
                # Insert legs
                for i, leg in enumerate(data.get("legs", [])):
                    cursor.execute(
                        """
                        INSERT INTO strategy_legs
                            (strategy_id, leg_order, option_type, strike, expiration,
                             action, quantity, entry_price, current_price,
                             delta, gamma, theta, vega, implied_vol)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            strategy_id,
                            i + 1,
                            leg["option_type"],
                            leg["strike"],
                            leg["expiration"],
                            leg["action"],
                            leg["quantity"],
                            leg.get("entry_price"),
                            leg.get("current_price"),
                            leg.get("delta"),
                            leg.get("gamma"),
                            leg.get("theta"),
                            leg.get("vega"),
                            leg.get("implied_vol"),
                        ),
                    )
                conn.commit()
            return strategy_id
        except Exception as exc:
            logger.exception("Failed to insert strategy")
            raise DatabaseError(f"Failed to insert strategy: {exc}") from exc

    def update(self, strategy_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.get_by_id(strategy_id)  # raises NotFoundError
        sets: list[str] = []
        params: list[Any] = []
        updatable = [
            "name", "status", "unrealized_pl", "unrealized_pl_pct",
            "notes", "exit_date",
        ]
        for key in updatable:
            if key in data:
                sets.append(f"{key} = ?")
                params.append(data[key])
        if sets:
            sets.append("last_updated = GETUTCDATE()")
            params.append(strategy_id)
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"UPDATE strategies SET {', '.join(sets)} WHERE id = ?",
                        params,
                    )
                    conn.commit()
            except Exception as exc:
                logger.exception("Failed to update strategy %s", strategy_id)
                raise DatabaseError(f"Failed to update strategy: {exc}") from exc
        return self.get_by_id(strategy_id)

    def delete(self, strategy_id: str) -> None:
        self.get_by_id(strategy_id)  # raises NotFoundError
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM strategy_legs WHERE strategy_id = ?", (strategy_id,))
                cursor.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
                conn.commit()
        except Exception as exc:
            logger.exception("Failed to delete strategy %s", strategy_id)
            raise DatabaseError(f"Failed to delete strategy: {exc}") from exc

    def get_active_strategies(self) -> list[dict[str, Any]]:
        return self.get_all(status="active")
