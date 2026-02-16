"""Strategy management service for multi-leg option strategies."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..exceptions import AppError, NotFoundError
from ..models import Strategy, StrategyLeg, StrategyMetrics
from ..repositories.strategy_repository import StrategyRepository

logger = logging.getLogger(__name__)

_VALID_TYPES = {
    "BULL_CALL_SPREAD",
    "BEAR_PUT_SPREAD",
    "IRON_CONDOR",
    "IRON_BUTTERFLY",
    "STRADDLE",
    "STRANGLE",
    "COVERED_CALL",
    "PROTECTIVE_PUT",
    "COLLAR",
    "CALENDAR_SPREAD",
    "DIAGONAL_SPREAD",
    "CUSTOM",
    # Accept lowercase-hyphenated variants from frontend
    "VERTICAL-SPREAD",
    "VERTICAL_SPREAD",
    "IRON-CONDOR",
    "BUTTERFLY",
    "CALENDAR",
    "DIAGONAL",
}


class StrategyService:
    """Business logic for multi-leg strategy CRUD and P&L."""

    def __init__(self, repo: StrategyRepository | None = None) -> None:
        self._repo = repo or StrategyRepository()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_strategies(
        self,
        *,
        ticker: str | None = None,
        status: str | None = None,
        strategy_type: str | None = None,
    ) -> list[Strategy]:
        rows = self._repo.get_all(
            ticker=ticker,
            status=status,
            strategy_type=strategy_type,
        )
        return [self._row_to_model(r) for r in rows]

    def get_strategy(self, strategy_id: str) -> Strategy:
        row = self._repo.get_by_id(strategy_id)
        if row is None:
            raise NotFoundError("Strategy", strategy_id)
        return self._row_to_model(row)

    def create_strategy(self, data: dict[str, Any]) -> Strategy:
        stype = data.get("strategyType", "CUSTOM").upper().replace("-", "_")
        if stype not in _VALID_TYPES and stype.replace("_", "-") not in _VALID_TYPES:
            raise AppError(f"Invalid strategy type: {stype}", status_code=400)

        legs = data.get("legs", [])
        if len(legs) < 1 or len(legs) > 4:
            raise AppError("Strategy must have 1-4 legs", status_code=400)

        # Validate ticker consistency — all legs implicitly share the
        # strategy's ticker
        strategy_ticker = data["ticker"].upper()

        # Validate expiration dates
        for i, leg in enumerate(legs):
            exp_str = leg.get("expiration", "")
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                raise AppError(
                    f"Leg {i + 1}: invalid expiration '{exp_str}'. "
                    "Must be YYYY-MM-DD format.",
                    status_code=400,
                )
            if exp_date.date() < datetime.now(timezone.utc).date():
                raise AppError(
                    f"Leg {i + 1}: expiration '{exp_str}' is in the past.",
                    status_code=400,
                )

        strategy_id = f"strat-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        row = {
            "id": strategy_id,
            "strategy_type": stype,
            "name": data.get("name") or f"{stype} on {data['ticker']}",
            "ticker": data["ticker"].upper(),
            "underlying_price": data.get("underlyingPrice"),
            "status": "active",
            "entry_date": now_iso,
            "last_updated": now_iso,
            "tags": ",".join(data.get("tags") or []),
            "notes": data.get("notes"),
        }

        leg_rows = []
        for i, leg in enumerate(legs):
            leg_rows.append(
                {
                    "id": f"leg-{uuid.uuid4().hex[:12]}",
                    "strategy_id": strategy_id,
                    "leg_index": i,
                    "option_type": leg["type"].upper(),
                    "strike": leg["strike"],
                    "expiration": leg["expiration"],
                    "action": leg["action"].upper(),
                    "quantity": leg["quantity"],
                    "entry_price": leg.get("entryPrice"),
                    "current_price": leg.get("currentPrice"),
                    "delta": leg.get("delta"),
                    "gamma": leg.get("gamma"),
                    "theta": leg.get("theta"),
                    "vega": leg.get("vega"),
                    "implied_volatility": leg.get("impliedVolatility"),
                }
            )

        row["legs"] = leg_rows
        self._repo.insert(row)
        return self.get_strategy(strategy_id)

    def update_strategy(self, strategy_id: str, data: dict[str, Any]) -> Strategy:
        existing = self._repo.get_by_id(strategy_id)
        if existing is None:
            raise NotFoundError("Strategy", strategy_id)

        updates: dict[str, Any] = {}
        if "name" in data and data["name"] is not None:
            updates["name"] = data["name"]
        if "status" in data and data["status"] is not None:
            updates["status"] = data["status"]
        if "notes" in data and data["notes"] is not None:
            updates["notes"] = data["notes"]
        if "tags" in data:
            updates["tags"] = ",".join(data["tags"] or [])

        updates["last_updated"] = datetime.now(timezone.utc).isoformat()

        if updates:
            self._repo.update(strategy_id, updates)
        return self.get_strategy(strategy_id)

    def delete_strategy(self, strategy_id: str) -> dict[str, str]:
        existing = self._repo.get_by_id(strategy_id)
        if existing is None:
            raise NotFoundError("Strategy", strategy_id)
        self._repo.delete(strategy_id)
        return {"status": "deleted", "id": strategy_id}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_model(row: dict[str, Any]) -> Strategy:
        legs: list[StrategyLeg] = []
        for leg in row.get("legs", []):
            legs.append(
                StrategyLeg(
                    id=leg.get("id"),
                    type=leg.get("type", "CALL"),
                    strike=float(leg.get("strike", 0)),
                    expiration=str(leg.get("expiration", "")),
                    action=leg.get("action", "BUY"),
                    quantity=int(leg.get("quantity", 1)),
                    entryPrice=(
                        float(leg["entry_price"])
                        if leg.get("entry_price") is not None
                        else None
                    ),
                    currentPrice=(
                        float(leg["current_price"])
                        if leg.get("current_price") is not None
                        else None
                    ),
                    delta=(
                        float(leg["delta"]) if leg.get("delta") is not None else None
                    ),
                    gamma=(
                        float(leg["gamma"]) if leg.get("gamma") is not None else None
                    ),
                    theta=(
                        float(leg["theta"]) if leg.get("theta") is not None else None
                    ),
                    vega=(
                        float(leg["vega"]) if leg.get("vega") is not None else None
                    ),
                    impliedVolatility=(
                        float(leg["implied_volatility"])
                        if leg.get("implied_volatility") is not None
                        else None
                    ),
                )
            )

        tags_raw = row.get("tags") or ""
        tags = (
            [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else None
        )

        # Calculate unrealized P&L from legs
        unrealized_pl = 0.0
        cost_basis = 0.0
        for leg in legs:
            if leg.entryPrice is not None and leg.currentPrice is not None:
                multiplier = 1 if leg.action.upper() == "BUY" else -1
                unrealized_pl += (
                    multiplier
                    * (leg.currentPrice - leg.entryPrice)
                    * leg.quantity
                    * 100
                )
                cost_basis += abs(leg.entryPrice * leg.quantity * 100)

        unrealized_pct = (
            (unrealized_pl / cost_basis * 100) if cost_basis > 0 else 0.0
        )

        return Strategy(
            id=row["id"],
            strategyType=row.get("strategy_type", "CUSTOM"),
            name=row.get("name"),
            ticker=row.get("ticker", ""),
            underlyingPrice=(
                float(row["underlying_price"])
                if row.get("underlying_price") is not None
                else None
            ),
            legs=legs,
            unrealizedPL=round(unrealized_pl, 2) if legs else None,
            unrealizedPLPercent=round(unrealized_pct, 2) if legs else None,
            status=row.get("status", "active"),
            entryDate=str(row.get("entry_date", "")),
            exitDate=(
                str(row.get("exit_date", "")) if row.get("exit_date") else None
            ),
            lastUpdated=str(row.get("last_updated", "")),
            tags=tags,
            notes=row.get("notes"),
        )
