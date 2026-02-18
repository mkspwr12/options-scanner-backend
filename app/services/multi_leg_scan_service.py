"""Multi-leg scan service — generates multi-leg option strategy results.

Issue #11: POST /api/multi-leg-scan endpoint.
Uses mock/sample data; ready for live provider integration.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import MultiLegScanLeg, MultiLegScanResult, PayoutChart
from ..schemas import MultiLegScanRequest

logger = logging.getLogger(__name__)

# Supported strategy types
_STRATEGY_TYPES = {
    "iron_condor",
    "vertical_spread",
    "calendar_spread",
    "butterfly",
    "diagonal_spread",
}


class MultiLegScanService:
    """Scans for multi-leg option strategy opportunities."""

    def scan(self, request: MultiLegScanRequest) -> dict[str, Any]:
        """Execute a multi-leg scan for the given ticker and strategy."""
        strategy = request.strategyType.lower()
        if strategy not in _STRATEGY_TYPES:
            return {
                "status": "error",
                "message": f"Unsupported strategy type: {strategy}. "
                f"Supported: {', '.join(sorted(_STRATEGY_TYPES))}",
                "results": [],
            }

        results = self._generate_sample_results(
            ticker=request.ticker,
            strategy_type=strategy,
            filters=request.filters,
        )

        # Enrich results with Issue #17 fields
        self._enrich_results(results, request.ticker)

        return {"status": "ok", "results": [r.model_dump() for r in results]}

    # ------------------------------------------------------------------
    # Sample data generation
    # ------------------------------------------------------------------

    def _generate_sample_results(
        self,
        ticker: str,
        strategy_type: str,
        filters: Any | None = None,
    ) -> list[MultiLegScanResult]:
        """Generate sample multi-leg scan results."""
        generators = {
            "iron_condor": self._sample_iron_condor,
            "vertical_spread": self._sample_vertical_spread,
            "calendar_spread": self._sample_calendar_spread,
            "butterfly": self._sample_butterfly,
            "diagonal_spread": self._sample_diagonal_spread,
        }
        gen = generators.get(strategy_type, self._sample_vertical_spread)
        results = gen(ticker)

        # Apply filters
        if filters:
            results = self._apply_filters(results, filters)

        return results

    @staticmethod
    def _sample_iron_condor(ticker: str) -> list[MultiLegScanResult]:
        base_price = 180.0
        results: list[MultiLegScanResult] = []
        for offset in [5, 10, 15]:
            sell_put_strike = base_price - offset
            buy_put_strike = sell_put_strike - 5
            sell_call_strike = base_price + offset
            buy_call_strike = sell_call_strike + 5

            net_credit = round(2.5 + offset * 0.1, 2)
            max_profit = round(net_credit * 100, 2)
            max_loss = round(-500 + net_credit * 100, 2)

            be_low = round(sell_put_strike - net_credit, 2)
            be_high = round(sell_call_strike + net_credit, 2)

            # Payout chart
            price_range = [
                round(buy_put_strike - 5, 2),
                buy_put_strike,
                sell_put_strike,
                base_price,
                sell_call_strike,
                buy_call_strike,
                round(buy_call_strike + 5, 2),
            ]
            profit_range = []
            for p in price_range:
                if p <= buy_put_strike:
                    profit_range.append(max_loss)
                elif p <= sell_put_strike:
                    profit_range.append(
                        round(max_loss + (p - buy_put_strike) * 100, 2)
                    )
                elif p <= sell_call_strike:
                    profit_range.append(max_profit)
                elif p <= buy_call_strike:
                    profit_range.append(
                        round(max_profit - (p - sell_call_strike) * 100, 2)
                    )
                else:
                    profit_range.append(max_loss)

            results.append(
                MultiLegScanResult(
                    strategyType="iron_condor",
                    legs=[
                        MultiLegScanLeg(
                            type="sell_put",
                            strike=sell_put_strike,
                            premium=round(net_credit * 0.4, 2),
                            delta=round(-0.3 + offset * 0.005, 2),
                        ),
                        MultiLegScanLeg(
                            type="buy_put",
                            strike=buy_put_strike,
                            premium=round(net_credit * 0.15, 2),
                            delta=round(-0.15 + offset * 0.003, 2),
                        ),
                        MultiLegScanLeg(
                            type="sell_call",
                            strike=sell_call_strike,
                            premium=round(net_credit * 0.35, 2),
                            delta=round(0.3 - offset * 0.005, 2),
                        ),
                        MultiLegScanLeg(
                            type="buy_call",
                            strike=buy_call_strike,
                            premium=round(net_credit * 0.1, 2),
                            delta=round(0.15 - offset * 0.003, 2),
                        ),
                    ],
                    netCredit=round(net_credit * 100, 2),
                    maxProfit=max_profit,
                    maxLoss=max_loss,
                    breakevens=[be_low, be_high],
                    probability=round(65 + offset * 1.5, 1),
                    payoutChart=PayoutChart(
                        pricePoints=price_range, profitPoints=profit_range
                    ),
                )
            )
        return results

    @staticmethod
    def _sample_vertical_spread(ticker: str) -> list[MultiLegScanResult]:
        base_price = 180.0
        results: list[MultiLegScanResult] = []

        # Bull call spread
        buy_strike = base_price
        sell_strike = base_price + 5
        net_debit = 2.0
        max_profit = round((sell_strike - buy_strike - net_debit) * 100, 2)
        max_loss = round(-net_debit * 100, 2)
        be = round(buy_strike + net_debit, 2)

        prices = [170.0, 175.0, 180.0, 182.0, 185.0, 190.0, 195.0]
        profits = []
        for p in prices:
            if p <= buy_strike:
                profits.append(max_loss)
            elif p >= sell_strike:
                profits.append(max_profit)
            else:
                profits.append(round((p - buy_strike - net_debit) * 100, 2))

        results.append(
            MultiLegScanResult(
                strategyType="vertical_spread",
                legs=[
                    MultiLegScanLeg(type="buy_call", strike=buy_strike, premium=4.5, delta=0.52),
                    MultiLegScanLeg(type="sell_call", strike=sell_strike, premium=2.5, delta=0.35),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[be],
                probability=55.0,
                payoutChart=PayoutChart(pricePoints=prices, profitPoints=profits),
            )
        )

        # Bear put spread
        buy_strike_p = base_price
        sell_strike_p = base_price - 5
        net_debit_p = 1.8
        max_profit_p = round((buy_strike_p - sell_strike_p - net_debit_p) * 100, 2)
        max_loss_p = round(-net_debit_p * 100, 2)
        be_p = round(buy_strike_p - net_debit_p, 2)

        profits_p = []
        for p in prices:
            if p >= buy_strike_p:
                profits_p.append(max_loss_p)
            elif p <= sell_strike_p:
                profits_p.append(max_profit_p)
            else:
                profits_p.append(round((buy_strike_p - p - net_debit_p) * 100, 2))

        results.append(
            MultiLegScanResult(
                strategyType="vertical_spread",
                legs=[
                    MultiLegScanLeg(type="buy_put", strike=buy_strike_p, premium=3.8, delta=-0.48),
                    MultiLegScanLeg(type="sell_put", strike=sell_strike_p, premium=2.0, delta=-0.30),
                ],
                netCredit=0,
                maxProfit=max_profit_p,
                maxLoss=max_loss_p,
                breakevens=[be_p],
                probability=48.0,
                payoutChart=PayoutChart(pricePoints=prices, profitPoints=profits_p),
            )
        )
        return results

    @staticmethod
    def _sample_calendar_spread(ticker: str) -> list[MultiLegScanResult]:
        strike = 180.0
        net_debit = 1.5
        max_profit = round(net_debit * 100 * 1.5, 2)
        max_loss = round(-net_debit * 100, 2)

        prices = [170.0, 175.0, 178.0, 180.0, 182.0, 185.0, 190.0]
        profits = [
            max_loss,
            round(max_loss * 0.5, 2),
            round(max_profit * 0.6, 2),
            max_profit,
            round(max_profit * 0.6, 2),
            round(max_loss * 0.5, 2),
            max_loss,
        ]

        return [
            MultiLegScanResult(
                strategyType="calendar_spread",
                legs=[
                    MultiLegScanLeg(type="sell_call", strike=strike, premium=2.5, delta=0.50),
                    MultiLegScanLeg(type="buy_call", strike=strike, premium=4.0, delta=0.52),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[round(strike - 3, 2), round(strike + 3, 2)],
                probability=45.0,
                payoutChart=PayoutChart(pricePoints=prices, profitPoints=profits),
            )
        ]

    @staticmethod
    def _sample_butterfly(ticker: str) -> list[MultiLegScanResult]:
        center = 180.0
        width = 5.0
        net_debit = 1.0
        max_profit = round((width - net_debit) * 100, 2)
        max_loss = round(-net_debit * 100, 2)

        prices = [170.0, 175.0, 178.0, 180.0, 182.0, 185.0, 190.0]
        profits = []
        for p in prices:
            if p <= center - width or p >= center + width:
                profits.append(max_loss)
            elif p <= center:
                profits.append(round(max_loss + (p - (center - width)) / width * (max_profit - max_loss), 2))
            else:
                profits.append(round(max_profit - (p - center) / width * (max_profit - max_loss), 2))

        return [
            MultiLegScanResult(
                strategyType="butterfly",
                legs=[
                    MultiLegScanLeg(type="buy_call", strike=center - width, premium=6.0, delta=0.65),
                    MultiLegScanLeg(type="sell_call", strike=center, premium=3.5, delta=0.50),
                    MultiLegScanLeg(type="sell_call", strike=center, premium=3.5, delta=0.50),
                    MultiLegScanLeg(type="buy_call", strike=center + width, premium=2.0, delta=0.35),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[round(center - width + net_debit, 2), round(center + width - net_debit, 2)],
                probability=35.0,
                payoutChart=PayoutChart(pricePoints=prices, profitPoints=profits),
            )
        ]

    @staticmethod
    def _sample_diagonal_spread(ticker: str) -> list[MultiLegScanResult]:
        buy_strike = 180.0
        sell_strike = 185.0
        net_debit = 2.5
        max_profit = round((sell_strike - buy_strike) * 100 * 0.8, 2)
        max_loss = round(-net_debit * 100, 2)

        prices = [170.0, 175.0, 180.0, 183.0, 185.0, 190.0, 195.0]
        profits = [
            max_loss,
            round(max_loss * 0.6, 2),
            round(max_loss * 0.2, 2),
            round(max_profit * 0.7, 2),
            max_profit,
            round(max_profit * 0.5, 2),
            round(max_loss * 0.3, 2),
        ]

        return [
            MultiLegScanResult(
                strategyType="diagonal_spread",
                legs=[
                    MultiLegScanLeg(type="buy_call", strike=buy_strike, premium=5.0, delta=0.55),
                    MultiLegScanLeg(type="sell_call", strike=sell_strike, premium=2.5, delta=0.35),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[round(buy_strike + net_debit, 2)],
                probability=50.0,
                payoutChart=PayoutChart(pricePoints=prices, profitPoints=profits),
            )
        ]

    @staticmethod
    def _enrich_results(
        results: list[MultiLegScanResult], ticker: str
    ) -> None:
        """Add Issue #17 fields: id, ticker, buyingPower, split leg types."""
        exp_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        for r in results:
            r.id = f"strategy-{uuid.uuid4().hex[:8]}"
            r.ticker = ticker
            r.buyingPower = round(abs(r.maxLoss), 2)
            for leg in r.legs:
                parts = leg.type.split("_", 1)
                if len(parts) == 2:
                    action, opt_type = parts
                    leg.type = opt_type  # "put" or "call"
                    leg.position = "short" if action == "sell" else "long"
                leg.quantity = 1
                leg.expiration = exp_date

    @staticmethod
    def _apply_filters(
        results: list[MultiLegScanResult],
        filters: Any,
    ) -> list[MultiLegScanResult]:
        """Apply optional scan filters."""
        filtered: list[MultiLegScanResult] = []
        for r in results:
            if filters.minProbability is not None and r.probability < filters.minProbability:
                continue
            if filters.minCredit is not None and r.netCredit < filters.minCredit:
                continue
            if filters.maxBuyingPower is not None and abs(r.maxLoss) > filters.maxBuyingPower:
                continue
            filtered.append(r)
        return filtered
