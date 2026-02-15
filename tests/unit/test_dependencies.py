"""Unit tests for dependency injection factories (app/dependencies.py).

Covers:
- Each factory returns the correct service type
- Services receive fresh repository instances
"""
from __future__ import annotations

import os
os.environ.setdefault("SQL_CONNECTION_STRING", "Server=test;Database=test;")

from app.dependencies import (
    get_portfolio_service,
    get_scan_service,
    get_trade_service,
    get_watchlist_service,
)
from app.services.portfolio_service import PortfolioService
from app.services.scan_service import ScanService
from app.services.trade_service import TradeService
from app.services.watchlist_service import WatchlistService


class TestDependencyFactories:
    def test_get_trade_service_returns_correct_type(self) -> None:
        svc = get_trade_service()
        assert isinstance(svc, TradeService)

    def test_get_portfolio_service_returns_correct_type(self) -> None:
        svc = get_portfolio_service()
        assert isinstance(svc, PortfolioService)

    def test_get_watchlist_service_returns_correct_type(self) -> None:
        svc = get_watchlist_service()
        assert isinstance(svc, WatchlistService)

    def test_get_scan_service_returns_correct_type(self) -> None:
        svc = get_scan_service()
        assert isinstance(svc, ScanService)

    def test_each_call_returns_new_instance(self) -> None:
        """No singletons — each call should produce a fresh service."""
        s1 = get_trade_service()
        s2 = get_trade_service()
        assert s1 is not s2
