"""Trade service — business logic for trade tracking."""
from __future__ import annotations

import logging
from typing import Any

from ..repositories.trade_repository import TradeRepository
from ..schemas import CloseTradeRequest, TrackTradeRequest

logger = logging.getLogger(__name__)


class TradeService:
    """Coordinates trade-related business logic."""

    def __init__(self, repo: TradeRepository | None = None) -> None:
        self._repo = repo or TradeRepository()

    def track_trade(self, request: TrackTradeRequest) -> dict[str, Any]:
        """Create a new tracked trade position."""
        data = request.model_dump()
        # Flatten greeks for repo
        data["greeks"] = {
            "delta": request.greeks.delta,
            "gamma": request.greeks.gamma,
            "theta": request.greeks.theta,
            "vega": request.greeks.vega,
        }
        trade_id = self._repo.insert(data)
        logger.info("Trade tracked: %s %s (%s)", request.symbol, request.optionType, trade_id)
        return {
            "status": "ok",
            "tradeId": trade_id,
            "message": f"Trade tracked: {request.symbol} {request.optionType}",
        }

    def close_trade(self, request: CloseTradeRequest) -> dict[str, Any]:
        """Close an existing trade position."""
        result = self._repo.close_trade(request.tradeId, request.exitPrice)
        logger.info(
            "Trade closed: %s @ $%.2f (P/L: $%.2f)",
            request.tradeId, request.exitPrice, result["realizedPL"],
        )
        return {
            "status": "ok",
            "tradeId": result["tradeId"],
            "realizedPL": result["realizedPL"],
            "message": f"Trade closed with P/L: ${result['realizedPL']:.2f}",
        }

    def get_trade(self, trade_id: str) -> dict[str, Any]:
        """Retrieve a single trade by ID."""
        trade = self._repo.get_by_id(trade_id)
        return trade.model_dump()
