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
