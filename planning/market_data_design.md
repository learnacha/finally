# Market Data Backend — Detailed Design

This document is the implementation blueprint for the FinAlly market data
backend. It unifies three concerns:

1. A single abstract interface (`MarketDataClient`) that all consumers depend on
2. A built-in **GBM simulator** used when no API key is configured
3. A **Massive (Polygon.io)** REST polling client used when `MASSIVE_API_KEY` is set

Everything downstream — the SSE stream, the watchlist routes, the portfolio
valuation logic, the LLM context loader — touches only the abstract interface
and the `PriceEvent` model. Concrete implementations are interchangeable.

---

## 1. Module Layout

```
backend/app/market/
├── __init__.py            # Re-exports MarketDataClient, PriceEvent, create_market_client
├── base.py                # Abstract MarketDataClient interface
├── models.py              # PriceEvent dataclass, SEED_PRICES, DEFAULT_TICKERS
├── factory.py             # create_market_client() — selects implementation
├── simulator.py           # SimulatorMarketClient (GBM)
├── massive_client.py      # MassiveMarketClient (Polygon.io REST polling)
└── stream.py              # SSE endpoint logic (reads from MarketDataClient)
```

The package is the only module in the backend that knows about Massive or
random-walk math. Everywhere else, code imports from `app.market` and gets a
configured client through FastAPI app state or a dependency.

---

## 2. Shared Data Model — `PriceEvent`

`PriceEvent` is the canonical shape used by:

- The in-memory price cache inside each `MarketDataClient`
- The SSE event JSON sent to browsers
- The portfolio valuation code (computes current value from `price`)

**`backend/app/market/models.py`**

```python
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
```

### Semantic notes

| Field | Simulator meaning | Massive meaning |
|---|---|---|
| `price` | Latest GBM price | `lastTrade.p` → `day.c` → `prevDay.c` → seed |
| `previous_price` | Price at previous tick (500 ms ago) | Price stored in cache from previous poll (15 s ago) |
| `change` | `price - session_open_price` | `snap.todays_change` (vs previous market close) |
| `change_percent` | `change / session_open_price × 100` | `snap.todays_change_perc` (already in percent) |
| `direction` | `up`/`down`/`flat` vs previous tick | `up`/`down`/`flat` vs cached previous price |
| `timestamp` | `time.time()` at tick | `time.time()` at poll |

The semantics differ in unavoidable ways (a 15s poll cannot give a 500ms tick
direction), but both produce the same JSON shape — the frontend doesn't care
which side it's wired to.

---

## 3. Abstract Interface — `MarketDataClient`

**`backend/app/market/base.py`**

```python
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
```

### Why these specific methods

- **`get_all_prices` is sync** — the SSE endpoint loops at ~500 ms and must not
  yield to network I/O on every iteration. Returning `dict(self._cache)` is
  O(N) over ~10 tickers — fast and lock-free.
- **`add_ticker` / `remove_ticker` are sync** — invoked from FastAPI HTTP
  handlers (already running on the event loop). Returning immediately keeps
  HTTP responses snappy; the next tick picks up the change.
- **`start` / `stop` are async** — they spawn / cancel `asyncio.Task` objects.

---

## 4. Factory — Implementation Selection

**`backend/app/market/factory.py`**

```python
import logging
import os
from .base import MarketDataClient

log = logging.getLogger(__name__)


def create_market_client() -> MarketDataClient:
    """
    Select the market data implementation based on environment.

    MASSIVE_API_KEY set & non-empty → MassiveMarketClient (real data)
    MASSIVE_API_KEY absent / empty  → SimulatorMarketClient (GBM sim)
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()

    if api_key:
        from .massive_client import MassiveMarketClient
        log.info("market: using Massive (Polygon.io) real market data")
        return MassiveMarketClient(api_key=api_key)

    from .simulator import SimulatorMarketClient
    log.info("market: using built-in GBM simulator (no MASSIVE_API_KEY)")
    return SimulatorMarketClient()
```

The factory is called **once**, from the FastAPI lifespan handler. No other
module imports a concrete client. Tests instantiate clients directly.

---

## 5. Simulator — `SimulatorMarketClient`

The simulator must feel real on screen: subtle drift between dramatic flashes,
sector-correlated moves so heatmaps look meaningful, and the occasional event
shock so users see flashes without staring.

### 5.1 GBM math

