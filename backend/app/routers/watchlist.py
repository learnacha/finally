"""Watchlist API endpoints.

GET  /api/watchlist          — current tickers with latest prices from the price cache
POST /api/watchlist          — add a ticker  {ticker: str}
DELETE /api/watchlist/{ticker} — remove a ticker
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

USER_ID = "default"


class AddTickerRequest(BaseModel):
    ticker: str


def _get_price_cache(request: Request):
    """Pull the PriceCache instance from app state."""
    return request.app.state.price_cache


def _get_market_source(request: Request):
    """Pull the MarketDataSource instance from app state."""
    return request.app.state.market_source


@router.get("")
async def get_watchlist(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> list[dict]:
    """Return all watchlist tickers with latest prices from the cache."""
    price_cache = _get_price_cache(request)

    async with db.execute(
        "SELECT ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (USER_ID,),
    ) as cursor:
        rows = await cursor.fetchall()

    result = []
    for row in rows:
        ticker = row["ticker"]
        update = price_cache.get(ticker)
        entry: dict = {
            "ticker": ticker,
            "added_at": row["added_at"],
        }
        if update:
            entry.update(
                {
                    "price": update.price,
                    "previous_price": update.previous_price,
                    "change": update.change,
                    "change_percent": update.change_percent,
                    "direction": update.direction,
                    "timestamp": update.timestamp,
                }
            )
        else:
            entry.update(
                {
                    "price": None,
                    "previous_price": None,
                    "change": None,
                    "change_percent": None,
                    "direction": None,
                    "timestamp": None,
                }
            )
        result.append(entry)

    return result


@router.post("", status_code=201)
async def add_ticker(
    body: AddTickerRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Add a ticker to the watchlist. No-op if already present (returns 200-like 201)."""
    ticker = body.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker must not be empty")

    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(
            """
            INSERT INTO watchlist (id, user_id, ticker, added_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid4()), USER_ID, ticker, now),
        )
        await db.commit()
    except aiosqlite.IntegrityError:
        # Already in the watchlist — treat as success
        return {"ticker": ticker, "added": False, "message": "Ticker already in watchlist"}

    # Tell the market data source to start tracking this ticker
    market_source = _get_market_source(request)
    await market_source.add_ticker(ticker)

    logger.info("Added ticker %s to watchlist", ticker)
    return {"ticker": ticker, "added": True}


@router.delete("/{ticker}", status_code=200)
async def remove_ticker(
    ticker: str,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Remove a ticker from the watchlist."""
    ticker = ticker.upper().strip()

    async with db.execute(
        "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not in watchlist")

    await db.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    )
    await db.commit()

    # Tell the market data source to stop tracking this ticker
    market_source = _get_market_source(request)
    await market_source.remove_ticker(ticker)

    # Also remove from the price cache
    price_cache = _get_price_cache(request)
    price_cache.remove(ticker)

    logger.info("Removed ticker %s from watchlist", ticker)
    return {"ticker": ticker, "removed": True}
