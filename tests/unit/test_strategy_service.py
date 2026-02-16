"""Unit tests for StrategyService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.exceptions import AppError, NotFoundError
from app.repositories.strategy_repository import StrategyRepository
from app.services.strategy_service import StrategyService


@pytest.fixture()
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=StrategyRepository)
    repo.get_all.return_value = []
    repo.get_by_id.return_value = None
    repo.insert.return_value = None
    repo.update.return_value = None
    repo.delete.return_value = None
    return repo


@pytest.fixture()
def svc(mock_repo: MagicMock) -> StrategyService:
    return StrategyService(repo=mock_repo)


def _sample_row():
    return {
        "id": "strat-abc",
        "strategy_type": "BULL_CALL_SPREAD",
        "name": "Test Spread",
        "ticker": "META",
        "underlying_price": 689.30,
        "status": "active",
        "entry_date": "2025-01-15T00:00:00",
        "exit_date": None,
        "last_updated": "2025-01-15T00:00:00",
        "tags": "earnings,weekly",
        "notes": None,
        "legs": [
            {
                "id": "leg-1",
                "type": "CALL",
                "strike": 680.0,
                "expiration": "2025-02-28",
                "action": "BUY",
                "quantity": 1,
                "entry_price": 8.5,
                "current_price": 10.0,
                "delta": 0.6,
                "gamma": 0.04,
                "theta": -0.02,
                "vega": 0.10,
                "implied_volatility": 0.30,
            },
            {
                "id": "leg-2",
                "type": "CALL",
                "strike": 700.0,
                "expiration": "2025-02-28",
                "action": "SELL",
                "quantity": 1,
                "entry_price": 3.0,
                "current_price": 2.0,
                "delta": 0.35,
                "gamma": 0.03,
                "theta": -0.01,
                "vega": 0.08,
                "implied_volatility": 0.28,
            },
        ],
    }


class TestListStrategies:
    def test_empty(self, svc: StrategyService) -> None:
        assert svc.list_strategies() == []

    def test_with_filters(self, svc: StrategyService, mock_repo: MagicMock) -> None:
        svc.list_strategies(ticker="META", status="active")
        mock_repo.get_all.assert_called_once_with(
            ticker="META", status="active", strategy_type=None,
        )


class TestGetStrategy:
    def test_not_found(self, svc: StrategyService) -> None:
        with pytest.raises(NotFoundError):
            svc.get_strategy("nonexistent")

    def test_found(self, svc: StrategyService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = _sample_row()
        result = svc.get_strategy("strat-abc")
        assert result.id == "strat-abc"
        assert result.strategyType == "BULL_CALL_SPREAD"
        assert len(result.legs) == 2


class TestCreateStrategy:
    def test_invalid_type(self, svc: StrategyService) -> None:
        with pytest.raises(AppError, match="Invalid strategy type"):
            svc.create_strategy({
                "strategyType": "INVALID",
                "ticker": "META",
                "legs": [{"type": "CALL", "strike": 100, "expiration": "2027-03-01", "action": "BUY", "quantity": 1}],
            })

    def test_too_many_legs(self, svc: StrategyService) -> None:
        with pytest.raises(AppError, match="1-4 legs"):
            svc.create_strategy({
                "strategyType": "CUSTOM",
                "ticker": "META",
                "legs": [
                    {"type": "CALL", "strike": 100, "expiration": "2027-03-01", "action": "BUY", "quantity": 1}
                    for _ in range(5)
                ],
            })

    def test_no_legs(self, svc: StrategyService) -> None:
        with pytest.raises(AppError, match="1-4 legs"):
            svc.create_strategy({
                "strategyType": "CUSTOM",
                "ticker": "META",
                "legs": [],
            })

    def test_valid_create(self, svc: StrategyService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = _sample_row()
        result = svc.create_strategy({
            "strategyType": "BULL_CALL_SPREAD",
            "ticker": "META",
            "legs": [
                {"type": "CALL", "strike": 680, "expiration": "2027-02-28", "action": "BUY", "quantity": 1},
                {"type": "CALL", "strike": 700, "expiration": "2027-02-28", "action": "SELL", "quantity": 1},
            ],
        })
        assert result.id == "strat-abc"
        mock_repo.insert.assert_called_once()


class TestUpdateStrategy:
    def test_not_found(self, svc: StrategyService) -> None:
        with pytest.raises(NotFoundError):
            svc.update_strategy("nonexistent", {"name": "New"})

    def test_update(self, svc: StrategyService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = _sample_row()
        result = svc.update_strategy("strat-abc", {"name": "Updated"})
        mock_repo.update.assert_called_once()


class TestDeleteStrategy:
    def test_not_found(self, svc: StrategyService) -> None:
        with pytest.raises(NotFoundError):
            svc.delete_strategy("nonexistent")

    def test_delete(self, svc: StrategyService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = _sample_row()
        result = svc.delete_strategy("strat-abc")
        assert result["status"] == "deleted"


class TestRowToModel:
    def test_unrealized_pl_calculation(self) -> None:
        row = _sample_row()
        model = StrategyService._row_to_model(row)
        # BUY leg: (10 - 8.5) * 1 * 100 = 150
        # SELL leg: -1 * (2 - 3) * 1 * 100 = 100
        assert model.unrealizedPL == 250.0

    def test_tags_parsing(self) -> None:
        row = _sample_row()
        model = StrategyService._row_to_model(row)
        assert model.tags == ["earnings", "weekly"]

    def test_empty_tags(self) -> None:
        row = _sample_row()
        row["tags"] = ""
        model = StrategyService._row_to_model(row)
        assert model.tags is None