Geometric Brownian Motion at a discrete tick:

```
S(t+dt) = S(t) × exp((μ - σ²/2) × dt + σ × ε × √dt)
```

With a 500ms tick and 30% annual volatility, per-tick standard deviation is
roughly 0.09 % — a $190 stock moves ±$0.17 per tick. Subtle but visible.

### 5.2 Sector correlation

Before stepping any ticker, a single Gaussian sector shock is drawn per sector.
Each ticker mixes its sector shock with its idiosyncratic shock:

```
total_shock = ρ × sector_shock + √(1 - ρ²) × individual_shock
```

`ρ = 0.5` is enough to make all tech names visibly move together without
collapsing to a single line.

### 5.3 Event shocks

With probability ~0.0005 per ticker per tick (≈ once per 30 min per ticker), a
± 2–5 % jump is added on top of the GBM step. Just often enough to keep the
heatmap interesting.

### 5.4 Full implementation

**`backend/app/market/simulator.py`**

```python
import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass

from .base import MarketDataClient
from .models import PriceEvent

log = logging.getLogger(__name__)

# ── Tunables ───────────────────────────────────────────────────────────────
TICK_INTERVAL = 0.5
TRADING_DAYS_PER_YEAR = 252
SECONDS_PER_TRADING_DAY = 6.5 * 3600
TICKS_PER_YEAR = TRADING_DAYS_PER_YEAR * SECONDS_PER_TRADING_DAY / TICK_INTERVAL
DT = 1.0 / TICKS_PER_YEAR

SECTOR_VOLATILITY = 0.15
SECTOR_CORRELATION = 0.5

EVENT_PROBABILITY = 0.0005
EVENT_MAGNITUDE_MIN = 0.02
EVENT_MAGNITUDE_MAX = 0.05

PRICE_FLOOR = 0.01


@dataclass(slots=True, frozen=True)
class TickerConfig:
    seed_price: float
    drift: float
    volatility: float
    sector: str


TICKER_CONFIGS: dict[str, TickerConfig] = {
    "AAPL":  TickerConfig(190.00, 0.08, 0.28, "tech"),
    "GOOGL": TickerConfig(175.00, 0.07, 0.30, "tech"),
    "MSFT":  TickerConfig(415.00, 0.10, 0.25, "tech"),
    "AMZN":  TickerConfig(185.00, 0.09, 0.32, "tech"),
    "TSLA":  TickerConfig(175.00, 0.05, 0.65, "ev"),
    "NVDA":  TickerConfig(875.00, 0.15, 0.55, "tech"),
    "META":  TickerConfig(490.00, 0.08, 0.35, "tech"),
    "JPM":   TickerConfig(195.00, 0.06, 0.22, "finance"),
    "V":     TickerConfig(270.00, 0.07, 0.20, "finance"),
    "NFLX":  TickerConfig(630.00, 0.06, 0.40, "media"),
}

DEFAULT_CONFIG = TickerConfig(seed_price=100.00, drift=0.05, volatility=0.30, sector="other")


class SimulatorMarketClient(MarketDataClient):
    """GBM simulator with sector correlation and event shocks."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._prices: dict[str, float] = {}        # raw current price
        self._open_prices: dict[str, float] = {}   # session-open snapshot
        self._cache: dict[str, PriceEvent] = {}
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None

    # ── MarketDataClient interface ─────────────────────────────────────────
    async def start(self, tickers: list[str]) -> None:
        for t in tickers:
            self._init_ticker(t)
        self._emit_initial_events()
        self._task = asyncio.create_task(self._tick_loop(), name="sim-tick")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def get_price(self, ticker: str) -> PriceEvent | None:
        return self._cache.get(ticker.upper())

    def get_all_prices(self) -> dict[str, PriceEvent]:
        return dict(self._cache)

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        if ticker not in self._tickers:
            self._init_ticker(ticker)
            self._emit_event_for(ticker, prev_price=self._prices[ticker], now=time.time())

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._tickers.discard(ticker)
        self._prices.pop(ticker, None)
        self._open_prices.pop(ticker, None)
        self._cache.pop(ticker, None)

    @property
    def tickers(self) -> list[str]:
        return sorted(self._tickers)

    # ── Internal ───────────────────────────────────────────────────────────
    def _init_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        cfg = TICKER_CONFIGS.get(ticker, DEFAULT_CONFIG)
        self._prices[ticker] = cfg.seed_price
        self._open_prices[ticker] = cfg.seed_price
        self._tickers.add(ticker)

    def _emit_initial_events(self) -> None:
        now = time.time()
        for ticker in self._tickers:
            self._emit_event_for(ticker, prev_price=self._prices[ticker], now=now)

    def _emit_event_for(self, ticker: str, prev_price: float, now: float) -> None:
        price = self._prices[ticker]
        open_price = self._open_prices[ticker]
        change = price - open_price
        change_pct = (change / open_price * 100) if open_price > 0 else 0.0
        direction: str = (
            "up" if price > prev_price
            else "down" if price < prev_price
            else "flat"
        )
        self._cache[ticker] = PriceEvent(
            ticker=ticker,
            price=price,
            previous_price=prev_price,
            change=change,
            change_percent=change_pct,
            direction=direction,
            timestamp=now,
        )

    async def _tick_loop(self) -> None:
        try:
            while True:
                self._step()
                await asyncio.sleep(TICK_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("simulator tick loop crashed")
            raise

    def _step(self) -> None:
        now = time.time()
        tickers = list(self._tickers)
        if not tickers:
            return

        # 1. Sector shocks (one draw per sector this tick)
        sectors = {TICKER_CONFIGS.get(t, DEFAULT_CONFIG).sector for t in tickers}
        sqrt_dt = math.sqrt(DT)
        sector_shocks = {
            sector: self._rng.gauss(0.0, 1.0) * SECTOR_VOLATILITY * sqrt_dt
            for sector in sectors
        }

        # 2. Step each ticker
        for ticker in tickers:
            cfg = TICKER_CONFIGS.get(ticker, DEFAULT_CONFIG)
            prev_price = self._prices[ticker]

            z_sector = sector_shocks[cfg.sector]
            z_idio = self._rng.gauss(0.0, 1.0) * cfg.volatility * sqrt_dt
            total_shock = (
                SECTOR_CORRELATION * z_sector
                + math.sqrt(1.0 - SECTOR_CORRELATION ** 2) * z_idio
            )

            drift_term = (cfg.drift - 0.5 * cfg.volatility ** 2) * DT
            new_price = prev_price * math.exp(drift_term + total_shock)

            # 3. Occasional event shock
            if self._rng.random() < EVENT_PROBABILITY:
                magnitude = self._rng.uniform(EVENT_MAGNITUDE_MIN, EVENT_MAGNITUDE_MAX)
                sign = self._rng.choice((1.0, -1.0))
                new_price *= 1.0 + sign * magnitude

            new_price = max(new_price, PRICE_FLOOR)
            self._prices[ticker] = new_price
            self._emit_event_for(ticker, prev_price=prev_price, now=now)
```

