import asyncio
import logging
import os
import time

from .base import MarketDataClient
from .models import PriceEvent, SEED_PRICES

log = logging.getLogger(__name__)

POLL_INTERVAL = float(os.getenv("MASSIVE_POLL_INTERVAL", "15"))
BACKOFF_INITIAL = 5.0
BACKOFF_MAX = 120.0


class MassiveMarketClient(MarketDataClient):
    """REST polling client for Massive (Polygon.io) snapshots."""

    def __init__(self, api_key: str):
        # Import lazily so tests can mock before the import resolves
        from massive import RESTClient
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
        # Seed an entry so the UI has something until the next poll
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

        from massive.rest.models import TickerSnapshot
        now = time.time()
        for snap in snapshots:
            if not isinstance(snap, TickerSnapshot):
                continue
            event = self._snap_to_event(snap, now)
            if event is not None:
                self._cache[snap.ticker.upper()] = event
        return True

    def _snap_to_event(self, snap, now: float) -> PriceEvent | None:
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
