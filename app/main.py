from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException

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

app = FastAPI(title="Options Scanner API")


@app.get("/health")
def health() -> dict:
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

        return {
            "status": "ok",
            "auth": "managed-identity",
            "database": db_name,
            "server": server,
        }
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
    return {"status": "ok", "symbols": ["META", "SPY", "AAPL", "NVDA"]}
