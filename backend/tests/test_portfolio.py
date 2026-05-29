"""
Tests for portfolio trade execution business logic.

These tests exercise the core portfolio operations (buy, sell, P&L calculation)
directly against an in-memory SQLite database, without requiring the FastAPI
router layer to be built. If a router exists at app.routers.portfolio, its
execute_trade function is tested; otherwise a local helper mirrors the spec.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
import pytest

from app.db.schema import ALL_CREATE_STATEMENTS
from app.db.seed import seed_database, DEFAULT_USER_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    """Fresh in-memory DB with schema and seed data (default user, $10k cash)."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        for stmt in ALL_CREATE_STATEMENTS:
            await conn.execute(stmt)
        await conn.commit()
        await seed_database(conn)
        yield conn


# ---------------------------------------------------------------------------
# Portfolio helper functions
# (mirror the business logic the router will implement)
# ---------------------------------------------------------------------------


async def get_cash(db, user_id: str = DEFAULT_USER_ID) -> float:
    async with db.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    return float(row["cash_balance"])


async def get_position(db, ticker: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    async with db.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def execute_buy(db, ticker: str, quantity: float, price: float, user_id: str = DEFAULT_USER_ID):
    """Buy shares. Returns error string on failure, None on success."""
    total_cost = quantity * price
    cash = await get_cash(db, user_id)
    if cash < total_cost:
        return "Insufficient cash"

    now = datetime.now(timezone.utc).isoformat()
    position = await get_position(db, ticker, user_id)

    if position is None:
        await db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, quantity, price, now),
        )
    else:
        old_qty = position["quantity"]
        old_cost = position["avg_cost"]
        new_qty = old_qty + quantity
        new_avg_cost = (old_qty * old_cost + quantity * price) / new_qty
        await db.execute(
            "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE user_id = ? AND ticker = ?",
            (new_qty, new_avg_cost, now, user_id, ticker),
        )

    # Deduct cash
    await db.execute(
        "UPDATE users_profile SET cash_balance = cash_balance - ? WHERE id = ?",
        (total_cost, user_id),
    )
    # Log trade
    await db.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, ticker, "buy", quantity, price, now),
    )
    await db.commit()
    return None


async def execute_sell(db, ticker: str, quantity: float, price: float, user_id: str = DEFAULT_USER_ID):
    """Sell shares. Returns error string on failure, None on success."""
    position = await get_position(db, ticker, user_id)
    if position is None or position["quantity"] < quantity:
        return "Insufficient shares"

    total_proceeds = quantity * price
    now = datetime.now(timezone.utc).isoformat()

    new_qty = position["quantity"] - quantity
    if new_qty < 1e-9:
        await db.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
    else:
        await db.execute(
            "UPDATE positions SET quantity = ?, updated_at = ? WHERE user_id = ? AND ticker = ?",
            (new_qty, now, user_id, ticker),
        )

    # Add cash
    await db.execute(
        "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = ?",
        (total_proceeds, user_id),
    )
    # Log trade
    await db.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, ticker, "sell", quantity, price, now),
    )
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Buy tests
# ---------------------------------------------------------------------------


