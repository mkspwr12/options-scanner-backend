"""Unit tests for Pydantic request schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import Greeks
from app.schemas import (
    CloseTradeRequest,
    LogEntryRequest,
    TrackTradeRequest,
    WatchlistRequest,
)


class TestTrackTradeRequest:
    def _valid_payload(self, **overrides) -> dict:
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
        return base

    def test_valid_request(self) -> None:
        req = TrackTradeRequest(**self._valid_payload())
        assert req.symbol == "META"
        assert req.optionType == "CALL"

    def test_symbol_uppercased(self) -> None:
        req = TrackTradeRequest(**self._valid_payload(symbol="meta"))
        assert req.symbol == "META"

    def test_symbol_whitespace_stripped(self) -> None:
        req = TrackTradeRequest(**self._valid_payload(symbol="  aapl  "))
        assert req.symbol == "AAPL"

    def test_invalid_date_format(self) -> None:
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            TrackTradeRequest(**self._valid_payload(expirationDate="03-01-2025"))

    def test_invalid_option_type(self) -> None:
        with pytest.raises(ValidationError):
            TrackTradeRequest(**self._valid_payload(optionType="STRADDLE"))

    def test_strike_price_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            TrackTradeRequest(**self._valid_payload(strikePrice=-1.0))

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            TrackTradeRequest(**self._valid_payload(quantity=0))

    def test_entry_price_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            TrackTradeRequest(**self._valid_payload(entryPrice=0))

    def test_current_price_can_be_zero(self) -> None:
        # currentPrice ge=0 allows zero (worthless option)
        req = TrackTradeRequest(**self._valid_payload(currentPrice=0.0))
        assert req.currentPrice == 0.0


class TestCloseTradeRequest:
    def test_valid_close(self) -> None:
        req = CloseTradeRequest(tradeId="trade-abc", exitPrice=4.5)
        assert req.tradeId == "trade-abc"
        assert req.exitPrice == 4.5

    def test_exit_price_zero_allowed(self) -> None:
        req = CloseTradeRequest(tradeId="trade-abc", exitPrice=0.0)
        assert req.exitPrice == 0.0

    def test_missing_trade_id(self) -> None:
        with pytest.raises(ValidationError):
            CloseTradeRequest(tradeId="", exitPrice=1.0)


class TestWatchlistRequest:
    def test_symbol_uppercased(self) -> None:
        req = WatchlistRequest(symbol="spy")
        assert req.symbol == "SPY"

    def test_symbol_required(self) -> None:
        with pytest.raises(ValidationError):
            WatchlistRequest(symbol="")


class TestLogEntryRequest:
    def test_valid_log(self) -> None:
        req = LogEntryRequest(level="error", message="something broke")
        assert req.level == "error"

    def test_default_level(self) -> None:
        req = LogEntryRequest(message="hello")
        assert req.level == "info"

    def test_invalid_level(self) -> None:
        with pytest.raises(ValidationError):
            LogEntryRequest(level="critical", message="oops")

    def test_data_optional(self) -> None:
        req = LogEntryRequest(message="hi", data={"key": "val"})
        assert req.data == {"key": "val"}
