"""Tests for the market data factory."""
import os
from unittest.mock import patch

import pytest


def test_factory_returns_simulator_without_api_key():
    from app.market.factory import create_market_client
    from app.market.simulator import SimulatorMarketClient

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        client = create_market_client()
    assert isinstance(client, SimulatorMarketClient)


def test_factory_returns_simulator_for_empty_api_key():
    from app.market.factory import create_market_client
    from app.market.simulator import SimulatorMarketClient

    with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
        client = create_market_client()
    assert isinstance(client, SimulatorMarketClient)


def test_factory_returns_simulator_for_whitespace_api_key():
    from app.market.factory import create_market_client
    from app.market.simulator import SimulatorMarketClient

    with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
        client = create_market_client()
    assert isinstance(client, SimulatorMarketClient)


def test_factory_returns_massive_client_when_api_key_set():
    from app.market.factory import create_market_client
    from app.market.massive_client import MassiveMarketClient

    with patch("massive.RESTClient"):
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "real-key-abc123"}):
            client = create_market_client()
    assert isinstance(client, MassiveMarketClient)


def test_factory_implements_market_data_client_interface():
    from app.market.base import MarketDataClient
    from app.market.factory import create_market_client

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        client = create_market_client()
    assert isinstance(client, MarketDataClient)
