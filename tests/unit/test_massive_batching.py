"""Unit tests for Massive provider batching capabilities."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from app.providers.massive_provider import MassiveProvider


class TestMassiveProviderBatching:
    """Test batching capabilities of Massive provider."""

    def test_batch_bars_parsing_multiple_symbols(self):
        """Batch bars response with multiple symbols is correctly parsed."""
        provider = MassiveProvider(api_key=os.getenv("MASSIVE_API_KEY", ""))
        
        payload = {
            "results": [
                {"T": "AAPL", "c": 150.5, "h": 151.0, "l": 150.0, "v": 1000000},
                {"T": "AAPL", "c": 150.3, "h": 150.8, "l": 150.1, "v": 900000},
                {"T": "MSFT", "c": 380.2, "h": 381.0, "l": 380.0, "v": 800000},
                {"T": "MSFT", "c": 380.0, "h": 380.9, "l": 379.8, "v": 750000},
            ]
        }
        
        bars = provider._parse_batch_bars(payload, ["AAPL", "MSFT"])
        
        assert len(bars["AAPL"]) == 2
        assert len(bars["MSFT"]) == 2

    def test_batch_bars_parsing_single_symbol(self):
        """Single symbol batch response is correctly parsed."""
        provider = MassiveProvider(api_key=os.getenv("MASSIVE_API_KEY", ""))
        
        payload = {
            "results": [
                {"c": 150.5, "h": 151.0, "l": 150.0, "v": 1000000},
                {"c": 150.3, "h": 150.8, "l": 150.1, "v": 900000},
            ]
        }
        
        bars = provider._parse_batch_bars(payload, ["AAPL"])
        
        assert len(bars["AAPL"]) == 2

    def test_batch_bars_parsing_empty_response(self):
        """Empty batch response returns empty dict."""
        provider = MassiveProvider(api_key=os.getenv("MASSIVE_API_KEY", ""))
        
        payload = {"results": []}
        
        bars = provider._parse_batch_bars(payload, ["AAPL", "MSFT"])
        
        assert bars["AAPL"] == []
        assert bars["MSFT"] == []

    def test_get_stock_scan_data_delegates_to_batch(self):
        """Single symbol get delegates to batch method."""
        provider = MassiveProvider(api_key=os.getenv("MASSIVE_API_KEY", ""))
        
        # Mock the batch method
        batch_result = {
            "AAPL": {
                "symbol": "AAPL",
                "name": "Apple",
                "price": 150.5,
                "prev_close": 149.0,
                "volume": 1000000,
                "closes": [140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 150.5, 150.3, 150.2, 150.5],
                "market_cap": 3000000000000,
                "pe_ratio": 25.0,
            }
        }
        
        with patch.object(provider, "get_stock_scan_data_batch", return_value=batch_result):
            result = provider.get_stock_scan_data("AAPL")
            
            assert result is not None
            assert result["symbol"] == "AAPL"
            assert result["name"] == "Apple"
            assert result["price"] == 150.5

    def test_min_request_interval_reduced_for_batching(self):
        """Minimum request interval should be 2s for batching instead of 13s."""
        provider = MassiveProvider(api_key=os.getenv("MASSIVE_API_KEY", ""))
        
        assert provider._min_request_interval == 2.0

    def test_batch_method_signature_accepts_list(self):
        """Batch method exists and accepts list of symbols."""
        provider = MassiveProvider(api_key=os.getenv("MASSIVE_API_KEY", ""))
        
        assert hasattr(provider, "get_stock_scan_data_batch")
        
        # Check that it's callable
        assert callable(provider.get_stock_scan_data_batch)
