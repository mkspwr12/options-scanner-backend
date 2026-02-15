"""Unit tests for PortfolioService."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.repositories.trade_repository import TradeRepository
from app.services.portfolio_service import PortfolioService

from tests.conftest import make_active_trade, make_closed_trade


class TestGetPortfolio:
    def test_returns_portfolio_response(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = [make_active_trade()]
        repo.get_closed_trades.return_value = [make_closed_trade()]

        svc = PortfolioService(repo=repo)
        result = svc.get_portfolio()

        assert result.metrics.totalTrades == 2
        assert result.metrics.activeTrades == 1
        assert len(result.activeTrades) == 1
        assert len(result.closedTrades) == 1

    def test_empty_portfolio(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_active_trades.return_value = []
        repo.get_closed_trades.return_value = []

        svc = PortfolioService(repo=repo)
        result = svc.get_portfolio()

        assert result.metrics.totalTrades == 0
        assert result.metrics.totalValue == 0.0
        assert result.metrics.winRate == 0.0


class TestCalculateMetrics:
    def test_win_rate_calculation(self) -> None:
        active = []
        closed = [
            make_closed_trade(realizedPL=100.0),
            make_closed_trade(id="t2", realizedPL=-50.0),
            make_closed_trade(id="t3", realizedPL=75.0),
        ]
        metrics = PortfolioService._calculate_metrics(active, closed)
        # 2 wins out of 3
        assert round(metrics.winRate, 1) == 66.7

    def test_total_value_from_active_trades(self) -> None:
        active = [
            make_active_trade(currentPrice=10.0, quantity=1),  # 10 * 1 * 100 = 1000
            make_active_trade(id="t2", currentPrice=5.0, quantity=3),  # 5 * 3 * 100 = 1500
        ]
        metrics = PortfolioService._calculate_metrics(active, [])
        assert metrics.totalValue == 2500.0

    def test_aggregate_greeks(self) -> None:
        from app.models import Greeks

        active = [
            make_active_trade(
                greeks=Greeks(delta=0.5, gamma=0.1, theta=-0.02, vega=0.15),
                quantity=2,
            ),
        ]
        metrics = PortfolioService._calculate_metrics(active, [])
        assert metrics.aggregateGreeks.delta == 1.0  # 0.5 * 2
        assert metrics.aggregateGreeks.gamma == 0.2  # 0.1 * 2
