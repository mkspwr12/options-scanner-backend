"""Trades and portfolio router."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ..dependencies import get_portfolio_service, get_position_service, get_trade_service
from ..schemas import CloseTradeRequest, TrackTradeRequest
from ..services.portfolio_service import PortfolioService
from ..services.position_service import PositionService
from ..services.trade_service import TradeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Trades"])


@router.post("/trades/track", status_code=201)
def track_trade(
    request: TrackTradeRequest,
    svc: TradeService = Depends(get_trade_service),
) -> dict:
    """Track a new trade position."""
    return svc.track_trade(request)


@router.post("/trades/close")
def close_trade(
    request: CloseTradeRequest,
    svc: TradeService = Depends(get_trade_service),
) -> dict:
    """Close an existing trade position."""
    return svc.close_trade(request)


@router.get("/portfolio")
def portfolio(
    svc: PortfolioService = Depends(get_portfolio_service),
    pos_svc: PositionService = Depends(get_position_service),
) -> dict:
    """Get portfolio data aligned to frontend contract (Issues #13, #16, #18).

    Merges positions from both the legacy trades table and the newer
    positions table so all tracked instruments appear in a single view.
    """
    # --- Legacy trades-based positions ---
    result = svc.get_enhanced_portfolio()
    data = result.model_dump()

    summary = data["summary"]
    positions_raw = data.get("positions", [])

    total_cost_basis = sum(p["entryPrice"] for p in positions_raw)

    positions = []
    trade_ids: set[str] = set()
    for p in positions_raw:
        trade_ids.add(p["id"])
        legs = []
        for i, leg in enumerate(p.get("legs", [])):
            # Parse leg type like "long_call" → optionType: "call", side: "buy"
            parts = leg["type"].split("_", 1)
            opt_type = parts[1] if len(parts) == 2 else leg["type"]
            pos_type = parts[0] if len(parts) == 2 else "long"
            side = "buy" if pos_type == "long" else "sell"
            legs.append({
                "id": f"{p['id']}-leg-{i}",
                "strike": leg["strike"],
                "expiration": p.get("expiration", ""),
                "optionType": opt_type,
                "side": side,
                "quantity": leg["quantity"],
                "premium": round(
                    p["entryPrice"] / max(len(p.get("legs", [])), 1) / max(leg["quantity"] * 100, 1),
                    2,
                ),
            })

        entry_price = p["entryPrice"]
        unrealized_pnl = p["unrealizedPL"]
        pnl_pct = round((unrealized_pnl / entry_price * 100) if entry_price else 0, 2)

        positions.append({
            "id": p["id"],
            "ticker": p["ticker"],
            "strategyName": p.get("strategy", "").replace("_", " ").title(),
            "strategy": p.get("strategy", "single-leg"),
            "entryDate": p.get("openDate", ""),
            "quantity": sum(leg.get("quantity", 1) for leg in p.get("legs", [{"quantity": 1}])),
            "costBasis": entry_price,
            "currentValue": p["currentValue"],
            "pnl": unrealized_pnl,
            "pnlPercent": pnl_pct,
            "unrealizedPnL": unrealized_pnl,
            "greeks": {"delta": 0, "gamma": 0, "theta": 0, "vega": 0},
            "legs": legs,
            "openedAt": p["openDate"] + "T00:00:00Z",
        })

    # --- Positions table (add-position / Track button) ---
    try:
        pos_data = pos_svc.get_positions()
        for pos in pos_data.get("positions", []):
            p = pos if isinstance(pos, dict) else pos.model_dump()
            # Skip duplicates (same ID already from trades table)
            if p["id"] in trade_ids:
                continue

            cost_basis = round(p["premium"] * p["quantity"] * 100, 2)
            current_value = p.get("currentValue", cost_basis)
            pnl = round(current_value - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis * 100) if cost_basis else 0, 2)
            entry_date = p.get("entryDate", "")

            positions.append({
                "id": p["id"],
                "ticker": p["symbol"],
                "strategyName": "Single Leg",
                "strategy": "single-leg",
                "entryDate": entry_date,
                "quantity": p.get("quantity", 1),
                "costBasis": cost_basis,
                "currentValue": current_value,
                "pnl": pnl,
                "pnlPercent": pnl_pct,
                "unrealizedPnL": pnl,
                "greeks": {"delta": 0, "gamma": 0, "theta": 0, "vega": 0},
                "legs": [{
                    "id": f"{p['id']}-leg-0",
                    "strike": p.get("strike", 0),
                    "expiration": p.get("expiration", ""),
                    "optionType": p.get("type", "call"),
                    "side": "buy",
                    "quantity": p.get("quantity", 1),
                    "premium": p.get("premium", 0),
                }],
                "openedAt": entry_date + "T00:00:00Z" if entry_date else "",
            })

            total_cost_basis += cost_basis
    except Exception:
        logger.warning("Could not load positions table — showing trades only")

    # --- Recalculate summary including positions ---
    total_value = sum(p["currentValue"] for p in positions)
    total_pnl = sum(p["pnl"] for p in positions)
    total_pnl_pct = round((total_pnl / total_cost_basis * 100) if total_cost_basis else 0, 2)

    return {
        "portfolio": {
            "id": "portfolio-default",
            "userId": "user-default",
        },
        "summary": {
            "totalPnL": total_pnl,
            "pnlPercent": total_pnl_pct,
            "totalValue": total_value,
            "totalCostBasis": round(total_cost_basis, 2),
        },
        "positions": positions,
    }
