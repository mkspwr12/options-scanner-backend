"""Shared fixtures for the Options Scanner test suite.

Every test gets a FastAPI `TestClient` wired with stubbed-out
repository dependencies so no database is needed.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure required env vars are set **before** anything imports config
os.environ.setdefault("SQL_CONNECTION_STRING", "Server=test;Database=test;")


from app.dependencies import (  # noqa: E402
    get_portfolio_service,
    get_scan_service,
    get_trade_service,
    get_watchlist_service,
)
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    ClosedTrade,
    Greeks,
    PortfolioMetrics,
    PortfolioResponse,
    TrackedTrade,
)
from app.repositories.scan_repository import ScanRepository  # noqa: E402
from app.repositories.trade_repository import TradeRepository  # noqa: E402
from app.repositories.watchlist_repository import WatchlistRepository  # noqa: E402
from app.services.portfolio_service import PortfolioService  # noqa: E402
from app.services.scan_service import ScanService  # noqa: E402
from app.services.trade_service import TradeService  # noqa: E402
from app.services.watchlist_service import WatchlistService  # noqa: E402


# ---------------------------------------------------------------------------
# Factory helpers for sample domain objects
# ---------------------------------------------------------------------------

def make_greeks(**overrides: float) -> Greeks:
    defaults: dict[str, float] = {"delta": 0.42, "gamma": 0.06, "theta": -0.03, "vega": 0.12}
    defaults.update(overrides)
    return Greeks(**defaults)


def make_active_trade(**overrides: Any) -> TrackedTrade:
    now_ms = 1_700_000_000_000
    defaults: dict[str, Any] = {
        "id": "trade-abc123",
        "opportunityId": "opp-001",
        "symbol": "META",
        "strikePrice": 690.0,
        "expirationDate": "2025-02-28",
        "optionType": "CALL",
        "entryPrice": 5.8,
        "currentPrice": 6.9,
        "quantity": 2,
        "underlyingPrice": 689.3,
        "greeks": make_greeks(),
        "entryDate": now_ms - 86_400_000,
        "unrealizedPL": 220.0,
        "unrealizedPLPercent": 18.96,
        "status": "active",
    }
    defaults.update(overrides)
    return TrackedTrade(**defaults)


def make_closed_trade(**overrides: Any) -> ClosedTrade:
    now_ms = 1_700_000_000_000
    defaults: dict[str, Any] = {
        "id": "trade-xyz789",
        "opportunityId": "opp-000",
        "symbol": "AAPL",
        "strikePrice": 220.0,
        "expirationDate": "2025-02-14",
        "optionType": "CALL",
        "entryPrice": 3.2,
        "currentPrice": 3.2,
        "quantity": 1,
        "underlyingPrice": 219.7,
        "greeks": make_greeks(delta=0.35, gamma=0.04, theta=-0.02, vega=0.09),
        "entryDate": now_ms - 259_200_000,
        "unrealizedPL": 0.0,
        "unrealizedPLPercent": 0.0,
        "status": "closed",
        "exitPrice": 4.1,
        "exitDate": now_ms - 86_400_000,
        "realizedPL": 90.0,
        "realizedPLPercent": 28.12,
    }
    defaults.update(overrides)
    return ClosedTrade(**defaults)


# ---------------------------------------------------------------------------
# Stubbed repositories (avoid real DB access)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_trade_repo() -> MagicMock:
    repo = MagicMock(spec=TradeRepository)
    repo.insert.return_value = "trade-new123"
    repo.get_active_trades.return_value = [make_active_trade()]
    repo.get_closed_trades.return_value = [make_closed_trade()]
    repo.get_by_id.return_value = make_active_trade()
    repo.close_trade.return_value = {"tradeId": "trade-abc123", "realizedPL": 220.0}
    return repo


@pytest.fixture()
def mock_watchlist_repo() -> MagicMock:
    repo = MagicMock(spec=WatchlistRepository)
    repo.get_all_symbols.return_value = ["META", "SPY", "AAPL"]
    repo.add_symbol.return_value = None
    repo.remove_symbol.return_value = None
    return repo


@pytest.fixture()
def mock_scan_repo() -> MagicMock:
    repo = MagicMock(spec=ScanRepository)
    repo.get_latest.return_value = []  # triggers fallback to sample data
    return repo


# ---------------------------------------------------------------------------
# TestClient with overridden DI
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(
    mock_trade_repo: MagicMock,
    mock_watchlist_repo: MagicMock,
    mock_scan_repo: MagicMock,
) -> TestClient:
    """Return a FastAPI TestClient with stubbed service dependencies."""

    def _trade_svc() -> TradeService:
        return TradeService(repo=mock_trade_repo)

    def _portfolio_svc() -> PortfolioService:
        return PortfolioService(repo=mock_trade_repo)

    def _watchlist_svc() -> WatchlistService:
        return WatchlistService(repo=mock_watchlist_repo)

    def _scan_svc() -> ScanService:
        return ScanService(repo=mock_scan_repo)

    app.dependency_overrides[get_trade_service] = _trade_svc
    app.dependency_overrides[get_portfolio_service] = _portfolio_svc
    app.dependency_overrides[get_watchlist_service] = _watchlist_svc
    app.dependency_overrides[get_scan_service] = _scan_svc

    yield TestClient(app)

    app.dependency_overrides.clear()
