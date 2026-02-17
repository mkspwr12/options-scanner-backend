"""Portfolio actions router — close, roll, and adjust positions (Issue #14)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_position_action_service
from ..schemas import AdjustPositionRequest, ClosePositionRequest, RollPositionRequest
from ..services.position_action_service import PositionActionService

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio Actions"])


@router.post("/close-position")
def close_position(
    request: ClosePositionRequest,
    svc: PositionActionService = Depends(get_position_action_service),
) -> dict:
    """Close an open position with P&L calculation."""
    return svc.close_position(request)


@router.post("/roll-position")
def roll_position(
    request: RollPositionRequest,
    svc: PositionActionService = Depends(get_position_action_service),
) -> dict:
    """Roll a position to a new expiration."""
    return svc.roll_position(request)


@router.post("/adjust-position")
def adjust_position(
    request: AdjustPositionRequest,
    svc: PositionActionService = Depends(get_position_action_service),
) -> dict:
    """Adjust a position (add protective legs, reduce size, etc.)."""
    return svc.adjust_position(request)
