"""Unit tests for WatchlistService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.exceptions import ConflictError, NotFoundError
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.watchlist_service import WatchlistService


class TestGetSymbols:
    def test_returns_list(self) -> None:
        repo = MagicMock(spec=WatchlistRepository)
        repo.get_all_symbols.return_value = ["META", "SPY"]

        svc = WatchlistService(repo=repo)
        assert svc.get_symbols() == ["META", "SPY"]

    def test_db_error_returns_default_symbols(self) -> None:
        """When DB is unavailable, get_symbols should return defaults."""
        repo = MagicMock(spec=WatchlistRepository)
        repo.get_all_symbols.side_effect = Exception("DB down")

        svc = WatchlistService(repo=repo)
        result = svc.get_symbols()
        assert isinstance(result, list)
        assert len(result) > 0
        assert "AAPL" in result  # default list includes AAPL

    def test_empty_db_returns_default_symbols(self) -> None:
        """When DB returns empty list, fall back to defaults."""
        repo = MagicMock(spec=WatchlistRepository)
        repo.get_all_symbols.return_value = []

        svc = WatchlistService(repo=repo)
        result = svc.get_symbols()
        assert len(result) > 0  # should return defaults instead of empty


class TestAddSymbol:
    def test_success(self) -> None:
        repo = MagicMock(spec=WatchlistRepository)
        svc = WatchlistService(repo=repo)
        result = svc.add_symbol("NVDA")

        assert result["status"] == "ok"
        assert result["symbol"] == "NVDA"
        repo.add_symbol.assert_called_once_with("NVDA")

    def test_duplicate_raises_conflict(self) -> None:
        repo = MagicMock(spec=WatchlistRepository)
        repo.add_symbol.side_effect = ConflictError("NVDA already on watchlist")

        svc = WatchlistService(repo=repo)
        with pytest.raises(ConflictError, match="already on watchlist"):
            svc.add_symbol("NVDA")


class TestRemoveSymbol:
    def test_success(self) -> None:
        repo = MagicMock(spec=WatchlistRepository)
        svc = WatchlistService(repo=repo)
        result = svc.remove_symbol("META")

        assert result["status"] == "ok"
        repo.remove_symbol.assert_called_once_with("META")

    def test_not_found_raises(self) -> None:
        repo = MagicMock(spec=WatchlistRepository)
        repo.remove_symbol.side_effect = NotFoundError("Symbol", "XYZ")

        svc = WatchlistService(repo=repo)
        with pytest.raises(NotFoundError):
            svc.remove_symbol("XYZ")
