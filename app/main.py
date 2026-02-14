from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import get_connection
from .models import (
    Greeks,
    OptionOpportunity,
    PortfolioMetrics,
    PortfolioResponse,
    TrackedTrade,
    ClosedTrade,
)

# Configure structured logging
try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
except Exception:
    pass  # Ignore logging errors

logger = logging.getLogger(__name__)

app_insights_connection = (
    os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    or os.getenv("APPINSIGHTS_CONNECTION_STRING")
)
if app_insights_connection:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=app_insights_connection)
        safe_logger = logging.getLogger("appinsights")
        safe_logger.info("Application Insights configured")
    except Exception:
        pass

# In-memory log storage for frontend access
class LogStore:
    def __init__(self, max_entries: int = 1000):
        self.logs: List[Dict[str, Any]] = []
        self.max_entries = max_entries
    
    def add(self, level: str, message: str, data: Any = None) -> None:
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": level,
                "message": message,
                "data": data,
                "source": "backend"
            }
            self.logs.append(entry)
            if len(self.logs) > self.max_entries:
                self.logs.pop(0)
        except Exception:
            pass  # Silently fail on log store errors
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            return list(reversed(self.logs[-limit:]))
        except Exception:
            return []

try:
    log_store = LogStore()
except Exception:
    # Fallback if LogStore fails to initialize
    class FallbackLogStore:
        def add(self, level: str, message: str, data: Any = None) -> None:
            pass
        def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
            return []
    log_store = FallbackLogStore()


def safe_log(level: str, message: str, data: Any = None) -> None:
    try:
        log_store.add(level, message, data)
    except Exception:
        pass
    try:
        if data is not None:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"{message} | {json.dumps(data, default=str)}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), message)
    except Exception:
        pass

