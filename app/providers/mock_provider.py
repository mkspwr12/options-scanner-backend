"""Mock market data provider for testing and development.

Returns deterministic data so tests are reproducible and no network
calls are made in CI.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .base import MarketDataProvider, OptionContract, Quote

# Pre-built quotes for common symbols
_MOCK_QUOTES: dict[str, Quote] = {
    "META": Quote(
        symbol="META", price=689.30, day_high=695.00,
        day_low=685.00, volume=12_500_000, previous_close=687.50,
    ),
    "SPY": Quote(
        symbol="SPY", price=681.70, day_high=684.00,
        day_low=679.50, volume=45_000_000, previous_close=680.00,
    ),
    "AAPL": Quote(
        symbol="AAPL", price=232.50, day_high=234.00,
        day_low=231.00, volume=30_000_000, previous_close=231.80,
    ),
    "NVDA": Quote(
        symbol="NVDA", price=875.20, day_high=882.00,
        day_low=870.00, volume=20_000_000, previous_close=873.00,
    ),
    "TSLA": Quote(
        symbol="TSLA", price=245.60, day_high=248.00,
        day_low=243.00, volume=35_000_000, previous_close=244.90,
    ),
    "MSFT": Quote(
        symbol="MSFT", price=420.15, day_high=422.50,
        day_low=418.00, volume=18_000_000, previous_close=419.30,
    ),
    "GOOGL": Quote(
        symbol="GOOGL", price=178.90, day_high=180.20,
        day_low=177.50, volume=22_000_000, previous_close=178.30,
    ),
    "AMZN": Quote(
        symbol="AMZN", price=225.40, day_high=227.00,
        day_low=224.00, volume=16_000_000, previous_close=224.80,
    ),
}


def _default_quote(symbol: str) -> Quote:
    return Quote(
        symbol=symbol, price=100.00, day_high=102.00,
        day_low=98.00, volume=5_000_000, previous_close=99.50,
    )


class MockProvider:
    """Deterministic mock provider implementing ``MarketDataProvider``."""

    def get_options_chain(
        self, symbol: str, expiration: str | None = None
    ) -> list[OptionContract]:
        quote = _MOCK_QUOTES.get(symbol.upper(), _default_quote(symbol.upper()))
        price = quote.price

        if expiration is None:
            # Generate nearest monthly expiration (~30 days out)
            now = datetime.now(timezone.utc)
            expiration = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        contracts: list[OptionContract] = []
        # Generate 5 strikes around the money for both CALL and PUT
        for pct in (-0.05, -0.02, 0.0, 0.02, 0.05):
            strike = round(price * (1 + pct), 2)
            for opt_type in ("CALL", "PUT"):
                moneyness = price / strike
                if opt_type == "CALL":
                    mid = max(price - strike, 0) + price * 0.02
                else:
                    mid = max(strike - price, 0) + price * 0.02

                contracts.append(
                    OptionContract(
                        symbol=symbol.upper(),
                        strike=strike,
                        expiration=expiration,
                        option_type=opt_type,
                        bid=round(mid * 0.95, 2),
                        ask=round(mid * 1.05, 2),
                        last_price=round(mid, 2),
                        volume=int(1000 * (1 + abs(pct) * 10)),
                        open_interest=int(5000 * (1 + abs(pct) * 5)),
                        implied_volatility=round(0.30 + abs(pct), 4),
                    )
                )
        return contracts

    def get_quote(self, symbol: str) -> Quote:
        return _MOCK_QUOTES.get(symbol.upper(), _default_quote(symbol.upper()))

    def is_available(self) -> bool:
        return True

    def get_expiration_dates(self, symbol: str) -> list[str]:
        """Return mock expiration dates (~30, 60, 90 days out)."""
        now = datetime.now(timezone.utc)
        return [
            (now + timedelta(days=d)).strftime("%Y-%m-%d")
            for d in (30, 60, 90)
        ]
