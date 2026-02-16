"""Integration tests for the Options Chain API."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.providers.base import OptionContract, Quote


class TestOptionsChainEndpoint:
    def test_get_chain(self, client: TestClient, mock_registry: MagicMock) -> None:
        provider = MagicMock()
        provider.get_quote.return_value = Quote(
            symbol="META", price=689.30, day_high=695.0,
            day_low=685.0, volume=12_500_000, previous_close=687.50,
        )
        provider.get_options_chain.return_value = [
            OptionContract(
                symbol="META", strike=690.0, expiration="2025-03-28",
                option_type="CALL", bid=5.0, ask=6.0, last_price=5.5,
                volume=1000, open_interest=5000, implied_volatility=0.30,
            ),
        ]
        mock_registry.get_best_provider.return_value = ("test-prov", provider)
        mock_registry.get_rate_limit_info.return_value = {
            "limit": 2000, "remaining": 1999, "reset": 3600, "window": "hour",
        }

        resp = client.get("/api/options-chain/META")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["ticker"] == "META"
        assert data["contractCount"] == 1
        assert "greeks" in data["contracts"][0]

        # Phase 6: Rate-limit headers
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "2000"

    def test_get_chain_with_expiration(self, client: TestClient, mock_registry: MagicMock) -> None:
        provider = MagicMock()
        provider.get_quote.return_value = Quote(
            symbol="SPY", price=500.0, day_high=502.0,
            day_low=498.0, volume=50_000_000, previous_close=499.0,
        )
        provider.get_options_chain.return_value = []
        mock_registry.get_best_provider.return_value = ("test-prov", provider)
        mock_registry.get_rate_limit_info.return_value = {}

        resp = client.get("/api/options-chain/SPY?expiration=2025-04-18")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contractCount"] == 0


class TestExpirationsEndpoint:
    def test_get_expirations(self, client: TestClient, mock_registry: MagicMock) -> None:
        provider = MagicMock()
        provider.get_expiration_dates.return_value = ["2025-03-28", "2025-04-25"]
        mock_registry.get_best_provider.return_value = ("test-prov", provider)
        mock_registry.get_rate_limit_info.return_value = {}

        resp = client.get("/api/options-chain/META/expirations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expirations"] == ["2025-03-28", "2025-04-25"]
