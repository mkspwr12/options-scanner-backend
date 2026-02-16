"""Unit tests for OptionsChainService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import AppError
from app.providers.base import OptionContract, Quote
from app.providers.registry import ProviderRegistry
from app.services.options_chain_service import OptionsChainService


def _mock_quote() -> Quote:
    return Quote(
        symbol="META", price=689.30, day_high=695.0,
        day_low=685.0, volume=12_500_000, previous_close=687.50,
    )


def _mock_contracts() -> list[OptionContract]:
    return [
        OptionContract(
            symbol="META", strike=690.0, expiration="2025-03-28",
            option_type="CALL", bid=5.0, ask=6.0, last_price=5.5,
            volume=1000, open_interest=5000, implied_volatility=0.30,
        ),
        OptionContract(
            symbol="META", strike=690.0, expiration="2025-03-28",
            option_type="PUT", bid=4.0, ask=5.0, last_price=4.5,
            volume=800, open_interest=4000, implied_volatility=0.32,
        ),
    ]


@pytest.fixture()
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    provider = MagicMock()
    provider.get_quote.return_value = _mock_quote()
    provider.get_options_chain.return_value = _mock_contracts()
    provider.get_expiration_dates.return_value = ["2025-03-28", "2025-04-25"]
    registry.get_best_provider.return_value = ("test-provider", provider)
    return registry


@pytest.fixture()
def svc(mock_registry: MagicMock) -> OptionsChainService:
    return OptionsChainService(registry=mock_registry)


class TestGetChain:
    def test_returns_enriched_contracts(self, svc: OptionsChainService) -> None:
        result = svc.get_chain("META")
        assert result["status"] == "ok"
        assert result["ticker"] == "META"
        assert result["contractCount"] == 2
        assert len(result["contracts"]) == 2
        assert "greeks" in result["contracts"][0]
        assert "moneyness" in result["contracts"][0]
        assert "dte" in result["contracts"][0]

    def test_records_success(self, svc: OptionsChainService, mock_registry: MagicMock) -> None:
        svc.get_chain("META")
        mock_registry.record_success.assert_called_once_with("test-provider")

    def test_records_failure_on_error(self, mock_registry: MagicMock) -> None:
        _, provider = mock_registry.get_best_provider.return_value
        provider.get_quote.side_effect = RuntimeError("boom")
        svc = OptionsChainService(registry=mock_registry)
        with pytest.raises(AppError, match="Upstream provider"):
            svc.get_chain("META")
        mock_registry.record_failure.assert_called_once()


class TestGetExpirations:
    def test_returns_dates(self, svc: OptionsChainService) -> None:
        result = svc.get_expirations("META")
        assert result["status"] == "ok"
        assert result["expirations"] == ["2025-03-28", "2025-04-25"]


class TestEnrich:
    def test_moneyness_itm_call(self) -> None:
        c = OptionContract(
            symbol="X", strike=90.0, expiration="2025-04-01",
            option_type="CALL", bid=12, ask=13, last_price=12.5,
            volume=100, open_interest=500, implied_volatility=0.25,
        )
        result = OptionsChainService._enrich(c, 100.0)
        assert result["moneyness"] == "ITM"

    def test_moneyness_otm_call(self) -> None:
        c = OptionContract(
            symbol="X", strike=110.0, expiration="2025-04-01",
            option_type="CALL", bid=1, ask=2, last_price=1.5,
            volume=100, open_interest=500, implied_volatility=0.25,
        )
        result = OptionsChainService._enrich(c, 100.0)
        assert result["moneyness"] == "OTM"

    def test_moneyness_atm(self) -> None:
        c = OptionContract(
            symbol="X", strike=100.0, expiration="2025-04-01",
            option_type="CALL", bid=3, ask=4, last_price=3.5,
            volume=100, open_interest=500, implied_volatility=0.25,
        )
        result = OptionsChainService._enrich(c, 100.0)
        assert result["moneyness"] == "ATM"
