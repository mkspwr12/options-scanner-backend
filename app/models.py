from __future__ import annotations

from pydantic import BaseModel


class Greeks(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float


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
