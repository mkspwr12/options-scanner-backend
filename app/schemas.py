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
        "YAHOO_FINANCE", "ALPACA", "TRADIER", "CUSTOM"
    ] = Field(..., description="YAHOO_FINANCE, ALPACA, TRADIER, CUSTOM")
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


# ---------------------------------------------------------------------------
# Multi-leg scan schemas (Issue #11)
# ---------------------------------------------------------------------------


class MultiLegScanFilters(BaseModel):
    """Filters for POST /api/multi-leg-scan."""

    minProbability: float | None = Field(default=None, ge=0, le=100)
    minCredit: float | None = Field(default=None, ge=0)
    dteRange: list[int] | None = Field(default=None, min_length=2, max_length=2)
    maxBuyingPower: float | None = Field(default=None, ge=0)


class MultiLegScanRequest(BaseModel):
    """Request body for POST /api/multi-leg-scan."""

    ticker: str = Field(..., min_length=1, max_length=10)
    strategyType: str = Field(
        ...,
        description="iron_condor, vertical_spread, calendar_spread, butterfly, diagonal_spread",
    )
    filters: MultiLegScanFilters | None = None

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()


# ---------------------------------------------------------------------------
# Single scan schemas (Issue #17)
# ---------------------------------------------------------------------------


class StrikeRangeFilter(BaseModel):
    """Min/max strike price range."""

    min: float | None = None
    max: float | None = None


class SingleScanFilters(BaseModel):
    """Filters for POST /api/scan single options scanner."""

    minDelta: float | None = None
    maxDelta: float | None = None
    minDTE: int | None = None
    maxDTE: int | None = None
    minIV: float | None = None
    maxIV: float | None = None
    strikeRange: StrikeRangeFilter | None = None


class SingleScanRequest(BaseModel):
    """Request body for POST /api/scan (Issue #17)."""

    ticker: str = Field(..., min_length=1, max_length=10)
    filters: SingleScanFilters | None = None

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()


# ---------------------------------------------------------------------------
# Stock scan schemas (Issue #12)
# ---------------------------------------------------------------------------


class RangeFilter(BaseModel):
    """Generic min/max range filter."""

    min: float | None = None
    max: float | None = None


class IntRangeFilter(BaseModel):
    """Generic min/max range filter for integers."""

    min: int | None = None
    max: int | None = None


class MovingAverageFilter(BaseModel):
    period: int = 50
    above: bool = True


class TechnicalFilters(BaseModel):
    rsi: RangeFilter | None = None
    macd: str | None = None
    macdBullish: bool | None = None
    movingAverage: MovingAverageFilter | None = None
    above50MA: bool | None = None
    above200MA: bool | None = None
    unusualVolume: bool | None = None


class FundamentalFilters(BaseModel):
    peRatio: RangeFilter | None = None
    marketCap: IntRangeFilter | str | None = None
    sector: list[str] | None = None
    earningsGrowth: RangeFilter | None = None


class PriceChangeFilter(BaseModel):
    period: str = "1d"
    min: float | None = None


class MomentumFilters(BaseModel):
    volumeIncrease: float | None = None
    priceChange: PriceChangeFilter | None = None
    insiderBuying: bool | None = None
    earningsWithinDays: int | None = None
    volumeSpike: RangeFilter | None = None


class StockScanFilters(BaseModel):
    technical: TechnicalFilters | None = None
    fundamental: FundamentalFilters | None = None
    momentum: MomentumFilters | None = None


class StockScanRequest(BaseModel):
    """Request body for POST /api/stock-scan."""

    filters: StockScanFilters | None = None
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=200)


# ---------------------------------------------------------------------------
# Position action schemas (Issue #14)
# ---------------------------------------------------------------------------


class ClosePositionRequest(BaseModel):
    """Request body for POST /api/portfolio/close-position."""

    positionId: str = Field(..., min_length=1)
    closePrice: float = Field(..., ge=0)


class RollPositionStrikes(BaseModel):
    sellPut: float | None = None
    buyPut: float | None = None
    sellCall: float | None = None
    buyCall: float | None = None


class RollPositionRequest(BaseModel):
    """Request body for POST /api/portfolio/roll-position."""

    positionId: str = Field(..., min_length=1)
    newExpiration: str = Field(..., description="YYYY-MM-DD")
    adjustStrikes: bool = False
    newStrikes: RollPositionStrikes | None = None


class AdjustPositionRequest(BaseModel):
    """Request body for POST /api/portfolio/adjust-position."""

    positionId: str = Field(..., min_length=1)
    adjustmentType: Literal[
        "add_protective_put",
        "add_protective_call",
        "adjust_strike",
        "reduce_size",
    ] = Field(...)
    strike: float | None = None
    quantity: int | None = Field(default=None, ge=1)


class AddPositionRequest(BaseModel):
    """Request body for POST /api/portfolio/add-position (Issue #18)."""

    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")
    strike: float = Field(..., gt=0, description="Option strike price")
    expiration: str = Field(..., description="Expiration date YYYY-MM-DD")
    type: Literal["call", "put", "CALL", "PUT"] = Field(..., description="Option type")
    quantity: int = Field(default=1, gt=0, description="Number of contracts")
    premium: float = Field(..., gt=0, description="Premium per contract")
    entryDate: str | None = Field(default=None, description="Entry date YYYY-MM-DD (defaults to today)")

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("type", mode="before")
    @classmethod
    def lowercase_type(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("expiration")
    @classmethod
    def validate_expiration(cls, v: str) -> str:
        from datetime import datetime

        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("expiration must be YYYY-MM-DD format")
        return v

    @field_validator("entryDate")
    @classmethod
    def validate_entry_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from datetime import datetime

        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("entryDate must be YYYY-MM-DD format")
        return v
