"""
Tests for database schema initialization, seed data, and lazy init behavior.
Uses an in-memory SQLite database to keep tests fast and isolated.
"""

import pytest
import aiosqlite

from app.db.schema import ALL_CREATE_STATEMENTS
from app.db.seed import (
    seed_database,
    DEFAULT_USER_ID,
    DEFAULT_CASH_BALANCE,
    DEFAULT_WATCHLIST_TICKERS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    """Provide a fresh in-memory SQLite connection with schema + seed data."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        for stmt in ALL_CREATE_STATEMENTS:
            await conn.execute(stmt)
        await conn.commit()
        await seed_database(conn)
        yield conn


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemaInit:
    async def test_all_tables_created(self, db):
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            rows = await cursor.fetchall()
        table_names = {row["name"] for row in rows}
        expected = {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }
        assert expected.issubset(table_names)

    async def test_users_profile_columns(self, db):
        async with db.execute("PRAGMA table_info(users_profile)") as cursor:
            cols = {row["name"] for row in await cursor.fetchall()}
        assert cols == {"id", "cash_balance", "created_at"}

    async def test_watchlist_columns(self, db):
        async with db.execute("PRAGMA table_info(watchlist)") as cursor:
            cols = {row["name"] for row in await cursor.fetchall()}
        assert {"id", "user_id", "ticker", "added_at"}.issubset(cols)

    async def test_positions_columns(self, db):
        async with db.execute("PRAGMA table_info(positions)") as cursor:
            cols = {row["name"] for row in await cursor.fetchall()}
        assert {"id", "user_id", "ticker", "quantity", "avg_cost", "updated_at"}.issubset(cols)

    async def test_trades_columns(self, db):
        async with db.execute("PRAGMA table_info(trades)") as cursor:
            cols = {row["name"] for row in await cursor.fetchall()}
        assert {"id", "user_id", "ticker", "side", "quantity", "price", "executed_at"}.issubset(cols)

    async def test_portfolio_snapshots_columns(self, db):
        async with db.execute("PRAGMA table_info(portfolio_snapshots)") as cursor:
            cols = {row["name"] for row in await cursor.fetchall()}
        assert {"id", "user_id", "total_value", "recorded_at"}.issubset(cols)

    async def test_chat_messages_columns(self, db):
        async with db.execute("PRAGMA table_info(chat_messages)") as cursor:
            cols = {row["name"] for row in await cursor.fetchall()}
        assert {"id", "user_id", "role", "content", "actions", "created_at"}.issubset(cols)

    async def test_idempotent_schema_creation(self, db):
        """Running CREATE TABLE IF NOT EXISTS twice should not raise."""
        for stmt in ALL_CREATE_STATEMENTS:
            await db.execute(stmt)
        await db.commit()


# ---------------------------------------------------------------------------
# Seed data tests
# ---------------------------------------------------------------------------


class TestSeedData:
    async def test_default_user_profile_exists(self, db):
        async with db.execute(
            "SELECT id, cash_balance FROM users_profile WHERE id = ?",
            (DEFAULT_USER_ID,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        assert row["id"] == DEFAULT_USER_ID
        assert row["cash_balance"] == DEFAULT_CASH_BALANCE

    async def test_default_cash_balance_is_10000(self, db):
        async with db.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?",
            (DEFAULT_USER_ID,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["cash_balance"] == 10000.0

    async def test_default_watchlist_has_10_tickers(self, db):
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM watchlist WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["cnt"] == 10

    async def test_default_watchlist_tickers(self, db):
        async with db.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY ticker",
            (DEFAULT_USER_ID,),
        ) as cursor:
            rows = await cursor.fetchall()
        tickers = {row["ticker"] for row in rows}
        assert tickers == set(DEFAULT_WATCHLIST_TICKERS)

    async def test_seed_idempotent_on_reinvoke(self, db):
        """Calling seed_database again should not duplicate rows (INSERT OR IGNORE)."""
        await seed_database(db)
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM users_profile WHERE id = ?",
            (DEFAULT_USER_ID,),
        ) as cursor:
            row = await cursor.fetchone()
        assert row["cnt"] == 1

    async def test_watchlist_unique_constraint(self, db):
        """Duplicate (user_id, ticker) should raise an IntegrityError."""
        import uuid
        with pytest.raises(Exception):  # aiosqlite wraps sqlite3.IntegrityError
            await db.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, "AAPL", "2024-01-01T00:00:00+00:00"),
            )
            await db.commit()

    async def test_positions_unique_constraint(self, db):
        """Duplicate (user_id, ticker) in positions should raise."""
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, "AAPL", 10.0, 190.0, now),
        )
        await db.commit()
        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, "AAPL", 5.0, 195.0, now),
            )
            await db.commit()
