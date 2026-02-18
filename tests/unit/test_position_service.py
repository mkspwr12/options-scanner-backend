"""Unit tests for PositionService and AddPositionRequest schema (Issue #18)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.models import PortfolioPositionRecord
from app.repositories.position_repository import PositionRepository
from app.schemas import AddPositionRequest
from app.services.position_service import PositionService


# ---------------------------------------------------------------------------
# AddPositionRequest schema validation
# ---------------------------------------------------------------------------


class TestAddPositionRequestSchema:
    """Validates Pydantic request schema for add-position."""

    def _valid_payload(self, **overrides) -> dict:
        base = {
            "symbol": "AAPL",
            "strike": 190.0,
            "expiration": "2025-06-20",
            "type": "call",
            "quantity": 1,
            "premium": 5.25,
            "entryDate": "2025-01-15",
        }
        base.update(overrides)
        return base

    def test_valid_request(self) -> None:
        req = AddPositionRequest(**self._valid_payload())
        assert req.symbol == "AAPL"
        assert req.strike == 190.0
        assert req.type == "call"

    def test_symbol_uppercased(self) -> None:
        req = AddPositionRequest(**self._valid_payload(symbol="aapl"))
        assert req.symbol == "AAPL"

    def test_symbol_whitespace_stripped(self) -> None:
        req = AddPositionRequest(**self._valid_payload(symbol="  spy  "))
        assert req.symbol == "SPY"

    def test_type_lowercased(self) -> None:
        req = AddPositionRequest(**self._valid_payload(type="CALL"))
        assert req.type == "call"

    def test_type_put_accepted(self) -> None:
        req = AddPositionRequest(**self._valid_payload(type="PUT"))
        assert req.type == "put"

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(type="straddle"))

    def test_empty_symbol_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(symbol=""))

    def test_symbol_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(symbol="A" * 11))

    def test_strike_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(strike=-1.0))

    def test_strike_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(strike=0))

    def test_premium_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(premium=0))

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AddPositionRequest(**self._valid_payload(quantity=0))

    def test_quantity_defaults_to_one(self) -> None:
        payload = self._valid_payload()
        del payload["quantity"]
        req = AddPositionRequest(**payload)
        assert req.quantity == 1

    def test_invalid_expiration_format(self) -> None:
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            AddPositionRequest(**self._valid_payload(expiration="06-20-2025"))

    def test_invalid_entry_date_format(self) -> None:
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            AddPositionRequest(**self._valid_payload(entryDate="Jan 15, 2025"))

    def test_entry_date_none_accepted(self) -> None:
        payload = self._valid_payload()
        payload["entryDate"] = None
        req = AddPositionRequest(**payload)
        assert req.entryDate is None

    def test_entry_date_missing_defaults_none(self) -> None:
        payload = self._valid_payload()
        del payload["entryDate"]
        req = AddPositionRequest(**payload)
        assert req.entryDate is None


# ---------------------------------------------------------------------------
# PositionService.add_position()
# ---------------------------------------------------------------------------


class TestAddPosition:
    """Tests for PositionService.add_position()."""

    def _make_request(self, **overrides) -> AddPositionRequest:
        base = {
            "symbol": "NVDA",
            "strike": 200.0,
            "expiration": "2025-07-18",
            "type": "call",
            "quantity": 2,
            "premium": 8.50,
            "entryDate": "2025-01-20",
        }
        base.update(overrides)
        return AddPositionRequest(**base)

    def test_returns_success_true(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-abc12345"

        svc = PositionService(repo=repo)
        result = svc.add_position(self._make_request())

        assert result["success"] is True

    def test_position_has_required_fields(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-xyz99999"

        svc = PositionService(repo=repo)
        result = svc.add_position(self._make_request())

        pos = result["position"]
        assert pos["id"] == "pos-xyz99999"
        assert pos["symbol"] == "NVDA"
        assert pos["strike"] == 200.0
        assert pos["expiration"] == "2025-07-18"
        assert pos["type"] == "call"
        assert pos["quantity"] == 2
        assert pos["premium"] == 8.50
        assert pos["entryDate"] == "2025-01-20"
        assert pos["pnl"] == 0

    def test_current_value_calculation(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-calc"

        svc = PositionService(repo=repo)
        # currentValue = premium * quantity * 100 = 8.50 * 2 * 100 = 1700.0
        result = svc.add_position(self._make_request(premium=8.50, quantity=2))

        assert result["position"]["currentValue"] == 1700.0

    def test_current_value_single_contract(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-single"

        svc = PositionService(repo=repo)
        # currentValue = 3.25 * 1 * 100 = 325.0
        result = svc.add_position(self._make_request(premium=3.25, quantity=1))

        assert result["position"]["currentValue"] == 325.0

    def test_entry_date_defaults_to_today(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-today"

        svc = PositionService(repo=repo)
        result = svc.add_position(self._make_request(entryDate=None))

        # Should be a valid YYYY-MM-DD string
        entry = result["position"]["entryDate"]
        assert len(entry) == 10
        assert entry[4] == "-" and entry[7] == "-"

    def test_repo_insert_called_with_correct_data(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-call01"

        svc = PositionService(repo=repo)
        svc.add_position(self._make_request())

        repo.insert.assert_called_once()
        call_data = repo.insert.call_args[0][0]
        assert call_data["symbol"] == "NVDA"
        assert call_data["strike"] == 200.0
        assert call_data["type"] == "call"
        assert call_data["quantity"] == 2
        assert call_data["premium"] == 8.50

    def test_type_uppercase_normalised_to_lower(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-norm"

        svc = PositionService(repo=repo)
        result = svc.add_position(self._make_request(type="PUT"))

        assert result["position"]["type"] == "put"

    def test_created_at_is_iso_string(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.insert.return_value = "pos-ts"

        svc = PositionService(repo=repo)
        result = svc.add_position(self._make_request())

        created = result["position"]["createdAt"]
        assert isinstance(created, str)
        # ISO format contains 'T' separator
        assert "T" in created


# ---------------------------------------------------------------------------
# PositionService.get_positions()
# ---------------------------------------------------------------------------


class TestGetPositions:
    """Tests for PositionService.get_positions()."""

    def test_empty_list_when_no_positions(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.get_all_open.return_value = []

        svc = PositionService(repo=repo)
        result = svc.get_positions()

        assert result["status"] == "ok"
        assert result["positions"] == []
        assert result["count"] == 0

    def test_returns_open_positions(self) -> None:
        pos = PortfolioPositionRecord(
            id="pos-test1",
            symbol="AAPL",
            strike=190.0,
            expiration="2025-06-20",
            type="call",
            quantity=1,
            premium=5.0,
            entryDate="2025-01-15",
            currentValue=500.0,
            pnl=0.0,
            status="open",
            createdAt="2025-01-15T12:00:00",
        )
        repo = MagicMock(spec=PositionRepository)
        repo.get_all_open.return_value = [pos]

        svc = PositionService(repo=repo)
        result = svc.get_positions()

        assert result["count"] == 1
        assert result["positions"][0]["symbol"] == "AAPL"

    def test_graceful_fallback_on_db_error(self) -> None:
        repo = MagicMock(spec=PositionRepository)
        repo.get_all_open.side_effect = Exception("DB unavailable")

        svc = PositionService(repo=repo)
        result = svc.get_positions()

        assert result["status"] == "ok"
        assert result["positions"] == []
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# PositionRepository._row_to_model()
# ---------------------------------------------------------------------------


class TestPositionRepositoryRowToModel:
    """Tests for PositionRepository._row_to_model() conversion."""

    def _make_row_and_desc(self, **overrides):
        """Build a mock pyodbc row + cursor.description for testing."""
        cols = [
            "id", "symbol", "strike", "expiration", "option_type",
            "quantity", "premium", "entry_date", "current_value",
            "pnl", "status", "created_at", "updated_at",
        ]
        values = {
            "id": "pos-test99",
            "symbol": "SPY",
            "strike": 500.0,
            "expiration": "2025-08-15",
            "option_type": "put",
            "quantity": 3,
            "premium": 12.50,
            "entry_date": "2025-02-01",
            "current_value": 3750.0,
            "pnl": 150.0,
            "status": "open",
            "created_at": "2025-02-01 10:00:00",
            "updated_at": "2025-02-01 10:00:00",
        }
        values.update(overrides)

        # Build mock row that behaves like a tuple
        row_values = [values[c] for c in cols]

        class MockRow:
            def __init__(self, vals):
                self._vals = vals

            def __iter__(self):
                return iter(self._vals)

        description = [(c,) for c in cols]
        return MockRow(row_values), description

    def test_basic_conversion(self) -> None:
        row, desc = self._make_row_and_desc()
        model = PositionRepository._row_to_model(row, desc)

        assert model.id == "pos-test99"
        assert model.symbol == "SPY"
        assert model.strike == 500.0
        assert model.type == "put"
        assert model.quantity == 3
        assert model.premium == 12.50
        assert model.currentValue == 3750.0
        assert model.pnl == 150.0
        assert model.status == "open"

    def test_null_current_value_defaults_zero(self) -> None:
        row, desc = self._make_row_and_desc(current_value=None)
        model = PositionRepository._row_to_model(row, desc)
        assert model.currentValue == 0.0

    def test_null_pnl_defaults_zero(self) -> None:
        row, desc = self._make_row_and_desc(pnl=None)
        model = PositionRepository._row_to_model(row, desc)
        assert model.pnl == 0.0
