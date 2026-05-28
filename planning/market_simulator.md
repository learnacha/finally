# Market Simulator Design

This document describes the design and implementation of `SimulatorMarketClient` — the built-in market data simulator used when no `MASSIVE_API_KEY` is set. It implements the `MarketDataClient` interface defined in `market_interface.md`.

---

## Goals

1. **Realistic feel** — prices drift and oscillate like real stocks; green/red flashes in the UI feel meaningful
2. **Correlated moves** — tech stocks move together; financials have their own correlation
3. **Drama** — occasional sudden "events" keep the demo exciting
4. **Deterministic enough** — same seed produces the same opening session for classroom demos
5. **Zero external dependencies** — runs entirely in-process, no API key, no network

---

## Simulation Model: Geometric Brownian Motion (GBM)

GBM is the standard model for stock price processes. The discrete-time update rule is:

```
S(t+dt) = S(t) × exp((μ - σ²/2)×dt + σ×ε×√dt)
```

Where:
- `S(t)` — current price
- `μ` — drift (annualized; controls long-run trend)
- `σ` — volatility (annualized)
- `dt` — time step in years (500ms ≈ 1.585×10⁻⁸ years at 252 trading days)
- `ε` — standard normal random variable

In practice, at a 500ms tick interval with realistic annual volatility (~30%), the per-tick standard deviation is small (~0.06%), producing smooth, realistic-looking price motion.

---

## Ticker Parameters

Each ticker has its own drift and volatility. These are calibrated to produce realistic-looking ranges over a trading session.

```python
# backend/app/market/simulator.py

from dataclasses import dataclass

@dataclass
class TickerConfig:
    seed_price: float    # Starting price
    drift: float         # Annual drift (e.g. 0.05 = 5% per year)
    volatility: float    # Annual volatility (e.g. 0.30 = 30% per year)
    sector: str          # Used for correlation grouping


TICKER_CONFIGS: dict[str, TickerConfig] = {
    "AAPL":  TickerConfig(seed_price=190.00, drift=0.08,  volatility=0.28, sector="tech"),
    "GOOGL": TickerConfig(seed_price=175.00, drift=0.07,  volatility=0.30, sector="tech"),
    "MSFT":  TickerConfig(seed_price=415.00, drift=0.10,  volatility=0.25, sector="tech"),
    "AMZN":  TickerConfig(seed_price=185.00, drift=0.09,  volatility=0.32, sector="tech"),
    "TSLA":  TickerConfig(seed_price=175.00, drift=0.05,  volatility=0.65, sector="ev"),
    "NVDA":  TickerConfig(seed_price=875.00, drift=0.15,  volatility=0.55, sector="tech"),
    "META":  TickerConfig(seed_price=490.00, drift=0.08,  volatility=0.35, sector="tech"),
    "JPM":   TickerConfig(seed_price=195.00, drift=0.06,  volatility=0.22, sector="finance"),
    "V":     TickerConfig(seed_price=270.00, drift=0.07,  volatility=0.20, sector="finance"),
    "NFLX":  TickerConfig(seed_price=630.00, drift=0.06,  volatility=0.40, sector="media"),
}
```

Higher-volatility tickers (TSLA, NVDA, NFLX) produce more dramatic flashes; lower-volatility ones (V, JPM) feel stable. This contrast makes the portfolio heatmap visually engaging.

---

## Correlation: Sector Shocks

At each tick, a small sector-wide shock is injected before individual GBM steps. This makes tech stocks move together — realistic and visually interesting.

```
sector_shock[sector] = N(0, σ_sector) × √dt
final_shock[ticker] = ρ × sector_shock[sector] + √(1-ρ²) × individual_shock
```

Where `ρ` controls correlation strength (default: 0.5 for tech, 0.4 for finance).

---

## Dramatic Events

Randomly, with low probability, a ticker experiences a sudden 2-5% jump or drop — simulating earnings surprises, news events, or large block trades.

```python
EVENT_PROBABILITY = 0.0005   # ~0.05% per tick per ticker (fires roughly once per 30 min)
EVENT_MAGNITUDE_RANGE = (0.02, 0.05)  # 2–5% shock
```

Events fire independently per ticker per tick. When an event fires, the price instantly jumps or drops by the event magnitude, then GBM resumes from the new level. This produces the kind of sudden flash the UI's price animation is designed to highlight.

---

## Full Implementation

**`backend/app/market/simulator.py`**

