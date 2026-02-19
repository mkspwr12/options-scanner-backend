"""Scan service — orchestrates option scanning with live market data.

Delegates to a ``MarketDataProvider`` for real options chain data,
calculates Greeks via Black-Scholes, scores opportunities, and
persists results.  Returns empty results when no data is available.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import Greeks, MultiLegOpportunity, OptionOpportunity, PayoutChart
from ..providers.base import MarketDataProvider, OptionContract
from ..providers.circuit_breaker import CircuitBreaker
from ..providers.greeks import calculate_greeks
from ..providers.scoring import score_opportunity
from ..repositories.scan_repository import ScanRepository

logger = logging.getLogger(__name__)

# Risk-free rate approximation (US 10-year treasury)
_RISK_FREE_RATE = 0.045


class ScanService:
    """Orchestrates option scanning with provider + scoring pipeline."""

    def __init__(
        self,
        repo: ScanRepository | None = None,
        provider: MarketDataProvider | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._repo = repo or ScanRepository()
        self._provider = provider
        self._cb = circuit_breaker or CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=300.0,
            name="market_data",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_opportunities(
        self,
        *,
        symbol: str | None = None,
        option_type: str | None = None,
        min_confidence: float = 0,
        min_risk_reward: float = 0,
        sort_by: str = "confidenceScore",
        limit: int = 50,
        # Phase 3: advanced filters
        iv_min: float | None = None,
        iv_max: float | None = None,
        dte_min: int | None = None,
        dte_max: int | None = None,
        delta_min: float | None = None,
        delta_max: float | None = None,
        theta_min: float | None = None,
        theta_max: float | None = None,
        vega_min: float | None = None,
        vega_max: float | None = None,
        min_volume: int | None = None,
        moneyness: str | None = None,
    ) -> dict[str, Any]:
        """Return scan results.

        Priority order:
        1. Database (latest persisted scan results)
        2. Live provider scan (if symbol provided)
        3. Empty results (no data available)
        """
        try:
            db_results = self._repo.get_latest(
                symbol=symbol,
                option_type=option_type,
                min_confidence=min_confidence,
                min_risk_reward=min_risk_reward,
                sort_by=sort_by,
                limit=limit,
                iv_min=iv_min,
                iv_max=iv_max,
                dte_min=dte_min,
                dte_max=dte_max,
                delta_min=delta_min,
                delta_max=delta_max,
                theta_min=theta_min,
                theta_max=theta_max,
                vega_min=vega_min,
                vega_max=vega_max,
                min_volume=min_volume,
            )
            if db_results:
                # Apply in-memory filters that cannot be done in SQL
                filtered = self._apply_in_memory_filters(
                    db_results,
                    moneyness=moneyness,
                    min_volume=min_volume,
                )
                return {
                    "status": "ok",
                    "opportunities": filtered,
                    "source": "database",
                    "stale": False,
                }
        except Exception:
            logger.warning("DB scan retrieval failed — falling back to live/sample data")

        # Try live provider scan for the requested symbol before falling back
        if self._provider and symbol and self._cb.allow_request():
            try:
                live_result = self.run_scan([symbol])
                if live_result.get("resultsCount", 0) > 0:
                    # Re-fetch from DB after live scan populated it
                    try:
                        db_results = self._repo.get_latest(
                            symbol=symbol,
                            option_type=option_type,
                            min_confidence=min_confidence,
                            min_risk_reward=min_risk_reward,
                            sort_by=sort_by,
                            limit=limit,
                        )
                        if db_results:
                            return {
                                "status": "ok",
                                "opportunities": db_results,
                                "source": "live",
                                "stale": False,
                            }
                    except Exception:
                        pass
            except Exception:
                logger.warning("Live scan fallback failed for %s", symbol)

        # No data available — return empty results
        return {
            "status": "ok",
            "opportunities": [],
            "source": "none",
            "stale": False,
            "message": "No scan data available. Trigger a scan first.",
        }

    def scan_single(
        self,
        ticker: str,
        *,
        min_delta: float | None = None,
        max_delta: float | None = None,
        min_dte: int | None = None,
        max_dte: int | None = None,
        min_iv: float | None = None,
        max_iv: float | None = None,
        strike_min: float | None = None,
        strike_max: float | None = None,
    ) -> dict[str, Any]:
        """POST /api/scan — single options scanner (Issue #17).

        Reuses get_opportunities() internally and transforms results
        into the frontend-expected response format.
        """
        raw = self.get_opportunities(
            symbol=ticker,
            delta_min=min_delta,
            delta_max=max_delta,
            dte_min=min_dte,
            dte_max=max_dte,
            iv_min=min_iv,
            iv_max=max_iv,
        )
        opportunities = raw.get("opportunities", [])
        results: list[dict[str, Any]] = []

        for opp in opportunities:
            # Normalize to dict
            if hasattr(opp, "model_dump"):
                o = opp.model_dump()
            elif isinstance(opp, dict):
                o = opp
            else:
                continue

            strike = o.get("strikePrice", 0)

            # Apply strike range filter
            if strike_min is not None and strike < strike_min:
                continue
            if strike_max is not None and strike > strike_max:
                continue

            premium = o.get("currentPrice", 0)
            opt_type = (o.get("optionType") or "call").lower()
            iv = o.get("impliedVolatility", 0)

            greeks = o.get("greeks", {})
            if isinstance(greeks, dict):
                delta = greeks.get("delta", 0)
            else:
                delta = getattr(greeks, "delta", 0)

            probability = o.get("probability") or round(abs(delta) * 100, 1)
            breakeven = o.get("breakeven") or (
                round(strike + premium, 2)
                if opt_type == "call"
                else round(strike - premium, 2)
            )

            # Payout chart (transform pricePoints/profitPoints → prices/pnl)
            payout = o.get("payoutChart")
            if payout:
                if isinstance(payout, dict):
                    prices = payout.get("pricePoints", [])
                    pnl = payout.get("profitPoints", [])
                else:
                    prices = getattr(payout, "pricePoints", [])
                    pnl = getattr(payout, "profitPoints", [])
            else:
                prices = [round(strike * f, 2) for f in [0.9, 0.95, 1.0, 1.05, 1.1]]
                pnl = []
                for p in prices:
                    if opt_type == "call":
                        intrinsic = max(p - strike, 0)
                    else:
                        intrinsic = max(strike - p, 0)
                    pnl.append(round((intrinsic - premium) * 100, 2))

            max_profit = o.get("maxProfit") or (round(max(pnl), 2) if pnl else 0)
            max_loss = o.get("maxLoss") or (round(min(pnl), 2) if pnl else 0)

            results.append({
                "symbol": o.get("symbol", ticker),
                "strike": strike,
                "expiration": o.get("expirationDate", ""),
                "type": opt_type,
                "premium": round(premium, 2),
                "delta": round(delta, 4),
                "iv": round(iv, 1),
                "probability": round(probability, 1),
                "payoutChart": {"prices": prices, "pnl": pnl},
                "breakeven": round(breakeven, 2),
                "maxProfit": round(max_profit, 2),
                "maxLoss": round(max_loss, 2),
            })

        return {"results": results}

    def get_multi_leg_opportunities(self) -> dict[str, Any]:
        """Return multi-leg strategies from database or empty list."""
        return {
            "status": "ok",
            "opportunities": [],
            "message": "Use POST /api/multi-leg-scan for live multi-leg scanning.",
        }

    def run_scan(self, symbols: list[str] | None = None) -> dict[str, Any]:
        """Execute a live scan for the given symbols.

        Uses the market data provider to fetch options chains, compute
        Greeks, score opportunities, and persist them.  When the provider
        is unavailable or the circuit breaker is open, returns cached
        results with ``stale: True``.
        """
        if self._provider is None:
            return {
                "status": "ok",
                "message": "No market data provider configured",
                "resultsCount": 0,
                "source": "none",
            }

        if not self._cb.allow_request():
            logger.warning("Circuit breaker OPEN — returning cached results")
            return self._cached_results()

        all_opportunities: list[dict[str, Any]] = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        for sym in (symbols or []):
            try:
                quote = self._provider.get_quote(sym)
                contracts = self._provider.get_options_chain(sym)
                self._cb.record_success()

                for c in contracts:
                    opp = self._contract_to_opportunity(c, quote.price, now_ms)
                    if opp is not None:
                        all_opportunities.append(opp)

            except Exception:
                logger.exception("Provider failed for %s", sym)
                self._cb.record_failure()
                if not self._cb.allow_request():
                    return self._cached_results()

        # Deduplicate: keep only one entry per (symbol, strike, expiration, type)
        seen: dict[tuple, dict] = {}
        for opp in all_opportunities:
            key = (
                opp["symbol"],
                opp["strikePrice"],
                opp["expirationDate"],
                opp["optionType"],
            )
            if key not in seen:
                seen[key] = opp
        all_opportunities = list(seen.values())

        # Sort by confidence descending
        all_opportunities.sort(key=lambda o: o["confidenceScore"], reverse=True)

        # Persist
        try:
            self._repo.save_results(all_opportunities)
        except Exception:
            logger.warning("Failed to persist scan results")

        return {
            "status": "ok",
            "message": "Scan complete",
            "resultsCount": len(all_opportunities),
            "scanTimestamp": now_ms,
            "source": "live",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_in_memory_filters(
        results: list[OptionOpportunity],
        *,
        moneyness: str | None = None,
        min_volume: int | None = None,
    ) -> list[OptionOpportunity]:
        """Apply filters that cannot be handled by SQL."""
        filtered = results

        if moneyness and moneyness.lower() != "all":
            target = moneyness.upper()  # ITM, OTM, ATM
            out: list[OptionOpportunity] = []
            for opp in filtered:
                m = ScanService._classify_moneyness(
                    opp.strikePrice, opp.underlyingPrice, opp.optionType
                )
                if m == target:
                    out.append(opp)
            filtered = out

        # min_volume: volume is not persisted in scan_results, so this
        # filter only applies when the opportunity carries volume data.
        # For DB-sourced results this is a no-op (by design).
        if min_volume is not None:
            filtered = [
                opp
                for opp in filtered
                if getattr(opp, "volume", None) is None
                or getattr(opp, "volume", 0) >= min_volume
            ]

        return filtered

    @staticmethod
    def _classify_moneyness(
        strike: float, underlying: float, option_type: str
    ) -> str:
        """Return 'ITM', 'OTM', or 'ATM' for a given strike/underlying."""
        if strike <= 0:
            return "ATM"
        ratio = underlying / strike
        if option_type.upper() == "CALL":
            if ratio > 1.02:
                return "ITM"
            if ratio < 0.98:
                return "OTM"
        else:
            if ratio < 0.98:
                return "ITM"
            if ratio > 1.02:
                return "OTM"
        return "ATM"

    def _contract_to_opportunity(
        self, c: OptionContract, underlying_price: float, timestamp: int
    ) -> dict[str, Any] | None:
        """Convert a raw contract into a scored opportunity dict."""
        mid_price = (c.bid + c.ask) / 2.0 if c.bid and c.ask else c.last_price
        if mid_price <= 0:
            return None

        # Time to expiry in years
        try:
            exp_date = datetime.strptime(c.expiration, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            dte = max((exp_date - datetime.now(timezone.utc)).days, 0)
            T = dte / 365.0
        except Exception:
            dte = 30
            T = 30 / 365.0

        # Greeks via Black-Scholes
        greeks = calculate_greeks(
            S=underlying_price,
            K=c.strike,
            T=T,
            r=_RISK_FREE_RATE,
            sigma=c.implied_volatility,
            option_type=c.option_type,
        )

        # Potential gain / loss (simplified)
        if c.option_type == "CALL":
            potential_gain = max(underlying_price - c.strike, 0) + mid_price
            potential_loss = mid_price
        else:
            potential_gain = max(c.strike - underlying_price, 0) + mid_price
            potential_loss = mid_price

        risk_reward = potential_gain / potential_loss if potential_loss > 0 else 0.0

        confidence = score_opportunity(
            implied_volatility=c.implied_volatility,
            volume=c.volume,
            open_interest=c.open_interest,
            potential_gain=potential_gain,
            potential_loss=potential_loss,
            dte=dte,
            delta=greeks.delta,
        )

        # Issue #10 — payout chart data
        payout = self._calculate_payout_chart(
            underlying_price, c.strike, mid_price, c.option_type
        )
        breakeven = self._calculate_breakeven(c.strike, mid_price, c.option_type)
        probability = self._calculate_probability(greeks.delta, c.option_type)
        max_profit_val = payout["maxProfit"]
        max_loss_val = payout["maxLoss"]

        return {
            "id": f"opp-{uuid.uuid4().hex[:12]}",
            "symbol": c.symbol,
            "strikePrice": c.strike,
            "expirationDate": c.expiration,
            "optionType": c.option_type,
            "currentPrice": round(mid_price, 4),
            "underlyingPrice": underlying_price,
            "impliedVolatility": round(c.implied_volatility, 4),
            "greeks": {
                "delta": greeks.delta,
                "gamma": greeks.gamma,
                "theta": greeks.theta,
                "vega": greeks.vega,
            },
            "potentialGain": round(potential_gain, 4),
            "potentialLoss": round(potential_loss, 4),
            "riskRewardRatio": round(risk_reward, 4),
            "confidenceScore": confidence,
            "timestamp": timestamp,
            "payoutChart": {
                "pricePoints": payout["pricePoints"],
                "profitPoints": payout["profitPoints"],
            },
            "probability": probability,
            "breakeven": breakeven,
            "maxProfit": max_profit_val,
            "maxLoss": max_loss_val,
            "position": "long",
        }

    def _cached_results(self) -> dict[str, Any]:
        """Return cached DB results with stale flag."""
        try:
            cached = self._repo.get_latest(limit=50)
            if cached:
                return {
                    "status": "ok",
                    "opportunities": cached,
                    "source": "cache",
                    "stale": True,
                    "message": "Provider unavailable — showing cached results",
                }
        except Exception:
            pass
        return {
            "status": "ok",
            "opportunities": [],
            "source": "none",
            "stale": True,
            "message": "Provider unavailable — no cached results available",
        }

    # ------------------------------------------------------------------
    # Payout chart calculation helpers (Issue #10)
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_payout_chart(
        underlying_price: float,
        strike: float,
        premium: float,
        option_type: str,
        num_points: int = 7,
    ) -> dict[str, Any]:
        """Generate payout chart data for a long option position.

        Returns dict with pricePoints, profitPoints, maxProfit, maxLoss.
        """
        low = round(underlying_price * 0.85, 2)
        high = round(underlying_price * 1.15, 2)
        step = (high - low) / (num_points - 1) if num_points > 1 else 0
        price_points: list[float] = [round(low + i * step, 2) for i in range(num_points)]
        profit_points: list[float] = []
        premium_cost = premium * 100  # per-contract cost

        for p in price_points:
            if option_type.upper() == "CALL":
                intrinsic = max(p - strike, 0)
                pnl = round((intrinsic * 100) - premium_cost, 2)
            else:
                intrinsic = max(strike - p, 0)
                pnl = round((intrinsic * 100) - premium_cost, 2)
            profit_points.append(pnl)

        max_profit = round(max(profit_points), 2)
        max_loss = round(-premium_cost, 2)

        return {
            "pricePoints": price_points,
            "profitPoints": profit_points,
            "maxProfit": max_profit,
            "maxLoss": max_loss,
        }

    @staticmethod
    def _calculate_breakeven(
        strike: float, premium: float, option_type: str
    ) -> float:
        """Calculate the breakeven price for a long option."""
        if option_type.upper() == "CALL":
            return round(strike + premium, 2)
        return round(strike - premium, 2)

    @staticmethod
    def _calculate_probability(delta: float, option_type: str) -> float:
        """Approximate probability of profit using delta.

        For long calls, probability ≈ delta * 100.
        For long puts, probability ≈ (1 - |delta|) * 100 ... but
        more accurately |delta| for puts already reflects ITM probability.
        We use |delta| as a rough proxy for probability of finishing ITM.
        """
        prob = abs(delta) * 100
        return round(min(max(prob, 0), 100), 1)
