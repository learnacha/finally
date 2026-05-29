"""
Tests for watchlist CRUD operations against an in-memory SQLite database.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import aiosqlite
import pytest

from app.db.schema import ALL_CREATE_STATEMENTS
from app.db.seed import seed_database, DEFAULT_USER_ID, DEFAULT_WATCHLIST_TICKERS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    """Fresh in-memory DB with schema + seed data."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        for stmt in ALL_CREATE_STATEMENTS:
            await conn.execute(stmt)
        await conn.commit()
        await seed_database(conn)
        yield conn


# ---------------------------------------------------------------------------
# Watchlist helper functions
# ---------------------------------------------------------------------------


async def get_watchlist(db, user_id: str = DEFAULT_USER_ID) -> list[str]:
    async with db.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [r["ticker"] for r in rows]


async def add_ticker(db, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Add a ticker. Returns True on success, False if already present."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, now),
        )
        await db.commit()
        return True
    except Exception:
        return False


async def remove_ticker(db, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker. Returns True if a row was deleted."""
    async with db.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ) as cur:
        rowcount = cur.rowcount
    await db.commit()
    return rowcount > 0


async def ticker_in_watchlist(db, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    async with db.execute(
        "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ) as cur:
        row = await cur.fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Read tests
# ---------------------------------------------------------------------------


class TestWatchlistRead:
    async def test_default_watchlist_has_10_tickers(self, db):
        tickers = await get_watchlist(db)
        assert len(tickers) == 10

    async def test_default_watchlist_contains_expected_tickers(self, db):
        tickers = await get_watchlist(db)
        assert set(tickers) == set(DEFAULT_WATCHLIST_TICKERS)

    async def test_aapl_in_watchlist(self, db):
        assert await ticker_in_watchlist(db, "AAPL") is True

    async def test_unknown_ticker_not_in_watchlist(self, db):
        assert await ticker_in_watchlist(db, "XYZQ") is False


# ---------------------------------------------------------------------------
# Add tests
# ---------------------------------------------------------------------------


class TestWatchlistAdd:
    async def test_add_new_ticker(self, db):
        success = await add_ticker(db, "PYPL")
        assert success is True
        assert await ticker_in_watchlist(db, "PYPL") is True

    async def test_add_increases_count(self, db):
        before = len(await get_watchlist(db))
        await add_ticker(db, "PYPL")
        after = len(await get_watchlist(db))
        assert after == before + 1

    async def test_add_duplicate_fails(self, db):
        success = await add_ticker(db, "AAPL")  # already exists
        assert success is False

    async def test_add_duplicate_does_not_increase_count(self, db):
        before = len(await get_watchlist(db))
        await add_ticker(db, "AAPL")
        after = len(await get_watchlist(db))
        assert after == before

    async def test_add_multiple_tickers(self, db):
        for ticker in ["COIN", "HOOD", "ROBINHOOD"]:
            await add_ticker(db, ticker)
        for ticker in ["COIN", "HOOD", "ROBINHOOD"]:
            assert await ticker_in_watchlist(db, ticker) is True


# ---------------------------------------------------------------------------
# Remove tests
# ---------------------------------------------------------------------------


class TestWatchlistRemove:
    async def test_remove_existing_ticker(self, db):
        success = await remove_ticker(db, "AAPL")
        assert success is True
        assert await ticker_in_watchlist(db, "AAPL") is False

    async def test_remove_decreases_count(self, db):
        before = len(await get_watchlist(db))
        await remove_ticker(db, "AAPL")
        after = len(await get_watchlist(db))
        assert after == before - 1

    async def test_remove_nonexistent_ticker_returns_false(self, db):
        success = await remove_ticker(db, "XYZQ")
        assert success is False

    async def test_remove_then_readd(self, db):
        await remove_ticker(db, "AAPL")
        success = await add_ticker(db, "AAPL")
        assert success is True
        assert await ticker_in_watchlist(db, "AAPL") is True

    async def test_remove_all_tickers(self, db):
        for ticker in DEFAULT_WATCHLIST_TICKERS:
            await remove_ticker(db, ticker)
        tickers = await get_watchlist(db)
        assert tickers == []


# ---------------------------------------------------------------------------
# Multi-user isolation tests
# ---------------------------------------------------------------------------


class TestWatchlistMultiUserIsolation:
    async def test_different_users_have_separate_watchlists(self, db):
        await add_ticker(db, "PYPL", user_id="user2")
        assert await ticker_in_watchlist(db, "PYPL", user_id="user2") is True
        assert await ticker_in_watchlist(db, "PYPL", user_id=DEFAULT_USER_ID) is False

    async def test_removing_from_one_user_does_not_affect_other(self, db):
        # user2 adds AAPL independently
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "user2", "AAPL", now),
        )
        await db.commit()
        # Remove AAPL for default user
        await remove_ticker(db, "AAPL", user_id=DEFAULT_USER_ID)
        # user2 should still have it
        assert await ticker_in_watchlist(db, "AAPL", user_id="user2") is True
