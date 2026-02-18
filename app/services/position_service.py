"""Position service — business logic for portfolio position management (Issue #18)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..repositories.position_repository import PositionRepository
from ..schemas import AddPositionRequest

logger = logging.getLogger(__name__)


class PositionService:
    """Coordinates position-related business logic."""

    def __init__(self, repo: PositionRepository | None = None) -> None:
        self._repo = repo or PositionRepository()

    def add_position(self, request: AddPositionRequest) -> dict[str, Any]:
        """Add a new portfolio position."""
        entry_date = request.entryDate or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        option_type = request.type.lower()
        current_value = round(request.premium * request.quantity * 100, 2)

        data = {
            "symbol": request.symbol,
            "strike": request.strike,
            "expiration": request.expiration,
            "type": option_type,
            "quantity": request.quantity,
            "premium": request.premium,
            "entryDate": entry_date,
        }

        position_id = self._repo.insert(data)
        now = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Position added: %s %s %.2f %s (%s)",
            request.symbol, option_type, request.strike, request.expiration, position_id,
        )

        return {
            "success": True,
            "position": {
                "id": position_id,
                "symbol": request.symbol,
                "strike": request.strike,
                "expiration": request.expiration,
                "type": option_type,
                "quantity": request.quantity,
                "premium": request.premium,
                "entryDate": entry_date,
                "currentValue": current_value,
                "pnl": 0,
                "createdAt": now,
            },
        }

    def get_positions(self) -> dict[str, Any]:
        """Return all open positions."""
        try:
            positions = self._repo.get_all_open()
        except Exception:
            logger.warning("Positions DB unavailable — returning empty list")
            positions = []

        return {
            "status": "ok",
            "positions": [p.model_dump() for p in positions],
            "count": len(positions),
        }
