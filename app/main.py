"""Options Scanner API — FastAPI application entry point.

This module creates the FastAPI app, registers middleware, error handlers,
and includes routers.  Business logic lives in services/ and data access
in repositories/.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .dependencies import get_scan_service, get_watchlist_service
from .exceptions import register_error_handlers
from .middleware.auth import ApiKeyMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routers import health, logs, scan, trades, watchlist
from .routers import options_chain, portfolio_actions, portfolio_risk, providers, strategies

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
try:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
except Exception:
    pass

logger = logging.getLogger(__name__)

# Azure Application Insights (optional)
_ai_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") or os.getenv(
    "APPINSIGHTS_CONNECTION_STRING"
)
if _ai_conn:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=_ai_conn)
        logging.getLogger("appinsights").info("Application Insights configured")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# In-memory log store (shared with routers/logs.py & routers/health.py)
# ---------------------------------------------------------------------------
class LogStore:
    """Simple in-memory ring-buffer for recent log entries."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.logs: List[Dict[str, Any]] = []
        self.max_entries = max_entries

    def add(self, level: str, message: str, data: Any = None) -> None:
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
                "data": data,
                "source": "backend",
            }
            self.logs.append(entry)
            if len(self.logs) > self.max_entries:
                self.logs.pop(0)
        except Exception:
            pass

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            return list(reversed(self.logs[-limit:]))
        except Exception:
            return []


try:
    log_store = LogStore()
except Exception:

    class _Fallback:
        logs: List[Dict[str, Any]] = []

        def add(self, level: str, message: str, data: Any = None) -> None:
            pass

        def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
            return []

    log_store = _Fallback()  # type: ignore[assignment]


def safe_log(level: str, message: str, data: Any = None) -> None:
    """Write to both the in-memory store and stdlib logger."""
    try:
        log_store.add(level, message, data)
    except Exception:
        pass
    try:
        if data is not None:
            logger.log(
                getattr(logging, level.upper(), logging.INFO),
                "%s | %s",
                message,
                json.dumps(data, default=str),
            )
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), message)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Background scanner task
# ---------------------------------------------------------------------------
_scan_task: asyncio.Task[None] | None = None


async def _background_scanner() -> None:
    """Periodically scan watchlist symbols using the configured provider."""
    try:
        settings = get_settings()
        interval = settings.scan_interval_minutes * 60
    except Exception:
        interval = 15 * 60

    logger.info("Background scanner started (interval=%ds)", interval)

    while True:
        try:
            await asyncio.sleep(interval)
            scan_svc = get_scan_service()
            wl_svc = get_watchlist_service()
            symbols = wl_svc.get_symbols()
            result = scan_svc.run_scan(symbols)
            safe_log(
                "info",
                f"Background scan completed: {result.get('resultsCount', 0)} results",
            )
        except asyncio.CancelledError:
            logger.info("Background scanner stopped")
            return
        except Exception:
            logger.exception("Background scanner error — will retry next interval")


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ANN201
    """Startup / shutdown lifecycle for background tasks and migrations."""
    # Run database migrations on startup
    _run_migrations()

    global _scan_task  # noqa: PLW0603
    try:
        settings = get_settings()
        if settings.scan_enabled:
            _scan_task = asyncio.create_task(_background_scanner())
            logger.info("Background scanner task created")
    except Exception:
        logger.warning("Could not start background scanner (config error)")
    yield
    if _scan_task is not None:
        _scan_task.cancel()
        try:
            await _scan_task
        except asyncio.CancelledError:
            pass


def _run_migrations() -> None:
    """Execute all SQL migration files in order on startup (idempotent)."""
    import glob
    import pathlib

    from .db import get_connection

    migrations_dir = pathlib.Path(__file__).resolve().parent.parent / "migrations"
    files = sorted(glob.glob(str(migrations_dir / "*.sql")))

    if not files:
        logger.info("No migration files found in %s", migrations_dir)
        return

    logger.info("Running %d migration(s) from %s", len(files), migrations_dir)

    try:
        conn = get_connection()
        conn.autocommit = True
    except Exception:
        logger.warning("Cannot connect to database — skipping migrations")
        return

    for path in files:
        name = os.path.basename(path)
        try:
            with open(path, "r") as f:
                sql = f.read()

            # Split on GO statements (SQL Server batch separator)
            batches = [b.strip() for b in sql.split("\nGO") if b.strip()]

            for batch in batches:
                if not batch or batch.upper() == "GO":
                    continue
                cursor = conn.cursor()
                cursor.execute(batch)
                try:
                    while cursor.nextset():
                        pass
                except Exception:
                    pass

            logger.info("Migration %s: OK", name)
        except Exception as exc:
            logger.warning("Migration %s: FAILED — %s", name, exc)

    try:
        conn.close()
    except Exception:
        pass

    logger.info("Migrations complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Options Scanner API",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — uses configurable origins with safe fallback
try:
    _origins = get_settings().allowed_origins
except Exception:
    _origins = [
        "https://options-scanner-frontend-2exk6s.azurewebsites.net",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key authentication (disabled when API_KEY env var is unset)
try:
    _api_key = get_settings().api_key
except Exception:
    _api_key = None
app.add_middleware(ApiKeyMiddleware, api_key=_api_key)

# Rate limiting
try:
    _rate_limit = get_settings().rate_limit_per_minute
except Exception:
    _rate_limit = 60
app.add_middleware(RateLimitMiddleware, max_requests=_rate_limit, window_seconds=60)

# Register global error handlers
register_error_handlers(app)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):  # noqa: ANN001
    safe_log("info", f"→ {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        safe_log("info", f"← {request.method} {request.url.path} {response.status_code}")
        return response
    except Exception as exc:
        safe_log("error", f"✗ {request.method} {request.url.path}", {"error": str(exc)})
        raise


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(trades.router)
app.include_router(watchlist.router)
app.include_router(scan.router)
app.include_router(logs.router)
app.include_router(providers.router)
app.include_router(options_chain.router)
app.include_router(strategies.router)
app.include_router(portfolio_risk.router)
app.include_router(portfolio_actions.router)
