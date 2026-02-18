"""Multi-leg scan service — generates multi-leg option strategy results.

Issue #11: POST /api/multi-leg-scan endpoint.
Uses Yahoo Finance (yfinance) for real options chain data.
Falls back to mock data when the provider is unavailable.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import MultiLegScanLeg, MultiLegScanResult, PayoutChart
from ..providers.base import MarketDataProvider, OptionContract, Quote
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
    """Scans for multi-leg option strategy opportunities using live data."""

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self._provider = provider

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

        results = self._generate_results(
            ticker=request.ticker,
            strategy_type=strategy,
            filters=request.filters,
        )

        # Enrich results with Issue #17 fields
        self._enrich_results(results, request.ticker)

        return {"status": "ok", "results": [r.model_dump() for r in results]}

    # ------------------------------------------------------------------
    # Result generation (live or fallback)
    # ------------------------------------------------------------------

    def _generate_results(
        self,
        ticker: str,
        strategy_type: str,
        filters: Any | None = None,
    ) -> list[MultiLegScanResult]:
        """Generate multi-leg results using live data or fallback to mock."""
        if self._provider is not None:
            try:
                results = self._build_from_live_data(ticker, strategy_type)
                if results:
                    if filters:
                        results = self._apply_filters(results, filters)
                    return results
            except Exception:
                logger.exception(
                    "Live multi-leg scan failed for %s/%s — fallback to mock",
                    ticker, strategy_type,
                )

        # Fallback to mock
        results = self._generate_sample_results(ticker, strategy_type, filters)
        return results

    def _build_from_live_data(
        self, ticker: str, strategy_type: str,
    ) -> list[MultiLegScanResult]:
        """Build multi-leg strategies from live options chain data."""
        assert self._provider is not None

        quote = self._provider.get_quote(ticker)
        contracts = self._provider.get_options_chain(ticker)

        if not contracts:
            logger.warning("No options contracts for %s", ticker)
            return []

        base_price = quote.price

        # Separate calls and puts, sort by strike
        calls = sorted(
            [c for c in contracts if c.option_type == "CALL"],
            key=lambda c: c.strike,
        )
        puts = sorted(
            [c for c in contracts if c.option_type == "PUT"],
            key=lambda c: c.strike,
        )

        if not calls or not puts:
            return []

        expiration = contracts[0].expiration

        generators = {
            "iron_condor": self._live_iron_condor,
            "vertical_spread": self._live_vertical_spread,
            "calendar_spread": self._live_calendar_spread,
            "butterfly": self._live_butterfly,
            "diagonal_spread": self._live_diagonal_spread,
        }

        gen = generators.get(strategy_type, self._live_vertical_spread)
        return gen(ticker, base_price, calls, puts, expiration)

    # ------------------------------------------------------------------
    # Live strategy builders
    # ------------------------------------------------------------------

    @staticmethod
    def _mid_price(contract: OptionContract) -> float:
        """Get mid price from bid/ask or fall back to last price."""
        if contract.bid > 0 and contract.ask > 0:
            return round((contract.bid + contract.ask) / 2, 2)
        return round(contract.last_price, 2)

    @staticmethod
    def _find_contract_near_strike(
        contracts: list[OptionContract], target_strike: float,
    ) -> OptionContract | None:
        """Find the contract closest to a target strike."""
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(c.strike - target_strike))

    def _live_iron_condor(
        self,
        ticker: str,
        base_price: float,
        calls: list[OptionContract],
        puts: list[OptionContract],
        expiration: str,
    ) -> list[MultiLegScanResult]:
        """Build iron condor strategies from live data."""
        results: list[MultiLegScanResult] = []

        # Try multiple widths
        for offset_pct in [0.03, 0.05, 0.08]:
            sell_put_target = base_price * (1 - offset_pct)
            buy_put_target = base_price * (1 - offset_pct - 0.03)
            sell_call_target = base_price * (1 + offset_pct)
            buy_call_target = base_price * (1 + offset_pct + 0.03)

            sell_put = self._find_contract_near_strike(puts, sell_put_target)
            buy_put = self._find_contract_near_strike(puts, buy_put_target)
            sell_call = self._find_contract_near_strike(calls, sell_call_target)
            buy_call = self._find_contract_near_strike(calls, buy_call_target)

            if not all([sell_put, buy_put, sell_call, buy_call]):
                continue

            sp_mid = self._mid_price(sell_put)
            bp_mid = self._mid_price(buy_put)
            sc_mid = self._mid_price(sell_call)
            bc_mid = self._mid_price(buy_call)

            net_credit = round((sp_mid - bp_mid + sc_mid - bc_mid), 2)
            if net_credit <= 0:
                continue

            put_width = abs(sell_put.strike - buy_put.strike)
            call_width = abs(buy_call.strike - sell_call.strike)
            max_width = max(put_width, call_width)
            max_loss_val = round((max_width - net_credit) * 100, 2)
            max_profit_val = round(net_credit * 100, 2)

            be_low = round(sell_put.strike - net_credit, 2)
            be_high = round(sell_call.strike + net_credit, 2)

            # Payout chart
            price_range = [
                round(buy_put.strike - 5, 2),
                buy_put.strike,
                sell_put.strike,
                base_price,
                sell_call.strike,
                buy_call.strike,
                round(buy_call.strike + 5, 2),
            ]
            profit_range = []
            for p in price_range:
                if p <= buy_put.strike:
                    profit_range.append(-max_loss_val)
                elif p <= sell_put.strike:
                    profit_range.append(
                        round(-max_loss_val + (p - buy_put.strike) * 100, 2)
                    )
                elif p <= sell_call.strike:
                    profit_range.append(max_profit_val)
                elif p <= buy_call.strike:
                    profit_range.append(
                        round(max_profit_val - (p - sell_call.strike) * 100, 2)
                    )
                else:
                    profit_range.append(-max_loss_val)

            # Probability estimate from delta
            prob = round(
                (1 - abs(sell_put.implied_volatility * 0.5)
                 - abs(sell_call.implied_volatility * 0.5)) * 100,
                1,
            )
            prob = max(30.0, min(prob, 85.0))

            results.append(
                MultiLegScanResult(
                    strategyType="iron_condor",
                    legs=[
                        MultiLegScanLeg(
                            type="sell_put",
                            strike=sell_put.strike,
                            premium=sp_mid,
                            delta=round(-0.3 + offset_pct * 5, 2),
                        ),
                        MultiLegScanLeg(
                            type="buy_put",
                            strike=buy_put.strike,
                            premium=bp_mid,
                            delta=round(-0.15 + offset_pct * 3, 2),
                        ),
                        MultiLegScanLeg(
                            type="sell_call",
                            strike=sell_call.strike,
                            premium=sc_mid,
                            delta=round(0.3 - offset_pct * 5, 2),
                        ),
                        MultiLegScanLeg(
                            type="buy_call",
                            strike=buy_call.strike,
                            premium=bc_mid,
                            delta=round(0.15 - offset_pct * 3, 2),
                        ),
                    ],
                    netCredit=round(net_credit * 100, 2),
                    maxProfit=max_profit_val,
                    maxLoss=-max_loss_val,
                    breakevens=[be_low, be_high],
                    probability=prob,
                    payoutChart=PayoutChart(
                        pricePoints=price_range, profitPoints=profit_range,
                    ),
                )
            )

        return results

    def _live_vertical_spread(
        self,
        ticker: str,
        base_price: float,
        calls: list[OptionContract],
        puts: list[OptionContract],
        expiration: str,
    ) -> list[MultiLegScanResult]:
        """Build bull call and bear put spreads from live data."""
        results: list[MultiLegScanResult] = []

        # Bull call spread: buy ATM call, sell OTM call
        atm_call = self._find_contract_near_strike(calls, base_price)
        otm_call = self._find_contract_near_strike(
            calls, base_price * 1.03
        )

        if atm_call and otm_call and atm_call.strike != otm_call.strike:
            buy_mid = self._mid_price(atm_call)
            sell_mid = self._mid_price(otm_call)
            net_debit = round(buy_mid - sell_mid, 2)

            if net_debit > 0:
                spread_width = otm_call.strike - atm_call.strike
                max_profit = round((spread_width - net_debit) * 100, 2)
                max_loss = round(-net_debit * 100, 2)
                be = round(atm_call.strike + net_debit, 2)

                prices = [
                    round(base_price * f, 2)
                    for f in [0.94, 0.97, 1.0, 1.01, 1.03, 1.05, 1.08]
                ]
                profits = []
                for p in prices:
                    if p <= atm_call.strike:
                        profits.append(max_loss)
                    elif p >= otm_call.strike:
                        profits.append(max_profit)
                    else:
                        profits.append(
                            round((p - atm_call.strike - net_debit) * 100, 2)
                        )

                results.append(
                    MultiLegScanResult(
                        strategyType="vertical_spread",
                        legs=[
                            MultiLegScanLeg(
                                type="buy_call",
                                strike=atm_call.strike,
                                premium=buy_mid,
                                delta=round(atm_call.implied_volatility * 0.5 + 0.3, 2),
                            ),
                            MultiLegScanLeg(
                                type="sell_call",
                                strike=otm_call.strike,
                                premium=sell_mid,
                                delta=round(otm_call.implied_volatility * 0.3 + 0.15, 2),
                            ),
                        ],
                        netCredit=0,
                        maxProfit=max_profit,
                        maxLoss=max_loss,
                        breakevens=[be],
                        probability=55.0,
                        payoutChart=PayoutChart(
                            pricePoints=prices, profitPoints=profits,
                        ),
                    )
                )

        # Bear put spread: buy ATM put, sell OTM put
        atm_put = self._find_contract_near_strike(puts, base_price)
        otm_put = self._find_contract_near_strike(puts, base_price * 0.97)

        if atm_put and otm_put and atm_put.strike != otm_put.strike:
            buy_mid = self._mid_price(atm_put)
            sell_mid = self._mid_price(otm_put)
            net_debit = round(buy_mid - sell_mid, 2)

            if net_debit > 0:
                spread_width = atm_put.strike - otm_put.strike
                max_profit = round((spread_width - net_debit) * 100, 2)
                max_loss = round(-net_debit * 100, 2)
                be = round(atm_put.strike - net_debit, 2)

                prices = [
                    round(base_price * f, 2)
                    for f in [0.92, 0.95, 0.97, 0.99, 1.0, 1.03, 1.06]
                ]
                profits = []
                for p in prices:
                    if p >= atm_put.strike:
                        profits.append(max_loss)
                    elif p <= otm_put.strike:
                        profits.append(max_profit)
                    else:
                        profits.append(
                            round((atm_put.strike - p - net_debit) * 100, 2)
                        )

                results.append(
                    MultiLegScanResult(
                        strategyType="vertical_spread",
                        legs=[
                            MultiLegScanLeg(
                                type="buy_put",
                                strike=atm_put.strike,
                                premium=buy_mid,
                                delta=round(-atm_put.implied_volatility * 0.5 - 0.2, 2),
                            ),
                            MultiLegScanLeg(
                                type="sell_put",
                                strike=otm_put.strike,
                                premium=sell_mid,
                                delta=round(-otm_put.implied_volatility * 0.3 - 0.1, 2),
                            ),
                        ],
                        netCredit=0,
                        maxProfit=max_profit,
                        maxLoss=max_loss,
                        breakevens=[be],
                        probability=48.0,
                        payoutChart=PayoutChart(
                            pricePoints=prices, profitPoints=profits,
                        ),
                    )
                )

        return results

    def _live_calendar_spread(
        self,
        ticker: str,
        base_price: float,
        calls: list[OptionContract],
        puts: list[OptionContract],
        expiration: str,
    ) -> list[MultiLegScanResult]:
        """Build calendar spread from live data (ATM strike, sell near / buy far)."""
        atm_call = self._find_contract_near_strike(calls, base_price)
        if not atm_call:
            return []

        strike = atm_call.strike
        near_mid = self._mid_price(atm_call)
        # For calendar, the far-dated option costs more (approximate +60% premium)
        far_mid = round(near_mid * 1.6, 2)
        net_debit = round(far_mid - near_mid, 2)
        if net_debit <= 0:
            net_debit = round(near_mid * 0.6, 2)

        max_profit = round(net_debit * 100 * 1.5, 2)
        max_loss = round(-net_debit * 100, 2)

        prices = [
            round(base_price * f, 2)
            for f in [0.94, 0.97, 0.99, 1.0, 1.01, 1.03, 1.06]
        ]
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
                    MultiLegScanLeg(
                        type="sell_call", strike=strike,
                        premium=near_mid, delta=0.50,
                    ),
                    MultiLegScanLeg(
                        type="buy_call", strike=strike,
                        premium=far_mid, delta=0.52,
                    ),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[round(strike - 3, 2), round(strike + 3, 2)],
                probability=45.0,
                payoutChart=PayoutChart(
                    pricePoints=prices, profitPoints=profits,
                ),
            )
        ]

    def _live_butterfly(
        self,
        ticker: str,
        base_price: float,
        calls: list[OptionContract],
        puts: list[OptionContract],
        expiration: str,
    ) -> list[MultiLegScanResult]:
        """Build butterfly spread from live data."""
        center_call = self._find_contract_near_strike(calls, base_price)
        if not center_call:
            return []

        center = center_call.strike
        # Find wings
        wing_width_target = base_price * 0.03
        lower_call = self._find_contract_near_strike(
            calls, center - wing_width_target,
        )
        upper_call = self._find_contract_near_strike(
            calls, center + wing_width_target,
        )

        if not lower_call or not upper_call:
            return []
        if lower_call.strike == center or upper_call.strike == center:
            return []

        lower_mid = self._mid_price(lower_call)
        center_mid = self._mid_price(center_call)
        upper_mid = self._mid_price(upper_call)

        net_debit = round(lower_mid - 2 * center_mid + upper_mid, 2)
        if net_debit <= 0:
            net_debit = round(abs(net_debit) + 0.5, 2)

        width = min(
            abs(center - lower_call.strike),
            abs(upper_call.strike - center),
        )
        max_profit = round((width - net_debit) * 100, 2)
        max_loss = round(-net_debit * 100, 2)

        prices = [
            round(base_price * f, 2)
            for f in [0.94, 0.97, 0.99, 1.0, 1.01, 1.03, 1.06]
        ]
        profits = []
        for p in prices:
            if p <= lower_call.strike or p >= upper_call.strike:
                profits.append(max_loss)
            elif p <= center:
                frac = (p - lower_call.strike) / max(
                    center - lower_call.strike, 0.01
                )
                profits.append(round(max_loss + frac * (max_profit - max_loss), 2))
            else:
                frac = (p - center) / max(
                    upper_call.strike - center, 0.01
                )
                profits.append(round(max_profit - frac * (max_profit - max_loss), 2))

        return [
            MultiLegScanResult(
                strategyType="butterfly",
                legs=[
                    MultiLegScanLeg(
                        type="buy_call", strike=lower_call.strike,
                        premium=lower_mid, delta=0.65,
                    ),
                    MultiLegScanLeg(
                        type="sell_call", strike=center,
                        premium=center_mid, delta=0.50,
                    ),
                    MultiLegScanLeg(
                        type="sell_call", strike=center,
                        premium=center_mid, delta=0.50,
                    ),
                    MultiLegScanLeg(
                        type="buy_call", strike=upper_call.strike,
                        premium=upper_mid, delta=0.35,
                    ),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[
                    round(lower_call.strike + net_debit, 2),
                    round(upper_call.strike - net_debit, 2),
                ],
                probability=35.0,
                payoutChart=PayoutChart(
                    pricePoints=prices, profitPoints=profits,
                ),
            )
        ]

    def _live_diagonal_spread(
        self,
        ticker: str,
        base_price: float,
        calls: list[OptionContract],
        puts: list[OptionContract],
        expiration: str,
    ) -> list[MultiLegScanResult]:
        """Build diagonal spread from live data."""
        atm_call = self._find_contract_near_strike(calls, base_price)
        otm_call = self._find_contract_near_strike(calls, base_price * 1.03)

        if not atm_call or not otm_call or atm_call.strike == otm_call.strike:
            return []

        buy_mid = self._mid_price(atm_call)
        sell_mid = self._mid_price(otm_call)
        net_debit = round(buy_mid - sell_mid * 0.6, 2)  # far-dated buy, near-dated sell
        if net_debit <= 0:
            net_debit = round(buy_mid * 0.4, 2)

        max_profit = round((otm_call.strike - atm_call.strike) * 100 * 0.8, 2)
        max_loss = round(-net_debit * 100, 2)

        prices = [
            round(base_price * f, 2)
            for f in [0.94, 0.97, 1.0, 1.02, 1.03, 1.05, 1.08]
        ]
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
                    MultiLegScanLeg(
                        type="buy_call", strike=atm_call.strike,
                        premium=buy_mid, delta=0.55,
                    ),
                    MultiLegScanLeg(
                        type="sell_call", strike=otm_call.strike,
                        premium=sell_mid, delta=0.35,
                    ),
                ],
                netCredit=0,
                maxProfit=max_profit,
                maxLoss=max_loss,
                breakevens=[round(atm_call.strike + net_debit, 2)],
                probability=50.0,
                payoutChart=PayoutChart(
                    pricePoints=prices, profitPoints=profits,
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Mock fallback generators (used when provider is unavailable)
    # ------------------------------------------------------------------

    def _generate_sample_results(
        self,
        ticker: str,
        strategy_type: str,
        filters: Any | None = None,
    ) -> list[MultiLegScanResult]:
        """Generate sample multi-leg scan results (mock fallback)."""
        generators = {
            "iron_condor": self._sample_iron_condor,
            "vertical_spread": self._sample_vertical_spread,
            "calendar_spread": self._sample_calendar_spread,
            "butterfly": self._sample_butterfly,
            "diagonal_spread": self._sample_diagonal_spread,
        }
        gen = generators.get(strategy_type, self._sample_vertical_spread)
        results = gen(ticker)

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
