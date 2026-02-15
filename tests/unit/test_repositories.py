"""Unit tests for repository row-to-model conversion methods.

Covers:
- ScanRepository._row_to_model() with various data shapes
- TradeRepository._row_to_model() for active and closed trades
- Null/missing field handling
"""
from __future__ import annotations

import os

os.environ.setdefault("SQL_CONNECTION_STRING", "Server=test;Database=test;")

from app.repositories.scan_repository import ScanRepository
from app.repositories.trade_repository import TradeRepository


class TestScanRepositoryRowToModel:
    """Tests for ScanRepository._row_to_model()."""

    def _make_row(self, **overrides) -> dict:
        defaults = {
            "id": "opp-test-001",
            "symbol": "AAPL",
            "strike_price": 150.0,
            "expiration_date": "2025-03-15",
            "option_type": "CALL",
            "current_price": 5.5,
            "underlying_price": 155.0,
            "implied_volatility": 0.28,
            "delta": 0.45,
            "gamma": 0.08,
            "theta": -0.03,
            "vega": 0.12,
            "potential_gain": 11.0,
            "potential_loss": 5.5,
            "risk_reward_ratio": 2.0,
            "confidence_score": 82.0,
            "scan_timestamp": 1700000000000,
        }
        defaults.update(overrides)
        return defaults

    def test_basic_conversion(self) -> None:
        row = self._make_row()
        model = ScanRepository._row_to_model(row)
        assert model.id == "opp-test-001"
        assert model.symbol == "AAPL"
        assert model.strikePrice == 150.0
        assert model.optionType == "CALL"
        assert model.confidenceScore == 82.0

    def test_greeks_populated(self) -> None:
        row = self._make_row(delta=0.65, gamma=0.10, theta=-0.04, vega=0.15)
        model = ScanRepository._row_to_model(row)
        assert model.greeks.delta == 0.65
        assert model.greeks.gamma == 0.10
        assert model.greeks.theta == -0.04
        assert model.greeks.vega == 0.15

    def test_null_fields_default_to_zero(self) -> None:
        row = self._make_row(
            current_price=None,
            underlying_price=None,
            implied_volatility=None,
            delta=None,
            gamma=None,
            theta=None,
            vega=None,
            potential_gain=None,
            potential_loss=None,
            risk_reward_ratio=None,
            confidence_score=None,
            scan_timestamp=None,
        )
        model = ScanRepository._row_to_model(row)
        assert model.currentPrice == 0.0
        assert model.underlyingPrice == 0.0
        assert model.greeks.delta == 0.0
        assert model.timestamp == 0

    def test_string_numeric_coercion(self) -> None:
        """Database might return Decimal or string — floats should still work."""
        from decimal import Decimal

        row = self._make_row(strike_price=Decimal("150.50"), confidence_score=Decimal("75"))
        model = ScanRepository._row_to_model(row)
        assert model.strikePrice == 150.50
        assert model.confidenceScore == 75.0


