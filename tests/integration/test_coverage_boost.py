"""Additional integration tests for coverage: portfolio risk with strategies,
provider CRUD (update/delete/test), strategy update/delete success paths."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.models import Strategy, StrategyLeg


def _make_strategy(**overrides) -> Strategy:
    defaults = dict(
        id="strat-1",
        strategyType="STRADDLE",
        name="Test Straddle",
        ticker="META",
        underlyingPrice=689.30,
        legs=[
            StrategyLeg(
                type="CALL", strike=690.0, expiration="2025-03-28",
                action="BUY", quantity=2,
                delta=0.55, gamma=0.04, theta=-0.03, vega=0.10,
            ),
            StrategyLeg(
                type="PUT", strike=690.0, expiration="2025-03-28",
                action="BUY", quantity=2,
                delta=-0.45, gamma=0.04, theta=-0.03, vega=0.10,
            ),
        ],
        status="active",
    )
    defaults.update(overrides)
    return Strategy(**defaults)


class TestPortfolioRiskWithStrategies:
    """Cover the strategy aggregation and alert logic in portfolio_risk router."""

    def test_risk_strategy_aggregation(
        self, client: TestClient, mock_strategy_repo: MagicMock,
    ) -> None:
        """Strategies with legs should be reflected in aggregate Greeks."""
        mock_strategy_repo.get_all.return_value = [
            {
                "id": "s1",
                "strategy_type": "STRADDLE",
                "name": "Test",
                "ticker": "META",
                "underlying_price": 689.30,
                "status": "active",
                "entry_date": "2025-01-15",
                "exit_date": None,
                "last_updated": "2025-01-15",
                "tags": "",
                "notes": None,
                "legs": [
                    {
                        "id": "leg-1",
                        "type": "CALL",
                        "strike": 690.0,
                        "expiration": "2025-03-28",
                        "action": "BUY",
                        "quantity": 10,
                        "entry_price": 5.0,
                        "current_price": 6.0,
                        "delta": 0.55,
                        "gamma": 0.04,
                        "theta": -0.03,
                        "vega": 0.10,
                        "implied_volatility": 0.30,
                    },
                    {
                        "id": "leg-2",
                        "type": "PUT",
                        "strike": 690.0,
                        "expiration": "2025-03-28",
                        "action": "BUY",
                        "quantity": 10,
                        "entry_price": 4.0,
                        "current_price": 3.5,
                        "delta": -0.45,
                        "gamma": 0.04,
                        "theta": -0.03,
                        "vega": 0.10,
                        "implied_volatility": 0.32,
                    },
                ],
            },
        ]
        resp = client.get("/api/portfolio/risk")
        assert resp.status_code == 200
        data = resp.json()
        # Strategy contributes delta: (0.55*10 + (-0.45)*10) = 1.0
        # Plus trades: 0.42*2 = 0.84
        assert data["strategyCount"] == 1
        assert data["aggregateGreeks"]["delta"] == pytest.approx(1.84, abs=0.1)

    def test_risk_with_sell_leg_strategies(
        self, client: TestClient, mock_strategy_repo: MagicMock,
    ) -> None:
        """SELL legs should negate Greek contributions."""
        mock_strategy_repo.get_all.return_value = [
            {
                "id": "s2",
                "strategy_type": "COVERED_CALL",
                "name": "Covered Call",
                "ticker": "SPY",
                "underlying_price": 500.0,
                "status": "active",
                "entry_date": "2025-01-01",
                "exit_date": None,
                "last_updated": "2025-01-01",
                "tags": "hedge",
                "notes": None,
                "legs": [
                    {
                        "id": "leg-1",
                        "type": "CALL",
                        "strike": 510.0,
                        "expiration": "2025-04-18",
                        "action": "SELL",
                        "quantity": 5,
                        "entry_price": 3.0,
                        "current_price": 2.0,
                        "delta": 0.30,
                        "gamma": 0.02,
                        "theta": -0.01,
                        "vega": 0.05,
                        "implied_volatility": 0.20,
                    },
                ],
            },
        ]
        resp = client.get("/api/portfolio/risk")
        assert resp.status_code == 200
        data = resp.json()
        # SELL: delta contribution = -0.30 * 5 * -1 = -1.5 wait no:
        # m = -1 for SELL, delta = 0.30 * 5 * -1 = -1.5
        # Total = trades (0.84) + strategy (-1.5) = -0.66
        assert abs(data["aggregateGreeks"]["delta"]) < 1

    def test_risk_group_by_with_strategies(
        self, client: TestClient, mock_strategy_repo: MagicMock,
    ) -> None:
        """groupBy=symbol should include strategy positions."""
        mock_strategy_repo.get_all.return_value = [
            {
                "id": "s3",
                "strategy_type": "CUSTOM",
                "name": "SPY Custom",
                "ticker": "SPY",
                "underlying_price": 500.0,
                "status": "active",
                "entry_date": "2025-01-01",
                "exit_date": None,
                "last_updated": "2025-01-01",
                "tags": "",
                "notes": None,
                "legs": [
                    {
                        "id": "leg-1",
                        "type": "CALL",
                        "strike": 505.0,
                        "expiration": "2025-04-18",
                        "action": "BUY",
                        "quantity": 1,
                        "entry_price": None,
                        "current_price": None,
                        "delta": 0.50,
                        "gamma": None,
                        "theta": None,
                        "vega": None,
                        "implied_volatility": None,
                    },
                ],
            },
        ]
        resp = client.get("/api/portfolio/risk?groupBy=symbol")
        assert resp.status_code == 200
        data = resp.json()
        assert data["groups"] is not None
        symbols = [g["symbol"] for g in data["groups"]]
        assert "META" in symbols  # from trade fixtures
        assert "SPY" in symbols  # from strategy


class TestProviderCRUDIntegration:
    """Cover update/delete/test success paths in the provider router."""

    def test_update_provider(
        self, client: TestClient, mock_provider_repo: MagicMock,
    ) -> None:
        mock_provider_repo.get_by_id.return_value = {
            "id": "p1",
            "name": "Updated",
            "type": "YAHOO_FINANCE",
            "base_url": "",
            "enabled": True,
            "priority": 1,
        }
        resp = client.put("/api/providers/p1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_delete_provider(
        self, client: TestClient, mock_provider_repo: MagicMock,
    ) -> None:
        mock_provider_repo.get_by_id.return_value = {
            "id": "p1",
            "name": "Old",
            "type": "YAHOO_FINANCE",
        }
        # Return 2 providers so the last-provider guard doesn't trigger
        mock_provider_repo.get_all.return_value = [
            {"id": "p1", "name": "Old", "type": "YAHOO_FINANCE"},
            {"id": "p2", "name": "Other", "type": "YAHOO_FINANCE"},
        ]
        resp = client.delete("/api/providers/p1")
        assert resp.status_code == 204

    def test_test_connection(
        self, client: TestClient, mock_provider_repo: MagicMock,
    ) -> None:
        mock_provider_repo.get_by_id.return_value = {
            "id": "p1",
            "type": "CUSTOM",
        }
        resp = client.post("/api/providers/p1/test")
        assert resp.status_code == 200
        data = resp.json()
        # CUSTOM type is not implemented, so connection test fails
        assert data["result"]["success"] is False


class TestStrategyUpdateDelete:
    """Cover update/delete success paths in strategy router."""

    def _row(self) -> dict:
        return {
            "id": "strat-abc",
            "strategy_type": "CUSTOM",
            "name": "Old",
            "ticker": "META",
            "underlying_price": 689.30,
            "status": "active",
            "entry_date": "2025-01-15T00:00:00",
            "exit_date": None,
            "last_updated": "2025-01-15T00:00:00",
            "tags": "",
            "notes": None,
            "legs": [],
        }

    def test_update_strategy(
        self, client: TestClient, mock_strategy_repo: MagicMock,
    ) -> None:
        mock_strategy_repo.get_by_id.return_value = self._row()
        resp = client.put("/api/portfolio/strategies/strat-abc", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
