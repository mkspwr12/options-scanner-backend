"""FastAPI dependency injection for services."""
from __future__ import annotations

import logging

from .config import get_settings
from .providers.base import MarketDataProvider
from .providers.circuit_breaker import CircuitBreaker
from .providers.registry import ProviderRegistry
from .repositories.metrics_repository import MetricsRepository
from .repositories.position_repository import PositionRepository
from .repositories.provider_repository import ProviderRepository
from .repositories.scan_repository import ScanRepository
from .repositories.strategy_repository import StrategyRepository
from .repositories.trade_repository import TradeRepository
from .repositories.watchlist_repository import WatchlistRepository
from .services.metrics_service import MetricsService
from .services.multi_leg_scan_service import MultiLegScanService
from .services.options_chain_service import OptionsChainService
from .services.portfolio_service import PortfolioService
from .services.position_action_service import PositionActionService
from .services.position_service import PositionService
from .services.provider_service import ProviderService
from .services.scan_service import ScanService
from .services.stock_scan_service import StockScanService
from .services.strategy_service import StrategyService
from .services.trade_service import TradeService
from .services.watchlist_service import WatchlistService

logger = logging.getLogger(__name__)

# Singleton-ish: created once, reused across requests
_provider: MarketDataProvider | None = None
_circuit_breaker: CircuitBreaker | None = None
_registry: ProviderRegistry | None = None


def _get_provider() -> MarketDataProvider | None:
    """Lazily create the market data provider based on config."""
    global _provider  # noqa: PLW0603
    if _provider is not None:
        return _provider

    try:
        settings = get_settings()
    except Exception:
        return None

    name = settings.market_data_provider
    if name in ("polygon", "polygon_io", "massive"):
        from .providers.polygon_provider import PolygonProvider

        _provider = PolygonProvider()
        logger.info("Market data provider: Polygon")
    elif name in ("yahoo_finance", "yahoo"):
        from .providers.yahoo_provider import YahooFinanceProvider

        _provider = YahooFinanceProvider()
        logger.info("Market data provider: YahooFinance")
    else:
        from .providers.yahoo_provider import YahooFinanceProvider

        _provider = YahooFinanceProvider()
        logger.info("Market data provider: YahooFinance (default)")
    return _provider


def _get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker  # noqa: PLW0603
    if _circuit_breaker is not None:
        return _circuit_breaker
    try:
        settings = get_settings()
        _circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_threshold,
            recovery_timeout=float(settings.circuit_breaker_timeout),
            name="market_data",
        )
    except Exception:
        _circuit_breaker = CircuitBreaker(name="market_data")
    return _circuit_breaker


def _get_registry() -> ProviderRegistry:
    """Lazily create the provider registry with the default provider."""
    global _registry  # noqa: PLW0603
    if _registry is not None:
        return _registry

    _registry = ProviderRegistry()
    try:
        settings = get_settings()
        name = settings.market_data_provider
        if name in ("polygon", "polygon_io", "massive"):
            ptype = "POLYGON"
        else:
            ptype = "YAHOO_FINANCE"
    except Exception:
        ptype = "YAHOO_FINANCE"

    _registry.register(
        "default",
        {"type": ptype, "enabled": True, "priority": 1},
    )

    # Load DB-stored providers into registry so proxy/test/metrics work
    try:
        repo = ProviderRepository()
        for row in repo.get_all():
            pid = row.get("id") or row.get("provider_id")
            if pid and pid != "default":
                _registry.register(pid, row)
        logger.debug("Loaded DB providers into registry")
    except Exception:
        logger.debug("Could not load DB providers into registry (DB may be unavailable)")

    return _registry


# ---------------------------------------------------------------------------
# Original service factories
# ---------------------------------------------------------------------------


def get_trade_service() -> TradeService:
    return TradeService(TradeRepository())


def get_portfolio_service() -> PortfolioService:
    return PortfolioService(TradeRepository())


def get_watchlist_service() -> WatchlistService:
    return WatchlistService(WatchlistRepository())


def get_scan_service() -> ScanService:
    return ScanService(
        repo=ScanRepository(),
        provider=_get_provider(),
        circuit_breaker=_get_circuit_breaker(),
    )


# ---------------------------------------------------------------------------
# New service factories (Phase 1–6)
# ---------------------------------------------------------------------------


def get_provider_service() -> ProviderService:
    return ProviderService(
        repo=ProviderRepository(),
        registry=_get_registry(),
    )


def get_options_chain_service() -> OptionsChainService:
    return OptionsChainService(registry=_get_registry())


def get_strategy_service() -> StrategyService:
    return StrategyService(repo=StrategyRepository())


def get_metrics_service() -> MetricsService:
    return MetricsService(repo=MetricsRepository())


# ---------------------------------------------------------------------------
# New service factories (Issues #11, #12, #14)
# ---------------------------------------------------------------------------


def get_multi_leg_scan_service() -> MultiLegScanService:
    return MultiLegScanService(provider=_get_provider())


def get_stock_scan_service() -> StockScanService:
    return StockScanService(provider=_get_provider())


def get_position_action_service() -> PositionActionService:
    return PositionActionService(repo=TradeRepository())


def get_position_service() -> PositionService:
    return PositionService(PositionRepository())
