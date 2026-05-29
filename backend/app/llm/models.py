"""
Pydantic models for LLM structured output and action results.

The LLM responds with a structured JSON object containing:
- message: conversational text to show the user
- trades: list of trade actions to auto-execute
- watchlist_changes: list of watchlist modifications to apply

After execution, ActionResults records the outcome of each action.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM Output Schema (what we ask the LLM to produce)
# ---------------------------------------------------------------------------


class TradeAction(BaseModel):
    """A trade action requested by the LLM."""

    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'AAPL'")
    side: Literal["buy", "sell"] = Field(..., description="Trade direction")
    quantity: float = Field(..., gt=0, description="Number of shares (fractional OK)")


class WatchlistChange(BaseModel):
    """A watchlist modification requested by the LLM."""

    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'AAPL'")
    action: Literal["add", "remove"] = Field(..., description="add or remove")


class LLMResponse(BaseModel):
    """Structured output from the LLM.

    The LLM is instructed to always respond with this schema.
    trades and watchlist_changes are optional and default to empty lists.
    """

    message: str = Field(..., description="Conversational response to show the user")
    trades: list[TradeAction] = Field(
        default_factory=list,
        description="Trades to auto-execute on behalf of the user",
    )
    watchlist_changes: list[WatchlistChange] = Field(
        default_factory=list,
        description="Watchlist additions or removals to apply",
    )


# ---------------------------------------------------------------------------
# Action Result Models (stored in chat_messages.actions as JSON)
# ---------------------------------------------------------------------------


class TradeResult(BaseModel):
    """Result of attempting to execute a single trade."""

    status: Literal["executed", "failed"] = Field(
        ..., description="Whether the trade was successfully executed"
    )
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    price: Optional[float] = Field(None, description="Fill price; null if failed")
    total: Optional[float] = Field(None, description="Total cost/proceeds; null if failed")
    error: Optional[str] = Field(None, description="Error message if status is 'failed'")


class WatchlistChangeResult(BaseModel):
    """Result of attempting a watchlist modification."""

    status: Literal["applied", "failed"] = Field(
        ..., description="Whether the change was applied"
    )
    ticker: str
    action: Literal["add", "remove"]
    error: Optional[str] = Field(None, description="Error message if status is 'failed'")


class ActionResults(BaseModel):
    """All action results for one assistant message — stored in chat_messages.actions."""

    trades: list[TradeResult] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChangeResult] = Field(default_factory=list)
