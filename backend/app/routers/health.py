"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def health_check() -> dict:
    """Return a simple health check response for Docker/deployment probes."""
    return {"status": "ok"}
