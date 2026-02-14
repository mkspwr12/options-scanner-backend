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
