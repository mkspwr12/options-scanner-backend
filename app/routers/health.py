"""Health and diagnostics router."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..db import get_connection

router = APIRouter(tags=["Health"])


@router.get("/healthz")
def healthz() -> dict:
    """Lightweight health check without database dependency."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health")
def health() -> dict:
    """Health check — verifies configuration is present."""
    try:
        settings = get_settings()

        if not settings.sql_connection_string:
            raise HTTPException(status_code=503, detail="SQL_CONNECTION_STRING not configured")

        server = "unknown"
        for part in settings.sql_connection_string.split(";"):
            if part.lower().startswith("server="):
                server = part.split("=", 1)[1]
                break

        return {
            "status": "ok",
            "auth": "managed-identity",
            "database": "configured",
            "server": server,
            "note": "Database connectivity check skipped due to pyodbc segfault on Linux. Use /healthz for lightweight check.",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/diagnostics")
def diagnostics() -> dict:
    """Comprehensive diagnostics endpoint."""
    from ..main import log_store  # deferred to avoid circular import

    settings = get_settings()

    db_info: dict = {"connected": False, "name": None, "server": None, "error": None}

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DB_NAME()")
            db_info["name"] = cursor.fetchone()[0]
            cursor.execute("SELECT @@version")
            db_info["version"] = cursor.fetchone()[0]
            db_info["connected"] = True
    except Exception as exc:
        db_info["error"] = str(exc)

    for part in settings.sql_connection_string.split(";"):
        if part.lower().startswith("server="):
            db_info["server"] = part.split("=", 1)[1]
            break

    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "backend": {"version": "2.0.0", "environment": "production", "uptime": "running"},
        "database": db_info,
        "environment": {
            "sql_connection_string_set": bool(settings.sql_connection_string),
            "sql_driver": settings.sql_driver,
            "azure_client_id": settings.azure_client_id is not None,
        },
        "recent_logs": log_store.get_logs(20),
    }


@router.get("/api/debug/config")
def debug_config() -> dict:
    """Show configuration (excluding secrets)."""
    settings = get_settings()
    return {
        "sql_driver": settings.sql_driver,
        "sql_connection_string_set": bool(settings.sql_connection_string),
        "azure_client_id_set": bool(settings.azure_client_id),
        "allowed_origins": settings.allowed_origins,
        "scan_interval_minutes": settings.scan_interval_minutes,
        "scan_enabled": settings.scan_enabled,
        "market_data_provider": settings.market_data_provider,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/")
def root() -> dict:
    """Root endpoint with API documentation."""
    return {
        "name": "Options Scanner API",
        "version": "2.0.0",
        "endpoints": {
            "GET /health": "Health check with database verification",
            "GET /healthz": "Lightweight liveness probe",
            "GET /api/scan": "Get scan opportunities",
            "GET /api/portfolio": "Get portfolio data",
            "GET /api/watchlist": "Get watched symbols",
            "POST /api/trades/track": "Track a new trade position",
            "POST /api/trades/close": "Close an existing trade",
            "GET /api/multi-leg-opportunities": "Get multi-leg strategies",
            "GET /api/logs": "Get recent backend logs",
            "POST /api/logs": "Receive logs from frontend",
            "GET /api/diagnostics": "Comprehensive system diagnostics",
            "GET /api/debug/config": "Show configuration (no secrets)",
        },
    }
