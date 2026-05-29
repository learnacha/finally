# LLM Chat Implementation — Task #3 Complete

**Agent**: llm-engineer  
**Status**: Completed  
**Date**: 2026-05-29

## Files Created

### `backend/app/llm/__init__.py`
Module init — exports all public symbols from models and service.

### `backend/app/llm/models.py`
Pydantic models for structured LLM I/O:
- `TradeAction` — ticker, side (buy/sell), quantity
- `WatchlistChange` — ticker, action (add/remove)
- `LLMResponse` — message + trades + watchlist_changes (LLM output schema)
- `TradeResult` — execution outcome with price, total, error
- `WatchlistChangeResult` — applied/failed with error
- `ActionResults` — aggregated results stored in `chat_messages.actions`

### `backend/app/llm/service.py`
`LLMService` class plus standalone async helpers:
- `build_portfolio_context(db, price_cache)` — loads cash, positions with live P&L, watchlist with prices, total_value
- `load_chat_history(db, limit=20)` — last 20 messages in chronological order
- `call_llm(messages)` — LiteLLM → `openrouter/openai/gpt-oss-120b` via Cerebras; JSON schema structured output; `LLM_MOCK=true` returns deterministic mock
- `execute_actions(db, price_cache, trades, watchlist_changes)` — validates and executes trades (cash/shares checks), applies watchlist changes, commits to DB, returns `ActionResults`
- `LLMService.chat(db, user_message)` — orchestrates full flow, returns `(LLMResponse, ActionResults)`

### `backend/app/routers/chat.py`
`POST /api/chat` FastAPI router:
1. Validates user message
2. Stores user message in `chat_messages`
3. Calls `LLMService.chat()`
4. Stores assistant response + action results in `chat_messages`
5. Returns `{message, trades, watchlist_changes, actions}` JSON

## Integration Notes for `main.py` (task #2)

The chat router needs `LLMService` registered on `app.state` at startup:

```python
from app.market.cache import PriceCache
from app.llm.service import LLMService
from app.routers.chat import router as chat_router

# In lifespan handler, after creating price_cache:
app.state.llm_service = LLMService(price_cache=app.state.price_cache)

# Register router:
app.include_router(chat_router)
```

The router reads `app.state.llm_service` from the FastAPI `Request` object (same pattern as watchlist router reads `price_cache`).

## Dependency
`litellm>=1.55.0` is already in `backend/pyproject.toml` — no additional packages needed.

## LLM_MOCK mode
Set `LLM_MOCK=true` in `.env` for deterministic mock responses (no API calls). Used for E2E tests.
