"""Chat API endpoint.

POST /api/chat — send a user message, receive LLM response with optional auto-executed actions.

The endpoint:
1. Stores the user's message in chat_messages
2. Loads portfolio context + last 20 messages
3. Calls LLM (or mock) via LLMService
4. Auto-executes trades and watchlist changes specified by the LLM
5. Stores the assistant response with action results in chat_messages
6. Returns the full JSON response to the frontend
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.db import get_db
from app.llm.service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

USER_ID = "default"


class ChatRequest(BaseModel):
    message: str


def _get_llm_service(request: Request) -> LLMService:
    """Pull the LLMService instance from app state."""
    return request.app.state.llm_service


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """
    Send a user message and receive an LLM response.

    Returns:
    {
        "message": "<assistant text>",
        "trades": [...],
        "watchlist_changes": [...],
        "actions": {
            "trades": [...],
            "watchlist_changes": [...]
        }
    }
    """
    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    now = datetime.now(timezone.utc).isoformat()

    # Store user message in chat history
    user_msg_id = str(uuid4())
    await db.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, 'user', ?, NULL, ?)",
        (user_msg_id, USER_ID, user_message, now),
    )
    await db.commit()

    # Get LLMService from app state
    llm_service = _get_llm_service(request)

    # Run the full LLM chat flow
    try:
        llm_response, action_results = await llm_service.chat(db, user_message)
    except Exception as exc:
        logger.error("LLM chat failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM service error: {exc}") from exc

    # Store assistant response with action results
    assistant_msg_id = str(uuid4())
    actions_json = action_results.model_dump_json()
    response_now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, 'assistant', ?, ?, ?)",
        (assistant_msg_id, USER_ID, llm_response.message, actions_json, response_now),
    )
    await db.commit()

    # Build response payload
    return {
        "message": llm_response.message,
        "trades": [t.model_dump() for t in llm_response.trades],
        "watchlist_changes": [w.model_dump() for w in llm_response.watchlist_changes],
        "actions": json.loads(actions_json),
    }