```python
import asyncio
import math
import random
import time
from dataclasses import dataclass, field

from .base import MarketDataClient
from .models import PriceEvent, SEED_PRICES

# ── Configuration ──────────────────────────────────────────────────────────

TICK_INTERVAL = 0.5          # seconds between price updates
TRADING_DAYS_PER_YEAR = 252
SECONDS_PER_TRADING_DAY = 6.5 * 3600
TICKS_PER_YEAR = TRADING_DAYS_PER_YEAR * SECONDS_PER_TRADING_DAY / TICK_INTERVAL
DT = 1.0 / TICKS_PER_YEAR   # time step in years per tick

SECTOR_VOLATILITY = 0.15     # annual vol of sector-wide shock
SECTOR_CORRELATION = 0.5     # correlation of individual tickers to sector

EVENT_PROBABILITY = 0.0005   # per ticker per tick
EVENT_MAGNITUDE_MIN = 0.02
EVENT_MAGNITUDE_MAX = 0.05


@dataclass
class TickerConfig:
    seed_price: float
    drift: float       # annual drift
    volatility: float  # annual individual volatility
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

# Default params for tickers not in TICKER_CONFIGS (e.g. added by user)
DEFAULT_CONFIG = TickerConfig(seed_price=100.00, drift=0.05, volatility=0.30, sector="other")


# ── Simulator ──────────────────────────────────────────────────────────────

class SimulatorMarketClient(MarketDataClient):
    """
    Simulates stock price movement using Geometric Brownian Motion (GBM)
    with sector-level correlation and occasional event shocks.
    
    Implements MarketDataClient. No external dependencies.
    """

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)
        
        self._prices: dict[str, float] = {}          # current sim prices
        self._open_prices: dict[str, float] = {}     # session open prices
        self._price_cache: dict[str, PriceEvent] = {}
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None

    # ── MarketDataClient interface ──────────────────────────────────────────

    async def start(self, tickers: list[str]) -> None:
        for t in tickers:
            self._init_ticker(t)
        self._task = asyncio.create_task(self._tick_loop())

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
        ticker = ticker.upper()
        if ticker not in self._tickers:
            self._init_ticker(ticker)

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._tickers.discard(ticker)
        self._prices.pop(ticker, None)
        self._open_prices.pop(ticker, None)
        self._price_cache.pop(ticker, None)

    @property
    def tickers(self) -> list[str]:
        return sorted(self._tickers)

    # ── Internal ────────────────────────────────────────────────────────────

    def _init_ticker(self, ticker: str) -> None:
        """Initialize GBM state for a new ticker."""
        ticker = ticker.upper()
        cfg = TICKER_CONFIGS.get(ticker, DEFAULT_CONFIG)
        price = cfg.seed_price
        self._prices[ticker] = price
        self._open_prices[ticker] = price
        self._tickers.add(ticker)

    async def _tick_loop(self) -> None:
        """Main simulation loop — fires every TICK_INTERVAL seconds."""
        while True:
            self._step()
            await asyncio.sleep(TICK_INTERVAL)

    def _step(self) -> None:
        """Advance all tickers by one GBM time step."""
        now = time.time()
        
        # 1. Generate sector shocks (correlated component)
        sectors: set[str] = set()
        for t in self._tickers:
            cfg = TICKER_CONFIGS.get(t, DEFAULT_CONFIG)
            sectors.add(cfg.sector)
        
        sector_shocks: dict[str, float] = {
            sector: random.gauss(0, 1) * SECTOR_VOLATILITY * math.sqrt(DT)
            for sector in sectors
        }
        
        # 2. Step each ticker
        for ticker in list(self._tickers):
            cfg = TICKER_CONFIGS.get(ticker, DEFAULT_CONFIG)
            prev_price = self._prices[ticker]
            
            # Composite shock: correlated sector + idiosyncratic
            z_sector = sector_shocks[cfg.sector]
            z_idio = random.gauss(0, 1) * cfg.volatility * math.sqrt(DT)
            total_shock = (
                SECTOR_CORRELATION * z_sector
                + math.sqrt(1 - SECTOR_CORRELATION ** 2) * z_idio
            )
            
            # GBM: S(t+dt) = S(t) * exp((μ - σ²/2)*dt + shock)
            drift_term = (cfg.drift - 0.5 * cfg.volatility ** 2) * DT
            new_price = prev_price * math.exp(drift_term + total_shock)
            
            # 3. Occasional dramatic event (2-5% shock)
            if random.random() < EVENT_PROBABILITY:
                magnitude = random.uniform(EVENT_MAGNITUDE_MIN, EVENT_MAGNITUDE_MAX)
                direction = random.choice([1, -1])
                new_price *= (1 + direction * magnitude)
            
            # 4. Price floor: never go below $0.01
            new_price = max(new_price, 0.01)
            
            # 5. Compute change metrics vs session open
            open_price = self._open_prices[ticker]
            change = new_price - open_price
            change_pct = (change / open_price * 100) if open_price > 0 else 0.0
            direction_str = (
                "up" if new_price > prev_price
                else "down" if new_price < prev_price
                else "flat"
            )
            
            # 6. Update state
            self._prices[ticker] = new_price
            self._price_cache[ticker] = PriceEvent(
                ticker=ticker,
                price=round(new_price, 4),
                previous_price=round(prev_price, 4),
                change=round(change, 4),
                change_percent=round(change_pct, 4),
                direction=direction_str,
                timestamp=now,
            )
```

