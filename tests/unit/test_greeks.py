"""Tests for the Black-Scholes Greeks calculator."""
from __future__ import annotations

import pytest

from app.providers.greeks import GreeksResult, calculate_greeks


class TestCalculateGreeks:
    """Unit tests for calculate_greeks()."""

    def test_call_delta_positive(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g.delta > 0
        assert g.delta <= 1.0

    def test_put_delta_negative(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="PUT")
        assert g.delta < 0
        assert g.delta >= -1.0

    def test_atm_call_delta_near_half(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert 0.40 < g.delta < 0.65

    def test_gamma_positive(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g.gamma > 0

    def test_theta_negative_for_calls(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g.theta < 0

    def test_vega_positive(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g.vega > 0

    def test_deep_itm_call_delta_near_one(self) -> None:
        g = calculate_greeks(S=200, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g.delta > 0.95

    def test_deep_otm_call_delta_near_zero(self) -> None:
        g = calculate_greeks(S=50, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g.delta < 0.05

    def test_zero_time_returns_zeros(self) -> None:
        g = calculate_greeks(S=100, K=100, T=0, r=0.05, sigma=0.30, option_type="CALL")
        assert g == GreeksResult(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

    def test_zero_volatility_returns_zeros(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0, option_type="CALL")
        assert g == GreeksResult(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

    def test_zero_price_returns_zeros(self) -> None:
        g = calculate_greeks(S=0, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert g == GreeksResult(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

    def test_result_is_greeks_result(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        assert isinstance(g, GreeksResult)

    def test_values_are_rounded(self) -> None:
        g = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        # All values should have at most 4 decimal places
        for val in (g.delta, g.gamma, g.theta, g.vega):
            assert val == round(val, 4)

    def test_put_call_parity_delta(self) -> None:
        """Put delta ≈ Call delta - 1."""
        call = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        put = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="PUT")
        assert abs((call.delta - 1) - put.delta) < 0.02

    def test_gamma_same_for_call_and_put(self) -> None:
        call = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="CALL")
        put = calculate_greeks(S=100, K=100, T=30 / 365, r=0.05, sigma=0.30, option_type="PUT")
        assert call.gamma == put.gamma
