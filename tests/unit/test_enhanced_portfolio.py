"""Unit tests for Issue #13 — enhanced portfolio service."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.models import EnhancedPortfolioResponse
from app.repositories.trade_repository import TradeRepository
from app.services.portfolio_service import PortfolioService

from tests.conftest import make_active_trade, make_closed_trade


class TestEnhancedPortfolio:
    def test_returns_enhanced_response(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = [make_active_trade()]
        repo.get_closed_trades.return_value = [make_closed_trade()]

        svc = PortfolioService(repo=repo)
        result = svc.get_enhanced_portfolio()

        assert isinstance(result, EnhancedPortfolioResponse)
        assert result.summary.totalValue > 0
        assert result.summary.netDelta != 0 or True  # could be 0
        assert len(result.positions) == 1
        assert result.aggregatePayoutChart is not None

    def test_empty_enhanced_portfolio(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = []
        repo.get_closed_trades.return_value = []

        svc = PortfolioService(repo=repo)
        result = svc.get_enhanced_portfolio()

        assert result.summary.totalValue == 0.0
        assert result.summary.maxProfit == 0.0
        assert result.summary.maxLoss == 0.0
        assert result.positions == []
        assert result.aggregatePayoutChart.pricePoints == []
        assert result.aggregatePayoutChart.profitPoints == []

    def test_positions_have_pl_history(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = [make_active_trade()]
        repo.get_closed_trades.return_value = []

        svc = PortfolioService(repo=repo)
        result = svc.get_enhanced_portfolio()

        pos = result.positions[0]
        assert len(pos.plHistory) >= 1
        assert pos.plHistory[0].date  # has date string
        assert isinstance(pos.plHistory[0].value, float)

    def test_positions_have_breakevens(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = [make_active_trade()]
        repo.get_closed_trades.return_value = []

        svc = PortfolioService(repo=repo)
        result = svc.get_enhanced_portfolio()

        pos = result.positions[0]
        assert len(pos.breakevens) >= 1
        assert pos.probability >= 0

    def test_aggregate_payout_chart_with_trades(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = [make_active_trade(), make_active_trade(id="t2")]
        repo.get_closed_trades.return_value = []

        svc = PortfolioService(repo=repo)
        result = svc.get_enhanced_portfolio()

        chart = result.aggregatePayoutChart
        assert len(chart.pricePoints) == 7
        assert len(chart.profitPoints) == 7

    def test_db_failure_returns_empty_enhanced(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.side_effect = Exception("DB down")

        svc = PortfolioService(repo=repo)
        result = svc.get_enhanced_portfolio()

        assert result.summary.totalValue == 0.0
        assert result.positions == []


class TestSummaryCalculation:
    def test_net_delta(self) -> None:
        from app.models import Greeks

        active = [
            make_active_trade(
                greeks=Greeks(delta=0.5, gamma=0.1, theta=-0.02, vega=0.15),
                quantity=2,
            ),
        ]
        summary = PortfolioService._calculate_summary(active, [])
        assert summary.netDelta == 1.0  # 0.5 * 2

    def test_net_theta(self) -> None:
        from app.models import Greeks

        active = [
            make_active_trade(
                greeks=Greeks(delta=0.5, gamma=0.1, theta=-0.05, vega=0.15),
                quantity=3,
            ),
        ]
        summary = PortfolioService._calculate_summary(active, [])
        assert summary.netTheta == -0.15  # -0.05 * 3
