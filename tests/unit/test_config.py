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
            "MARKET_DATA_PROVIDER": "massive",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.sql_connection_string == "Server=test;Database=test;"
            assert s.scan_interval_minutes == 15
            assert s.scan_enabled is True
            assert s.market_data_provider == "massive"

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

    def test_scan_enabled_truthy_values(self) -> None:
        for val in ("true", "True", "1", "yes", "YES"):
            env = {
                "SQL_CONNECTION_STRING": "Server=test;Database=test;",
                "SCAN_ENABLED": val,
            }
            with patch.dict(os.environ, env, clear=False):
                s = get_settings()
                assert s.scan_enabled is True, f"Expected True for '{val}'"

    def test_scan_enabled_falsy_values(self) -> None:
        for val in ("false", "False", "0", "no", "anything"):
            env = {
                "SQL_CONNECTION_STRING": "Server=test;Database=test;",
                "SCAN_ENABLED": val,
            }
            with patch.dict(os.environ, env, clear=False):
                s = get_settings()
                assert s.scan_enabled is False, f"Expected False for '{val}'"

    def test_custom_sql_driver(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "SQL_DRIVER": "ODBC Driver 17 for SQL Server",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.sql_driver == "ODBC Driver 17 for SQL Server"

    def test_default_sql_driver(self) -> None:
        env = {"SQL_CONNECTION_STRING": "Server=test;Database=test;"}
        with patch.dict(os.environ, env, clear=False):
            # Remove SQL_DRIVER if previously set
            os.environ.pop("SQL_DRIVER", None)
            s = get_settings()
            assert s.sql_driver == "ODBC Driver 18 for SQL Server"

    def test_azure_client_id(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "AZURE_CLIENT_ID": "my-client-id-123",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.azure_client_id == "my-client-id-123"

    def test_azure_client_id_none_when_unset(self) -> None:
        env = {"SQL_CONNECTION_STRING": "Server=test;Database=test;"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("AZURE_CLIENT_ID", None)
            s = get_settings()
            assert s.azure_client_id is None

    def test_api_key_stored(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "API_KEY": "secret-key-42",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.api_key == "secret-key-42"

    def test_scan_interval_custom(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "SCAN_INTERVAL_MINUTES": "30",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.scan_interval_minutes == 30

    def test_log_retention_custom(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "LOG_RETENTION": "500",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.log_retention == 500

    def test_market_data_provider_normalized(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "MARKET_DATA_PROVIDER": "  MASSIVE  ",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert s.market_data_provider == "massive"

    def test_default_origins_when_env_empty(self) -> None:
        env = {
            "SQL_CONNECTION_STRING": "Server=test;Database=test;",
            "ALLOWED_ORIGINS": "",
        }
        with patch.dict(os.environ, env, clear=False):
            s = get_settings()
            assert len(s.allowed_origins) > 0
            assert any("localhost" in o for o in s.allowed_origins)


class TestSettingsDataclass:
    """Test the Settings dataclass directly."""

    def test_frozen(self) -> None:
        s = Settings(
            sql_connection_string="Server=test;Database=test;",
            azure_client_id=None,
            sql_driver="ODBC Driver 18 for SQL Server",
        )
        with pytest.raises(AttributeError):
            s.sql_connection_string = "changed"  # type: ignore[misc]

    def test_default_values(self) -> None:
        s = Settings(
            sql_connection_string="Server=test;Database=test;",
            azure_client_id=None,
            sql_driver="ODBC Driver 18 for SQL Server",
        )
        assert s.api_key is None
        assert s.scan_interval_minutes == 15
        assert s.scan_enabled is True
        assert s.log_retention == 1000
        assert s.market_data_provider == "massive"
