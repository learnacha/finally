from abc import ABC, abstractmethod
from .models import PriceEvent


class MarketDataClient(ABC):
    """
    Contract for a market data provider.

    Implementations own a background async task that maintains an in-memory
    price cache. Reads are synchronous (no `await`) so the SSE hot path is
    cheap. Mutations to the tracked ticker set are synchronous and take
    effect on the next poll/tick.
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Start the background fetch/tick loop for `tickers`."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the background loop cleanly. Idempotent."""

    @abstractmethod
    def get_price(self, ticker: str) -> PriceEvent | None:
        """Latest cached price for one ticker. `None` if not yet populated."""

    @abstractmethod
    def get_all_prices(self) -> dict[str, PriceEvent]:
        """Snapshot copy of the full price cache."""

    @abstractmethod
    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the tracked set. No-op if already tracked."""

    @abstractmethod
    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker and drop it from the cache. No-op if absent."""

    @property
    @abstractmethod
    def tickers(self) -> list[str]:
        """Sorted list of currently tracked tickers."""