### 5.5 Seeded determinism

`SimulatorMarketClient(seed=42)` uses a private `random.Random` instance, so
parallel tests can each have their own deterministic stream without trampling
the global RNG.

---

## 6. Massive Client — `MassiveMarketClient`

### 6.1 Why polling, not WebSocket

The Massive Python client supports both, but the polling path is dramatically
simpler:

- Works on every plan tier (free → business)
- No reconnection state machine, no auth handshake
- A single 15 s request covers the whole watchlist
- Fits trivially inside the existing async pattern

### 6.2 Snapshot → `PriceEvent`

```
lastTrade.p exists?    → price = lastTrade.p
else day.c exists?     → price = day.c
else prevDay.c exists? → price = prevDay.c
else                   → price = SEED_PRICES[ticker]  (last resort)
```

`change` and `change_percent` come straight from `snap.todays_change` and
`snap.todays_change_perc` — these are session-relative just like the
simulator's, so the frontend stays uniform.

### 6.3 Concurrency model

The `massive.RESTClient` is **synchronous**. To avoid blocking the asyncio
loop (and freezing the SSE push for every connected browser), every API call
goes through `loop.run_in_executor(None, ...)`.

### 6.4 Rate-limit awareness

| Tier | Limit | Recommended interval |
|---|---|---|
| Free / Starter | 5 req/min | 15 s (default) |
| Advanced / Business | unlimited | 2–5 s |

A single `get_snapshot_all` call covers the entire watchlist, so one request
per interval is the steady state regardless of watchlist size.

### 6.5 Full implementation

**`backend/app/market/massive_client.py`**

