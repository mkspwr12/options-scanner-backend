"""Unit tests for database connection helpers (app/db.py).

Covers:
- Connection string normalization (driver injection, field stripping, defaults)
- Retry logic with exponential backoff
- Token encoding
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("SQL_CONNECTION_STRING", "Server=test;Database=test;")

from app.db import _normalize_connection_string, get_connection, _MAX_RETRIES


# ---------------------------------------------------------------------------
# _normalize_connection_string
# ---------------------------------------------------------------------------

class TestNormalizeConnectionString:
    """Tests for _normalize_connection_string()."""

    def test_injects_driver_when_missing(self) -> None:
        result = _normalize_connection_string(
            "Server=myserver;Database=mydb;", "ODBC Driver 18 for SQL Server"
        )
        assert "driver={ODBC Driver 18 for SQL Server}" in result

    def test_preserves_existing_driver(self) -> None:
        raw = "Server=srv;Database=db;Driver={ODBC Driver 17 for SQL Server};"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        assert "ODBC Driver 17" in result
        assert "ODBC Driver 18" not in result

    def test_strips_authentication_fields(self) -> None:
        raw = (
            "Server=srv;Database=db;User ID=sa;Password=secret;"
            "Authentication=ActiveDirectoryInteractive;"
        )
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        lower = result.lower()
        assert "user id" not in lower
        assert "password" not in lower
        assert "authentication" not in lower

    def test_strips_uid_pwd_fields(self) -> None:
        raw = "Server=srv;Database=db;UID=admin;PWD=p@ss;"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        lower = result.lower()
        assert "uid" not in lower
        assert "pwd" not in lower

    def test_adds_encrypt_and_trust_defaults(self) -> None:
        raw = "Server=srv;Database=db;"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        lower = result.lower()
        assert "encrypt=yes" in lower
        assert "trustservercertificate=no" in lower

    def test_preserves_custom_encrypt_value(self) -> None:
        raw = "Server=srv;Database=db;Encrypt=no;"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        assert "encrypt=no" in result.lower()
        # Should not have duplicate encrypt
        assert result.lower().count("encrypt=") == 1

    def test_handles_empty_segments(self) -> None:
        raw = "Server=srv;;Database=db;  ;  "
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        assert "server=srv" in result.lower()
        assert "database=db" in result.lower()

    def test_ends_with_semicolon(self) -> None:
        raw = "Server=srv;Database=db"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        assert result.endswith(";")

    def test_handles_values_with_equals(self) -> None:
        """Values can contain '=' (e.g. base64 tokens)."""
        raw = "Server=srv;Database=db;SomeKey=val=ue=;"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        assert "somekey=val=ue=" in result.lower()

    def test_key_lowercased(self) -> None:
        raw = "SERVER=srv;DATABASE=db;"
        result = _normalize_connection_string(raw, "ODBC Driver 18 for SQL Server")
        assert "server=srv" in result
        assert "database=db" in result


# ---------------------------------------------------------------------------
# get_connection — retry logic
# ---------------------------------------------------------------------------

class TestGetConnectionRetry:
    """Tests for get_connection() retry and token handling."""

    @patch("app.db.pyodbc")
    @patch("app.db.DefaultAzureCredential")
    @patch("app.db.get_settings")
    def test_success_on_first_attempt(
        self, mock_settings, mock_cred_cls, mock_pyodbc
    ) -> None:
        mock_settings.return_value = MagicMock(
            sql_connection_string="Server=test;Database=test;",
            sql_driver="ODBC Driver 18 for SQL Server",
            azure_client_id="test-client-id",
        )
        token_obj = MagicMock()
        token_obj.token = "fake-token"
        mock_cred_cls.return_value.get_token.return_value = token_obj

        fake_conn = MagicMock()
        mock_pyodbc.connect.return_value = fake_conn

        result = get_connection()
        assert result is fake_conn
        assert mock_pyodbc.connect.call_count == 1

    @patch("app.db.time.sleep")
    @patch("app.db.pyodbc")
    @patch("app.db.DefaultAzureCredential")
    @patch("app.db.get_settings")
    def test_retries_on_failure(
        self, mock_settings, mock_cred_cls, mock_pyodbc, mock_sleep
    ) -> None:
        mock_settings.return_value = MagicMock(
            sql_connection_string="Server=test;Database=test;",
            sql_driver="ODBC Driver 18 for SQL Server",
            azure_client_id=None,
        )
        token_obj = MagicMock()
        token_obj.token = "fake-token"
        mock_cred_cls.return_value.get_token.return_value = token_obj

        fake_conn = MagicMock()
        mock_pyodbc.connect.side_effect = [
            Exception("fail 1"),
            Exception("fail 2"),
            fake_conn,
        ]

        result = get_connection()
        assert result is fake_conn
        assert mock_pyodbc.connect.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("app.db.time.sleep")
    @patch("app.db.pyodbc")
    @patch("app.db.DefaultAzureCredential")
    @patch("app.db.get_settings")
    def test_raises_after_max_retries(
        self, mock_settings, mock_cred_cls, mock_pyodbc, mock_sleep
    ) -> None:
        mock_settings.return_value = MagicMock(
            sql_connection_string="Server=test;Database=test;",
            sql_driver="ODBC Driver 18 for SQL Server",
            azure_client_id=None,
        )
        token_obj = MagicMock()
        token_obj.token = "fake-token"
        mock_cred_cls.return_value.get_token.return_value = token_obj

        mock_pyodbc.connect.side_effect = Exception("persistent failure")

        with pytest.raises(Exception, match="persistent failure"):
            get_connection()

        assert mock_pyodbc.connect.call_count == _MAX_RETRIES

    @patch("app.db.time.sleep")
    @patch("app.db.pyodbc")
    @patch("app.db.DefaultAzureCredential")
    @patch("app.db.get_settings")
    def test_exponential_backoff_timing(
        self, mock_settings, mock_cred_cls, mock_pyodbc, mock_sleep
    ) -> None:
        mock_settings.return_value = MagicMock(
            sql_connection_string="Server=test;Database=test;",
            sql_driver="ODBC Driver 18 for SQL Server",
            azure_client_id=None,
        )
        token_obj = MagicMock()
        token_obj.token = "fake"
        mock_cred_cls.return_value.get_token.return_value = token_obj

        mock_pyodbc.connect.side_effect = Exception("fail")

        with pytest.raises(Exception):
            get_connection()

        # Backoff: 1s, 2s (for 3 retries, sleep called at attempts 1 and 2)
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 1.0
        assert calls[1][0][0] == 2.0

    @patch("app.db.pyodbc")
    @patch("app.db.DefaultAzureCredential")
    @patch("app.db.get_settings")
    def test_token_encoded_as_utf16le(
        self, mock_settings, mock_cred_cls, mock_pyodbc
    ) -> None:
        mock_settings.return_value = MagicMock(
            sql_connection_string="Server=test;Database=test;",
            sql_driver="ODBC Driver 18 for SQL Server",
            azure_client_id="cid",
        )
        token_obj = MagicMock()
        token_obj.token = "test-token-value"
        mock_cred_cls.return_value.get_token.return_value = token_obj

        mock_pyodbc.connect.return_value = MagicMock()
        get_connection()

        call_kwargs = mock_pyodbc.connect.call_args
        attrs = call_kwargs.kwargs.get("attrs_before") or call_kwargs[1].get("attrs_before")
        from app.db import SQL_COPT_SS_ACCESS_TOKEN

        assert SQL_COPT_SS_ACCESS_TOKEN in attrs
        # Token should be struct-packed with length prefix (prevents ODBC segfault)
        import struct

        expected_bytes = "test-token-value".encode("utf-16-le")
        expected_struct = struct.pack(
            f"<I{len(expected_bytes)}s", len(expected_bytes), expected_bytes
        )
        assert attrs[SQL_COPT_SS_ACCESS_TOKEN] == expected_struct

    @patch("app.db.pyodbc")
    @patch("app.db.DefaultAzureCredential")
    @patch("app.db.get_settings")
    def test_custom_retry_count(
        self, mock_settings, mock_cred_cls, mock_pyodbc
    ) -> None:
        mock_settings.return_value = MagicMock(
            sql_connection_string="Server=test;Database=test;",
            sql_driver="ODBC Driver 18 for SQL Server",
            azure_client_id=None,
        )
        token_obj = MagicMock()
        token_obj.token = "t"
        mock_cred_cls.return_value.get_token.return_value = token_obj

        mock_pyodbc.connect.side_effect = Exception("fail")

        with pytest.raises(Exception):
            get_connection(retries=1)

        assert mock_pyodbc.connect.call_count == 1
