"""Unit tests for Issue #10 — payout chart data on scan opportunities."""
from __future__ import annotations

from app.services.scan_service import ScanService


class TestPayoutChart:
    def test_call_breakeven(self) -> None:
        """Breakeven for long call = strike + premium."""
        be = ScanService._calculate_breakeven(180.0, 5.0, "CALL")
        assert be == 185.0

    def test_put_breakeven(self) -> None:
        """Breakeven for long put = strike - premium."""
        be = ScanService._calculate_breakeven(180.0, 5.0, "PUT")
        assert be == 175.0

    def test_probability_call(self) -> None:
        """Delta approximation for probability."""
        prob = ScanService._calculate_probability(0.42, "CALL")
        assert prob == 42.0

    def test_probability_put(self) -> None:
        prob = ScanService._calculate_probability(-0.38, "PUT")
        assert prob == 38.0

    def test_probability_clamped(self) -> None:
        """Probability should be clamped to 0-100."""
        prob = ScanService._calculate_probability(1.5, "CALL")
        assert prob == 100.0

    def test_payout_chart_call_structure(self) -> None:
        chart = ScanService._calculate_payout_chart(180.0, 180.0, 5.0, "CALL")
        assert "pricePoints" in chart
        assert "profitPoints" in chart
        assert "maxProfit" in chart
        assert "maxLoss" in chart
        assert len(chart["pricePoints"]) == 7
        assert len(chart["profitPoints"]) == 7

    def test_payout_chart_call_max_loss(self) -> None:
        """Max loss for long call = premium * 100."""
        chart = ScanService._calculate_payout_chart(180.0, 180.0, 5.0, "CALL")
        assert chart["maxLoss"] == -500.0

    def test_payout_chart_put_max_loss(self) -> None:
        """Max loss for long put = premium * 100."""
        chart = ScanService._calculate_payout_chart(180.0, 180.0, 5.0, "PUT")
        assert chart["maxLoss"] == -500.0

    def test_payout_chart_price_range(self) -> None:
        """Price points should span ±15% of underlying price."""
        chart = ScanService._calculate_payout_chart(200.0, 200.0, 5.0, "CALL")
        assert chart["pricePoints"][0] == 170.0  # 200 * 0.85
        assert chart["pricePoints"][-1] == 230.0  # 200 * 1.15
