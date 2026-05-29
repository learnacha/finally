from dataclasses import dataclass
from typing import Literal

Direction = Literal["up", "down", "flat"]


@dataclass(slots=True)
class PriceEvent:
    """A single price update for one ticker."""
    ticker: str
    price: float
    previous_price: float
    change: float          # absolute $ change vs session-open (sim) / vs prevClose (Massive)
    change_percent: float  # percentage form of `change`
    direction: Direction   # "up" | "down" | "flat" — tick-to-tick movement
    timestamp: float       # unix epoch seconds (float for sub-second precision)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": round(self.price, 4),
            "previous_price": round(self.previous_price, 4),
            "change": round(self.change, 4),
            "change_percent": round(self.change_percent, 4),
            "direction": self.direction,
            "timestamp": self.timestamp,
        }


# Seed prices used by both implementations.
# Simulator: starting price for the GBM walk.
# Massive: fallback if a snapshot arrives without trade/day/prevDay data.
SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  415.00,
    "AMZN":  185.00,
    "TSLA":  175.00,
    "NVDA":  875.00,
    "META":  490.00,
    "JPM":   195.00,
    "V":     270.00,
    "NFLX":  630.00,
}

DEFAULT_TICKERS: list[str] = list(SEED_PRICES.keys())
