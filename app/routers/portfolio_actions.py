"""Portfolio actions router — close, roll, adjust, and add positions (#14, #18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_position_action_service, get_position_service
from ..schemas import (
    AddPositionRequest,
    AdjustPositionRequest,
    ClosePositionRequest,
    RollPositionRequest,
)
from ..services.position_action_service import PositionActionService
from ..services.position_service import PositionService

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


@router.post("/add-position", status_code=201)
def add_position(
    request: AddPositionRequest,
    svc: PositionService = Depends(get_position_service),
) -> dict:
    """Add a new portfolio position (Track button from scanner)."""
    return svc.add_position(request)


@router.get("/positions")
def list_positions(
    svc: PositionService = Depends(get_position_service),
) -> dict:
    """List all open portfolio positions."""
    return svc.get_positions()
