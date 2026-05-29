"""
Seed data for the FinAlly database.

Seeds a default user profile with $10,000 cash balance and
a default watchlist of 10 tickers.
"""

from datetime import datetime, timezone
from uuid import uuid4

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

DEFAULT_WATCHLIST_TICKERS = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
]


async def seed_database(db) -> None:
    """Seed initial data into the database if not already present."""
    now = datetime.now(timezone.utc).isoformat()

    # Seed default user profile
    await db.execute(
        """
        INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at)
        VALUES (?, ?, ?)
        """,
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )

    # Seed default watchlist tickers
    for ticker in DEFAULT_WATCHLIST_TICKERS:
        await db.execute(
            """
            INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid4()), DEFAULT_USER_ID, ticker, now),
        )

    await db.commit()
