"""
Database connection and lifecycle management for FinAlly.

Uses aiosqlite for async SQLite access. The database is lazily initialized:
on first connection, tables are created and seeded with default data if they
do not already exist.

The SQLite file is stored at db/finally.db relative to the project root
(two levels above this file: backend/app/db/ -> backend/app/ -> backend/ -> project root).
"""

from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from .schema import ALL_CREATE_STATEMENTS
from .seed import seed_database

# Project root is three levels up from this file (backend/app/db/database.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = _PROJECT_ROOT / "db" / "finally.db"

_initialized = False


async def _ensure_initialized(db: aiosqlite.Connection) -> None:
    """Create schema and seed data if this is a fresh database."""
    global _initialized
    if _initialized:
        return

    # Check whether the users_profile table exists as a proxy for full schema
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users_profile'"
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        # Fresh database: create all tables and seed default data
        for statement in ALL_CREATE_STATEMENTS:
            await db.execute(statement)
        await db.commit()
        await seed_database(db)

    _initialized = True


async def init_db() -> None:
    """
    Explicitly initialize the database. Call this at application startup
    (e.g., from a FastAPI lifespan handler) to ensure the schema and seed
    data are ready before the first request arrives.
    """
    global _initialized
    _initialized = False  # Force re-check on explicit init call
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await _ensure_initialized(db)


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    FastAPI dependency that yields an open aiosqlite connection.

    Lazily initializes the schema on first use. The connection is closed
    automatically when the request finishes.

    Usage in a route:
        @router.get("/example")
        async def example(db: aiosqlite.Connection = Depends(get_db)):
            ...
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await _ensure_initialized(db)
        yield db
