"""Unit tests for custom exceptions and global error handlers (app/exceptions.py).

Covers:
- Exception class construction and attributes
- Global error handler response format
- Validation error formatting
- Unhandled exception catch-all
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SQL_CONNECTION_STRING", "Server=test;Database=test;")

from app.exceptions import AppError, ConflictError, DatabaseError, NotFoundError


# ---------------------------------------------------------------------------
# Exception class construction
# ---------------------------------------------------------------------------

class TestAppError:
    def test_default_status_code(self) -> None:
        err = AppError("something broke")
        assert err.status_code == 500
        assert err.message == "something broke"
        assert str(err) == "something broke"

    def test_custom_status_code(self) -> None:
        err = AppError("rate limited", status_code=429)
        assert err.status_code == 429

    def test_detail_attribute(self) -> None:
        err = AppError("fail", detail={"key": "value"})
        assert err.detail == {"key": "value"}

    def test_is_exception(self) -> None:
        assert issubclass(AppError, Exception)


class TestNotFoundError:
    def test_status_code_404(self) -> None:
        err = NotFoundError("Trade", "trade-123")
        assert err.status_code == 404

    def test_message_format(self) -> None:
        err = NotFoundError("Trade", "trade-abc")
        assert err.message == "Trade 'trade-abc' not found"

    def test_inherits_app_error(self) -> None:
        assert issubclass(NotFoundError, AppError)


class TestDatabaseError:
    def test_status_code_503(self) -> None:
        err = DatabaseError()
        assert err.status_code == 503

    def test_default_message(self) -> None:
        err = DatabaseError()
        assert err.message == "Database unavailable"

    def test_custom_message(self) -> None:
        err = DatabaseError("Connection pool exhausted")
        assert err.message == "Connection pool exhausted"

    def test_inherits_app_error(self) -> None:
        assert issubclass(DatabaseError, AppError)


class TestConflictError:
    def test_status_code_409(self) -> None:
        err = ConflictError("Already exists")
        assert err.status_code == 409

    def test_message(self) -> None:
        err = ConflictError("Duplicate entry")
        assert err.message == "Duplicate entry"

    def test_inherits_app_error(self) -> None:
        assert issubclass(ConflictError, AppError)


# ---------------------------------------------------------------------------
# Error handler response format (via TestClient)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app

from tests.conftest import (
    mock_trade_repo,
    mock_watchlist_repo,
    mock_scan_repo,
)
from unittest.mock import MagicMock
from app.dependencies import (
    get_trade_service,
    get_portfolio_service,
    get_watchlist_service,
    get_scan_service,
)
from app.repositories.trade_repository import TradeRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.repositories.scan_repository import ScanRepository
from app.services.trade_service import TradeService
from app.services.portfolio_service import PortfolioService
from app.services.watchlist_service import WatchlistService
from app.services.scan_service import ScanService


@pytest.fixture()
def error_client() -> TestClient:
    """TestClient with services that raise exceptions for error testing."""
    mock_trade = MagicMock(spec=TradeRepository)
    mock_watch = MagicMock(spec=WatchlistRepository)
    mock_scan = MagicMock(spec=ScanRepository)

    mock_trade.insert.return_value = "trade-1"
    mock_trade.get_active_trades.return_value = []
    mock_trade.get_closed_trades.return_value = []
    mock_trade.close_trade.side_effect = NotFoundError("Trade", "trade-nonexist")
    mock_watch.get_all_symbols.return_value = ["SPY"]
    mock_watch.add_symbol.side_effect = ConflictError("Symbol 'SPY' already in watchlist")
    mock_watch.remove_symbol.side_effect = NotFoundError("Watchlist symbol", "ZZZZ")
    mock_scan.get_latest.return_value = []

    def _trade_svc() -> TradeService:
        return TradeService(repo=mock_trade)

    def _portfolio_svc() -> PortfolioService:
        return PortfolioService(repo=mock_trade)

    def _watchlist_svc() -> WatchlistService:
        return WatchlistService(repo=mock_watch)

    def _scan_svc() -> ScanService:
        return ScanService(repo=mock_scan)

    app.dependency_overrides[get_trade_service] = _trade_svc
    app.dependency_overrides[get_portfolio_service] = _portfolio_svc
    app.dependency_overrides[get_watchlist_service] = _watchlist_svc
    app.dependency_overrides[get_scan_service] = _scan_svc

    yield TestClient(app)
    app.dependency_overrides.clear()


class TestErrorHandlerResponses:
    """Verify global error handlers return consistent JSON responses."""

    def test_not_found_returns_404_json(self, error_client: TestClient) -> None:
        resp = error_client.post(
            "/api/trades/close",
            json={"tradeId": "trade-nonexist", "exitPrice": 5.0},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["status"] == "error"
        assert "not found" in data["detail"]
        assert data["code"] == 404

    def test_conflict_returns_409_json(self, error_client: TestClient) -> None:
        resp = error_client.post(
            "/api/watchlist/add", json={"symbol": "SPY"}
        )
        assert resp.status_code == 409
        data = resp.json()
        assert data["status"] == "error"
        assert data["code"] == 409
        assert "already" in data["detail"].lower()

    def test_not_found_watchlist_remove_returns_404(self, error_client: TestClient) -> None:
        resp = error_client.post(
            "/api/watchlist/remove", json={"symbol": "ZZZZ"}
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["status"] == "error"

    def test_validation_error_returns_422_json(self, error_client: TestClient) -> None:
        resp = error_client.post(
            "/api/trades/track", json={"symbol": "META"}
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["status"] == "error"
        assert data["code"] == 422
        assert len(data["detail"]) > 0

    def test_validation_error_includes_field_info(self, error_client: TestClient) -> None:
        resp = error_client.post(
            "/api/trades/track",
            json={
                "opportunityId": "opp-001",
                "symbol": "META",
                "strikePrice": -1,  # invalid
                "expirationDate": "bad",
                "optionType": "CALL",
                "entryPrice": 5.0,
                "currentPrice": 6.0,
                "quantity": 1,
                "underlyingPrice": 100.0,
                "greeks": {"delta": 0.5, "gamma": 0.1, "theta": -0.02, "vega": 0.1},
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        # Should reference the field with the error
        assert "strikePrice" in detail or "expirationDate" in detail
