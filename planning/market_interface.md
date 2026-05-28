# Market Data Interface Design

This document defines the unified Python interface for market data in FinAlly. Both the **Massive (Polygon.io) client** and the **built-in simulator** implement this interface. All downstream code — the SSE stream, price cache, API routes — is agnostic to which implementation is active.

---

## Selection Logic

```
MASSIVE_API_KEY set and non-empty  →  MassiveMarketClient  (real market data)
MASSIVE_API_KEY absent or empty    →  SimulatorMarketClient (built-in GBM sim)
```

The selection happens once at application startup in `backend/app/market/factory.py`.

---

## Abstract Interface

**`backend/app/market/base.py`**

```python
from abc import ABC, abstractmethod
from .models import PriceEvent


class MarketDataClient(ABC):
    """
    Abstract base class for market data providers.
    
    Both MassiveMarketClient and SimulatorMarketClient implement this interface.
    The rest of the application only depends on this class — never on a concrete
    implementation.
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """
        Start the background data-fetch loop for the given tickers.
        
        Called once at application startup. The implementation is responsible
        for populating the shared price_cache on a recurring schedule.
        
        Args:
            tickers: Initial list of tickers to track. May be updated later
                     via add_ticker / remove_ticker.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background loop cleanly (called on app shutdown)."""
        ...

    @abstractmethod
    def get_price(self, ticker: str) -> PriceEvent | None:
        """
        Return the latest cached price event for a single ticker.
        
        Returns None if the ticker has no data yet (e.g., first poll not
        completed). Callers should handle None gracefully.
        """
        ...

    @abstractmethod
    def get_all_prices(self) -> dict[str, PriceEvent]:
        """
        Return latest cached price events for ALL tracked tickers.
        
        Returns a dict keyed by ticker symbol. Empty dict before first poll.
        """
        ...

    @abstractmethod
    def add_ticker(self, ticker: str) -> None:
        """
        Add a ticker to the tracked set.
        
        Takes effect on the next poll cycle. For the simulator, also
        initializes GBM state for the new ticker.
        """
        ...

    @abstractmethod
    def remove_ticker(self, ticker: str) -> None:
        """
        Remove a ticker from the tracked set.
        
        Removes the ticker from the price cache immediately. No-op if the
        ticker is not currently tracked.
        """
        ...

    @property
    @abstractmethod
    def tickers(self) -> list[str]:
        """Current list of tracked ticker symbols."""
        ...
```

---

## Price Event Model

**`backend/app/market/models.py`**

```python
from dataclasses import dataclass, field
import time


@dataclass
class PriceEvent:
    """
    A single price update for one ticker.
    
    This is the canonical data shape used throughout the application:
    - Written to the in-memory price cache by both market data implementations
    - Read by the SSE stream endpoint and serialized to JSON
    - Sent to connected browser clients as SSE events
    """
    ticker: str
    price: float
    previous_price: float
    change: float           # absolute dollar change (vs previous close or prev tick)
    change_percent: float   # percentage change (for watchlist display)
    direction: str          # "up" | "down" | "flat"
    timestamp: float        # unix epoch seconds (float for sub-second precision)

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


# Seed prices used as starting points for both implementations.
# The simulator initializes GBM state from these.
# The Massive client uses them as fallback if no data has arrived yet.
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
```

---

## Factory — Selects the Active Implementation

**`backend/app/market/factory.py`**

```python
import os
from .base import MarketDataClient


def create_market_client() -> MarketDataClient:
    """
    Return the appropriate market data client based on environment config.
    
    - MASSIVE_API_KEY set → MassiveMarketClient (real Polygon.io data)
    - MASSIVE_API_KEY absent → SimulatorMarketClient (GBM simulation)
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    
    if api_key:
        from .massive_client import MassiveMarketClient
        print("[market] Using Massive (Polygon.io) real market data")
        return MassiveMarketClient(api_key=api_key)
    else:
        from .simulator import SimulatorMarketClient
        print("[market] Using built-in market simulator (no MASSIVE_API_KEY set)")
        return SimulatorMarketClient()
```

---

## Massive Implementation Sketch

**`backend/app/market/massive_client.py`**

