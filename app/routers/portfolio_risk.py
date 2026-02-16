"""Portfolio risk analysis router — aggregate Greeks + risk alerts."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_portfolio_service, get_strategy_service
from ..models import RiskAlert
from ..services.portfolio_service import PortfolioService
from ..services.strategy_service import StrategyService

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio Risk"])


@router.get("/risk")
def portfolio_risk(
    groupBy: str | None = Query(
        default=None, description="Group by: symbol, strategy, optionType, expiration"
    ),
    portfolio_svc: PortfolioService = Depends(get_portfolio_service),
    strategy_svc: StrategyService = Depends(get_strategy_service),
) -> dict:
    """Analyse aggregate portfolio risk across trades and strategies."""
    portfolio = portfolio_svc.get_portfolio()
    strategies = strategy_svc.list_strategies(status="active")

    # Aggregate Greeks from active strategies
    strat_delta = strat_gamma = strat_theta = strat_vega = 0.0
    for s in strategies:
        for leg in s.legs:
            m = 1 if leg.action.upper() == "BUY" else -1
            strat_delta += (leg.delta or 0) * leg.quantity * m
            strat_gamma += (leg.gamma or 0) * leg.quantity * m
            strat_theta += (leg.theta or 0) * leg.quantity * m
            strat_vega += (leg.vega or 0) * leg.quantity * m

    trade_greeks = portfolio.metrics.aggregateGreeks
    total_delta = trade_greeks.delta + strat_delta
    total_gamma = trade_greeks.gamma + strat_gamma
    total_theta = trade_greeks.theta + strat_theta
    total_vega = trade_greeks.vega + strat_vega

    # Unrealized P&L from trades
    trade_unrealized = sum(t.unrealizedPL for t in portfolio.activeTrades)

    # Unrealized P&L from strategies
    strat_unrealized = sum(s.unrealizedPL or 0 for s in strategies)

    total_unrealized = trade_unrealized + strat_unrealized
    total_invested = sum(
        t.entryPrice * t.quantity * 100 for t in portfolio.activeTrades
    )
    for s in strategies:
        for leg in s.legs:
            if leg.entryPrice is not None:
                total_invested += abs(leg.entryPrice * leg.quantity * 100)

    unrealized_pct = (
        (total_unrealized / total_invested * 100) if total_invested > 0 else 0.0
    )

    # Generate risk alerts
    alerts: list[dict] = []
    if abs(total_delta) > 100:
        alerts.append(
            RiskAlert(
                severity="critical" if abs(total_delta) > 200 else "warning",
                metric="delta",
                threshold=100.0,
                currentValue=round(total_delta, 4),
                message=(
                    f"Portfolio delta exposure is "
                    f"{'high' if total_delta > 0 else 'negative'}: "
                    f"{total_delta:.2f}"
                ),
            ).model_dump()
        )
    if abs(total_theta) > 50:
        alerts.append(
            RiskAlert(
                severity="warning",
                metric="theta",
                threshold=50.0,
                currentValue=round(total_theta, 4),
                message=f"Daily time decay: ${total_theta:.2f}",
            ).model_dump()
        )
    if abs(total_vega) > 75:
        alerts.append(
            RiskAlert(
                severity="info",
                metric="vega",
                threshold=75.0,
                currentValue=round(total_vega, 4),
                message=f"Volatility sensitivity: {total_vega:.2f}",
            ).model_dump()
        )

    # Optional grouping
    groups = None
    if groupBy == "symbol":
        groups = _group_by_symbol(portfolio.activeTrades, strategies)
    elif groupBy == "strategy":
        groups = _group_by_strategy(strategies)

    # Build position details
    positions = _build_positions(portfolio.activeTrades, strategies)

    return {
        "status": "ok",
        "summary": {
            "totalDelta": round(total_delta, 4),
            "totalGamma": round(total_gamma, 4),
            "totalTheta": round(total_theta, 4),
            "totalVega": round(total_vega, 4),
            "portfolioValue": portfolio.metrics.totalValue,
            "unrealizedPL": round(total_unrealized, 2),
            "unrealizedPLPercent": round(unrealized_pct, 2),
            "positionCount": portfolio.metrics.activeTrades + len(strategies),
            "activeStrategies": len(strategies),
        },
        "aggregateGreeks": {
            "delta": round(total_delta, 4),
            "gamma": round(total_gamma, 4),
            "theta": round(total_theta, 4),
            "vega": round(total_vega, 4),
        },
        "tradeCount": portfolio.metrics.activeTrades,
        "strategyCount": len(strategies),
        "alerts": alerts,
        "groups": groups,
        "positions": positions,
    }


def _build_positions(trades, strategies):  # noqa: ANN001
    """Build position-level details with leg breakdown."""
    positions: list[dict] = []

    # Individual trades as positions
    for t in trades:
        positions.append(
            {
                "id": t.id,
                "ticker": t.symbol,
                "strategy": "single",
                "description": f"{t.symbol} {t.strikePrice} {t.optionType}",
                "entryPrice": t.entryPrice * t.quantity * 100,
                "currentValue": t.currentPrice * t.quantity * 100,
                "unrealizedPL": round(t.unrealizedPL, 2),
                "unrealizedPLPercent": round(t.unrealizedPLPercent, 2),
                "delta": round(t.greeks.delta * t.quantity, 4),
                "gamma": round(t.greeks.gamma * t.quantity, 4),
                "theta": round(t.greeks.theta * t.quantity, 4),
                "vega": round(t.greeks.vega * t.quantity, 4),
                "legs": [
                    {
                        "type": t.optionType.lower(),
                        "strike": t.strikePrice,
                        "action": "buy",
                        "quantity": t.quantity,
                        "entryPrice": t.entryPrice,
                        "currentPrice": t.currentPrice,
                        "delta": t.greeks.delta,
                        "gamma": t.greeks.gamma,
                        "theta": t.greeks.theta,
                        "vega": t.greeks.vega,
                    }
                ],
            }
        )

    # Strategy positions with leg breakdown
    for s in strategies:
        pos_delta = pos_gamma = pos_theta = pos_vega = 0.0
        entry_cost = current_val = 0.0
        legs_out: list[dict] = []

        for leg in s.legs:
            m = 1 if leg.action.upper() == "BUY" else -1
            pos_delta += (leg.delta or 0) * leg.quantity * m
            pos_gamma += (leg.gamma or 0) * leg.quantity * m
            pos_theta += (leg.theta or 0) * leg.quantity * m
            pos_vega += (leg.vega or 0) * leg.quantity * m

            if leg.entryPrice is not None:
                entry_cost += abs(leg.entryPrice * leg.quantity * 100)
            if leg.currentPrice is not None:
                current_val += abs(leg.currentPrice * leg.quantity * 100)

            legs_out.append(
                {
                    "type": leg.type.lower(),
                    "strike": leg.strike,
                    "expiration": leg.expiration,
                    "action": leg.action.lower(),
                    "quantity": leg.quantity,
                    "entryPrice": leg.entryPrice,
                    "currentPrice": leg.currentPrice,
                    "delta": leg.delta,
                    "gamma": leg.gamma,
                    "theta": leg.theta,
                    "vega": leg.vega,
                }
            )

        # Compute DTE from first leg
        dte = None
        if s.legs:
            try:
                exp = datetime.strptime(
                    s.legs[0].expiration, "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
                dte = max((exp - datetime.now(timezone.utc)).days, 0)
            except Exception:
                pass

        positions.append(
            {
                "id": s.id,
                "ticker": s.ticker,
                "strategy": s.strategyType,
                "description": f"{s.ticker} {s.strategyType}"
                + (f" ({s.name})" if s.name else ""),
                "entryPrice": round(entry_cost, 2),
                "currentValue": round(current_val, 2),
                "unrealizedPL": round(s.unrealizedPL or 0, 2),
                "unrealizedPLPercent": round(s.unrealizedPLPercent or 0, 2),
                "delta": round(pos_delta, 4),
                "gamma": round(pos_gamma, 4),
                "theta": round(pos_theta, 4),
                "vega": round(pos_vega, 4),
                "daysToExpiration": dte,
                "legs": legs_out,
            }
        )

    return positions


def _group_by_strategy(strategies):  # noqa: ANN001
    """Aggregate Greek exposure by strategy type."""
    groups: dict[str, dict] = {}

    for s in strategies:
        stype = s.strategyType
        if stype not in groups:
            groups[stype] = {
                "strategyType": stype,
                "count": 0,
                "totalDelta": 0.0,
                "totalGamma": 0.0,
                "totalTheta": 0.0,
                "totalVega": 0.0,
                "unrealizedPL": 0.0,
            }
        groups[stype]["count"] += 1
        groups[stype]["unrealizedPL"] += s.unrealizedPL or 0

        for leg in s.legs:
            m = 1 if leg.action.upper() == "BUY" else -1
            groups[stype]["totalDelta"] += (leg.delta or 0) * leg.quantity * m
            groups[stype]["totalGamma"] += (leg.gamma or 0) * leg.quantity * m
            groups[stype]["totalTheta"] += (leg.theta or 0) * leg.quantity * m
            groups[stype]["totalVega"] += (leg.vega or 0) * leg.quantity * m

    # Round values
    for g in groups.values():
        g["totalDelta"] = round(g["totalDelta"], 4)
        g["totalGamma"] = round(g["totalGamma"], 4)
        g["totalTheta"] = round(g["totalTheta"], 4)
        g["totalVega"] = round(g["totalVega"], 4)
        g["unrealizedPL"] = round(g["unrealizedPL"], 2)

    return list(groups.values())


def _group_by_symbol(trades, strategies):  # noqa: ANN001
    """Aggregate Greek exposure by ticker symbol."""
    groups: dict[str, dict] = {}

    for t in trades:
        sym = t.symbol
        if sym not in groups:
            groups[sym] = {
                "symbol": sym,
                "delta": 0,
                "gamma": 0,
                "theta": 0,
                "vega": 0,
                "positionCount": 0,
            }
        groups[sym]["delta"] += t.greeks.delta * t.quantity
        groups[sym]["gamma"] += t.greeks.gamma * t.quantity
        groups[sym]["theta"] += t.greeks.theta * t.quantity
        groups[sym]["vega"] += t.greeks.vega * t.quantity
        groups[sym]["positionCount"] += 1

    for s in strategies:
        sym = s.ticker
        if sym not in groups:
            groups[sym] = {
                "symbol": sym,
                "delta": 0,
                "gamma": 0,
                "theta": 0,
                "vega": 0,
                "positionCount": 0,
            }
        for leg in s.legs:
            m = 1 if leg.action.upper() == "BUY" else -1
            groups[sym]["delta"] += (leg.delta or 0) * leg.quantity * m
            groups[sym]["gamma"] += (leg.gamma or 0) * leg.quantity * m
            groups[sym]["theta"] += (leg.theta or 0) * leg.quantity * m
            groups[sym]["vega"] += (leg.vega or 0) * leg.quantity * m
        groups[sym]["positionCount"] += 1

    return list(groups.values())
