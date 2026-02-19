"""Unit tests for ScanService."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.repositories.scan_repository import ScanRepository
from app.services.scan_service import ScanService


class TestGetOpportunities:
    def test_no_data_returns_empty(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.get_latest.return_value = []  # empty = no persisted data

        svc = ScanService(repo=repo)
        result = svc.get_opportunities()

        assert result["status"] == "ok"
        assert result["source"] == "none"
        assert len(result["opportunities"]) == 0

    def test_db_error_falls_back_gracefully(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        repo.get_latest.side_effect = Exception("DB down")

        svc = ScanService(repo=repo)
        result = svc.get_opportunities()

        assert result["status"] == "ok"
        assert result["source"] == "none"

    def test_db_results_returned_when_available(self) -> None:
        fake_opp = MagicMock()
        repo = MagicMock(spec=ScanRepository)
        repo.get_latest.return_value = [fake_opp]

        svc = ScanService(repo=repo)
        result = svc.get_opportunities()

        assert result["source"] == "database"
        assert result["opportunities"] == [fake_opp]


class TestGetMultiLegOpportunities:
    def test_returns_empty_without_scan(self) -> None:
        repo = MagicMock(spec=ScanRepository)
        svc = ScanService(repo=repo)
        result = svc.get_multi_leg_opportunities()

        assert result["status"] == "ok"
        assert len(result["opportunities"]) == 0


class TestRunScanDeduplication:
    """Tests for Issue #19 — duplicate contract deduplication in run_scan."""

    def _make_contract(self, **overrides):
        """Create a minimal OptionContract-like object."""
        from app.providers.base import OptionContract
        defaults = dict(
            symbol="AAPL",
            strike=150.0,
            expiration="2026-03-20",
            option_type="CALL",
            bid=4.5,
            ask=5.0,
            last_price=4.75,
            volume=1000,
            open_interest=5000,
            implied_volatility=0.30,
        )
        defaults.update(overrides)
        return OptionContract(**defaults)

    def test_run_scan_deduplicates_identical_contracts(self) -> None:
        """Duplicate (symbol, strike, expiration, type) entries are removed."""
        from app.providers.base import MarketDataProvider, Quote

        class DuplicateProvider(MarketDataProvider):
            def get_quote(self, symbol):
                return Quote(symbol=symbol, price=150.0, day_high=155.0,
                             day_low=145.0, volume=1000000, previous_close=149.0)

            def get_options_chain(self, symbol, expiration=None):
                # Return 3 contracts with same (symbol, strike, exp, type)
                return [
                    self._outer._make_contract(),
                    self._outer._make_contract(),
                    self._outer._make_contract(),
                ]

            def is_available(self):
                return True

            def get_expiration_dates(self, symbol):
                return ["2026-03-20"]

        provider = DuplicateProvider()
        provider._outer = self

        repo = MagicMock(spec=ScanRepository)
        repo.save_results.return_value = None

        svc = ScanService(repo=repo, provider=provider)
        result = svc.run_scan(["AAPL"])

        # Should be deduplicated to 1 unique contract
        assert result["resultsCount"] == 1
        saved = repo.save_results.call_args[0][0]
        assert len(saved) == 1

    def test_run_scan_keeps_different_contracts(self) -> None:
        """Contracts with different keys are preserved."""
        from app.providers.base import MarketDataProvider, Quote

        class MultiProvider(MarketDataProvider):
            def get_quote(self, symbol):
                return Quote(symbol=symbol, price=150.0, day_high=155.0,
                             day_low=145.0, volume=1000000, previous_close=149.0)

            def get_options_chain(self, symbol, expiration=None):
                return [
                    self._outer._make_contract(strike=150.0, option_type="CALL"),
                    self._outer._make_contract(strike=155.0, option_type="CALL"),
                    self._outer._make_contract(strike=150.0, option_type="PUT"),
                ]

            def is_available(self):
                return True

            def get_expiration_dates(self, symbol):
                return ["2026-03-20"]

        provider = MultiProvider()
        provider._outer = self

        repo = MagicMock(spec=ScanRepository)
        repo.save_results.return_value = None

        svc = ScanService(repo=repo, provider=provider)
        result = svc.run_scan(["AAPL"])

        # 3 unique contracts should all remain
        assert result["resultsCount"] == 3
        saved = repo.save_results.call_args[0][0]
        assert len(saved) == 3

    def test_run_scan_dedup_keeps_first_occurrence(self) -> None:
        """When duplicates exist, the first occurrence is kept."""
        from app.providers.base import MarketDataProvider, Quote

        class FirstWinsProvider(MarketDataProvider):
            def get_quote(self, symbol):
                return Quote(symbol=symbol, price=150.0, day_high=155.0,
                             day_low=145.0, volume=1000000, previous_close=149.0)

            def get_options_chain(self, symbol, expiration=None):
                # Two identical contracts — first should win
                return [
                    self._outer._make_contract(bid=4.0, ask=5.0),
                    self._outer._make_contract(bid=6.0, ask=7.0),
                ]

            def is_available(self):
                return True

            def get_expiration_dates(self, symbol):
                return ["2026-03-20"]

        provider = FirstWinsProvider()
        provider._outer = self

        repo = MagicMock(spec=ScanRepository)
        repo.save_results.return_value = None

        svc = ScanService(repo=repo, provider=provider)
        result = svc.run_scan(["AAPL"])

        assert result["resultsCount"] == 1
        saved = repo.save_results.call_args[0][0]
        # The first contract had bid=4.0, ask=5.0 → mid=4.5
        assert saved[0]["currentPrice"] == 4.5
