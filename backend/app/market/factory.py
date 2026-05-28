import logging
import os
from .base import MarketDataClient

log = logging.getLogger(__name__)


def create_market_client() -> MarketDataClient:
    """
    Select the market data implementation based on environment.

    MASSIVE_API_KEY set & non-empty → MassiveMarketClient (real data)
    MASSIVE_API_KEY absent / empty  → SimulatorMarketClient (GBM sim)
    """
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()

    if api_key:
        from .massive_client import MassiveMarketClient
        log.info("market: using Massive (Polygon.io) real market data")
        return MassiveMarketClient(api_key=api_key)

    from .simulator import SimulatorMarketClient
    log.info("market: using built-in GBM simulator (no MASSIVE_API_KEY)")
    return SimulatorMarketClient()
