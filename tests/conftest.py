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
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"  # disable rate limiting in tests
os.environ["SCAN_ENABLED"] = "false"  # disable background scanner in tests


from app.dependencies import (  # noqa: E402
    get_portfolio_service,
    get_position_service,
    get_scan_service,
    get_multi_leg_scan_service,
    get_trade_service,
    get_watchlist_service,
    get_provider_service,
    get_options_chain_service,
    get_strategy_service,
    get_metrics_service,
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
from app.repositories.provider_repository import ProviderRepository  # noqa: E402
from app.repositories.strategy_repository import StrategyRepository  # noqa: E402
from app.repositories.metrics_repository import MetricsRepository  # noqa: E402
from app.repositories.position_repository import PositionRepository  # noqa: E402
from app.providers.registry import ProviderRegistry  # noqa: E402
from app.providers.mock_provider import MockProvider  # noqa: E402
from app.services.multi_leg_scan_service import MultiLegScanService  # noqa: E402
from app.services.portfolio_service import PortfolioService  # noqa: E402
from app.services.scan_service import ScanService  # noqa: E402
from app.services.trade_service import TradeService  # noqa: E402
from app.services.watchlist_service import WatchlistService  # noqa: E402
from app.services.provider_service import ProviderService  # noqa: E402
from app.services.options_chain_service import OptionsChainService  # noqa: E402
from app.services.strategy_service import StrategyService  # noqa: E402
from app.services.metrics_service import MetricsService  # noqa: E402
from app.services.position_service import PositionService  # noqa: E402


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
    stored: list = []

    def _save(results: list) -> None:
        stored.clear()
        stored.extend(results)

    def _get_latest(**kwargs: Any) -> list:
        return stored

    repo.get_latest.side_effect = _get_latest
    repo.save_results.side_effect = _save
    return repo


@pytest.fixture()
def mock_provider_repo() -> MagicMock:
    repo = MagicMock(spec=ProviderRepository)
    repo.get_all.return_value = []
    repo.get_by_id.return_value = None
    repo.insert.return_value = None
    repo.update.return_value = None
    repo.delete.return_value = None
    repo.count.return_value = 0
    return repo


@pytest.fixture()
def mock_strategy_repo() -> MagicMock:
    repo = MagicMock(spec=StrategyRepository)
    repo.get_all.return_value = []
    repo.get_by_id.return_value = None
    repo.insert.return_value = None
    repo.update.return_value = None
    repo.delete.return_value = None
    return repo


@pytest.fixture()
def mock_metrics_repo() -> MagicMock:
    repo = MagicMock(spec=MetricsRepository)
    repo.record.return_value = None
    repo.get_aggregated.return_value = {
        "total_calls": 0,
        "success_count": 0,
        "error_count": 0,
        "avg_latency": 0,
        "error_rate": 0,
    }
    repo.get_top_errors.return_value = []
    repo.get_all_providers_summary.return_value = []
    return repo


@pytest.fixture()
def mock_position_repo() -> MagicMock:
    repo = MagicMock(spec=PositionRepository)
    repo.insert.return_value = "pos-abc12345"
    repo.get_all_open.return_value = []
    repo.get_all.return_value = []
    repo.get_by_id.return_value = None
    return repo


@pytest.fixture()
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    return registry


# ---------------------------------------------------------------------------
# TestClient with overridden DI
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(
    mock_trade_repo: MagicMock,
    mock_watchlist_repo: MagicMock,
    mock_scan_repo: MagicMock,
    mock_provider_repo: MagicMock,
    mock_strategy_repo: MagicMock,
    mock_metrics_repo: MagicMock,
    mock_position_repo: MagicMock,
    mock_registry: MagicMock,
) -> TestClient:
    """Return a FastAPI TestClient with stubbed service dependencies."""

    mock_provider = MockProvider()

    def _trade_svc() -> TradeService:
        return TradeService(repo=mock_trade_repo)

    def _portfolio_svc() -> PortfolioService:
        return PortfolioService(repo=mock_trade_repo)

    def _watchlist_svc() -> WatchlistService:
        return WatchlistService(repo=mock_watchlist_repo)

    def _scan_svc() -> ScanService:
        return ScanService(repo=mock_scan_repo, provider=mock_provider)

    def _multi_leg_svc() -> MultiLegScanService:
        return MultiLegScanService(provider=mock_provider)

    def _provider_svc() -> ProviderService:
        return ProviderService(repo=mock_provider_repo, registry=mock_registry)

    def _options_chain_svc() -> OptionsChainService:
        return OptionsChainService(registry=mock_registry)

    def _strategy_svc() -> StrategyService:
        return StrategyService(repo=mock_strategy_repo)

    def _metrics_svc() -> MetricsService:
        return MetricsService(repo=mock_metrics_repo)

    def _position_svc() -> PositionService:
        return PositionService(repo=mock_position_repo)

    app.dependency_overrides[get_trade_service] = _trade_svc
    app.dependency_overrides[get_portfolio_service] = _portfolio_svc
    app.dependency_overrides[get_watchlist_service] = _watchlist_svc
    app.dependency_overrides[get_scan_service] = _scan_svc
    app.dependency_overrides[get_multi_leg_scan_service] = _multi_leg_svc
    app.dependency_overrides[get_provider_service] = _provider_svc
    app.dependency_overrides[get_options_chain_service] = _options_chain_svc
    app.dependency_overrides[get_strategy_service] = _strategy_svc
    app.dependency_overrides[get_metrics_service] = _metrics_svc
    app.dependency_overrides[get_position_service] = _position_svc

    # Pre-populate scan data by triggering a scan
    test_client = TestClient(app)
    test_client.post("/api/scan/trigger")

    yield test_client

    app.dependency_overrides.clear()
