"""Unit tests for TradeService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models import Greeks
from app.repositories.trade_repository import TradeRepository
from app.schemas import CloseTradeRequest, TrackTradeRequest
from app.services.trade_service import TradeService

from tests.conftest import make_active_trade


def _make_request(**overrides) -> TrackTradeRequest:
    base = {
        "opportunityId": "opp-001",
        "symbol": "META",
        "strikePrice": 690.0,
        "expirationDate": "2025-03-01",
        "optionType": "CALL",
        "entryPrice": 5.8,
        "currentPrice": 6.9,
        "quantity": 2,
        "underlyingPrice": 689.3,
        "greeks": {"delta": 0.42, "gamma": 0.06, "theta": -0.03, "vega": 0.12},
    }
    base.update(overrides)
    return TrackTradeRequest(**base)


class TestTrackTrade:
    def test_returns_trade_id(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.insert.return_value = "trade-new42"

        svc = TradeService(repo=repo)
        result = svc.track_trade(_make_request())

        assert result["status"] == "ok"
        assert result["tradeId"] == "trade-new42"
        repo.insert.assert_called_once()

    def test_message_includes_symbol_and_type(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.insert.return_value = "trade-new42"

        svc = TradeService(repo=repo)
        result = svc.track_trade(_make_request(symbol="SPY", optionType="PUT"))

        assert "SPY" in result["message"]
        assert "PUT" in result["message"]


class TestCloseTrade:
    def test_close_returns_realized_pl(self) -> None:
        repo = MagicMock(spec=TradeRepository)
        repo.close_trade.return_value = {"tradeId": "t1", "realizedPL": 150.0}

        svc = TradeService(repo=repo)
        req = CloseTradeRequest(tradeId="t1", exitPrice=7.0)
        result = svc.close_trade(req)

        assert result["status"] == "ok"
        assert result["realizedPL"] == 150.0
        repo.close_trade.assert_called_once_with("t1", 7.0)


class TestGetTrade:
    def test_returns_model_dump(self) -> None:
        trade = make_active_trade()
        repo = MagicMock(spec=TradeRepository)
        repo.get_by_id.return_value = trade

        svc = TradeService(repo=repo)
        result = svc.get_trade("trade-abc123")

        assert result["id"] == "trade-abc123"
        assert result["symbol"] == "META"
        repo.get_by_id.assert_called_once_with("trade-abc123")
