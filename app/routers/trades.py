"""Trades and portfolio router."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_portfolio_service, get_trade_service
from ..schemas import CloseTradeRequest, TrackTradeRequest
from ..services.portfolio_service import PortfolioService
from ..services.trade_service import TradeService

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
) -> dict:
    """Get portfolio data aligned to frontend contract (Issues #13, #16)."""
    result = svc.get_enhanced_portfolio()
    data = result.model_dump()

    summary = data["summary"]
    positions_raw = data.get("positions", [])

    total_cost_basis = sum(p["entryPrice"] for p in positions_raw)

    positions = []
    for p in positions_raw:
        legs = []
        for leg in p.get("legs", []):
            # Parse leg type like "long_call" → optionType: "call", position: "long"
            parts = leg["type"].split("_", 1)
            opt_type = parts[1] if len(parts) == 2 else leg["type"]
            pos_type = parts[0] if len(parts) == 2 else "long"
            legs.append({
                "strike": leg["strike"],
                "expiration": p.get("expiration", ""),
                "optionType": opt_type,
                "position": pos_type,
                "quantity": leg["quantity"],
                "premium": round(
                    p["entryPrice"] / max(len(p.get("legs", [])), 1) / max(leg["quantity"] * 100, 1),
                    2,
                ),
            })
        positions.append({
            "id": p["id"],
            "ticker": p["ticker"],
            "strategyName": p.get("strategy", "").replace("_", " ").title(),
            "costBasis": p["entryPrice"],
            "currentValue": p["currentValue"],
            "unrealizedPnL": p["unrealizedPL"],
            "legs": legs,
            "openedAt": p["openDate"] + "T00:00:00Z",
        })

    return {
        "portfolio": {
            "id": "portfolio-default",
            "userId": "user-default",
        },
        "summary": {
            "totalPnL": summary["totalPL"],
            "pnlPercent": summary["totalPLPercent"],
            "totalValue": summary["totalValue"],
            "totalCostBasis": round(total_cost_basis, 2),
        },
        "positions": positions,
    }
