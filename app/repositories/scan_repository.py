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
        # Phase 3: advanced filters
        iv_min: float | None = None,
        iv_max: float | None = None,
        dte_min: int | None = None,
        dte_max: int | None = None,
        delta_min: float | None = None,
        delta_max: float | None = None,
        theta_min: float | None = None,
        theta_max: float | None = None,
        vega_min: float | None = None,
        vega_max: float | None = None,
        min_volume: int | None = None,
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

        # Phase 3: advanced filters
        if iv_min is not None:
            conditions.append("implied_volatility >= ?")
            params.append(iv_min)
        if iv_max is not None:
            conditions.append("implied_volatility <= ?")
            params.append(iv_max)
        if dte_min is not None:
            conditions.append(
                "DATEDIFF(day, GETUTCDATE(), expiration_date) >= ?"
            )
            params.append(dte_min)
        if dte_max is not None:
            conditions.append(
                "DATEDIFF(day, GETUTCDATE(), expiration_date) <= ?"
            )
            params.append(dte_max)
        if delta_min is not None:
            conditions.append("delta >= ?")
            params.append(delta_min)
        if delta_max is not None:
            conditions.append("delta <= ?")
            params.append(delta_max)
        if theta_min is not None:
            conditions.append("theta >= ?")
            params.append(theta_min)
        if theta_max is not None:
            conditions.append("theta <= ?")
            params.append(theta_max)
        if vega_min is not None:
            conditions.append("vega >= ?")
            params.append(vega_min)
        if vega_max is not None:
            conditions.append("vega <= ?")
            params.append(vega_max)
        if min_volume is not None:
            # Note: volume is not persisted in scan_results —
            # this filter is applied in-memory during live scans.
            pass

        where = " AND ".join(conditions)
        where_clause = f"WHERE {where}" if where else ""

        # Deduplicate: keep only the latest row per unique contract
        # (symbol, strike_price, expiration_date, option_type)
        query = f"""
            SELECT TOP (?) *
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol, strike_price, expiration_date, option_type
                           ORDER BY scan_timestamp DESC
                       ) AS _rn
                FROM scan_results
                {where_clause}
            ) AS deduped
            WHERE _rn = 1
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
        """Bulk-insert scan results.  Returns count inserted.

        Deletes stale entries for the scanned symbols first to prevent
        duplicate contracts accumulating across scan runs.
        """
        if not results:
            return 0
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Delete old entries for the symbols being scanned
                symbols = list({r["symbol"] for r in results})
                if symbols:
                    placeholders = ",".join("?" for _ in symbols)
                    cursor.execute(
                        f"DELETE FROM scan_results WHERE symbol IN ({placeholders})",
                        symbols,
                    )

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
