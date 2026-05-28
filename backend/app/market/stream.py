import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .base import MarketDataClient

router = APIRouter(prefix="/api/stream", tags=["stream"])

SSE_PUSH_INTERVAL = 0.5     # seconds between pushes to the client
SSE_KEEPALIVE_AFTER = 15.0  # send a comment every 15s of silence to keep connection alive


@router.get("/prices")
async def price_stream(request: Request):
    client: MarketDataClient = request.app.state.market_client
    return StreamingResponse(
        _event_generator(request, client),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _event_generator(request: Request, client: MarketDataClient):
    last_sent = 0.0
    # Initial flush so the client sees something immediately
    initial = client.get_all_prices()
    if initial:
        payload = {t: e.to_dict() for t, e in initial.items()}
        yield f"data: {json.dumps(payload)}\n\n"
        last_sent = asyncio.get_event_loop().time()

    while True:
        if await request.is_disconnected():
            return

        prices = client.get_all_prices()
        now = asyncio.get_event_loop().time()
        if prices:
            payload = {t: e.to_dict() for t, e in prices.items()}
            yield f"data: {json.dumps(payload)}\n\n"
            last_sent = now
        elif now - last_sent > SSE_KEEPALIVE_AFTER:
            yield ": keepalive\n\n"
            last_sent = now

        await asyncio.sleep(SSE_PUSH_INTERVAL)
