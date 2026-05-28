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
