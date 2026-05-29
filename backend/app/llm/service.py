"""
LLM service for FinAlly chat functionality.

Orchestrates:
1. Portfolio context loading (cash, positions, watchlist with live prices)
2. Chat history loading (last 20 messages)
3. LLM call via LiteLLM → OpenRouter → Cerebras
4. Auto-execution of trades and watchlist changes
5. Result recording

When LLM_MOCK=true, deterministic mock responses are returned for testing.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiosqlite
import litellm

from ..market.cache import PriceCache
from .models import (
    ActionResults,
    LLMResponse,
    TradeAction,
    TradeResult,
    WatchlistChange,
    WatchlistChangeResult,
)

logger = logging.getLogger(__name__)

# LiteLLM model identifier
_MODEL = "openrouter/openai/gpt-oss-120b"

# System prompt for the FinAlly assistant
_SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant integrated into a simulated trading workstation.

You help users manage their portfolio, analyze their positions, and execute trades.

Your capabilities:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with clear reasoning
- Execute trades on the user's behalf when asked or agreed
- Add and remove tickers from the user's watchlist
- Provide market commentary on the user's holdings

Guidelines:
- Be concise and data-driven — this is a trading terminal, not a chatbot
- When the user agrees to a trade or asks you to trade, include it in the trades field
- Always acknowledge executed trades in your message
- If a trade would fail (insufficient cash/shares), explain why
- Use the portfolio context to give relevant, specific advice
- Never make up prices — use the prices from the context

You MUST always respond with valid JSON matching this exact schema:
{
  "message": "<your conversational response>",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}
trades and watchlist_changes should be empty arrays [] if no actions are needed.
"""


def _build_portfolio_context_text(
    cash: float,
    positions: list[dict],
    watchlist: list[dict],
    total_value: float,
) -> str:
    """Format portfolio context as a readable string for the LLM prompt."""
    lines = [
        "=== CURRENT PORTFOLIO CONTEXT ===",
        f"Cash Balance: ${cash:,.2f}",
        f"Total Portfolio Value: ${total_value:,.2f}",
        "",
    ]

    if positions:
        lines.append("Positions:")
        for pos in positions:
            pnl = pos.get("unrealized_pnl", 0.0)
            pnl_pct = pos.get("unrealized_pnl_pct", 0.0)
            sign = "+" if pnl >= 0 else ""
            lines.append(
                f"  {pos['ticker']:6s}  {pos['quantity']:.2f} shares @ avg ${pos['avg_cost']:.2f} "
                f"| current ${pos.get('current_price', 0):.2f} "
                f"| P&L: {sign}${pnl:.2f} ({sign}{pnl_pct:.2f}%)"
            )
    else:
        lines.append("Positions: None (all cash)")

    lines.append("")
    if watchlist:
        lines.append("Watchlist:")
        for item in watchlist:
            price = item.get("price")
            if price is not None:
                lines.append(f"  {item['ticker']:6s}  ${price:.2f}")
            else:
                lines.append(f"  {item['ticker']:6s}  (price unavailable)")
    else:
        lines.append("Watchlist: Empty")

    lines.append("=================================")
    return "\n".join(lines)


async def build_portfolio_context(db: aiosqlite.Connection, price_cache: PriceCache) -> dict[str, Any]:
    """
    Load the user's current portfolio state for LLM context.

    Returns a dict with:
      cash, positions (with current price + P&L), watchlist (with prices), total_value
    """
    # Load cash balance
    async with db.execute(
        "SELECT cash_balance FROM users_profile WHERE id = 'default'"
    ) as cursor:
        row = await cursor.fetchone()
    cash = row["cash_balance"] if row else 10000.0

    # Load positions
    async with db.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = 'default'"
    ) as cursor:
        position_rows = await cursor.fetchall()

    positions = []
    positions_value = 0.0
    for pos_row in position_rows:
        ticker = pos_row["ticker"]
        quantity = pos_row["quantity"]
        avg_cost = pos_row["avg_cost"]
        current_price = price_cache.get_price(ticker) or avg_cost
        market_value = quantity * current_price
        cost_basis = quantity * avg_cost
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        positions_value += market_value
        positions.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            }
        )

    # Load watchlist
    async with db.execute(
        "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY added_at"
    ) as cursor:
        watchlist_rows = await cursor.fetchall()

    watchlist = []
    for wl_row in watchlist_rows:
        ticker = wl_row["ticker"]
        price = price_cache.get_price(ticker)
        watchlist.append({"ticker": ticker, "price": price})

    total_value = cash + positions_value

    return {
        "cash": cash,
        "positions": positions,
        "watchlist": watchlist,
        "total_value": round(total_value, 2),
    }