```python
import asyncio
import os
import time
from massive import RESTClient
from massive.rest.models import TickerSnapshot

from .base import MarketDataClient
from .models import PriceEvent, SEED_PRICES

# Free tier: 5 req/min. One snapshot call per interval is safe at 15s.
# Advanced tier can use 2–5s intervals.
POLL_INTERVAL = float(os.getenv("MASSIVE_POLL_INTERVAL", "15"))


class MassiveMarketClient(MarketDataClient):
    """
    Market data client backed by Massive (Polygon.io) REST snapshot API.
    
    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers on a configurable interval and populates _price_cache.
    """

    def __init__(self, api_key: str):
        self._client = RESTClient(api_key=api_key)
        self._price_cache: dict[str, PriceEvent] = {}
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None

    # ── MarketDataClient interface ──────────────────────────────────────────

    async def start(self, tickers: list[str]) -> None:
        self._tickers = set(tickers)
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_price(self, ticker: str) -> PriceEvent | None:
        return self._price_cache.get(ticker)

    def get_all_prices(self) -> dict[str, PriceEvent]:
        return dict(self._price_cache)

    def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker.upper())

    def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker.upper())
        self._price_cache.pop(ticker.upper(), None)

    @property
    def tickers(self) -> list[str]:
        return sorted(self._tickers)

    # ── Internal ────────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while True:
            await self._fetch_and_update()
            await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_and_update(self) -> None:
        if not self._tickers:
            return
        
        ticker_list = list(self._tickers)
        now = time.time()
        
        try:
            # Run synchronous Massive client in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            snapshots = await loop.run_in_executor(
                None,
                lambda: list(self._client.get_snapshot_all("stocks", tickers=ticker_list))
            )
            
            for snap in snapshots:
                if not isinstance(snap, TickerSnapshot):
                    continue
                event = self._snap_to_event(snap, now)
                if event:
                    self._price_cache[snap.ticker] = event

        except Exception as e:
            print(f"[massive] Poll error: {e}")

    def _snap_to_event(self, snap: TickerSnapshot, now: float) -> PriceEvent | None:
        # Best current price: lastTrade → day close → prevDay close → seed
        price = None
        if snap.last_trade and snap.last_trade.price:
            price = snap.last_trade.price
        elif snap.day and snap.day.close:
            price = snap.day.close
        elif snap.prev_day and snap.prev_day.close:
            price = snap.prev_day.close
        else:
            price = SEED_PRICES.get(snap.ticker)
        
        if price is None:
            return None

        prev = self._price_cache.get(snap.ticker)
        prev_price = prev.price if prev else price

        change = snap.todays_change or 0.0
        change_pct = snap.todays_change_perc or 0.0
        direction = "up" if price > prev_price else ("down" if price < prev_price else "flat")

        return PriceEvent(
            ticker=snap.ticker,
            price=price,
            previous_price=prev_price,
            change=change,
            change_percent=change_pct,
            direction=direction,
            timestamp=now,
        )
```

---

## Consuming the Interface (SSE Stream)

The SSE endpoint and any other consumer only interacts with `MarketDataClient` — it never imports `MassiveMarketClient` or `SimulatorMarketClient` directly.

**`backend/app/market/stream.py`** (sketch):

```python
import asyncio
import json
from fastapi import Request
from fastapi.responses import StreamingResponse
from .base import MarketDataClient

SSE_PUSH_INTERVAL = 0.5  # Push to clients every 500ms


async def price_stream(request: Request, client: MarketDataClient):
    """SSE endpoint — streams price cache to a single connected client."""
    
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            prices = client.get_all_prices()
            if prices:
                payload = {ticker: event.to_dict() for ticker, event in prices.items()}
                yield f"data: {json.dumps(payload)}\n\n"
            
            await asyncio.sleep(SSE_PUSH_INTERVAL)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
```

---

## Application Wiring (FastAPI lifespan)

**`backend/app/main.py`** (sketch):

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .market.factory import create_market_client
from .market.models import DEFAULT_TICKERS
from .db.database import get_watchlist_tickers  # loads tickers from SQLite

market_client = create_market_client()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load watchlist from DB, start data client
    tickers = await get_watchlist_tickers() or DEFAULT_TICKERS
    await market_client.start(tickers)
    yield
    # Shutdown: stop background tasks
    await market_client.stop()

app = FastAPI(lifespan=lifespan)

# Inject market_client into routes via dependency injection or app state
app.state.market_client = market_client
```

---

## Module Layout

```
backend/app/market/
├── __init__.py
├── base.py            # Abstract MarketDataClient interface
├── models.py          # PriceEvent dataclass, SEED_PRICES, DEFAULT_TICKERS
├── factory.py         # create_market_client() — selects implementation
├── massive_client.py  # MassiveMarketClient (Polygon.io REST polling)
├── simulator.py       # SimulatorMarketClient (GBM simulation)
└── stream.py          # SSE push logic (reads from client.get_all_prices())
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Abstract base class, not duck typing | Explicit contract makes agent handoffs clear; IDEs surface the interface |
| In-memory price cache (dict) | SSE can push to N clients without N API calls; cache is the single source of truth |
| Async start/stop, sync get_price | Background loop is async; cache reads are synchronous (no await needed in hot SSE path) |
| run_in_executor for Massive client | Massive's `RESTClient` is synchronous; wrap in executor to avoid blocking the event loop |
| Factory pattern | One call site determines the implementation; no conditional imports elsewhere |
| add_ticker / remove_ticker | Watchlist changes at runtime (via chat or UI) update the tracked set without restart |