```python
import asyncio
import logging
import os
import time

from massive import RESTClient
from massive.rest.models import TickerSnapshot

from .base import MarketDataClient
from .models import PriceEvent, SEED_PRICES

log = logging.getLogger(__name__)

POLL_INTERVAL = float(os.getenv("MASSIVE_POLL_INTERVAL", "15"))
BACKOFF_INITIAL = 5.0
BACKOFF_MAX = 120.0


class MassiveMarketClient(MarketDataClient):
    """REST polling client for Massive (Polygon.io) snapshots."""

    def __init__(self, api_key: str):
        self._client = RESTClient(api_key=api_key)
        self._cache: dict[str, PriceEvent] = {}
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None

    # ── MarketDataClient interface ─────────────────────────────────────────
    async def start(self, tickers: list[str]) -> None:
        self._tickers = {t.upper() for t in tickers}
        self._seed_cache()
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poll")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def get_price(self, ticker: str) -> PriceEvent | None:
        return self._cache.get(ticker.upper())

    def get_all_prices(self) -> dict[str, PriceEvent]:
        return dict(self._cache)

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        if ticker in self._tickers:
            return
        self._tickers.add(ticker)
        # Seed an entry so the UI has *something* until the next poll
        seed = SEED_PRICES.get(ticker)
        if seed is not None:
            now = time.time()
            self._cache[ticker] = PriceEvent(
                ticker=ticker, price=seed, previous_price=seed,
                change=0.0, change_percent=0.0, direction="flat", timestamp=now,
            )

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._tickers.discard(ticker)
        self._cache.pop(ticker, None)

    @property
    def tickers(self) -> list[str]:
        return sorted(self._tickers)

    # ── Internal ───────────────────────────────────────────────────────────
    def _seed_cache(self) -> None:
        """Pre-populate the cache with seed prices for instant UI render."""
        now = time.time()
        for ticker in self._tickers:
            seed = SEED_PRICES.get(ticker)
            if seed is None:
                continue
            self._cache[ticker] = PriceEvent(
                ticker=ticker, price=seed, previous_price=seed,
                change=0.0, change_percent=0.0, direction="flat", timestamp=now,
            )

    async def _poll_loop(self) -> None:
        backoff = BACKOFF_INITIAL
        try:
            while True:
                ok = await self._fetch_and_update()
                if ok:
                    backoff = BACKOFF_INITIAL
                    await asyncio.sleep(POLL_INTERVAL)
                else:
                    log.warning("massive: poll failed, backing off %.1fs", backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, BACKOFF_MAX)
        except asyncio.CancelledError:
            raise

    async def _fetch_and_update(self) -> bool:
        if not self._tickers:
            return True

        ticker_list = sorted(self._tickers)
        loop = asyncio.get_running_loop()
        try:
            snapshots = await loop.run_in_executor(
                None,
                lambda: list(self._client.get_snapshot_all("stocks", tickers=ticker_list)),
            )
        except Exception as exc:
            log.warning("massive: snapshot fetch error: %s", exc)
            return False

        now = time.time()
        for snap in snapshots:
            if not isinstance(snap, TickerSnapshot):
                continue
            event = self._snap_to_event(snap, now)
            if event is not None:
                self._cache[snap.ticker.upper()] = event
        return True

    def _snap_to_event(self, snap: TickerSnapshot, now: float) -> PriceEvent | None:
        price: float | None = None
        if snap.last_trade and snap.last_trade.price:
            price = snap.last_trade.price
        elif snap.day and snap.day.close:
            price = snap.day.close
        elif snap.prev_day and snap.prev_day.close:
            price = snap.prev_day.close
        else:
            price = SEED_PRICES.get(snap.ticker.upper())

        if price is None:
            return None

        prev = self._cache.get(snap.ticker.upper())
        prev_price = prev.price if prev else price

        change = snap.todays_change or 0.0
        change_pct = snap.todays_change_perc or 0.0
        direction = (
            "up" if price > prev_price
            else "down" if price < prev_price
            else "flat"
        )

        return PriceEvent(
            ticker=snap.ticker.upper(),
            price=price,
            previous_price=prev_price,
            change=change,
            change_percent=change_pct,
            direction=direction,
            timestamp=now,
        )
```

### 6.6 Error handling

