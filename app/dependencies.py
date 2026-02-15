"""FastAPI dependency injection for services."""
from __future__ import annotations

from .repositories.scan_repository import ScanRepository
from .repositories.trade_repository import TradeRepository
from .repositories.watchlist_repository import WatchlistRepository
from .services.portfolio_service import PortfolioService
from .services.scan_service import ScanService
from .services.trade_service import TradeService
from .services.watchlist_service import WatchlistService


def get_trade_service() -> TradeService:
    return TradeService(TradeRepository())


def get_portfolio_service() -> PortfolioService:
    return PortfolioService(TradeRepository())


def get_watchlist_service() -> WatchlistService:
    return WatchlistService(WatchlistRepository())


def get_scan_service() -> ScanService:
    return ScanService(ScanRepository())
