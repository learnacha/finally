"""Tests for MassiveDataSource (mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def _make_snapshot(ticker: str, price: float, timestamp_ms: int) -> MagicMock:
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = MagicMock()
    snap.last_trade.price = price
    snap.last_trade.timestamp = timestamp_ms
    return snap


@pytest.mark.asyncio
class TestMassiveDataSource:

    async def test_poll_updates_cache(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "GOOGL"]
        source._client = MagicMock()
        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000), _make_snapshot("GOOGL", 175.25, 1707580800000)]
        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_malformed_snapshot_skipped(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "BAD"]
        source._client = MagicMock()
        good_snap = _make_snapshot("AAPL", 190.50, 1707580800000)
        bad_snap = MagicMock()
        bad_snap.ticker = "BAD"
        bad_snap.last_trade = None
        with patch.object(source, "_fetch_snapshots", return_value=[good_snap, bad_snap]):
            await source._poll_once()
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None

    async def test_api_error_does_not_crash(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = MagicMock()
        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()
        assert cache.get_price("AAPL") is None

    async def test_timestamp_conversion(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = MagicMock()
        with patch.object(source, "_fetch_snapshots", return_value=[_make_snapshot("AAPL", 190.50, 1707580800000)]):
            await source._poll_once()
        assert cache.get("AAPL").timestamp == 1707580800.0

    async def test_add_ticker(self):
        source = MassiveDataSource(api_key="test-key", price_cache=PriceCache())
        await source.add_ticker("AAPL")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_uppercase_normalization(self):
        source = MassiveDataSource(api_key="test-key", price_cache=PriceCache())
        await source.add_ticker("aapl")
        assert "AAPL" in source.get_tickers()

    async def test_remove_ticker(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "GOOGL"]
        cache.update("AAPL", 190.00)
        await source.remove_ticker("AAPL")
        assert "AAPL" not in source.get_tickers()
        assert cache.get("AAPL") is None

    async def test_empty_tickers_skips_poll(self):
        source = MassiveDataSource(api_key="test-key", price_cache=PriceCache())
        source._tickers = []
        with patch.object(source, "_fetch_snapshots") as mock_fetch:
            await source._poll_once()
            mock_fetch.assert_not_called()

    async def test_stop_is_idempotent(self):
        source = MassiveDataSource(api_key="test-key", price_cache=PriceCache())
        await source.stop()
        await source.stop()

    async def test_stop_cancels_task(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=10.0)
        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[]):
                await source.start(["AAPL"])
        assert source._task is not None
        await source.stop()
        assert source._task is None
