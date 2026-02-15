"""Scan service — orchestrates option scanning.

Phase 1: returns hardcoded sample data (preserving current behaviour).
Phase 2 (SPEC-8): delegates to a MarketDataProvider for live data.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..models import Greeks, MultiLegOpportunity, OptionOpportunity
from ..repositories.scan_repository import ScanRepository

logger = logging.getLogger(__name__)


class ScanService:
    """Orchestrates option scanning — currently returns sample data."""

    def __init__(self, repo: ScanRepository | None = None) -> None:
        self._repo = repo or ScanRepository()

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
    ) -> dict[str, Any]:
        """Return scan results.

        Tries the database first; falls back to hardcoded sample data
        when no persisted scan results exist (Phase 1 behaviour).
        """
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
                    "source": "database",
                    "stale": False,
                }
        except Exception:
            logger.warning("DB scan retrieval failed — falling back to sample data")

        # Fallback: hardcoded sample data (Phase 1)
        return {
            "status": "ok",
            "opportunities": self._sample_opportunities(),
            "source": "sample",
            "stale": False,
        }

    def get_multi_leg_opportunities(self) -> dict[str, Any]:
        """Return multi-leg strategies (hardcoded in Phase 1)."""
        return {
            "status": "ok",
            "opportunities": self._sample_multi_leg(),
        }

    # ------------------------------------------------------------------
    # Hardcoded sample data (preserved from original main.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_opportunities() -> list[OptionOpportunity]:
        now = int(datetime.utcnow().timestamp() * 1000)
        return [
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

    @staticmethod
    def _sample_multi_leg() -> list[MultiLegOpportunity]:
        now = int(datetime.utcnow().timestamp() * 1000)
        expiration = (datetime.utcnow() + timedelta(days=21)).strftime("%Y-%m-%d")
        return [
            MultiLegOpportunity(
                id="ml-001",
                symbol="SPY",
                strategyType="BULL_CALL_SPREAD",
                legs=[
                    OptionOpportunity(
                        id="leg-1", symbol="SPY", strikePrice=680.0,
                        expirationDate=expiration, optionType="CALL",
                        currentPrice=8.5, underlyingPrice=681.7,
                        impliedVolatility=0.27,
                        greeks=Greeks(delta=0.6, gamma=0.04, theta=-0.02, vega=0.10),
                        potentialGain=5.0, potentialLoss=3.5,
                        riskRewardRatio=1.43, confidenceScore=76, timestamp=now,
                    ),
                    OptionOpportunity(
                        id="leg-2", symbol="SPY", strikePrice=690.0,
                        expirationDate=expiration, optionType="CALL",
                        currentPrice=3.2, underlyingPrice=681.7,
                        impliedVolatility=0.25,
                        greeks=Greeks(delta=0.35, gamma=0.05, theta=-0.01, vega=0.09),
                        potentialGain=5.0, potentialLoss=1.8,
                        riskRewardRatio=2.78, confidenceScore=74, timestamp=now,
                    ),
                ],
                maxProfit=5.0, maxLoss=1.8, breakeven=681.8,
                riskRewardRatio=2.78, confidenceScore=75, timestamp=now,
            ),
            MultiLegOpportunity(
                id="ml-002",
                symbol="META",
                strategyType="IRON_CONDOR",
                legs=[
                    OptionOpportunity(
                        id="leg-3", symbol="META", strikePrice=680.0,
                        expirationDate=expiration, optionType="CALL",
                        currentPrice=2.5, underlyingPrice=689.3,
                        impliedVolatility=0.31,
                        greeks=Greeks(delta=0.25, gamma=0.03, theta=-0.01, vega=0.08),
                        potentialGain=2.5, potentialLoss=2.5,
                        riskRewardRatio=1.0, confidenceScore=72, timestamp=now,
                    ),
                    OptionOpportunity(
                        id="leg-4", symbol="META", strikePrice=700.0,
                        expirationDate=expiration, optionType="CALL",
                        currentPrice=0.8, underlyingPrice=689.3,
                        impliedVolatility=0.28,
                        greeks=Greeks(delta=0.10, gamma=0.02, theta=0.0, vega=0.05),
                        potentialGain=0.8, potentialLoss=1.2,
                        riskRewardRatio=0.67, confidenceScore=70, timestamp=now,
                    ),
                ],
                maxProfit=3.3, maxLoss=1.7, breakeven=686.7,
                riskRewardRatio=1.94, confidenceScore=73, timestamp=now,
            ),
        ]
