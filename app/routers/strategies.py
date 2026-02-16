"""Strategy management router — multi-leg option strategies."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_strategy_service
from ..schemas import CreateStrategyRequest, UpdateStrategyRequest
from ..services.strategy_service import StrategyService

router = APIRouter(prefix="/api/portfolio/strategies", tags=["Strategies"])


@router.get("")
def list_strategies(
    ticker: str | None = Query(default=None, description="Filter by ticker"),
    status: str | None = Query(default=None, description="active, closed, expired"),
    strategyType: str | None = Query(default=None, description="Strategy type"),
    svc: StrategyService = Depends(get_strategy_service),
) -> dict:
    strategies = svc.list_strategies(
        ticker=ticker, status=status, strategy_type=strategyType
    )
    return {
        "status": "ok",
        "strategies": [s.model_dump() for s in strategies],
    }


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: str,
    svc: StrategyService = Depends(get_strategy_service),
) -> dict:
    strategy = svc.get_strategy(strategy_id)
    return {"status": "ok", "strategy": strategy.model_dump()}


@router.post("", status_code=201)
def create_strategy(
    body: CreateStrategyRequest,
    svc: StrategyService = Depends(get_strategy_service),
) -> dict:
    strategy = svc.create_strategy(body.model_dump())
    return {"status": "created", "strategy": strategy.model_dump()}


@router.put("/{strategy_id}")
def update_strategy(
    strategy_id: str,
    body: UpdateStrategyRequest,
    svc: StrategyService = Depends(get_strategy_service),
) -> dict:
    strategy = svc.update_strategy(strategy_id, body.model_dump(exclude_unset=True))
    return {"status": "updated", "strategy": strategy.model_dump()}


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: str,
    svc: StrategyService = Depends(get_strategy_service),
) -> dict:
    return svc.delete_strategy(strategy_id)
