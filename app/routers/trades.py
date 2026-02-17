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
    """Get enhanced portfolio data with summary, positions, and payout chart (Issue #13)."""
    result = svc.get_enhanced_portfolio()
    return {"status": "ok", "portfolio": result.model_dump()}
