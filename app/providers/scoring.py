"""Deterministic opportunity scoring for option contracts.

Scoring algorithm (from SPEC-8):
    confidence_score = weighted_average(
        iv_rank_score     * 0.25,
        volume_oi_score   * 0.20,
        risk_reward_score * 0.30,
        time_decay_score  * 0.15,
        delta_score       * 0.10,
    )

Each sub-score is normalised to 0-100.
"""
from __future__ import annotations

import math


def score_opportunity(
    *,
    implied_volatility: float,
    iv_52w_high: float = 0.60,
    iv_52w_low: float = 0.15,
    volume: int = 0,
    open_interest: int = 0,
    potential_gain: float = 0.0,
    potential_loss: float = 0.0,
    dte: int = 0,
    delta: float = 0.0,
) -> float:
    """Return a composite confidence score (0-100).

    All inputs are raw market values; normalisation happens internally.
    """
    iv_score = _iv_rank_score(implied_volatility, iv_52w_high, iv_52w_low)
    vol_oi = _volume_oi_score(volume, open_interest)
    rr = _risk_reward_score(potential_gain, potential_loss)
    td = _time_decay_score(dte)
    ds = _delta_score(delta)

    composite = (
        iv_score * 0.25
        + vol_oi * 0.20
        + rr * 0.30
        + td * 0.15
        + ds * 0.10
    )
    return round(min(max(composite, 0.0), 100.0), 2)


# ------------------------------------------------------------------
# Sub-score helpers
# ------------------------------------------------------------------

def _iv_rank_score(iv: float, high: float, low: float) -> float:
    """IV percentile rank mapped to 0-100.

    Higher rank → higher score (selling premium is favourable).
    """
    if high <= low or high <= 0:
        return 50.0
    rank = (iv - low) / (high - low) * 100.0
    return min(max(rank, 0.0), 100.0)


def _volume_oi_score(volume: int, open_interest: int) -> float:
    """Liquidity proxy: volume / OI ratio, scaled 0-100.

    A ratio of ≥1.0 gets full marks; 0 gets zero.
    """
    if open_interest <= 0:
        return 10.0 if volume > 0 else 0.0
    ratio = volume / open_interest
    return min(ratio * 100.0, 100.0)


def _risk_reward_score(gain: float, loss: float) -> float:
    """Map risk-reward ratio to 0-100.

    2:1 → 66, 3:1 → 75, 5:1 → 83, 10:1 → 90.
    Uses diminishing-returns curve.
    """
    if loss <= 0:
        return 50.0
    rr = gain / loss
    # logistic-style curve: 100 * (1 - e^(-0.5 * rr))
    return min(100.0 * (1.0 - math.exp(-0.5 * rr)), 100.0)


def _time_decay_score(dte: int) -> float:
    """Sweet-spot scoring: 21-45 DTE is ideal.

    Below 7 → penalised (too close), above 90 → reduced premium.
    """
    if dte <= 0:
        return 0.0
    if 21 <= dte <= 45:
        return 100.0
    if 14 <= dte < 21:
        return 75.0
    if 7 <= dte < 14:
        return 50.0
    if dte < 7:
        return 20.0
    if 45 < dte <= 60:
        return 80.0
    if 60 < dte <= 90:
        return 60.0
    return 40.0  # > 90 DTE


def _delta_score(delta: float) -> float:
    """Optimal delta range: |delta| in [0.30, 0.50] → full score."""
    abs_d = abs(delta)
    if 0.30 <= abs_d <= 0.50:
        return 100.0
    if 0.20 <= abs_d < 0.30 or 0.50 < abs_d <= 0.60:
        return 75.0
    if 0.10 <= abs_d < 0.20 or 0.60 < abs_d <= 0.70:
        return 50.0
    return 25.0
