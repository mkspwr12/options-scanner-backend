"""Tests for the MockProvider."""
from __future__ import annotations

import pytest

from app.providers.base import MarketDataProvider, OptionContract, Quote
from app.providers.mock_provider import MockProvider


class TestMockProvider:
    """Unit tests for the MockProvider implementation."""

    def setup_method(self) -> None:
        self.provider = MockProvider()

    def test_implements_protocol(self) -> None:
        assert isinstance(self.provider, MarketDataProvider)

    def test_is_available(self) -> None:
        assert self.provider.is_available() is True

    def test_get_quote_known_symbol(self) -> None:
        q = self.provider.get_quote("META")
        assert isinstance(q, Quote)
        assert q.symbol == "META"
        assert q.price > 0

    def test_get_quote_unknown_symbol(self) -> None:
        q = self.provider.get_quote("UNKNOWN")
        assert isinstance(q, Quote)
        assert q.symbol == "UNKNOWN"
        assert q.price == 100.0

    def test_get_quote_case_insensitive(self) -> None:
        q = self.provider.get_quote("meta")
        assert q.symbol == "META"

    def test_get_options_chain_returns_contracts(self) -> None:
        contracts = self.provider.get_options_chain("META")
        assert len(contracts) > 0
        assert all(isinstance(c, OptionContract) for c in contracts)

    def test_options_chain_has_calls_and_puts(self) -> None:
        contracts = self.provider.get_options_chain("SPY")
        types = {c.option_type for c in contracts}
        assert "CALL" in types
        assert "PUT" in types

    def test_options_chain_contracts_have_valid_fields(self) -> None:
        contracts = self.provider.get_options_chain("AAPL")
        for c in contracts:
            assert c.symbol == "AAPL"
            assert c.strike > 0
            assert c.implied_volatility > 0
            assert c.volume > 0
            assert c.open_interest > 0
            assert len(c.expiration) == 10  # YYYY-MM-DD

    def test_options_chain_with_custom_expiration(self) -> None:
        contracts = self.provider.get_options_chain("META", expiration="2026-06-15")
        assert all(c.expiration == "2026-06-15" for c in contracts)

    def test_options_chain_generates_10_contracts(self) -> None:
        """5 strikes × 2 option types = 10 contracts."""
        contracts = self.provider.get_options_chain("SPY")
        assert len(contracts) == 10

    def test_known_symbols(self) -> None:
        """All standard symbols return specific quotes."""
        for sym in ("META", "SPY", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN"):
            q = self.provider.get_quote(sym)
            assert q.symbol == sym
            assert q.price != 100.0  # default
