"""Portfolio service — aggregates trade data into portfolio metrics."""
from __future__ import annotations

import logging

from ..models import (
    ClosedTrade,
    Greeks,
    PortfolioMetrics,
    PortfolioResponse,
    TrackedTrade,
)
from ..repositories.trade_repository import TradeRepository

logger = logging.getLogger(__name__)


class PortfolioService:
    """Calculates portfolio metrics from persisted trade data."""

    def __init__(self, repo: TradeRepository | None = None) -> None:
        self._repo = repo or TradeRepository()

    def get_portfolio(self) -> PortfolioResponse:
        """Build the full portfolio response from real trade data.

        Returns an empty portfolio when the database is unavailable so
        downstream consumers always receive a valid response shape.
        """
        try:
            active_trades: list[TrackedTrade] = self._repo.get_active_trades()
            closed_trades: list[ClosedTrade] = self._repo.get_closed_trades()
        except Exception:
            logger.warning("Portfolio DB unavailable — returning empty portfolio")
            active_trades = []
            closed_trades = []

        metrics = self._calculate_metrics(active_trades, closed_trades)
        return PortfolioResponse(
            metrics=metrics,
            activeTrades=active_trades,
            closedTrades=closed_trades,
        )

    # ------------------------------------------------------------------
    # Calculation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_metrics(
        active: list[TrackedTrade],
        closed: list[ClosedTrade],
    ) -> PortfolioMetrics:
        total_value = sum(t.currentPrice * t.quantity * 100 for t in active)
        unrealized_pl = sum(t.unrealizedPL for t in active)
        realized_pl = sum(t.realizedPL for t in closed)
        total_pl = unrealized_pl + realized_pl

        total_invested = sum(t.entryPrice * t.quantity * 100 for t in active) + sum(
            t.entryPrice * t.quantity * 100 for t in closed
        )
        total_pl_pct = (total_pl / total_invested * 100) if total_invested else 0.0

        wins = sum(1 for t in closed if t.realizedPL > 0)
        win_rate = (wins / len(closed) * 100) if closed else 0.0

        agg_delta = sum(t.greeks.delta * t.quantity for t in active)
        agg_gamma = sum(t.greeks.gamma * t.quantity for t in active)
        agg_theta = sum(t.greeks.theta * t.quantity for t in active)
        agg_vega = sum(t.greeks.vega * t.quantity for t in active)

        return PortfolioMetrics(
            totalValue=round(total_value, 2),
            totalPL=round(total_pl, 2),
            totalPLPercent=round(total_pl_pct, 2),
            winRate=round(win_rate, 2),
            totalTrades=len(active) + len(closed),
            activeTrades=len(active),
            aggregateGreeks=Greeks(
                delta=round(agg_delta, 4),
                gamma=round(agg_gamma, 4),
                theta=round(agg_theta, 4),
                vega=round(agg_vega, 4),
            ),
        )
