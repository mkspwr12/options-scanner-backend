"""Scan repository — SQL data access for the scan_results table."""
from __future__ import annotations

import logging
from typing import Any

from ..db import get_connection
from ..exceptions import DatabaseError
from ..models import Greeks, OptionOpportunity

logger = logging.getLogger(__name__)


class ScanRepository:
    """Encapsulates all SQL operations on the ``scan_results`` table."""

    def get_latest(
        self,
        *,
        symbol: str | None = None,
        option_type: str | None = None,
        min_confidence: float = 0,
        min_risk_reward: float = 0,
        sort_by: str = "confidence_score",
        limit: int = 50,
    ) -> list[OptionOpportunity]:
        """Return the most recent scan results, optionally filtered."""
        allowed_sort = {
            "confidenceScore": "confidence_score",
            "confidence_score": "confidence_score",
            "riskRewardRatio": "risk_reward_ratio",
            "risk_reward_ratio": "risk_reward_ratio",
            "potentialGain": "potential_gain",
            "potential_gain": "potential_gain",
        }
        order_col = allowed_sort.get(sort_by, "confidence_score")

        conditions: list[str] = []
        params: list[Any] = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if option_type:
            conditions.append("option_type = ?")
            params.append(option_type.upper())
        if min_confidence > 0:
            conditions.append("confidence_score >= ?")
            params.append(min_confidence)
        if min_risk_reward > 0:
            conditions.append("risk_reward_ratio >= ?")
            params.append(min_risk_reward)

        where = " AND ".join(conditions)
        where_clause = f"WHERE {where}" if where else ""

        query = f"""
            SELECT TOP (?) *
            FROM scan_results
            {where_clause}
            ORDER BY {order_col} DESC
        """
        params.insert(0, limit)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                cols = [col[0] for col in cursor.description]
                return [self._row_to_model(dict(zip(cols, row))) for row in cursor.fetchall()]
        except Exception as exc:
            logger.exception("Failed to retrieve scan results")
            raise DatabaseError(f"Failed to retrieve scan results: {exc}") from exc

    def save_results(self, results: list[dict[str, Any]]) -> int:
        """Bulk-insert scan results.  Returns count inserted."""
        if not results:
            return 0
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                for r in results:
                    cursor.execute(
                        """
                        INSERT INTO scan_results
                            (id, symbol, strike_price, expiration_date, option_type,
                             current_price, underlying_price, implied_volatility,
                             delta, gamma, theta, vega,
                             potential_gain, potential_loss, risk_reward_ratio,
                             confidence_score, strategy_type, scan_timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r["id"], r["symbol"], r["strikePrice"], r["expirationDate"],
                            r["optionType"], r["currentPrice"], r["underlyingPrice"],
                            r["impliedVolatility"],
                            r["greeks"]["delta"], r["greeks"]["gamma"],
                            r["greeks"]["theta"], r["greeks"]["vega"],
                            r["potentialGain"], r["potentialLoss"],
                            r["riskRewardRatio"], r["confidenceScore"],
                            r.get("strategyType"), r["timestamp"],
                        ),
                    )
                conn.commit()
            return len(results)
        except Exception as exc:
            logger.exception("Failed to save scan results")
            raise DatabaseError(f"Failed to save scan results: {exc}") from exc

    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_model(d: dict[str, Any]) -> OptionOpportunity:
        return OptionOpportunity(
            id=d["id"],
            symbol=d["symbol"],
            strikePrice=float(d["strike_price"]),
            expirationDate=str(d["expiration_date"]),
            optionType=d["option_type"],
            currentPrice=float(d.get("current_price") or 0),
            underlyingPrice=float(d.get("underlying_price") or 0),
            impliedVolatility=float(d.get("implied_volatility") or 0),
            greeks=Greeks(
                delta=float(d.get("delta") or 0),
                gamma=float(d.get("gamma") or 0),
                theta=float(d.get("theta") or 0),
                vega=float(d.get("vega") or 0),
            ),
            potentialGain=float(d.get("potential_gain") or 0),
            potentialLoss=float(d.get("potential_loss") or 0),
            riskRewardRatio=float(d.get("risk_reward_ratio") or 0),
            confidenceScore=float(d.get("confidence_score") or 0),
            timestamp=int(d.get("scan_timestamp") or 0),
        )
