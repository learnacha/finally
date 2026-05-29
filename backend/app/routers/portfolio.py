"""Portfolio API endpoints.

GET  /api/portfolio          — current positions, cash balance, total value, unrealized P&L
POST /api/portfolio/trade    — execute a market order {ticker, quantity, side}
GET  /api/portfolio/history  — portfolio value snapshots over time
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

USER_ID = "default"


class TradeRequest(BaseModel):
    ticker: str
    quantity: float = Field(..., gt=0, description="Number of shares (fractional OK)")
    side: Literal["buy", "sell"]


def _get_price_cache(request: Request):
    return request.app.state.price_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_cash_balance(db: aiosqlite.Connection) -> float:
    async with db.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (USER_ID,)
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="User profile not found")
    return float(row["cash_balance"])


async def _get_positions(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ? ORDER BY ticker",
        (USER_ID,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def record_snapshot(db: aiosqlite.Connection, price_cache) -> None:
    """Compute and record a portfolio value snapshot."""
    cash = await _get_cash_balance(db)
    positions = await _get_positions(db)

    market_value = 0.0
    for pos in positions:
        price = price_cache.get_price(pos["ticker"])
        if price is not None:
            market_value += pos["quantity"] * price
        else:
            # Fall back to avg cost if price unknown
            market_value += pos["quantity"] * pos["avg_cost"]

    total_value = cash + market_value
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """
        INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid4()), USER_ID, total_value, now),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def get_portfolio(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Return current portfolio state: cash, positions with P&L, and totals."""
    price_cache = _get_price_cache(request)
    cash = await _get_cash_balance(db)
    positions = await _get_positions(db)

    enriched = []
    total_market_value = 0.0
    total_unrealized_pnl = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        quantity = pos["quantity"]
        avg_cost = pos["avg_cost"]
        current_price = price_cache.get_price(ticker)

        if current_price is None:
            current_price = avg_cost  # Use avg cost as fallback

        market_value = quantity * current_price
        cost_basis = quantity * avg_cost
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis != 0 else 0.0

        total_market_value += market_value
        total_unrealized_pnl += unrealized_pnl

        enriched.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 4),
                "updated_at": pos["updated_at"],
            }
        )

    total_value = cash + total_market_value

    return {
        "cash": round(cash, 2),
        "positions": enriched,
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_value": round(total_value, 2),
    }


@router.post("/trade", status_code=200)
async def execute_trade(
    body: TradeRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Execute a market order. Validates cash/shares, updates positions and trade log."""
    price_cache = _get_price_cache(request)
    ticker = body.ticker.upper().strip()
    quantity = body.quantity
    side = body.side

    # Get current price
    current_price = price_cache.get_price(ticker)
    if current_price is None:
        raise HTTPException(
            status_code=400, detail=f"No price available for {ticker}. Is it in your watchlist?"
        )

    total_cost = quantity * current_price
    now = datetime.now(timezone.utc).isoformat()

    cash = await _get_cash_balance(db)

    if side == "buy":
        # Validate sufficient cash
        if cash < total_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient cash. Need ${total_cost:.2f}, have ${cash:.2f}",
            )

        # Deduct cash
        await db.execute(
            "UPDATE users_profile SET cash_balance = cash_balance - ? WHERE id = ?",
            (total_cost, USER_ID),
        )

        # Upsert position: update avg_cost using weighted average
        async with db.execute(
            "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (USER_ID, ticker),
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            old_qty = existing["quantity"]
            old_avg = existing["avg_cost"]
            new_qty = old_qty + quantity
            new_avg = ((old_qty * old_avg) + (quantity * current_price)) / new_qty
            await db.execute(
                """
                UPDATE positions
                SET quantity = ?, avg_cost = ?, updated_at = ?
                WHERE user_id = ? AND ticker = ?
                """,
                (new_qty, new_avg, now, USER_ID, ticker),
            )
        else:
            await db.execute(
                """
                INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), USER_ID, ticker, quantity, current_price, now),
            )

    elif side == "sell":
        # Validate sufficient shares
        async with db.execute(
            "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (USER_ID, ticker),
        ) as cursor:
            existing = await cursor.fetchone()

        if existing is None or existing["quantity"] < quantity:
            owned = existing["quantity"] if existing else 0
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient shares. Trying to sell {quantity}, own {owned:.4f}",
            )

        # Credit cash
        await db.execute(
            "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = ?",
            (total_cost, USER_ID),
        )

        new_qty = existing["quantity"] - quantity
        if new_qty < 1e-8:
            # Position fully closed — remove it
            await db.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (USER_ID, ticker),
            )
        else:
            await db.execute(
                """
                UPDATE positions
                SET quantity = ?, updated_at = ?
                WHERE user_id = ? AND ticker = ?
                """,
                (new_qty, now, USER_ID, ticker),
            )
    else:
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")

    # Record the trade
    await db.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid4()), USER_ID, ticker, side, quantity, current_price, now),
    )
    await db.commit()

    # Record a portfolio snapshot immediately after the trade
    try:
        await record_snapshot(db, price_cache)
    except Exception:
        logger.exception("Failed to record portfolio snapshot after trade")

    logger.info("Trade executed: %s %s x%.4f @ %.2f", side, ticker, quantity, current_price)

    return {
        "status": "executed",
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": current_price,
        "total": round(total_cost, 2),
    }


@router.get("/history")
async def get_portfolio_history(
    db: aiosqlite.Connection = Depends(get_db),
) -> list[dict]:
    """Return portfolio value snapshots over time (for the P&L chart)."""
    async with db.execute(
        """
        SELECT total_value, recorded_at
        FROM portfolio_snapshots
        WHERE user_id = ?
        ORDER BY recorded_at ASC
        """,
        (USER_ID,),
    ) as cursor:
        rows = await cursor.fetchall()

    return [{"total_value": row["total_value"], "recorded_at": row["recorded_at"]} for row in rows]
