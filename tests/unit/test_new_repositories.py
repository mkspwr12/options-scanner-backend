"""Unit tests for provider, strategy, and metrics repositories."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.repositories.provider_repository import ProviderRepository
from app.repositories.strategy_repository import StrategyRepository
from app.repositories.metrics_repository import MetricsRepository
from app.exceptions import ConflictError, NotFoundError, DatabaseError


class TestProviderRepository:
    """Tests for ProviderRepository using mocked DB connection."""

    @patch("app.repositories.provider_repository.get_connection")
    def test_get_all(self, mock_conn_fn: MagicMock) -> None:
        conn = MagicMock()
        cursor = MagicMock()
        cursor.description = [("id",), ("name",), ("type",)]
        cursor.fetchall.return_value = [("p1", "Yahoo", "YAHOO_FINANCE")]
        conn.cursor.return_value = cursor
        mock_conn_fn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_fn.return_value.__exit__ = MagicMock(return_value=False)

        repo = ProviderRepository()
        result = repo.get_all()
        assert len(result) == 1
        assert result[0]["id"] == "p1"

    @patch("app.repositories.provider_repository.get_connection")
    def test_get_by_id_none(self, mock_conn_fn: MagicMock) -> None:
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        mock_conn_fn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_fn.return_value.__exit__ = MagicMock(return_value=False)

        repo = ProviderRepository()
        with pytest.raises(NotFoundError):
            repo.get_by_id("nonexistent")

    @patch("app.repositories.provider_repository.get_connection")
    def test_insert_duplicate_raises(self, mock_conn_fn: MagicMock) -> None:
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)  # name exists
        conn.cursor.return_value = cursor
        mock_conn_fn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_fn.return_value.__exit__ = MagicMock(return_value=False)

        repo = ProviderRepository()
        with pytest.raises(ConflictError, match="already exists"):
            repo.insert({"id": "p1", "name": "Dup", "type": "MOCK"})


class TestStrategyRepository:
    @patch("app.repositories.strategy_repository.get_connection")
    def test_get_all_empty(self, mock_conn_fn: MagicMock) -> None:
        conn = MagicMock()
        cursor = MagicMock()
        cursor.description = [("id",), ("strategy_type",), ("ticker",)]
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_conn_fn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_fn.return_value.__exit__ = MagicMock(return_value=False)

        repo = StrategyRepository()
        assert repo.get_all() == []


class TestMetricsRepository:
    @patch("app.repositories.metrics_repository.get_connection")
    def test_record(self, mock_conn_fn: MagicMock) -> None:
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn_fn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn_fn.return_value.__exit__ = MagicMock(return_value=False)

        repo = MetricsRepository()
        repo.record(
            provider_id="p1",
            latency_ms=100,
            success=True,
            error=None,
            endpoint="/test",
        )
        cursor.execute.assert_called_once()
        conn.commit.assert_called_once()
