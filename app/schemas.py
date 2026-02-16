"""Pydantic request models for API input validation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .models import Greeks


class TrackTradeRequest(BaseModel):
    """Request body for POST /api/trades/track."""

    opportunityId: str = Field(..., min_length=1, description="Source opportunity ID")
    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")
    strikePrice: float = Field(..., gt=0, description="Option strike price")
    expirationDate: str = Field(..., description="Expiration date YYYY-MM-DD")
    optionType: Literal["CALL", "PUT"] = Field(..., description="Option type")
    entryPrice: float = Field(..., gt=0, description="Entry price per contract")
    currentPrice: float = Field(..., ge=0, description="Current price per contract")
    quantity: int = Field(..., gt=0, description="Number of contracts")
    underlyingPrice: float = Field(..., gt=0, description="Current underlying price")
    greeks: Greeks = Field(..., description="Option Greeks at entry")

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("expirationDate")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        from datetime import datetime

        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("expirationDate must be YYYY-MM-DD format")
        return v


class CloseTradeRequest(BaseModel):
    """Request body for POST /api/trades/close."""

    tradeId: str = Field(..., min_length=1, description="ID of the trade to close")
    exitPrice: float = Field(..., ge=0, description="Exit price per contract")


class WatchlistRequest(BaseModel):
    """Request body for POST /api/watchlist/add and /api/watchlist/remove."""

    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()


class LogEntryRequest(BaseModel):
    """Request body for POST /api/logs."""

    level: Literal["debug", "info", "warning", "error"] = Field(
        default="info", description="Log level"
    )
    message: str = Field(..., min_length=1, description="Log message")
    data: dict[str, Any] | None = Field(default=None, description="Optional extra data")


# ---------------------------------------------------------------------------
# Provider schemas
# ---------------------------------------------------------------------------


class RateLimitInput(BaseModel):
    maxPerHour: int = 2000
    maxPerDay: int = 20000
    costPerCall: float = 0.0


class CreateProviderRequest(BaseModel):
    """Request body for POST /api/providers."""

    name: str = Field(..., min_length=1, max_length=100)
    type: Literal[
        "YAHOO_FINANCE", "ALPACA", "TRADIER", "CUSTOM", "MOCK"
    ] = Field(..., description="YAHOO_FINANCE, ALPACA, TRADIER, CUSTOM, MOCK")
    apiKey: str | None = Field(default=None, description="API key (encrypted at rest)")
    apiSecret: str | None = Field(default=None, description="API secret")
    baseUrl: str = Field(default="", description="Provider base URL")
    priority: int = Field(default=1, ge=1, description="Lower = higher priority")
    rateLimit: RateLimitInput | None = None


class UpdateProviderRequest(BaseModel):
    """Request body for PUT /api/providers/{id}."""

    name: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1)
    apiKey: str | None = None
    apiSecret: str | None = None
    baseUrl: str | None = None
    rateLimit: RateLimitInput | None = None


class ConnectionTestInput(BaseModel):
    """Optional overrides for POST /api/providers/{id}/test."""

    type: str | None = None
    apiKey: str | None = None
    apiSecret: str | None = None
    baseUrl: str | None = None


# ---------------------------------------------------------------------------
# Strategy schemas
# ---------------------------------------------------------------------------


class StrategyLegInput(BaseModel):
    """Single leg definition for a multi-leg strategy."""

    type: Literal["CALL", "PUT", "call", "put"] = Field(..., description="Option type")
    strike: float = Field(..., gt=0)
    expiration: str = Field(..., description="YYYY-MM-DD")
    action: Literal["BUY", "SELL", "buy", "sell"] = Field(...)
    quantity: int = Field(..., gt=0)
    entryPrice: float | None = None
    currentPrice: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    impliedVolatility: float | None = None


class CreateStrategyRequest(BaseModel):
    """Request body for POST /api/strategies."""

    strategyType: str = Field(..., description="e.g. BULL_CALL_SPREAD, IRON_CONDOR")
    name: str | None = None
    ticker: str = Field(..., min_length=1, max_length=10)
    underlyingPrice: float | None = None
    legs: list[StrategyLegInput] = Field(..., min_length=1, max_length=4)
    tags: list[str] | None = None
    notes: str | None = None

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()


class UpdateStrategyRequest(BaseModel):
    """Request body for PUT /api/strategies/{id}."""

    name: str | None = None
    status: Literal["active", "closed", "expired"] | None = None
    tags: list[str] | None = None
    notes: str | None = None