---

## GBM Parameter Tuning Guide

To calibrate drift and volatility for a new ticker:

| Ticker type | Suggested drift | Suggested volatility | Notes |
|-------------|----------------|---------------------|-------|
| Large-cap stable (V, JPM) | 0.05–0.07 | 0.18–0.25 | Slow, steady movement |
| Large-cap growth (AAPL, GOOGL) | 0.07–0.10 | 0.25–0.35 | Active but not wild |
| High-growth / speculative (TSLA, NVDA) | 0.05–0.15 | 0.45–0.70 | Dramatic swings |
| Media / cyclical (NFLX) | 0.05–0.08 | 0.35–0.45 | Moderate-high vol |
| Unknown (user-added tickers) | 0.05 | 0.30 | Safe generic defaults |

**Rule of thumb:** at 500ms ticks, a volatility of 0.30 (30% annual) produces a per-tick standard deviation of:
```
σ_tick = 0.30 × √(1 / (252 × 46800)) ≈ 0.092%
```
This means a $190 AAPL price moves ±$0.17 per tick on average — subtle, but produces visible green/red flashes.

---

## Price Change Semantics

The simulator uses **session-relative change** (vs. session open price), which mirrors how real terminals display daily change. The SSE event's `change_percent` field is populated from this.

```
change       = current_price - open_price_at_session_start
change_pct   = (change / open_price) × 100
```

This is intentionally different from tick-to-tick delta. The UI watchlist shows "daily change %" which should reflect the full session move, not just the last 500ms.

When a ticker is first added during a session (via chat or UI), its `open_price` is set to its seed price (or a realistic guess). Its `change_pct` will start at 0 and drift from there.

---

## Testing the Simulator

```python
import asyncio
from backend.app.market.simulator import SimulatorMarketClient

async def main():
    sim = SimulatorMarketClient(seed=42)  # deterministic for testing
    await sim.start(["AAPL", "GOOGL", "TSLA"])
    
    # Wait a few ticks
    await asyncio.sleep(3)
    
    prices = sim.get_all_prices()
    for ticker, event in prices.items():
        print(f"{ticker}: ${event.price:.2f}  {event.direction}  {event.change_percent:+.3f}%")
    
    # Add a ticker mid-session
    sim.add_ticker("NVDA")
    await asyncio.sleep(2)
    print(sim.get_price("NVDA"))
    
    await sim.stop()

asyncio.run(main())
```

Expected output (approximate, seed=42):
```
AAPL:   $190.12  up    +0.063%
GOOGL:  $174.87  down  -0.074%
TSLA:   $175.31  up    +0.177%
```

---

## Unit Test Coverage

The pytest tests for the simulator should cover:

| Test | What to assert |
|------|---------------|
| `test_prices_initialize_from_seed` | All tickers have prices close to seed values after 0 ticks |
| `test_gbm_produces_valid_prices` | All prices > 0 after 1000 ticks |
| `test_change_percent_monotonic_from_open` | `change_pct` starts at 0 and drifts proportionally to open |
| `test_direction_reflects_prev_tick` | `direction == "up"` iff `price > previous_price` |
| `test_add_ticker_mid_session` | Added ticker appears in `get_all_prices()` within 2 ticks |
| `test_remove_ticker` | Removed ticker absent from `get_all_prices()` immediately |
| `test_event_shock_magnitude` | No single-tick change exceeds 10% (2× event maximum) |
| `test_correlation_tech_stocks` | AAPL and MSFT have Pearson correlation > 0.3 over 1000 ticks |
| `test_interface_conformance` | `SimulatorMarketClient` passes same test suite as `MassiveMarketClient` (via shared fixture) |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| GBM in log space | Prices can never go negative; standard finance model |
| Sector correlation | Makes heatmap visually meaningful — all tech drops together |
| Session-relative change (not tick delta) | Matches real terminal UX; `change_pct` accumulates over session |
| Separate open_prices dict | Avoids drift reset on ticker re-add; clean session semantics |
| Event shocks | Infrequent but dramatic; excellent for demos without being annoying |
| Deterministic seed | Classroom demos show same behavior; reproducible CI tests |
| asyncio.sleep (not threading) | Stays on the FastAPI event loop; no thread-safety issues |
