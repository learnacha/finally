"""
FinAlly — FastAPI application entry point.

Wires together:
  - Database initialization (lazy on first connection, explicit at startup)
  - Market data: PriceCache + MarketDataSource (simulator or Massive)
  - SSE streaming router
  - Portfolio, watchlist, health, and chat API routers
  - Static file serving for the Next.js export (served from /app/static/)
  - Background task: portfolio snapshot every 30 seconds
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Load .env from the project root (three levels up: backend/app/ -> backend/ -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

from app.db import init_db, get_db
from app.llm.service import LLMService
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.stream import create_stream_router
from app.routers import chat, health, portfolio, watchlist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Snapshot background task
# ---------------------------------------------------------------------------

_SNAPSHOT_INTERVAL = 30  # seconds


async def _snapshot_loop(app: FastAPI) -> None:
    """Periodically record portfolio value snapshots."""
    from app.routers.portfolio import record_snapshot

    while True:
        try:
            await asyncio.sleep(_SNAPSHOT_INTERVAL)
        except asyncio.CancelledError:
            break

        try:
            async for db in get_db():
                await record_snapshot(db, app.state.price_cache)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error recording portfolio snapshot")


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB, start background tasks, clean up."""
    # 1. Initialize the database (create tables + seed data if needed)
    await init_db()
    logger.info("Database initialized")

    # 2. Set up the price cache
    price_cache = PriceCache()
    app.state.price_cache = price_cache

    # 3. Load initial watchlist tickers from the database
    initial_tickers: list[str] = []
    async for db in get_db():
        async with db.execute(
            "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY added_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        initial_tickers = [row["ticker"] for row in rows]

    logger.info("Starting market data source with %d tickers: %s", len(initial_tickers), initial_tickers)

    # 4. Create and start the market data source
    market_source = create_market_data_source(price_cache)
    app.state.market_source = market_source
    await market_source.start(initial_tickers)
    logger.info("Market data source started")

    # 5. Create LLM service
    app.state.llm_service = LLMService(price_cache)
    logger.info("LLM service initialized")

    # 6. Start the portfolio snapshot background task
    snapshot_task = asyncio.create_task(_snapshot_loop(app))

    yield  # Application runs here

    # --- Shutdown ---
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass

    await market_source.stop()
    logger.info("Market data source stopped")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="FinAlly API",
        description="AI Trading Workstation backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    # API routers
    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(watchlist.router)
    app.include_router(chat.router)

    # SSE streaming router — needs the price cache at creation time, so we
    # use a lazy wrapper that pulls from app state at request time.
    # We create a placeholder here; the actual cache is set in lifespan.
    # NOTE: create_stream_router captures the cache reference; since Python
    # passes objects by reference, we create it after the cache is available.
    # We do this by attaching the router in lifespan instead — but FastAPI
    # does not support adding routers after startup. Instead we pass a
    # factory closure.
    #
    # Solution: we create the SSE router with a thin proxy that reads from
    # app.state.price_cache at request time. The stream.py already accepts a
    # PriceCache at construction time, so we create a small proxy object.
    class _CacheProxy:
        """Proxy that forwards all attribute access to app.state.price_cache."""
        def __init__(self, _app: FastAPI):
            self._app = _app

        def __getattr__(self, name: str):
            return getattr(self._app.state.price_cache, name)

    stream_router = create_stream_router(_CacheProxy(app))
    app.include_router(stream_router)

    # Static file serving for Next.js export
    # The static directory is at /app/static inside Docker; locally it may not exist yet.
    static_dir = Path(os.environ.get("STATIC_DIR", "/app/static"))
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        logger.info("Serving static files from %s", static_dir)
    else:
        logger.info(
            "Static directory %s not found — frontend will not be served. "
            "This is normal during backend-only development.",
            static_dir,
        )

    return app


app = create_app()