| Failure | Behavior |
|---|---|
| Transient network error | Logged, exponential backoff (5 s → 120 s), keep prior cache |
| `AuthorizationError` | Logged at WARN, backoff continues — admin must restart with fixed key |
| Empty / no-results | Cache retains prior values; next poll retries |
| `RESTClient` raises unexpected | Same as transient — logged and retried |

We deliberately don't crash the app on bad credentials: the simulator can keep
the SSE stream alive on a separate startup by restart, and meanwhile the UI
still has its seed prices.

---

## 7. SSE Streaming — `stream.py`

The SSE endpoint sits *on top of* `MarketDataClient`. It doesn't care which
implementation is active.

**`backend/app/market/stream.py`**

```python
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .base import MarketDataClient

router = APIRouter(prefix="/api/stream", tags=["stream"])

SSE_PUSH_INTERVAL = 0.5     # seconds between pushes to the client
SSE_KEEPALIVE_AFTER = 15.0  # send a comment every 15s of silence


@router.get("/prices")
async def price_stream(request: Request):
    client: MarketDataClient = request.app.state.market_client
    return StreamingResponse(
        _event_generator(request, client),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


async def _event_generator(request: Request, client: MarketDataClient):
    last_sent = 0.0
    # Initial flush so the client sees something immediately
    initial = client.get_all_prices()
    if initial:
        payload = {t: e.to_dict() for t, e in initial.items()}
        yield f"data: {json.dumps(payload)}\n\n"
        last_sent = asyncio.get_event_loop().time()

    while True:
        if await request.is_disconnected():
            return

        prices = client.get_all_prices()
        now = asyncio.get_event_loop().time()
        if prices:
            payload = {t: e.to_dict() for t, e in prices.items()}
            yield f"data: {json.dumps(payload)}\n\n"
            last_sent = now
        elif now - last_sent > SSE_KEEPALIVE_AFTER:
            yield ": keepalive\n\n"
            last_sent = now

        await asyncio.sleep(SSE_PUSH_INTERVAL)
```

### 7.1 Example SSE frame

```
data: {"AAPL":{"ticker":"AAPL","price":192.34,"previous_price":191.80,"change":0.54,"change_percent":0.2815,"direction":"up","timestamp":1748260800.123},"GOOGL":{...}}

```

The frontend's `EventSource` parses each frame's JSON and dispatches per-ticker
updates to the watchlist grid, sparkline buffers, and the heatmap.

---

## 8. FastAPI Wiring

**`backend/app/main.py` (relevant excerpt)**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .market.factory import create_market_client
from .market.models import DEFAULT_TICKERS
from .market.stream import router as stream_router
from .db.database import init_db, get_watchlist_tickers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # lazy schema + seed
    tickers = await get_watchlist_tickers() or DEFAULT_TICKERS

    client = create_market_client()
    await client.start(tickers)
    app.state.market_client = client

    try:
        yield
    finally:
        await client.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(stream_router)
```

### 8.1 Watchlist add/remove integration

The watchlist HTTP routes call into the active client so polling/simulation
stays in sync with the DB:

```python
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.post("")
async def add_watchlist_entry(payload: AddTickerRequest, request: Request):
    ticker = payload.ticker.upper()
    await db_add_watchlist(ticker)
    request.app.state.market_client.add_ticker(ticker)
    return {"ticker": ticker, "status": "added"}


@router.delete("/{ticker}")
async def remove_watchlist_entry(ticker: str, request: Request):
    ticker = ticker.upper()
    await db_remove_watchlist(ticker)
    request.app.state.market_client.remove_ticker(ticker)
    return {"ticker": ticker, "status": "removed"}
```

### 8.2 Portfolio valuation integration

Portfolio routes use the cache for current prices — the same source the
frontend sees, so the numbers always agree:

```python
def portfolio_value(positions, cash: float, client: MarketDataClient) -> float:
    total = cash
    for pos in positions:
        event = client.get_price(pos.ticker)
        if event is not None:
            total += pos.quantity * event.price
    return total
```

---

## 9. Configuration Reference

| Env var | Default | Purpose |
|---|---|---|
| `MASSIVE_API_KEY` | _(empty)_ | Selects Massive vs simulator |
| `MASSIVE_POLL_INTERVAL` | `15` (sec) | Massive polling cadence |
| `OPENROUTER_API_KEY` | _(required for live chat)_ | LLM, unrelated to market data |
| `LLM_MOCK` | `false` | LLM mock, unrelated to market data |

All values are read at process start. Restarting the container is required to
switch between simulator and Massive — that's by design (the choice is a
deployment decision, not a per-request one).

---

## 10. Testing Strategy

### 10.1 Shared interface contract tests

A single `pytest` parametrized fixture exercises both clients against the same
behavioural expectations:

```python
import pytest
from app.market.simulator import SimulatorMarketClient
from app.market.base import MarketDataClient