app = FastAPI(title="Options Scanner API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://options-scanner-frontend-2exk6s.azurewebsites.net",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to log all requests (with error handling)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    safe_log("info", f"→ {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        safe_log("info", f"← {request.method} {request.url.path} {response.status_code}")
        return response
    except Exception as e:
        safe_log("error", f"✗ {request.method} {request.url.path}", {"error": str(e)})
        raise


@app.get("/healthz")
def healthz() -> dict:
    """Lightweight health check without database dependency."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health() -> dict:
    """Health check endpoint - verifies database connectivity."""
    try:
        settings = get_settings()
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DB_NAME()")
            db_name = cursor.fetchone()[0]
        
        server = "unknown"
        for part in settings.sql_connection_string.split(";"):
            if part.lower().startswith("server="):
                server = part.split("=", 1)[1]
                break

        response = {
            "status": "ok",
            "auth": "managed-identity",
            "database": db_name,
            "server": server,
            "timestamp": datetime.utcnow().isoformat()
        }
        return response
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/scan")
def scan() -> dict:
    now = int(datetime.utcnow().timestamp() * 1000)
    sample = [
        OptionOpportunity(
            id="opp-001",
            symbol="META",
            strikePrice=690.0,
            expirationDate=(datetime.utcnow() + timedelta(days=28)).strftime("%Y-%m-%d"),
            optionType="CALL",
            currentPrice=6.9,
            underlyingPrice=689.3,
            impliedVolatility=0.31,
            greeks=Greeks(delta=0.42, gamma=0.06, theta=-0.03, vega=0.12),
            potentialGain=13.8,
            potentialLoss=4.9,
            riskRewardRatio=2.81,
            confidenceScore=78,
            timestamp=now,
        ),
        OptionOpportunity(
            id="opp-002",
            symbol="SPY",
            strikePrice=690.0,
            expirationDate=(datetime.utcnow() + timedelta(days=21)).strftime("%Y-%m-%d"),
            optionType="PUT",
            currentPrice=5.2,
            underlyingPrice=681.7,
            impliedVolatility=0.27,
            greeks=Greeks(delta=-0.38, gamma=0.05, theta=-0.02, vega=0.11),
            potentialGain=9.7,
            potentialLoss=3.8,
            riskRewardRatio=2.55,
            confidenceScore=74,
            timestamp=now,
        ),
    ]
    return {"status": "ok", "opportunities": sample}


@app.get("/api/portfolio")
def portfolio() -> dict:
    now = int(datetime.utcnow().timestamp() * 1000)
    metrics = PortfolioMetrics(
        totalValue=12450.0,
        totalPL=420.0,
        totalPLPercent=3.49,
        winRate=62.5,
        totalTrades=8,
        activeTrades=3,
        aggregateGreeks=Greeks(delta=0.28, gamma=0.07, theta=-0.11, vega=0.22),
    )

    active_trades = [
        TrackedTrade(
            id="trade-101",
            opportunityId="opp-001",
            symbol="META",
            strikePrice=690.0,
            expirationDate=(datetime.utcnow() + timedelta(days=28)).strftime("%Y-%m-%d"),
            optionType="CALL",
            entryPrice=5.8,
            currentPrice=6.9,
            quantity=2,
            underlyingPrice=689.3,
            greeks=Greeks(delta=0.42, gamma=0.06, theta=-0.03, vega=0.12),
            entryDate=now - 86400000,
            unrealizedPL=220.0,
            unrealizedPLPercent=18.96,
            status="active",
        )
    ]

    closed_trades = [
        ClosedTrade(
            id="trade-099",
            opportunityId="opp-000",
            symbol="AAPL",
            strikePrice=220.0,
            expirationDate=(datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d"),
            optionType="CALL",
            entryPrice=3.2,
            currentPrice=3.2,
            quantity=1,
            underlyingPrice=219.7,
            greeks=Greeks(delta=0.35, gamma=0.04, theta=-0.02, vega=0.09),
            entryDate=now - 259200000,
            unrealizedPL=0.0,
            unrealizedPLPercent=0.0,
            status="closed",
            exitPrice=4.1,
            exitDate=now - 86400000,
            realizedPL=90.0,
            realizedPLPercent=28.12,
        )
    ]

    response = PortfolioResponse(
        metrics=metrics,
        activeTrades=active_trades,
        closedTrades=closed_trades,
    )
    return {"status": "ok", "portfolio": response}


@app.get("/api/watchlist")
def watchlist() -> dict:
    symbols = ["META", "SPY", "AAPL", "NVDA"]
    return {"status": "ok", "symbols": symbols}


# ===== Diagnostics & Logging Endpoints =====

@app.get("/api/logs")
def get_logs(limit: int = 100) -> dict:
    """Get recent backend logs for debugging."""
    return {
        "status": "ok",
        "logs": log_store.get_logs(limit),
        "total": len(log_store.logs)
    }


@app.post("/api/logs")
def receive_logs(log_entry: Dict[str, Any]) -> dict:
    """Receive logs from frontend and store them."""
    log_entry["source"] = "frontend"
    log_store.add(
        log_entry.get("level", "info"),
        log_entry.get("message", ""),
        log_entry.get("data")
    )
    return {"status": "ok", "logged": True}


@app.get("/api/diagnostics")
def diagnostics() -> dict:
    """Comprehensive diagnostics endpoint."""
    try:
        settings = get_settings()
        
        # Database info
        db_info = {
            "connected": False,
            "name": None,
            "server": None,
            "error": None
        }
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DB_NAME()")
                db_info["name"] = cursor.fetchone()[0]
                cursor.execute("SELECT @@version")
                db_info["version"] = cursor.fetchone()[0]
                db_info["connected"] = True
        except Exception as e:
            db_info["error"] = str(e)
        
        for part in settings.sql_connection_string.split(";"):
            if part.lower().startswith("server="):
                db_info["server"] = part.split("=", 1)[1]
                break
        
        # Environment info
        env_info = {
            "sql_connection_string_set": bool(settings.sql_connection_string),
            "sql_driver": settings.sql_driver,
            "azure_client_id": settings.azure_client_id is not None,
        }
        
        diagnostics_response = {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "backend": {
                "version": "1.0.0",
                "environment": "production",
                "uptime": "running"
            },
            "database": db_info,
            "environment": env_info,
            "recent_logs": log_store.get_logs(20)
        }
        
        return diagnostics_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/debug/config")
def debug_config() -> dict:
    """Show configuration (excluding secrets)."""
    settings = get_settings()
    return {
        "sql_driver": settings.sql_driver,
        "sql_connection_string_set": bool(settings.sql_connection_string),
        "azure_client_id_set": bool(settings.azure_client_id),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
def root() -> dict:
    """Root endpoint with API documentation."""
    return {
        "name": "Options Scanner API",
        "version": "1.0.0",
        "endpoints": {
            "GET /health": "Health check with database verification",
            "GET /api/scan": "Get scan opportunities",
            "GET /api/portfolio": "Get portfolio data",
            "GET /api/watchlist": "Get watched symbols",
            "GET /api/logs": "Get recent backend logs",
            "POST /api/logs": "Receive logs from frontend",
            "GET /api/diagnostics": "Comprehensive system diagnostics",
            "GET /api/debug/config": "Show configuration (no secrets)",
        }
    }