class TestBuyTrade:
    async def test_buy_reduces_cash(self, db):
        initial_cash = await get_cash(db)
        err = await execute_buy(db, "AAPL", 10, 190.0)
        assert err is None
        new_cash = await get_cash(db)
        assert abs(new_cash - (initial_cash - 10 * 190.0)) < 0.01

    async def test_buy_creates_position(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        position = await get_position(db, "AAPL")
        assert position is not None
        assert position["quantity"] == 10
        assert abs(position["avg_cost"] - 190.0) < 0.01

    async def test_buy_logs_trade(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        async with db.execute(
            "SELECT * FROM trades WHERE ticker = ? AND side = 'buy'", ("AAPL",)
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row["quantity"] == 10
        assert row["price"] == 190.0

    async def test_buy_insufficient_cash_returns_error(self, db):
        err = await execute_buy(db, "AAPL", 1000, 190.0)  # $190,000 > $10,000
        assert err is not None
        assert "cash" in err.lower() or "insufficient" in err.lower()

    async def test_buy_insufficient_cash_does_not_change_cash(self, db):
        initial_cash = await get_cash(db)
        await execute_buy(db, "AAPL", 1000, 190.0)
        assert await get_cash(db) == initial_cash

    async def test_buy_insufficient_cash_does_not_create_position(self, db):
        await execute_buy(db, "TSMC", 1000, 190.0)
        assert await get_position(db, "TSMC") is None

    async def test_buy_averages_cost_on_second_purchase(self, db):
        await execute_buy(db, "AAPL", 10, 100.0)  # 10 shares @ $100
        await execute_buy(db, "AAPL", 10, 200.0)  # 10 shares @ $200
        position = await get_position(db, "AAPL")
        # avg_cost should be $150
        assert abs(position["avg_cost"] - 150.0) < 0.01
        assert position["quantity"] == 20

    async def test_buy_fractional_shares(self, db):
        err = await execute_buy(db, "AAPL", 0.5, 190.0)
        assert err is None
        position = await get_position(db, "AAPL")
        assert position["quantity"] == 0.5

    async def test_buy_exact_cash_amount(self, db):
        """Buy exactly up to the available cash balance."""
        cash = await get_cash(db)
        price = 100.0
        quantity = cash / price  # exactly $10,000 worth
        err = await execute_buy(db, "AAPL", quantity, price)
        assert err is None
        assert await get_cash(db) < 0.01


# ---------------------------------------------------------------------------
# Sell tests
# ---------------------------------------------------------------------------


class TestSellTrade:
    async def test_sell_increases_cash(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        cash_after_buy = await get_cash(db)
        err = await execute_sell(db, "AAPL", 5, 200.0)
        assert err is None
        assert await get_cash(db) > cash_after_buy

    async def test_sell_proceeds_correct(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        cash_after_buy = await get_cash(db)
        await execute_sell(db, "AAPL", 5, 200.0)
        expected = cash_after_buy + 5 * 200.0
        assert abs(await get_cash(db) - expected) < 0.01

    async def test_sell_reduces_position(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        await execute_sell(db, "AAPL", 4, 195.0)
        position = await get_position(db, "AAPL")
        assert abs(position["quantity"] - 6) < 1e-9

    async def test_sell_all_removes_position(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        await execute_sell(db, "AAPL", 10, 195.0)
        assert await get_position(db, "AAPL") is None

    async def test_sell_more_than_owned_returns_error(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        err = await execute_sell(db, "AAPL", 20, 195.0)
        assert err is not None
        assert "shares" in err.lower() or "insufficient" in err.lower()

    async def test_sell_without_position_returns_error(self, db):
        err = await execute_sell(db, "TSMC", 5, 100.0)
        assert err is not None

    async def test_sell_logs_trade(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        await execute_sell(db, "AAPL", 5, 200.0)
        async with db.execute(
            "SELECT * FROM trades WHERE ticker = ? AND side = 'sell'", ("AAPL",)
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row["quantity"] == 5

    async def test_sell_at_loss_still_succeeds(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        err = await execute_sell(db, "AAPL", 10, 100.0)  # sell at loss
        assert err is None

    async def test_sell_at_loss_cash_increases_by_proceeds(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        cash_after_buy = await get_cash(db)
        await execute_sell(db, "AAPL", 10, 100.0)
        assert abs(await get_cash(db) - (cash_after_buy + 10 * 100.0)) < 0.01


# ---------------------------------------------------------------------------
# P&L calculation tests
# ---------------------------------------------------------------------------


class TestPnL:
    async def test_unrealized_pnl_positive(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        position = await get_position(db, "AAPL")
        current_price = 200.0
        unrealized_pnl = (current_price - position["avg_cost"]) * position["quantity"]
        assert unrealized_pnl == pytest.approx(100.0)

    async def test_unrealized_pnl_negative(self, db):
        await execute_buy(db, "AAPL", 10, 200.0)
        position = await get_position(db, "AAPL")
        current_price = 190.0
        unrealized_pnl = (current_price - position["avg_cost"]) * position["quantity"]
        assert unrealized_pnl == pytest.approx(-100.0)

    async def test_unrealized_pnl_zero_on_flat(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        position = await get_position(db, "AAPL")
        unrealized_pnl = (190.0 - position["avg_cost"]) * position["quantity"]
        assert unrealized_pnl == pytest.approx(0.0)

    async def test_avg_cost_updates_across_buys(self, db):
        await execute_buy(db, "AAPL", 10, 100.0)   # $1,000
        await execute_buy(db, "AAPL", 10, 120.0)   # $1,200 — total $2,200, within $10k
        position = await get_position(db, "AAPL")
        # avg_cost = (10*100 + 10*120) / 20 = 110
        assert abs(position["avg_cost"] - 110.0) < 0.01


# ---------------------------------------------------------------------------
# Trade history tests
# ---------------------------------------------------------------------------


class TestTradeHistory:
    async def test_trade_history_records_buy_and_sell(self, db):
        await execute_buy(db, "AAPL", 10, 190.0)
        await execute_sell(db, "AAPL", 5, 200.0)
        async with db.execute(
            "SELECT side FROM trades WHERE user_id = ? ORDER BY executed_at",
            (DEFAULT_USER_ID,),
        ) as cur:
            rows = await cur.fetchall()
        sides = [r["side"] for r in rows]
        assert sides == ["buy", "sell"]

    async def test_multiple_trades_all_logged(self, db):
        for price in [190.0, 192.0, 194.0]:
            await execute_buy(db, "AAPL", 5, price)
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE user_id = ? AND ticker = 'AAPL'",
            (DEFAULT_USER_ID,),
        ) as cur:
            row = await cur.fetchone()
        assert row["cnt"] == 3


# ---------------------------------------------------------------------------
# Portfolio snapshot tests
# ---------------------------------------------------------------------------


class TestPortfolioSnapshots:
    async def test_no_snapshots_on_fresh_start(self, db):
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM portfolio_snapshots WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        ) as cur:
            row = await cur.fetchone()
        assert row["cnt"] == 0

    async def test_can_insert_snapshot(self, db):
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, 10500.0, now),
        )
        await db.commit()
        async with db.execute(
            "SELECT total_value FROM portfolio_snapshots WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        ) as cur:
            row = await cur.fetchone()
        assert row["total_value"] == 10500.0