class TestTradeRepositoryRowToModel:
    """Tests for TradeRepository._row_to_model()."""

    def _make_description(self, col_names: list[str]) -> list[tuple[str, ...]]:
        """Simulate pyodbc cursor.description format."""
        return [(name,) for name in col_names]

    def _standard_columns(self) -> list[str]:
        return [
            "id", "opportunity_id", "symbol", "strike_price",
            "expiration_date", "option_type", "entry_price", "current_price",
            "quantity", "underlying_price", "delta", "gamma", "theta", "vega",
            "entry_date", "status", "exit_price", "exit_date", "created_at",
            "updated_at",
        ]

    def _make_active_row(self, **overrides):
        """Return a tuple-like row for an active trade."""
        cols = self._standard_columns()
        data = {
            "id": "trade-test-001",
            "opportunity_id": "opp-001",
            "symbol": "MSFT",
            "strike_price": 400.0,
            "expiration_date": "2025-04-01",
            "option_type": "CALL",
            "entry_price": 8.0,
            "current_price": 10.0,
            "quantity": 3,
            "underlying_price": 405.0,
            "delta": 0.55,
            "gamma": 0.07,
            "theta": -0.02,
            "vega": 0.14,
            "entry_date": 1700000000000,
            "status": "active",
            "exit_price": None,
            "exit_date": None,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": None,
        }
        data.update(overrides)
        return tuple(data[c] for c in cols)

    def _make_closed_row(self, **overrides):
        """Return a tuple-like row for a closed trade."""
        base = {
            "id": "trade-test-002",
            "opportunity_id": "opp-002",
            "symbol": "GOOGL",
            "strike_price": 180.0,
            "expiration_date": "2025-03-15",
            "option_type": "PUT",
            "entry_price": 4.0,
            "current_price": 4.0,
            "quantity": 2,
            "underlying_price": 178.0,
            "delta": -0.40,
            "gamma": 0.05,
            "theta": -0.01,
            "vega": 0.09,
            "entry_date": 1700000000000,
            "status": "closed",
            "exit_price": 6.5,
            "exit_date": 1700100000000,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-02T00:00:00",
        }
        base.update(overrides)
        cols = self._standard_columns()
        return tuple(base[c] for c in cols)

    def test_active_trade_model(self) -> None:
        row = self._make_active_row()
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)

        assert model.id == "trade-test-001"
        assert model.symbol == "MSFT"
        assert model.status == "active"
        assert not hasattr(model, "exitPrice") or model.status == "active"

    def test_active_trade_unrealized_pl(self) -> None:
        # entry=8.0, current=10.0, qty=3 → (10-8)*3*100 = 600
        row = self._make_active_row(entry_price=8.0, current_price=10.0, quantity=3)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.unrealizedPL == 600.0

    def test_active_trade_unrealized_pl_percent(self) -> None:
        # entry=8.0, current=10.0 → ((10-8)/8)*100 = 25%
        row = self._make_active_row(entry_price=8.0, current_price=10.0)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.unrealizedPLPercent == 25.0

    def test_closed_trade_model(self) -> None:
        row = self._make_closed_row()
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)

        from app.models import ClosedTrade
        assert isinstance(model, ClosedTrade)
        assert model.status == "closed"
        assert model.exitPrice == 6.5
        assert model.exitDate == 1700100000000

    def test_closed_trade_realized_pl(self) -> None:
        # entry=4.0, exit=6.5, qty=2 → (6.5-4.0)*2*100 = 500
        row = self._make_closed_row(entry_price=4.0, exit_price=6.5, quantity=2)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.realizedPL == 500.0

    def test_closed_trade_realized_pl_percent(self) -> None:
        # entry=4.0, exit=6.5 → ((6.5-4.0)/4.0)*100 = 62.5%
        row = self._make_closed_row(entry_price=4.0, exit_price=6.5)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.realizedPLPercent == 62.5

    def test_greeks_from_trade_row(self) -> None:
        row = self._make_active_row(delta=0.55, gamma=0.07, theta=-0.02, vega=0.14)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.greeks.delta == 0.55
        assert model.greeks.gamma == 0.07

    def test_null_greeks_default_to_zero(self) -> None:
        row = self._make_active_row(delta=None, gamma=None, theta=None, vega=None)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.greeks.delta == 0.0
        assert model.greeks.gamma == 0.0

    def test_null_exit_fields_on_closed(self) -> None:
        row = self._make_closed_row(exit_price=None, exit_date=None)
        desc = self._make_description(self._standard_columns())
        model = TradeRepository._row_to_model(row, desc)
        assert model.exitPrice == 0.0
        assert model.exitDate == 0

    def test_zero_entry_price_no_division_error(self) -> None:
        """When entry_price is 0, PL percent calculations should not crash."""
        row = self._make_active_row(entry_price=0.0, current_price=5.0)
        desc = self._make_description(self._standard_columns())
        # Should not raise ZeroDivisionError
        model = TradeRepository._row_to_model(row, desc)
        assert model.unrealizedPLPercent == 0.0
