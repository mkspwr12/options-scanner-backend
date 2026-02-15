"""Options Scanner API — FastAPI application entry point.

This module creates the FastAPI app, registers middleware, error handlers,
and includes routers.  Business logic lives in services/ and data access
in repositories/.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .exceptions import register_error_handlers
from .routers import health, logs, scan, trades, watchlist

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
                "timestamp": datetime.utcnow().isoformat(),
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
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Options Scanner API", version="2.0.0")

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