@pytest.fixture(params=["simulator"])  # add "massive_mock" when stubbed
async def client(request) -> MarketDataClient:
    if request.param == "simulator":
        c = SimulatorMarketClient(seed=42)
    else:
        raise ValueError(request.param)
    await c.start(["AAPL", "GOOGL", "MSFT"])
    yield c
    await c.stop()


@pytest.mark.asyncio
async def test_interface_returns_events_for_all_tickers(client):
    await asyncio.sleep(1.0)
    prices = client.get_all_prices()
    assert {"AAPL", "GOOGL", "MSFT"} <= set(prices)
    for evt in prices.values():
        assert evt.price > 0
        assert evt.direction in ("up", "down", "flat")


@pytest.mark.asyncio
async def test_add_ticker_appears(client):
    client.add_ticker("NVDA")
    await asyncio.sleep(1.0)
    assert "NVDA" in client.get_all_prices()


@pytest.mark.asyncio
async def test_remove_ticker_disappears_immediately(client):
    client.remove_ticker("AAPL")
    assert "AAPL" not in client.get_all_prices()
```

### 10.2 Simulator-specific tests

| Test | Assertion |
|---|---|
| `test_seed_determinism` | Two `SimulatorMarketClient(seed=7)` instances produce identical event sequences after N ticks |
| `test_no_negative_prices` | All prices > 0 after 5000 ticks |
| `test_event_shock_bounded` | No single tick changes price by more than ~10% |
| `test_sector_correlation` | Pearson correlation of AAPL/MSFT log-returns > 0.3 over 2000 ticks |
| `test_change_percent_session_relative` | `change_percent ≈ (price − open_price)/open_price × 100` |

### 10.3 Massive client tests

The Massive REST client is mocked via `unittest.mock` — no real API calls in
unit tests.

```python
from unittest.mock import patch, MagicMock
from massive.rest.models import TickerSnapshot

def _mock_snap(ticker, price, change=0.5, change_pct=0.25):
    s = MagicMock(spec=TickerSnapshot)
    s.ticker = ticker
    s.last_trade.price = price
    s.day.close = price
    s.prev_day.close = price - change
    s.todays_change = change
    s.todays_change_perc = change_pct
    return s


@pytest.mark.asyncio
async def test_massive_populates_cache_after_poll():
    from app.market.massive_client import MassiveMarketClient

    client = MassiveMarketClient(api_key="test")
    fake_snaps = [_mock_snap("AAPL", 192.34), _mock_snap("GOOGL", 175.12)]
    with patch.object(client._client, "get_snapshot_all", return_value=fake_snaps):
        await client.start(["AAPL", "GOOGL"])
        await asyncio.sleep(0.1)  # let one fetch happen
        prices = client.get_all_prices()
        assert prices["AAPL"].price == 192.34
        assert prices["AAPL"].change_percent == 0.25
    await client.stop()
```

### 10.4 E2E (Playwright)

E2E always runs against the simulator (`MASSIVE_API_KEY` unset) — fast, free,
deterministic enough for "prices are flashing" assertions.

---

## 11. Key Design Decisions Recap

| Decision | Rationale |
|---|---|
| Abstract base class over duck typing | Explicit, IDE-discoverable contract for cross-agent handoff |
| Sync reads, async loop | SSE hot path stays cheap; no `await` per push |
| In-memory cache as single source of truth | N clients, 1 fetch loop; SSE & portfolio routes share it |
| Factory at startup | Implementation choice baked at boot — no per-request branching |
| Massive in executor pool | Sync client must not block the FastAPI event loop |
| Massive seeds cache with `SEED_PRICES` | First page paint shows numbers before the first poll completes |
| Exponential backoff on Massive errors | Don't hammer the API; recover cleanly when network returns |
| `add_ticker` / `remove_ticker` are sync | Called from HTTP handlers; effect lands on next tick |
| Simulator uses private `Random` instance | Test parallelism without RNG races |
| Session-relative `change_percent` | Matches what real terminals show; what the watchlist needs |
