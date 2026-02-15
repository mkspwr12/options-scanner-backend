"""Scan router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_scan_service
from ..services.scan_service import ScanService

router = APIRouter(prefix="/api", tags=["Scan"])


@router.get("/scan")
def scan(
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    optionType: str | None = Query(default=None, description="CALL or PUT"),
    minConfidence: float = Query(default=0, ge=0, description="Minimum confidence score"),
    minRiskReward: float = Query(default=0, ge=0, description="Minimum risk/reward ratio"),
    sortBy: str = Query(default="confidenceScore", description="Sort field"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
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
    )


@router.get("/multi-leg-opportunities")
def multi_leg_opportunities(
    svc: ScanService = Depends(get_scan_service),
) -> dict:
    """Return multi-leg option strategies."""
    return svc.get_multi_leg_opportunities()
