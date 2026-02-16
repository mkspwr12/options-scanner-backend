"""Tests for the opportunity scoring module."""
from __future__ import annotations

import pytest

from app.providers.scoring import (
    _delta_score,
    _iv_rank_score,
    _risk_reward_score,
    _time_decay_score,
    _volume_oi_score,
    score_opportunity,
)


class TestScoreOpportunity:
    """Integration tests for the composite scoring function."""

    def test_returns_float(self) -> None:
        result = score_opportunity(
            implied_volatility=0.30,
            volume=1000,
            open_interest=5000,
            potential_gain=10.0,
            potential_loss=5.0,
            dte=30,
            delta=0.40,
        )
        assert isinstance(result, float)

    def test_score_in_range(self) -> None:
        result = score_opportunity(
            implied_volatility=0.30,
            volume=1000,
            open_interest=5000,
            potential_gain=10.0,
            potential_loss=5.0,
            dte=30,
            delta=0.40,
        )
        assert 0 <= result <= 100

    def test_high_quality_scores_high(self) -> None:
        """Ideal params: high IV rank, good liquidity, 2:1 RR, 30 DTE, delta 0.4."""
        result = score_opportunity(
            implied_volatility=0.50,
            iv_52w_high=0.60,
            iv_52w_low=0.15,
            volume=5000,
            open_interest=5000,
            potential_gain=10.0,
            potential_loss=5.0,
            dte=30,
            delta=0.40,
        )
        assert result > 60

    def test_low_quality_scores_low(self) -> None:
        """Bad params: low IV, no volume, poor RR, near expiry."""
        result = score_opportunity(
            implied_volatility=0.10,
            iv_52w_high=0.60,
            iv_52w_low=0.15,
            volume=0,
            open_interest=0,
            potential_gain=1.0,
            potential_loss=10.0,
            dte=2,
            delta=0.05,
        )
        assert result < 30

    def test_score_rounded_to_two_decimals(self) -> None:
        result = score_opportunity(
            implied_volatility=0.30,
            volume=500,
            open_interest=2000,
            potential_gain=8.0,
            potential_loss=4.0,
            dte=25,
            delta=0.35,
        )
        assert result == round(result, 2)


class TestIVRankScore:
    def test_midpoint_iv(self) -> None:
        score = _iv_rank_score(0.375, 0.60, 0.15)
        assert 45 < score < 55

    def test_at_high(self) -> None:
        assert _iv_rank_score(0.60, 0.60, 0.15) == 100.0

    def test_at_low(self) -> None:
        assert _iv_rank_score(0.15, 0.60, 0.15) == 0.0

    def test_equal_high_low(self) -> None:
        assert _iv_rank_score(0.30, 0.30, 0.30) == 50.0

    def test_below_range_clamped(self) -> None:
        assert _iv_rank_score(0.05, 0.60, 0.15) == 0.0

    def test_above_range_clamped(self) -> None:
        assert _iv_rank_score(0.80, 0.60, 0.15) == 100.0


class TestVolumeOIScore:
    def test_ratio_one(self) -> None:
        assert _volume_oi_score(5000, 5000) == 100.0

    def test_ratio_half(self) -> None:
        assert _volume_oi_score(2500, 5000) == 50.0

    def test_zero_oi_with_volume(self) -> None:
        assert _volume_oi_score(100, 0) == 10.0

    def test_zero_both(self) -> None:
        assert _volume_oi_score(0, 0) == 0.0

    def test_high_ratio_capped(self) -> None:
        assert _volume_oi_score(10000, 100) == 100.0


class TestRiskRewardScore:
    def test_two_to_one(self) -> None:
        score = _risk_reward_score(10, 5)
        assert 55 < score < 75

    def test_zero_loss(self) -> None:
        assert _risk_reward_score(10, 0) == 50.0

    def test_higher_rr_higher_score(self) -> None:
        low = _risk_reward_score(5, 5)
        high = _risk_reward_score(20, 5)
        assert high > low


class TestTimeDecayScore:
    def test_sweet_spot(self) -> None:
        assert _time_decay_score(30) == 100.0
        assert _time_decay_score(21) == 100.0
        assert _time_decay_score(45) == 100.0

    def test_near_expiry(self) -> None:
        assert _time_decay_score(3) == 20.0

    def test_zero_dte(self) -> None:
        assert _time_decay_score(0) == 0.0

    def test_far_out(self) -> None:
        assert _time_decay_score(100) == 40.0

    def test_moderate_range(self) -> None:
        assert _time_decay_score(50) == 80.0

    def test_7_to_14_range(self) -> None:
        assert _time_decay_score(10) == 50.0

    def test_14_to_21_range(self) -> None:
        assert _time_decay_score(15) == 75.0

    def test_60_to_90_range(self) -> None:
        assert _time_decay_score(75) == 60.0


class TestDeltaScore:
    def test_optimal_range(self) -> None:
        assert _delta_score(0.40) == 100.0
        assert _delta_score(-0.35) == 100.0

    def test_slightly_out(self) -> None:
        assert _delta_score(0.25) == 75.0

    def test_far_out(self) -> None:
        assert _delta_score(0.05) == 25.0
