"""Unit tests for application configuration."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.config import Settings, get_settings, _parse_origins


class TestParseOrigins:
    def test_single_origin(self) -> None:
        assert _parse_origins("http://localhost:3000") == ["http://localhost:3000"]

    def test_multiple_origins(self) -> None:
        result = _parse_origins("http://a.com, http://b.com , http://c.com")
        assert result == ["http://a.com", "http://b.com", "http://c.com"]

    def test_empty_string(self) -> None:
        assert _parse_origins("") == []

    def test_trailing_comma(self) -> None:
        result = _parse_origins("http://a.com,")
        assert result == ["http://a.com"]


class TestGetSettings:
    def test_missing_sql_connection_string(self) -> None:
        with patch.dict(os.environ, {"SQL_CONNECTION_STRING": ""}, clear=False):
            with pytest.raises(RuntimeError, match="SQL_CONNECTION_STRING is required"):
                get_settings()

    def test_defaults(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "ALLOWED_ORIGINS": "",
            "API_KEY": "",
            "SCAN_INTERVAL_MINUTES": "15",
            "SCAN_ENABLED": "true",
            "LOG_RETENTION": "1000",
            "MARKET_DATA_PROVIDER": "mock",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.sql_connection_string == "Server=test;Database=test;"
            assert s.scan_interval_minutes == 15
            assert s.scan_enabled is True
            assert s.market_data_provider == "mock"

    def test_scan_disabled(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "SCAN_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.scan_enabled is False

    def test_custom_origins(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "ALLOWED_ORIGINS": "http://custom.com,http://other.com",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert "http://custom.com" in s.allowed_origins
            assert "http://other.com" in s.allowed_origins
