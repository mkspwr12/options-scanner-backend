"""Unit tests for new Pydantic models and schemas added in Phases 1-5."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    ConnectionTestResult,
    ProviderConfig,
    RateLimitConfig,
    RiskAlert,
    Strategy,
    StrategyLeg,
    StrategyMetrics,
)
from app.schemas import (
    CreateProviderRequest,
    CreateStrategyRequest,
    StrategyLegInput,
    ConnectionTestInput,
    UpdateProviderRequest,
    UpdateStrategyRequest,
)


class TestProviderModels:
    def test_provider_config_defaults(self) -> None:
        pc = ProviderConfig(id="p1", name="Test", type="YAHOO_FINANCE")
        assert pc.enabled is True
        assert pc.priority == 1
        assert pc.rateLimit.maxPerHour == 2000

    def test_rate_limit_config(self) -> None:
        rlc = RateLimitConfig(maxPerHour=500, costPerCall=0.01)
        assert rlc.maxPerDay == 20000
        assert rlc.costPerCall == 0.01

    def test_connection_test_result(self) -> None:
        ctr = ConnectionTestResult(success=True, latencyMs=42, message="OK")
        assert ctr.success is True
        assert ctr.error is None


class TestStrategyModels:
    def test_strategy_leg(self) -> None:
        leg = StrategyLeg(
            type="CALL", strike=100.0, expiration="2025-03-01",
            action="BUY", quantity=1,
        )
        assert leg.delta is None

    def test_strategy_full(self) -> None:
        s = Strategy(
            id="s1", strategyType="STRADDLE", ticker="META",
            legs=[
                StrategyLeg(type="CALL", strike=690, expiration="2025-03-01", action="BUY", quantity=1),
                StrategyLeg(type="PUT", strike=690, expiration="2025-03-01", action="BUY", quantity=1),
            ],
        )
        assert len(s.legs) == 2
        assert s.status == "active"

    def test_strategy_metrics(self) -> None:
        sm = StrategyMetrics(maxProfit=500, maxLoss=200, riskReward=2.5)
        assert sm.netDebit is None

    def test_risk_alert(self) -> None:
        ra = RiskAlert(
            severity="warning", metric="delta",
            threshold=100.0, currentValue=150.0,
            message="Delta too high",
        )
        assert ra.severity == "warning"


class TestProviderSchemas:
    def test_create_provider_valid(self) -> None:
        req = CreateProviderRequest(name="Yahoo", type="YAHOO_FINANCE")
        assert req.priority == 1

    def test_create_provider_missing_name(self) -> None:
        with pytest.raises(ValidationError):
            CreateProviderRequest(type="YAHOO_FINANCE")  # name is required

    def test_update_provider_partial(self) -> None:
        req = UpdateProviderRequest(name="Updated")
        assert req.enabled is None

    def test_test_connection_empty(self) -> None:
        req = ConnectionTestInput()
        assert req.type is None


class TestStrategySchemas:
    def test_create_strategy_valid(self) -> None:
        req = CreateStrategyRequest(
            strategyType="IRON_CONDOR",
            ticker="spy",
            legs=[
                StrategyLegInput(type="CALL", strike=500, expiration="2025-04-18", action="SELL", quantity=1),
                StrategyLegInput(type="CALL", strike=510, expiration="2025-04-18", action="BUY", quantity=1),
            ],
        )
        assert req.ticker == "SPY"  # auto-uppercased

    def test_create_strategy_missing_legs(self) -> None:
        with pytest.raises(ValidationError):
            CreateStrategyRequest(strategyType="CUSTOM", ticker="META", legs=[])

    def test_update_strategy_status(self) -> None:
        req = UpdateStrategyRequest(status="closed")
        assert req.name is None

    def test_leg_input_lowercase_accepted(self) -> None:
        leg = StrategyLegInput(
            type="call", strike=100, expiration="2025-03-01",
            action="buy", quantity=1,
        )
        assert leg.type == "call"
