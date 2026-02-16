"""Scan service — orchestrates option scanning with live market data.

Delegates to a ``MarketDataProvider`` for real options chain data,
calculates Greeks via Black-Scholes, scores opportunities, and
persists results.  Falls back to sample data when no provider is
available or the circuit breaker is open.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import Greeks, MultiLegOpportunity, OptionOpportunity
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
        2. Hardcoded sample data (Phase 1 fallback)
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
            logger.warning("DB scan retrieval failed — falling back to sample data")

        # Fallback: hardcoded sample data (apply filters in-memory)
        samples = self._sample_opportunities()
        filtered = self._filter_sample_opportunities(
            samples,
            symbol=symbol,
            option_type=option_type,
            min_confidence=min_confidence,
            min_risk_reward=min_risk_reward,
            moneyness=moneyness,
            iv_min=iv_min,
            iv_max=iv_max,
            delta_min=delta_min,
            delta_max=delta_max,
            theta_min=theta_min,
            theta_max=theta_max,
            vega_min=vega_min,
            vega_max=vega_max,
        )
        # Apply sort
        sort_key = sort_by or "confidenceScore"
        if hasattr(filtered[0], sort_key) if filtered else False:
            filtered.sort(key=lambda o: getattr(o, sort_key, 0), reverse=True)
        return {
            "status": "ok",
            "opportunities": filtered[:limit],
            "source": "sample",
            "stale": False,
        }

    def get_multi_leg_opportunities(self) -> dict[str, Any]:
        """Return multi-leg strategies (hardcoded sample data)."""
        return {
            "status": "ok",
            "opportunities": self._sample_multi_leg(),
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
    def _filter_sample_opportunities(
        opportunities: list[OptionOpportunity],
        *,
        symbol: str | None = None,
        option_type: str | None = None,
        min_confidence: float = 0,
        min_risk_reward: float = 0,
        moneyness: str | None = None,
        iv_min: float | None = None,
        iv_max: float | None = None,
        delta_min: float | None = None,
        delta_max: float | None = None,
        theta_min: float | None = None,
        theta_max: float | None = None,
        vega_min: float | None = None,
        vega_max: float | None = None,
    ) -> list[OptionOpportunity]:
        """Apply all filters to sample/fallback opportunities in-memory."""
        filtered: list[OptionOpportunity] = []
        for opp in opportunities:
            if symbol and opp.symbol.upper() != symbol.upper():
                continue
            if option_type and opp.optionType.upper() != option_type.upper():
                continue
            if min_confidence and opp.confidenceScore < min_confidence:
                continue
            if min_risk_reward and opp.riskRewardRatio < min_risk_reward:
                continue
            if iv_min is not None and (opp.impliedVolatility or 0) < iv_min:
                continue
            if iv_max is not None and (opp.impliedVolatility or 0) > iv_max:
                continue
            greeks = opp.greeks
            if greeks:
                if delta_min is not None and (greeks.delta or 0) < delta_min:
                    continue
                if delta_max is not None and (greeks.delta or 0) > delta_max:
                    continue
                if theta_min is not None and (greeks.theta or 0) < theta_min:
                    continue
                if theta_max is not None and (greeks.theta or 0) > theta_max:
                    continue
                if vega_min is not None and (greeks.vega or 0) < vega_min:
                    continue
                if vega_max is not None and (greeks.vega or 0) > vega_max:
                    continue
            if moneyness and moneyness.lower() != "all":
                m = ScanService._classify_moneyness(
                    opp.strikePrice, opp.underlyingPrice, opp.optionType
                )
                if m != moneyness.upper():
                    continue
            filtered.append(opp)
        return filtered

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
            "opportunities": self._sample_opportunities(),
            "source": "sample",
            "stale": True,
            "message": "Provider unavailable — showing sample results",
        }

    # ------------------------------------------------------------------
    # Hardcoded sample data (preserved from Phase 1)
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_opportunities() -> list[OptionOpportunity]:
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        return [
            OptionOpportunity(
                id="opp-001",
                symbol="META",
                strikePrice=690.0,
                expirationDate=(
                    datetime.now(timezone.utc) + timedelta(days=28)
                ).strftime("%Y-%m-%d"),
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
                expirationDate=(
                    datetime.now(timezone.utc) + timedelta(days=21)
                ).strftime("%Y-%m-%d"),
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

    @staticmethod
    def _sample_multi_leg() -> list[MultiLegOpportunity]:
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        expiration = (datetime.now(timezone.utc) + timedelta(days=21)).strftime(
            "%Y-%m-%d"
        )
        return [
            MultiLegOpportunity(
                id="ml-001",
                symbol="SPY",
                strategyType="BULL_CALL_SPREAD",
                legs=[
                    OptionOpportunity(
                        id="leg-1",
                        symbol="SPY",
                        strikePrice=680.0,
                        expirationDate=expiration,
                        optionType="CALL",
                        currentPrice=8.5,
                        underlyingPrice=681.7,
                        impliedVolatility=0.27,
                        greeks=Greeks(delta=0.6, gamma=0.04, theta=-0.02, vega=0.10),
                        potentialGain=5.0,
                        potentialLoss=3.5,
                        riskRewardRatio=1.43,
                        confidenceScore=76,
                        timestamp=now,
                    ),
                    OptionOpportunity(
                        id="leg-2",
                        symbol="SPY",
                        strikePrice=690.0,
                        expirationDate=expiration,
                        optionType="CALL",
                        currentPrice=3.2,
                        underlyingPrice=681.7,
                        impliedVolatility=0.25,
                        greeks=Greeks(delta=0.35, gamma=0.05, theta=-0.01, vega=0.09),
                        potentialGain=5.0,
                        potentialLoss=1.8,
                        riskRewardRatio=2.78,
                        confidenceScore=74,
                        timestamp=now,
                    ),
                ],
                maxProfit=5.0,
                maxLoss=1.8,
                breakeven=681.8,
                riskRewardRatio=2.78,
                confidenceScore=75,
                timestamp=now,
            ),
            MultiLegOpportunity(
                id="ml-002",
                symbol="META",
                strategyType="IRON_CONDOR",
                legs=[
                    OptionOpportunity(
                        id="leg-3",
                        symbol="META",
                        strikePrice=680.0,
                        expirationDate=expiration,
                        optionType="CALL",
                        currentPrice=2.5,
                        underlyingPrice=689.3,
                        impliedVolatility=0.31,
                        greeks=Greeks(delta=0.25, gamma=0.03, theta=-0.01, vega=0.08),
                        potentialGain=2.5,
                        potentialLoss=2.5,
                        riskRewardRatio=1.0,
                        confidenceScore=72,
                        timestamp=now,
                    ),
                    OptionOpportunity(
                        id="leg-4",
                        symbol="META",
                        strikePrice=700.0,
                        expirationDate=expiration,
                        optionType="CALL",
                        currentPrice=0.8,
                        underlyingPrice=689.3,
                        impliedVolatility=0.28,
                        greeks=Greeks(delta=0.10, gamma=0.02, theta=0.0, vega=0.05),
                        potentialGain=0.8,
                        potentialLoss=1.2,
                        riskRewardRatio=0.67,
                        confidenceScore=70,
                        timestamp=now,
                    ),
                ],
                maxProfit=3.3,
                maxLoss=1.7,
                breakeven=686.7,
                riskRewardRatio=1.94,
                confidenceScore=73,
                timestamp=now,
            ),
        ]
