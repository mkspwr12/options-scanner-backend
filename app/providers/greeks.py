"""Black-Scholes Greeks calculator.

Provides delta, gamma, theta, and vega for European-style options.
Uses ``scipy.stats.norm`` for the cumulative-normal distribution.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm


@dataclass(frozen=True)
class GreeksResult:
    """Computed Greeks for a single option contract."""

    delta: float
    gamma: float
    theta: float
    vega: float


_TRADING_DAYS = 252  # annualised trading days


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "CALL",
) -> GreeksResult:
    """Calculate Black-Scholes Greeks.

    Args:
        S: Current underlying price.
        K: Strike price.
        T: Time to expiration **in years** (e.g. 30 / 365).
        r: Risk-free interest rate (annualised, e.g. 0.05).
        sigma: Implied volatility (annualised, e.g. 0.30).
        option_type: ``"CALL"`` or ``"PUT"``.

    Returns:
        ``GreeksResult`` with delta, gamma, theta, vega.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return GreeksResult(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # --- Delta ---
    if option_type == "CALL":
        delta = float(norm.cdf(d1))
    else:
        delta = float(norm.cdf(d1) - 1.0)

    # --- Gamma (same for calls and puts) ---
    gamma = float(norm.pdf(d1) / (S * sigma * sqrt_T))

    # --- Theta ---
    common_theta = -(S * norm.pdf(d1) * sigma) / (2.0 * sqrt_T)
    if option_type == "CALL":
        theta = float(common_theta - r * K * math.exp(-r * T) * norm.cdf(d2))
    else:
        theta = float(common_theta + r * K * math.exp(-r * T) * norm.cdf(-d2))
    # Convert to daily theta
    theta = theta / _TRADING_DAYS

    # --- Vega ---
    vega = float(S * norm.pdf(d1) * sqrt_T)
    # Express per 1% move in IV
    vega = vega / 100.0

    return GreeksResult(
        delta=round(delta, 4),
        gamma=round(gamma, 4),
        theta=round(theta, 4),
        vega=round(vega, 4),
    )
