"""Unit tests for Issue #14 — position action service."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.repositories.trade_repository import TradeRepository
from app.schemas import AdjustPositionRequest, ClosePositionRequest, RollPositionRequest
from app.services.position_action_service import PositionActionService

from tests.conftest import make_active_trade


class TestClosePosition:
    def test_close_position_mock(self) -> None:
        """Close position returns success even when position is not in DB."""
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.side_effect = Exception("not found")
        svc = PositionActionService(repo=repo)

        result = svc.close_position(
            ClosePositionRequest(positionId="pos-123", closePrice=180.0)
        )
        assert result["success"] is True
        assert "closedPosition" in result
        assert result["closedPosition"]["id"] == "pos-123"
        assert "closedAt" in result["closedPosition"]
        assert "realizedPnL" in result["closedPosition"]

    def test_close_position_with_trade(self) -> None:
        """Close position with an existing trade calculates P&L."""
        trade = make_active_trade(entryPrice=5.0, quantity=1)
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = trade
        repo.close_trade.return_value = {"tradeId": trade.id, "realizedPL": 200.0}
        svc = PositionActionService(repo=repo)

        result = svc.close_position(
            ClosePositionRequest(positionId=trade.id, closePrice=7.0)
        )
        assert result["success"] is True
        assert result["closedPosition"]["realizedPnL"] == 200.0  # (7 - 5) * 1 * 100


class TestRollPosition:
    def test_roll_position_mock(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = None
        svc = PositionActionService(repo=repo)

        result = svc.roll_position(
            RollPositionRequest(positionId="pos-123", newExpiration="2026-03-21")
        )
        assert result["success"] is True
        assert "oldPositionId" in result
        assert "newPositionId" in result
        assert "rollCredit" in result
        assert result["oldPositionId"] == "pos-123"

    def test_roll_position_with_trade(self) -> None:
        trade = make_active_trade()
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = trade
        repo.close_trade.return_value = {"tradeId": trade.id, "realizedPL": 50.0}
        repo.insert.return_value = "pos-new-123"
        svc = PositionActionService(repo=repo)

        result = svc.roll_position(
            RollPositionRequest(positionId=trade.id, newExpiration="2026-04-15")
        )
        assert result["success"] is True
        assert result["oldPositionId"] == trade.id
        assert "newPositionId" in result
        assert "rollCredit" in result


class TestAdjustPosition:
    def test_adjust_protective_put_mock(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = None
        svc = PositionActionService(repo=repo)

        result = svc.adjust_position(
            AdjustPositionRequest(
                positionId="pos-123",
                adjustmentType="add_protective_put",
                strike=160.0,
                quantity=1,
            )
        )
        assert result["success"] is True
        assert "adjustedPosition" in result
        legs = result["adjustedPosition"]["newLegs"]
        assert len(legs) == 1
        assert legs[0]["optionType"] == "put"
        assert legs[0]["position"] == "long"
        assert legs[0]["strike"] == 160.0

    def test_adjust_reduce_size(self) -> None:
        trade = make_active_trade()
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = trade
        svc = PositionActionService(repo=repo)

        result = svc.adjust_position(
            AdjustPositionRequest(
                positionId=trade.id,
                adjustmentType="reduce_size",
                quantity=1,
            )
        )
        assert result["success"] is True

    def test_adjust_protective_call(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = None
        svc = PositionActionService(repo=repo)

        result = svc.adjust_position(
            AdjustPositionRequest(
                positionId="pos-456",
                adjustmentType="add_protective_call",
                strike=200.0,
                quantity=2,
            )
        )
        assert result["success"] is True
        legs = result["adjustedPosition"]["newLegs"]
        assert len(legs) == 1
        assert legs[0]["optionType"] == "call"
        assert legs[0]["position"] == "long"
