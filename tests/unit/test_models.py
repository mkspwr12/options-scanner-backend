"""Unit tests for Pydantic response models."""
from __future__ import annotations

from app.models import (
    ClosedTrade,
    Greeks,
    OptionOpportunity,
    MultiLegOpportunity,
    PortfolioMetrics,
    PortfolioResponse,
    TrackedTrade,
)


class TestGreeks:
    def test_create_greeks(self) -> None:
        g = Greeks(delta=0.5, gamma=0.1, theta=-0.02, vega=0.15)
        assert g.delta == 0.5
        assert g.gamma == 0.1
        assert g.theta == -0.02
        assert g.vega == 0.15

    def test_greeks_serialise(self) -> None:
        g = Greeks(delta=0.5, gamma=0.1, theta=-0.02, vega=0.15)
        d = g.model_dump()
        assert d == {"delta": 0.5, "gamma": 0.1, "theta": -0.02, "vega": 0.15}


class TestTrackedTrade:
    def test_create_tracked_trade(self) -> None:
        t = TrackedTrade(
            id="t1",
            opportunityId="o1",
            symbol="AAPL",
            strikePrice=150.0,
            expirationDate="2025-03-01",
            optionType="CALL",
            entryPrice=3.0,
            currentPrice=4.0,
            quantity=1,
            underlyingPrice=155.0,
            greeks=Greeks(delta=0.5, gamma=0.1, theta=-0.02, vega=0.15),
            entryDate=1_700_000_000_000,
            unrealizedPL=100.0,
            unrealizedPLPercent=33.33,
            status="active",
        )
        assert t.symbol == "AAPL"
        assert t.status == "active"

    def test_closed_trade_inherits_tracked(self) -> None:
        c = ClosedTrade(
            id="t2",
            opportunityId="o2",
            symbol="SPY",
            strikePrice=400.0,
            expirationDate="2025-03-01",
            optionType="PUT",
            entryPrice=5.0,
            currentPrice=5.0,
            quantity=2,
            underlyingPrice=398.0,
            greeks=Greeks(delta=-0.4, gamma=0.05, theta=-0.01, vega=0.1),
            entryDate=1_700_000_000_000,
            unrealizedPL=0.0,
            unrealizedPLPercent=0.0,
            status="closed",
            exitPrice=6.0,
            exitDate=1_700_086_400_000,
            realizedPL=200.0,
            realizedPLPercent=20.0,
        )
        assert c.status == "closed"
        assert c.exitPrice == 6.0
        assert c.realizedPL == 200.0


class TestOptionOpportunity:
    def test_create(self) -> None:
        o = OptionOpportunity(
            id="opp-1",
            symbol="META",
            strikePrice=690.0,
            expirationDate="2025-03-01",
            optionType="CALL",
            currentPrice=6.9,
            underlyingPrice=689.3,
            impliedVolatility=0.31,
            greeks=Greeks(delta=0.42, gamma=0.06, theta=-0.03, vega=0.12),
            potentialGain=13.8,
            potentialLoss=4.9,
            riskRewardRatio=2.81,
            confidenceScore=78,
            timestamp=1_700_000_000_000,
        )
        assert o.riskRewardRatio == 2.81
        assert o.confidenceScore == 78


class TestPortfolioResponse:
    def test_create_portfolio_response(self) -> None:
        metrics = PortfolioMetrics(
            totalValue=10_000.0,
            totalPL=500.0,
            totalPLPercent=5.0,
            winRate=60.0,
            totalTrades=10,
            activeTrades=3,
            aggregateGreeks=Greeks(delta=0.3, gamma=0.07, theta=-0.1, vega=0.2),
        )
        resp = PortfolioResponse(metrics=metrics, activeTrades=[], closedTrades=[])
        assert resp.metrics.totalValue == 10_000.0
        assert resp.activeTrades == []
