"""Portfolio service — aggregates trade data into portfolio metrics."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..models import (
    ClosedTrade,
    EnhancedPortfolioResponse,
    Greeks,
    PayoutChart,
    PLHistoryEntry,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioResponse,
    PortfolioSummary,
    PositionLeg,
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

    def get_enhanced_portfolio(self) -> EnhancedPortfolioResponse:
        """Build the enhanced portfolio response (Issue #13).

        Returns summary, positions with P&L history, and aggregate
        payout chart.  Falls back to empty portfolio on DB errors.
        """
        try:
            active_trades: list[TrackedTrade] = self._repo.get_active_trades()
            closed_trades: list[ClosedTrade] = self._repo.get_closed_trades()
        except Exception:
            logger.warning("Portfolio DB unavailable — returning empty enhanced portfolio")
            active_trades = []
            closed_trades = []

        summary = self._calculate_summary(active_trades, closed_trades)
        positions = self._build_positions(active_trades)
        agg_chart = self._build_aggregate_payout_chart(active_trades)

        return EnhancedPortfolioResponse(
            summary=summary,
            positions=positions,
            aggregatePayoutChart=agg_chart,
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

    @staticmethod
    def _calculate_summary(
        active: list[TrackedTrade],
        closed: list[ClosedTrade],
    ) -> PortfolioSummary:
        """Build the portfolio-level summary (Issue #13)."""
        total_value = sum(t.currentPrice * t.quantity * 100 for t in active)
        unrealized_pl = sum(t.unrealizedPL for t in active)
        realized_pl = sum(t.realizedPL for t in closed)
        total_pl = unrealized_pl + realized_pl

        total_invested = sum(t.entryPrice * t.quantity * 100 for t in active) + sum(
            t.entryPrice * t.quantity * 100 for t in closed
        )
        total_pl_pct = (total_pl / total_invested * 100) if total_invested else 0.0

        # Aggregate max profit/loss from positions
        max_profit = sum(t.currentPrice * t.quantity * 100 for t in active)
        max_loss = sum(-t.entryPrice * t.quantity * 100 for t in active)

        net_delta = sum(t.greeks.delta * t.quantity for t in active)
        net_theta = sum(t.greeks.theta * t.quantity for t in active)

        return PortfolioSummary(
            totalValue=round(total_value, 2),
            totalPL=round(total_pl, 2),
            totalPLPercent=round(total_pl_pct, 2),
            maxProfit=round(max_profit, 2),
            maxLoss=round(max_loss, 2),
            netDelta=round(net_delta, 4),
            netTheta=round(net_theta, 4),
        )

    @staticmethod
    def _build_positions(active: list[TrackedTrade]) -> list[PortfolioPosition]:
        """Convert active trades to enriched portfolio positions."""
        positions: list[PortfolioPosition] = []
        now = datetime.now(timezone.utc)

        for t in active:
            # Days to expiration
            try:
                exp = datetime.strptime(t.expirationDate, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                dte = max((exp - now).days, 0)
            except Exception:
                dte = 0

            # Simulate 30-day P&L history (daily snapshots)
            pl_history = PortfolioService._generate_pl_history(
                entry_price=t.entryPrice,
                current_price=t.currentPrice,
                quantity=t.quantity,
                entry_date_ms=t.entryDate,
            )

            # Position leg (single-leg for now)
            leg_type = f"long_{t.optionType.lower()}"
            legs = [PositionLeg(type=leg_type, strike=t.strikePrice, quantity=t.quantity)]

            # Breakeven
            if t.optionType.upper() == "CALL":
                breakeven = round(t.strikePrice + t.entryPrice, 2)
            else:
                breakeven = round(t.strikePrice - t.entryPrice, 2)

            entry_value = t.entryPrice * t.quantity * 100
            current_value = t.currentPrice * t.quantity * 100

            positions.append(
                PortfolioPosition(
                    id=t.id,
                    ticker=t.symbol,
                    strategy=f"long_{t.optionType.lower()}",
                    legs=legs,
                    openDate=datetime.fromtimestamp(
                        t.entryDate / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d"),
                    expiration=t.expirationDate,
                    dte=dte,
                    entryPrice=round(entry_value, 2),
                    currentValue=round(current_value, 2),
                    unrealizedPL=round(t.unrealizedPL, 2),
                    unrealizedPLPercent=round(t.unrealizedPLPercent, 2),
                    maxProfit=round(current_value, 2),
                    maxLoss=round(-entry_value, 2),
                    breakevens=[breakeven],
                    probability=round(abs(t.greeks.delta) * 100, 1),
                    plHistory=pl_history,
                )
            )

        return positions

    @staticmethod
    def _generate_pl_history(
        entry_price: float,
        current_price: float,
        quantity: int,
        entry_date_ms: int,
        days: int = 30,
    ) -> list[PLHistoryEntry]:
        """Generate synthetic 30-day P&L history via linear interpolation."""
        now = datetime.now(timezone.utc)
        try:
            entry_dt = datetime.fromtimestamp(entry_date_ms / 1000, tz=timezone.utc)
        except Exception:
            entry_dt = now - timedelta(days=days)

        actual_days = max((now - entry_dt).days, 1)
        num_points = min(actual_days, days)
        if num_points < 1:
            num_points = 1

        entry_val = entry_price * quantity * 100
        current_val = current_price * quantity * 100

        history: list[PLHistoryEntry] = []
        for i in range(num_points):
            frac = i / max(num_points - 1, 1)
            val = entry_val + (current_val - entry_val) * frac
            date = entry_dt + timedelta(days=i)
            history.append(
                PLHistoryEntry(date=date.strftime("%Y-%m-%d"), value=round(val, 2))
            )

        return history

    @staticmethod
    def _build_aggregate_payout_chart(
        active: list[TrackedTrade],
    ) -> PayoutChart:
        """Build combined portfolio payoff curve."""
        if not active:
            return PayoutChart(pricePoints=[], profitPoints=[])

        # Find price range across all positions
        prices = [t.underlyingPrice for t in active]
        min_price = min(prices) * 0.85
        max_price = max(prices) * 1.15
        num_points = 7
        step = (max_price - min_price) / (num_points - 1) if num_points > 1 else 0
        price_points = [round(min_price + i * step, 2) for i in range(num_points)]

        profit_points = [0.0] * num_points
        for t in active:
            premium = t.entryPrice
            for i, p in enumerate(price_points):
                if t.optionType.upper() == "CALL":
                    intrinsic = max(p - t.strikePrice, 0)
                else:
                    intrinsic = max(t.strikePrice - p, 0)
                pnl = (intrinsic - premium) * t.quantity * 100
                profit_points[i] += pnl

        profit_points = [round(v, 2) for v in profit_points]
        return PayoutChart(pricePoints=price_points, profitPoints=profit_points)