async def load_chat_history(db: aiosqlite.Connection, limit: int = 20) -> list[dict]:
    """Load the last `limit` chat messages for LLM context."""
    async with db.execute(
        """
        SELECT role, content FROM chat_messages
        WHERE user_id = 'default'
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()

    # Reverse so oldest is first (chronological order for LLM)
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def _get_mock_response() -> LLMResponse:
    """Return a deterministic mock LLM response for testing (LLM_MOCK=true)."""
    return LLMResponse(
        message=(
            "I'm FinAlly, your AI trading assistant. I can see your portfolio and help you "
            "analyze positions, execute trades, and manage your watchlist. What would you like to do?"
        ),
        trades=[],
        watchlist_changes=[],
    )


async def call_llm(messages: list[dict]) -> LLMResponse:
    """
    Call the LLM via LiteLLM → OpenRouter → Cerebras.

    When LLM_MOCK=true, returns a deterministic mock response.
    Uses structured output (JSON schema) to ensure parseable responses.
    """
    if os.getenv("LLM_MOCK", "false").lower() == "true":
        logger.info("LLM_MOCK=true — returning mock response")
        return _get_mock_response()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set")

    # Build the JSON schema for structured output
    response_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "LLMResponse",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Conversational response to show the user",
                    },
                    "trades": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"},
                                "side": {"type": "string", "enum": ["buy", "sell"]},
                                "quantity": {"type": "number"},
                            },
                            "required": ["ticker", "side", "quantity"],
                            "additionalProperties": False,
                        },
                    },
                    "watchlist_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"},
                                "action": {"type": "string", "enum": ["add", "remove"]},
                            },
                            "required": ["ticker", "action"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["message", "trades", "watchlist_changes"],
                "additionalProperties": False,
            },
        },
    }

    try:
        response = await litellm.acompletion(
            model=_MODEL,
            messages=messages,
            api_key=api_key,
            response_format=response_schema,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return LLMResponse(**data)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned non-JSON content: %s", exc)
        # Fallback: return a safe error message
        return LLMResponse(
            message="I encountered an error processing your request. Please try again.",
            trades=[],
            watchlist_changes=[],
        )
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise


async def execute_actions(
    db: aiosqlite.Connection,
    price_cache: PriceCache,
    trades: list[TradeAction],
    watchlist_changes: list[WatchlistChange],
) -> ActionResults:
    """
    Auto-execute trades and watchlist changes specified by the LLM.

    Trades go through full validation:
    - Buy: sufficient cash required
    - Sell: sufficient shares required

    Returns ActionResults recording success/failure of each action.
    """
    trade_results: list[TradeResult] = []
    wl_results: list[WatchlistChangeResult] = []
    now = datetime.now(timezone.utc).isoformat()

    for trade in trades:
        ticker = trade.ticker.upper()
        side = trade.side
        quantity = trade.quantity

        # Get current price
        current_price = price_cache.get_price(ticker)
        if current_price is None:
            trade_results.append(
                TradeResult(
                    status="failed",
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    price=None,
                    total=None,
                    error=f"No price available for {ticker}. Is it on the watchlist?",
                )
            )
            continue

        total_cost = round(current_price * quantity, 2)

        if side == "buy":
            # Check cash
            async with db.execute(
                "SELECT cash_balance FROM users_profile WHERE id = 'default'"
            ) as cursor:
                row = await cursor.fetchone()
            cash = row["cash_balance"] if row else 0.0

            if cash < total_cost:
                trade_results.append(
                    TradeResult(
                        status="failed",
                        ticker=ticker,
                        side=side,
                        quantity=quantity,
                        price=current_price,
                        total=total_cost,
                        error=f"Insufficient cash. Need ${total_cost:.2f}, have ${cash:.2f}.",
                    )
                )
                continue

            # Deduct cash
            await db.execute(
                "UPDATE users_profile SET cash_balance = cash_balance - ? WHERE id = 'default'",
                (total_cost,),
            )

            # Upsert position (update avg_cost using weighted average)
            async with db.execute(
                "SELECT quantity, avg_cost FROM positions WHERE user_id = 'default' AND ticker = ?",
                (ticker,),
            ) as cursor:
                pos_row = await cursor.fetchone()

            if pos_row:
                old_qty = pos_row["quantity"]
                old_avg = pos_row["avg_cost"]
                new_qty = old_qty + quantity
                new_avg = ((old_qty * old_avg) + (quantity * current_price)) / new_qty
                await db.execute(
                    "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                    "WHERE user_id = 'default' AND ticker = ?",
                    (new_qty, new_avg, now, ticker),
                )
            else:
                await db.execute(
                    "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                    "VALUES (?, 'default', ?, ?, ?, ?)",
                    (str(uuid4()), ticker, quantity, current_price, now),
                )

        elif side == "sell":
            # Check shares owned
            async with db.execute(
                "SELECT quantity, avg_cost FROM positions WHERE user_id = 'default' AND ticker = ?",
                (ticker,),
            ) as cursor:
                pos_row = await cursor.fetchone()

            if not pos_row or pos_row["quantity"] < quantity:
                owned = pos_row["quantity"] if pos_row else 0.0
                trade_results.append(
                    TradeResult(
                        status="failed",
                        ticker=ticker,
                        side=side,
                        quantity=quantity,
                        price=current_price,
                        total=total_cost,
                        error=f"Insufficient shares. Trying to sell {quantity}, own {owned:.2f}.",
                    )
                )
                continue

            # Add cash proceeds
            await db.execute(
                "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = 'default'",
                (total_cost,),
            )

            # Update or remove position
            new_qty = pos_row["quantity"] - quantity
            if new_qty < 1e-9:  # Effectively zero
                await db.execute(
                    "DELETE FROM positions WHERE user_id = 'default' AND ticker = ?",
                    (ticker,),
                )
            else:
                await db.execute(
                    "UPDATE positions SET quantity = ?, updated_at = ? "
                    "WHERE user_id = 'default' AND ticker = ?",
                    (new_qty, now, ticker),
                )

        # Record trade in history
        await db.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, 'default', ?, ?, ?, ?, ?)",
            (str(uuid4()), ticker, side, quantity, current_price, now),
        )

        trade_results.append(
            TradeResult(
                status="executed",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=current_price,
                total=total_cost,
                error=None,
            )
        )

    # Process watchlist changes
    for change in watchlist_changes:
        ticker = change.ticker.upper()
        action = change.action

        try:
            if action == "add":
                await db.execute(
                    "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) "
                    "VALUES (?, 'default', ?, ?)",
                    (str(uuid4()), ticker, now),
                )
                wl_results.append(
                    WatchlistChangeResult(status="applied", ticker=ticker, action=action, error=None)
                )
            elif action == "remove":
                await db.execute(
                    "DELETE FROM watchlist WHERE user_id = 'default' AND ticker = ?",
                    (ticker,),
                )
                wl_results.append(
                    WatchlistChangeResult(status="applied", ticker=ticker, action=action, error=None)
                )
        except Exception as exc:
            wl_results.append(
                WatchlistChangeResult(
                    status="failed", ticker=ticker, action=action, error=str(exc)
                )
            )

    await db.commit()

    return ActionResults(trades=trade_results, watchlist_changes=wl_results)


class LLMService:
    """
    High-level service that orchestrates the full LLM chat flow.

    Usage:
        service = LLMService(price_cache)
        response, actions = await service.chat(db, user_message)
    """

    def __init__(self, price_cache: PriceCache) -> None:
        self.price_cache = price_cache

    async def chat(
        self, db: aiosqlite.Connection, user_message: str
    ) -> tuple[LLMResponse, ActionResults]:
        """
        Full chat flow:
        1. Build portfolio context
        2. Load last 20 chat messages
        3. Construct LLM messages
        4. Call LLM
        5. Execute any actions
        6. Return (llm_response, action_results)

        The caller is responsible for storing messages in chat_messages.
        """
        # 1. Build portfolio context
        context = await build_portfolio_context(db, self.price_cache)
        context_text = _build_portfolio_context_text(
            cash=context["cash"],
            positions=context["positions"],
            watchlist=context["watchlist"],
            total_value=context["total_value"],
        )

        # 2. Load chat history
        history = await load_chat_history(db, limit=20)

        # 3. Construct messages list
        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "system", "content": context_text},
            *history,
            {"role": "user", "content": user_message},
        ]

        # 4. Call LLM
        llm_response = await call_llm(messages)

        # 5. Execute actions
        action_results = await execute_actions(
            db=db,
            price_cache=self.price_cache,
            trades=llm_response.trades,
            watchlist_changes=llm_response.watchlist_changes,
        )

        return llm_response, action_results
