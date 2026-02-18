from __future__ import annotations

from pydantic import BaseModel


class Greeks(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float


# ---------------------------------------------------------------------------
# Payout chart model (Issue #10)
# ---------------------------------------------------------------------------


class PayoutChart(BaseModel):
    """Mini payout chart for an option position."""

    pricePoints: list[float]
    profitPoints: list[float]


class FrontendPayoutChart(BaseModel):
    """Payout chart with frontend-expected field names (Issue #17)."""

    prices: list[float]
    pnl: list[float]


class OptionOpportunity(BaseModel):
    id: str
    symbol: str
    strikePrice: float
    expirationDate: str
    optionType: str
    currentPrice: float
    underlyingPrice: float
    impliedVolatility: float
    greeks: Greeks
    potentialGain: float
    potentialLoss: float
    riskRewardRatio: float
    confidenceScore: float
    timestamp: int
    # Issue #10 — payout chart fields (optional for backward compat)
    payoutChart: PayoutChart | None = None
    probability: float | None = None
    breakeven: float | None = None
    maxProfit: float | None = None
    maxLoss: float | None = None
    position: str | None = None


class MultiLegOpportunity(BaseModel):
    id: str
    symbol: str
    strategyType: str
    legs: list[OptionOpportunity]
    maxProfit: float
    maxLoss: float
    breakeven: float
    riskRewardRatio: float
    confidenceScore: float
    timestamp: int
    # Issue #11 — extra multi-leg fields (optional for backward compat)
    netCredit: float | None = None
    breakevens: list[float] | None = None
    probability: float | None = None
    payoutChart: PayoutChart | None = None


class TrackedTrade(BaseModel):
    id: str
    opportunityId: str
    symbol: str
    strikePrice: float
    expirationDate: str
    optionType: str
    entryPrice: float
    currentPrice: float
    quantity: int
    underlyingPrice: float
    greeks: Greeks
    entryDate: int
    unrealizedPL: float
    unrealizedPLPercent: float
    status: str


class ClosedTrade(TrackedTrade):
    exitPrice: float
    exitDate: int
    realizedPL: float
    realizedPLPercent: float


class PortfolioMetrics(BaseModel):
    totalValue: float
    totalPL: float
    totalPLPercent: float
    winRate: float
    totalTrades: int
    activeTrades: int
    aggregateGreeks: Greeks


class PortfolioResponse(BaseModel):
    metrics: PortfolioMetrics
    activeTrades: list[TrackedTrade]
    closedTrades: list[ClosedTrade]


# ---------------------------------------------------------------------------
# Enhanced portfolio models (Issue #13)
# ---------------------------------------------------------------------------


class PLHistoryEntry(BaseModel):
    """Daily P&L snapshot for a position."""

    date: str
    value: float


class PositionLeg(BaseModel):
    """A single leg within a portfolio position."""

    type: str  # e.g. "sell_put", "buy_call"
    strike: float
    quantity: int


class PortfolioPosition(BaseModel):
    """Enriched position for enhanced portfolio endpoint."""

    id: str
    ticker: str
    strategy: str
    legs: list[PositionLeg]
    openDate: str
    expiration: str
    dte: int
    entryPrice: float
    currentValue: float
    unrealizedPL: float
    unrealizedPLPercent: float
    maxProfit: float
    maxLoss: float
    breakevens: list[float]
    probability: float
    plHistory: list[PLHistoryEntry]


class PortfolioSummary(BaseModel):
    """Aggregate portfolio summary."""

    totalValue: float
    totalPL: float
    totalPLPercent: float
    maxProfit: float
    maxLoss: float
    netDelta: float
    netTheta: float


class EnhancedPortfolioResponse(BaseModel):
    """Issue #13 — enhanced portfolio response."""

    summary: PortfolioSummary
    positions: list[PortfolioPosition]
    aggregatePayoutChart: PayoutChart


# ---------------------------------------------------------------------------
# Multi-leg scan result (Issue #11)
# ---------------------------------------------------------------------------


class MultiLegScanLeg(BaseModel):
    """A single leg in a multi-leg scan result."""

    type: str  # "put" or "call"
    strike: float
    premium: float
    delta: float
    expiration: str = ""
    position: str = ""  # "long" or "short"
    quantity: int = 1


class MultiLegScanResult(BaseModel):
    """A single result from multi-leg scan."""

    id: str = ""
    ticker: str = ""
    strategyType: str
    legs: list[MultiLegScanLeg]
    netCredit: float
    maxProfit: float
    maxLoss: float
    breakevens: list[float]
    probability: float
    payoutChart: PayoutChart
    buyingPower: float = 0.0


# ---------------------------------------------------------------------------
# Stock scan result (Issue #12)
# ---------------------------------------------------------------------------


class MACDData(BaseModel):
    value: float
    signal: float
    histogram: float


class StockScanResult(BaseModel):
    """A single result from the stock screener."""

    ticker: str
    name: str
    price: float
    change: float
    volume: int
    rsi: float
    macd: MACDData
    pe: float
    marketCap: int
    optionLiquidity: str


class SingleScanResult(BaseModel):
    """A single result from the single options scanner (Issue #17)."""

    symbol: str
    strike: float
    expiration: str
    type: str
    premium: float
    delta: float
    iv: float
    probability: float
    payoutChart: FrontendPayoutChart
    breakeven: float
    maxProfit: float
    maxLoss: float


# ---------------------------------------------------------------------------
# Position action models (Issue #14)
# ---------------------------------------------------------------------------


class ClosedPositionInfo(BaseModel):
    id: str
    ticker: str
    closeDate: str
    closePrice: float
    entryPrice: float
    realizedPL: float


class AdjustmentRecord(BaseModel):
    date: str
    type: str
    strike: float | None = None
    quantity: int | None = None


# ---------------------------------------------------------------------------
# Provider models
# ---------------------------------------------------------------------------


class RateLimitConfig(BaseModel):
    maxPerHour: int = 2000
    maxPerDay: int = 20000
    costPerCall: float = 0.0


class ProviderConfig(BaseModel):
    id: str
    name: str
    type: str  # YAHOO_FINANCE, ALPACA, TRADIER, CUSTOM, MOCK
    apiKeyMasked: str | None = None
    baseUrl: str = ""
    enabled: bool = True
    priority: int = 1
    rateLimit: RateLimitConfig = RateLimitConfig()
    createdAt: str = ""
    updatedAt: str = ""


class ConnectionTestResult(BaseModel):
    success: bool
    latencyMs: int
    message: str | None = None
    error: str | None = None
    details: dict | None = None


# ---------------------------------------------------------------------------
# Strategy models
# ---------------------------------------------------------------------------


class StrategyLeg(BaseModel):
    id: str | None = None
    type: str  # CALL or PUT
    strike: float
    expiration: str
    action: str  # BUY or SELL
    quantity: int
    entryPrice: float | None = None
    currentPrice: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    impliedVolatility: float | None = None


class StrategyMetrics(BaseModel):
    maxProfit: float | None = None
    maxLoss: float | None = None
    breakevens: list[float] | None = None
    riskReward: float | None = None
    netDebit: float | None = None
    netCredit: float | None = None
    probability: float | None = None


class Strategy(BaseModel):
    id: str
    strategyType: str
    name: str | None = None
    ticker: str
    underlyingPrice: float | None = None
    legs: list[StrategyLeg]
    metrics: StrategyMetrics | None = None
    unrealizedPL: float | None = None
    unrealizedPLPercent: float | None = None
    status: str = "active"
    entryDate: str | None = None
    exitDate: str | None = None
    lastUpdated: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Risk models
# ---------------------------------------------------------------------------


class RiskAlert(BaseModel):
    severity: str  # info, warning, critical
    metric: str
    threshold: float
    currentValue: float
    message: str


# ---------------------------------------------------------------------------
# Portfolio position models (Issue #18)
# ---------------------------------------------------------------------------


class PortfolioPositionRecord(BaseModel):
    """Persisted position from the positions table."""

    id: str
    symbol: str
    strike: float
    expiration: str
    type: str  # call or put
    quantity: int
    premium: float
    entryDate: str
    currentValue: float
    pnl: float
    status: str  # open or closed
    createdAt: str
