"""Scan router."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ..dependencies import get_multi_leg_scan_service, get_scan_service, get_stock_scan_service, get_watchlist_service
from ..schemas import MultiLegScanRequest, SingleScanRequest, StockScanRequest
from ..services.multi_leg_scan_service import MultiLegScanService
from ..services.scan_service import ScanService
from ..services.stock_scan_service import StockScanService
from ..services.watchlist_service import WatchlistService

router = APIRouter(prefix="/api", tags=["Scan"])


@router.get("/scan")
def scan(
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    optionType: str | None = Query(default=None, description="CALL or PUT"),
    minConfidence: float = Query(default=0, ge=0, description="Minimum confidence score"),
    minRiskReward: float = Query(default=0, ge=0, description="Minimum risk/reward ratio"),
    sortBy: str = Query(default="confidenceScore", description="Sort field"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    # Phase 3: Advanced filters
    ivMin: float | None = Query(default=None, ge=0, description="Min implied volatility"),
    ivMax: float | None = Query(default=None, ge=0, description="Max implied volatility"),
    dteMin: int | None = Query(default=None, ge=0, description="Min days to expiration"),
    dteMax: int | None = Query(default=None, ge=0, description="Max days to expiration"),
    deltaMin: float | None = Query(default=None, description="Min delta"),
    deltaMax: float | None = Query(default=None, description="Max delta"),
    thetaMin: float | None = Query(default=None, description="Min theta"),
    thetaMax: float | None = Query(default=None, description="Max theta"),
    vegaMin: float | None = Query(default=None, description="Min vega"),
    vegaMax: float | None = Query(default=None, description="Max vega"),
    minVolume: int | None = Query(default=None, ge=0, description="Min volume"),
    moneyness: str | None = Query(
        default=None, description="Moneyness filter: itm, otm, atm, or all"
    ),
    svc: ScanService = Depends(get_scan_service),
) -> dict:
    """Get scan opportunities (with optional filtering)."""
    return svc.get_opportunities(
        symbol=symbol,
        option_type=optionType,
        min_confidence=minConfidence,
        min_risk_reward=minRiskReward,
        sort_by=sortBy,
        limit=limit,
        iv_min=ivMin,
        iv_max=ivMax,
        dte_min=dteMin,
        dte_max=dteMax,
        delta_min=deltaMin,
        delta_max=deltaMax,
        theta_min=thetaMin,
        theta_max=thetaMax,
        vega_min=vegaMin,
        vega_max=vegaMax,
        min_volume=minVolume,
        moneyness=moneyness,
    )


@router.post("/scan")
def scan_post(
    request: SingleScanRequest,
    svc: ScanService = Depends(get_scan_service),
) -> dict:
    """POST single options scanner (Issue #17)."""
    f = request.filters
    return svc.scan_single(
        ticker=request.ticker,
        min_delta=f.minDelta if f else None,
        max_delta=f.maxDelta if f else None,
        min_dte=f.minDTE if f else None,
        max_dte=f.maxDTE if f else None,
        min_iv=f.minIV if f else None,
        max_iv=f.maxIV if f else None,
        strike_min=f.strikeRange.min if f and f.strikeRange else None,
        strike_max=f.strikeRange.max if f and f.strikeRange else None,
    )


@router.post("/scan/trigger")
def trigger_scan(
    background_tasks: BackgroundTasks,
    scan_svc: ScanService = Depends(get_scan_service),
    wl_svc: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    """Manually trigger a live scan for watchlist symbols.

    Runs the scan asynchronously in the background to avoid HTTP gateway
    timeouts (the throttled scan takes several minutes).
    """
    symbols = wl_svc.get_symbols()
    background_tasks.add_task(scan_svc.run_scan, symbols)
    return {
        "status": "ok",
        "message": f"Scan triggered for {len(symbols)} symbols. Running in background with rate limiting. Check /api/scan for results in a few minutes.",
        "symbols": symbols,
    }


@router.get("/multi-leg-opportunities")
def multi_leg_opportunities(
    svc: ScanService = Depends(get_scan_service),
) -> dict:
    """Return multi-leg option strategies."""
    return svc.get_multi_leg_opportunities()


@router.post("/multi-leg-scan")
def multi_leg_scan(
    request: MultiLegScanRequest,
    svc: MultiLegScanService = Depends(get_multi_leg_scan_service),
) -> dict:
    """Scan for multi-leg option strategies (Issue #11)."""
    return svc.scan(request)


@router.post("/stock-scan")
def stock_scan(
    request: StockScanRequest,
    svc: StockScanService = Depends(get_stock_scan_service),
) -> dict:
    """Server-side stock screening with caching (Issue #12)."""
    return svc.scan(request)
