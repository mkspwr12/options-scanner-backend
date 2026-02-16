"""Repository tests with mocked pyodbc connections.

These tests verify the repository classes' SQL logic, row-to-model
conversion, and error handling without requiring a real database.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import ConflictError, DatabaseError, NotFoundError
from app.models import ClosedTrade, Greeks, OptionOpportunity, TrackedTrade


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _make_cursor(
    rows: list[tuple] | None = None,
    description: list[tuple[str, ...]] | None = None,
    fetchone_val: Any = None,
    rowcount: int = 1,
) -> MagicMock:
    cursor = MagicMock()
    cursor.description = description or []
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = fetchone_val
    cursor.rowcount = rowcount
    return cursor


def _mock_conn(cursor: MagicMock) -> MagicMock:
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


# Standard column layout for the trades table
_TRADE_COLS: list[tuple[str, ...]] = [
    ("id",), ("opportunity_id",), ("symbol",), ("strike_price",),
    ("expiration_date",), ("option_type",), ("entry_price",),
    ("current_price",), ("quantity",), ("underlying_price",),
    ("delta",), ("gamma",), ("theta",), ("vega",),
    ("entry_date",), ("status",),
    ("exit_price",), ("exit_date",), ("created_at",), ("updated_at",),
]

_ACTIVE_ROW = (
    "t-1", "opp-1", "META", 690.0, "2025-02-28", "CALL",
    5.80, 6.90, 2, 689.3,
    0.42, 0.06, -0.03, 0.12,
    1700000000000, "active",
    None, None, "2025-01-01", "2025-01-01",
)

_CLOSED_ROW = (
    "t-2", "opp-2", "AAPL", 220.0, "2025-02-14", "CALL",
    3.20, 4.10, 1, 219.7,
    0.35, 0.04, -0.02, 0.09,
    1699800000000, "closed",
    4.10, 1699900000000, "2025-01-01", "2025-01-02",
)

# Standard columns for scan_results
_SCAN_COLS: list[tuple[str, ...]] = [
    ("id",), ("symbol",), ("strike_price",), ("expiration_date",), ("option_type",),
    ("current_price",), ("underlying_price",), ("implied_volatility",),
    ("delta",), ("gamma",), ("theta",), ("vega",),
    ("potential_gain",), ("potential_loss",), ("risk_reward_ratio",),
    ("confidence_score",), ("scan_timestamp",),
]

_SCAN_ROW = (
    "s-1", "META", 690.0, "2025-02-28", "CALL",
    6.50, 689.3, 0.32,
    0.45, 0.05, -0.03, 0.11,
    350.0, 200.0, 1.75,
    82.5, 1700000000000,
)


# =====================================================================
# TradeRepository
# =====================================================================

class TestTradeRepository:

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_by_id_active(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor(
            fetchone_val=_ACTIVE_ROW,
            description=_TRADE_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        result = repo.get_by_id("t-1")
        assert isinstance(result, TrackedTrade)
        assert result.id == "t-1"
        assert result.symbol == "META"
        assert result.status == "active"

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_by_id_closed(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor(
            fetchone_val=_CLOSED_ROW,
            description=_TRADE_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        result = repo.get_by_id("t-2")
        assert isinstance(result, ClosedTrade)
        assert result.status == "closed"
        assert result.exitPrice == 4.10

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_by_id_not_found(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor(fetchone_val=None, description=_TRADE_COLS)
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        with pytest.raises(NotFoundError):
            repo.get_by_id("nonexistent")

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_by_id_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        mock_gc.return_value.__enter__ = MagicMock(side_effect=RuntimeError("conn fail"))
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)

        repo = TradeRepository()
        with pytest.raises(DatabaseError):
            repo.get_by_id("t-1")

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_active_trades(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor(
            rows=[_ACTIVE_ROW],
            description=_TRADE_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        result = repo.get_active_trades()
        assert len(result) == 1
        assert isinstance(result[0], TrackedTrade)

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_closed_trades(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor(
            rows=[_CLOSED_ROW],
            description=_TRADE_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        result = repo.get_closed_trades()
        assert len(result) == 1
        assert isinstance(result[0], ClosedTrade)

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_all(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor(
            rows=[_ACTIVE_ROW, _CLOSED_ROW],
            description=_TRADE_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        result = repo.get_all()
        assert len(result) == 2

    @patch("app.repositories.trade_repository.get_connection")
    def test_insert(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor()
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        trade_data = {
            "opportunityId": "opp-1",
            "symbol": "META",
            "strikePrice": 690.0,
            "expirationDate": "2025-02-28",
            "optionType": "CALL",
            "entryPrice": 5.80,
            "currentPrice": 6.90,
            "quantity": 2,
            "underlyingPrice": 689.3,
            "greeks": {"delta": 0.42, "gamma": 0.06, "theta": -0.03, "vega": 0.12},
        }
        trade_id = repo.insert(trade_data)
        assert trade_id.startswith("trade-")
        cursor.execute.assert_called_once()

    @patch("app.repositories.trade_repository.get_connection")
    def test_insert_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        cursor = _make_cursor()
        cursor.execute.side_effect = RuntimeError("insert fail")
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        with pytest.raises(DatabaseError):
            repo.insert({
                "opportunityId": "opp-1", "symbol": "META",
                "strikePrice": 690.0, "expirationDate": "2025-02-28",
                "optionType": "CALL", "entryPrice": 5.80,
                "currentPrice": 6.90, "quantity": 2, "underlyingPrice": 689.3,
                "greeks": {"delta": 0.42, "gamma": 0.06, "theta": -0.03, "vega": 0.12},
            })

    @patch("app.repositories.trade_repository.get_connection")
    def test_close_trade(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        # First call for get_by_id, second for close
        cursor = _make_cursor(
            fetchone_val=_ACTIVE_ROW,
            description=_TRADE_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = TradeRepository()
        result = repo.close_trade("t-1", exit_price=7.50)
        assert result["tradeId"] == "t-1"
        assert "realizedPL" in result
        assert "realizedPLPercent" in result

    @patch("app.repositories.trade_repository.get_connection")
    def test_get_active_trades_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.trade_repository import TradeRepository

        mock_gc.return_value.__enter__ = MagicMock(side_effect=RuntimeError("conn fail"))
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)

        repo = TradeRepository()
        with pytest.raises(DatabaseError):
            repo.get_active_trades()


# =====================================================================
# WatchlistRepository
# =====================================================================

class TestWatchlistRepository:

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_get_all_symbols(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor(rows=[("AAPL",), ("META",), ("SPY",)])
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        result = repo.get_all_symbols()
        assert result == ["AAPL", "META", "SPY"]

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_get_all_symbols_empty(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor(rows=[])
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        assert repo.get_all_symbols() == []

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_get_all_symbols_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        mock_gc.return_value.__enter__ = MagicMock(side_effect=RuntimeError("fail"))
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)

        repo = WatchlistRepository()
        with pytest.raises(DatabaseError):
            repo.get_all_symbols()

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_add_symbol(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor(fetchone_val=(0,))
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        repo.add_symbol("NVDA")  # should not raise
        assert cursor.execute.call_count == 2  # SELECT + INSERT

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_add_symbol_conflict(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor(fetchone_val=(1,))
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        with pytest.raises(ConflictError):
            repo.add_symbol("META")

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_add_symbol_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor()
        cursor.execute.side_effect = RuntimeError("fail")
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        with pytest.raises(DatabaseError):
            repo.add_symbol("NVDA")

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_remove_symbol(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor(rowcount=1)
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        repo.remove_symbol("META")  # should not raise

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_remove_symbol_not_found(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor(rowcount=0)
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        with pytest.raises(NotFoundError):
            repo.remove_symbol("NONEXIST")

    @patch("app.repositories.watchlist_repository.get_connection")
    def test_remove_symbol_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.watchlist_repository import WatchlistRepository

        cursor = _make_cursor()
        cursor.execute.side_effect = RuntimeError("fail")
        mock_gc.return_value = _mock_conn(cursor)

        repo = WatchlistRepository()
        with pytest.raises(DatabaseError):
            repo.remove_symbol("META")


# =====================================================================
# ScanRepository
# =====================================================================

class TestScanRepository:

    @patch("app.repositories.scan_repository.get_connection")
    def test_get_latest(self, mock_gc: MagicMock) -> None:
        from app.repositories.scan_repository import ScanRepository

        cursor = _make_cursor(
            rows=[_SCAN_ROW],
            description=_SCAN_COLS,
        )
        mock_gc.return_value = _mock_conn(cursor)

        repo = ScanRepository()
        result = repo.get_latest()
        assert len(result) == 1
        assert isinstance(result[0], OptionOpportunity)
        assert result[0].symbol == "META"

    @patch("app.repositories.scan_repository.get_connection")
    def test_get_latest_with_filters(self, mock_gc: MagicMock) -> None:
        from app.repositories.scan_repository import ScanRepository

        cursor = _make_cursor(rows=[], description=_SCAN_COLS)
        mock_gc.return_value = _mock_conn(cursor)

        repo = ScanRepository()
        result = repo.get_latest(
            symbol="META",
            option_type="CALL",
            min_confidence=70.0,
            min_risk_reward=1.5,
        )
        assert result == []
        # Verify parameters included filters
        call_args = cursor.execute.call_args
        assert "symbol = ?" in call_args[0][0]
        assert "option_type = ?" in call_args[0][0]

    @patch("app.repositories.scan_repository.get_connection")
    def test_get_latest_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.scan_repository import ScanRepository

        mock_gc.return_value.__enter__ = MagicMock(side_effect=RuntimeError("fail"))
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)

        repo = ScanRepository()
        with pytest.raises(DatabaseError):
            repo.get_latest()

    @patch("app.repositories.scan_repository.get_connection")
    def test_save_results(self, mock_gc: MagicMock) -> None:
        from app.repositories.scan_repository import ScanRepository

        cursor = _make_cursor()
        mock_gc.return_value = _mock_conn(cursor)

        repo = ScanRepository()
        count = repo.save_results([{
            "id": "s-1", "symbol": "META", "strikePrice": 690.0,
            "expirationDate": "2025-02-28", "optionType": "CALL",
            "currentPrice": 6.50, "underlyingPrice": 689.3,
            "impliedVolatility": 0.32,
            "greeks": {"delta": 0.45, "gamma": 0.05, "theta": -0.03, "vega": 0.11},
            "potentialGain": 350.0, "potentialLoss": 200.0,
            "riskRewardRatio": 1.75, "confidenceScore": 82.5,
            "strategyType": None, "timestamp": 1700000000000,
        }])
        assert count == 1

    @patch("app.repositories.scan_repository.get_connection")
    def test_save_results_empty(self, mock_gc: MagicMock) -> None:
        from app.repositories.scan_repository import ScanRepository

        repo = ScanRepository()
        assert repo.save_results([]) == 0
        mock_gc.assert_not_called()

    @patch("app.repositories.scan_repository.get_connection")
    def test_save_results_db_error(self, mock_gc: MagicMock) -> None:
        from app.repositories.scan_repository import ScanRepository

        cursor = _make_cursor()
        cursor.execute.side_effect = RuntimeError("fail")
        mock_gc.return_value = _mock_conn(cursor)

        repo = ScanRepository()
        with pytest.raises(DatabaseError):
            repo.save_results([{
                "id": "s-1", "symbol": "META", "strikePrice": 690.0,
                "expirationDate": "2025-02-28", "optionType": "CALL",
                "currentPrice": 6.50, "underlyingPrice": 689.3,
                "impliedVolatility": 0.32,
                "greeks": {"delta": 0.45, "gamma": 0.05, "theta": -0.03, "vega": 0.11},
                "potentialGain": 350.0, "potentialLoss": 200.0,
                "riskRewardRatio": 1.75, "confidenceScore": 82.5,
                "strategyType": None, "timestamp": 1700000000000,
            }])
