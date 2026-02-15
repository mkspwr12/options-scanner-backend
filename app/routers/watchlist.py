"""Watchlist router."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_watchlist_service
from ..schemas import WatchlistRequest
from ..services.watchlist_service import WatchlistService

router = APIRouter(prefix="/api", tags=["Watchlist"])


@router.get("/watchlist")
def get_watchlist(
    svc: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    """Get all watched symbols."""
    symbols = svc.get_symbols()
    return {"status": "ok", "symbols": symbols}


@router.post("/watchlist/add")
def add_to_watchlist(
    request: WatchlistRequest,
    svc: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    """Add a symbol to the watchlist."""
    return svc.add_symbol(request.symbol)


@router.post("/watchlist/remove")
def remove_from_watchlist(
    request: WatchlistRequest,
    svc: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    """Remove a symbol from the watchlist."""
    return svc.remove_symbol(request.symbol)
