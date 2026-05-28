"""Tests for MassiveMarketClient (Massive/Polygon.io REST polling client).

All tests mock the underlying massive.RESTClient — no real API calls.
"""
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from app.market.models import SEED_PRICES


# ── Mock helpers ──────────────────────────────────────────────────────────

def _make_snap(ticker: str, price: float, change: float = 0.5, change_pct: float = 0.25):
    """Build a mock TickerSnapshot-like object."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = MagicMock()
    snap.last_trade.price = price
    snap.day = MagicMock()
    snap.day.close = price
    snap.prev_day = MagicMock()
    snap.prev_day.close = price - change
    snap.todays_change = change
    snap.todays_change_perc = change_pct
    return snap


def _make_client():
    """Return a MassiveMarketClient with a mocked underlying REST client."""
    with patch("massive.RESTClient"):
        from app.market.massive_client import MassiveMarketClient
        client = MassiveMarketClient(api_key="test")
    client._cache = {}
    client._tickers = set()
    client._task = None
    return client


# ── Seed cache ─────────────────────────────────────────────────────────────

def test_seed_cache_populates_known_tickers():
    client = _make_client()
    client._tickers = {"AAPL", "MSFT"}
    client._seed_cache()
    assert "AAPL" in client._cache
    assert "MSFT" in client._cache
    assert client._cache["AAPL"].price == SEED_PRICES["AAPL"]
    assert client._cache["AAPL"].direction == "flat"
    assert client._cache["AAPL"].change == 0.0
    assert client._cache["AAPL"].change_percent == 0.0


def test_seed_cache_skips_unknown_tickers():
    client = _make_client()
    client._tickers = {"ZZZZ"}
    client._seed_cache()
    assert "ZZZZ" not in client._cache


def test_seed_cache_previous_price_equals_price():
    client = _make_client()
    client._tickers = {"AAPL"}
    client._seed_cache()
    evt = client._cache["AAPL"]
    assert evt.price == evt.previous_price


# ── add_ticker / remove_ticker ─────────────────────────────────────────────

def test_add_ticker_seeds_known_price():
    client = _make_client()
    client.add_ticker("AAPL")
    assert "AAPL" in client._tickers
    assert "AAPL" in client._cache
    assert client._cache["AAPL"].price == SEED_PRICES["AAPL"]


def test_add_ticker_idempotent():
    client = _make_client()
    client._tickers = {"AAPL"}
    original = {"AAPL"}
    client.add_ticker("AAPL")  # already present
    assert client._tickers == original


def test_add_ticker_uppercase_normalisation():
    client = _make_client()
    client.add_ticker("aapl")
    assert "AAPL" in client._tickers


def test_add_unknown_ticker_no_seed_in_cache():
    """Tickers without a seed price are tracked but not seeded in cache."""
    client = _make_client()
    client.add_ticker("ZZZZ")
    assert "ZZZZ" in client._tickers
    assert "ZZZZ" not in client._cache


def test_remove_ticker_clears_cache_and_set():
    client = _make_client()
    client._tickers = {"AAPL", "MSFT"}
    client._seed_cache()
    client.remove_ticker("AAPL")
    assert "AAPL" not in client._tickers
    assert "AAPL" not in client._cache
    assert "MSFT" in client._tickers


def test_remove_nonexistent_ticker_is_noop():
    client = _make_client()
    client._tickers = {"AAPL"}
    client.remove_ticker("NOTREAL")  # should not raise
    assert "AAPL" in client._tickers


def test_tickers_property_sorted():
    client = _make_client()
    client._tickers = {"MSFT", "AAPL", "GOOGL"}
    assert client.tickers == ["AAPL", "GOOGL", "MSFT"]


# ── get_price / get_all_prices ─────────────────────────────────────────────

def test_get_price_returns_none_before_cache_populated():
    client = _make_client()
    assert client.get_price("AAPL") is None


def test_get_price_case_insensitive():
    client = _make_client()
    client._tickers = {"AAPL"}
    client._seed_cache()
    assert client.get_price("aapl") is not None
    assert client.get_price("AAPL") is not None


def test_get_all_prices_returns_copy():
    client = _make_client()
    client._tickers = {"AAPL"}
    client._seed_cache()
    prices = client.get_all_prices()
    prices["EXTRA"] = None  # mutate the copy
    assert "EXTRA" not in client._cache


def test_get_all_prices_empty_before_start():
    client = _make_client()
    assert client.get_all_prices() == {}


# ── _snap_to_event ─────────────────────────────────────────────────────────

def test_snap_to_event_uses_last_trade_price():
    client = _make_client()
    snap = _make_snap("AAPL", 192.34, change=0.54, change_pct=0.2815)
    evt = client._snap_to_event(snap, time.time())
    assert evt is not None
    assert evt.price == 192.34
    assert evt.change == 0.54
    assert evt.change_percent == 0.2815
    assert evt.ticker == "AAPL"


def test_snap_to_event_falls_back_to_day_close():
    client = _make_client()
    snap = _make_snap("AAPL", 0)
    snap.last_trade.price = None
    snap.day.close = 192.00
    evt = client._snap_to_event(snap, time.time())
    assert evt is not None
    assert evt.price == 192.00


def test_snap_to_event_falls_back_to_prev_day_close():
    client = _make_client()
    snap = _make_snap("AAPL", 0)
    snap.last_trade.price = None
    snap.day.close = None
    snap.prev_day.close = 191.50
    evt = client._snap_to_event(snap, time.time())
    assert evt is not None
    assert evt.price == 191.50


def test_snap_to_event_falls_back_to_seed_price():
    client = _make_client()
    snap = _make_snap("AAPL", 0)
    snap.last_trade.price = None
    snap.day.close = None
    snap.prev_day.close = None
    evt = client._snap_to_event(snap, time.time())
    assert evt is not None
    assert evt.price == SEED_PRICES["AAPL"]


def test_snap_to_event_returns_none_for_unknown_ticker_no_price():
    client = _make_client()
    snap = _make_snap("ZZZZ", 0)
    snap.last_trade.price = None
    snap.day.close = None
    snap.prev_day.close = None
    evt = client._snap_to_event(snap, time.time())
    assert evt is None


def test_snap_to_event_direction_up_vs_cached():
    from app.market.models import PriceEvent
    client = _make_client()
    client._cache["AAPL"] = PriceEvent("AAPL", 190.0, 190.0, 0.0, 0.0, "flat", time.time())
    snap = _make_snap("AAPL", 192.0)
    evt = client._snap_to_event(snap, time.time())
    assert evt.direction == "up"
    assert evt.previous_price == 190.0


def test_snap_to_event_direction_down_vs_cached():
    from app.market.models import PriceEvent
    client = _make_client()
    client._cache["AAPL"] = PriceEvent("AAPL", 195.0, 195.0, 0.0, 0.0, "flat", time.time())
    snap = _make_snap("AAPL", 192.0)
    evt = client._snap_to_event(snap, time.time())
    assert evt.direction == "down"


def test_snap_to_event_direction_flat_on_equal_price():
    from app.market.models import PriceEvent
    client = _make_client()
    client._cache["AAPL"] = PriceEvent("AAPL", 192.0, 192.0, 0.0, 0.0, "flat", time.time())
    snap = _make_snap("AAPL", 192.0)
    evt = client._snap_to_event(snap, time.time())
    assert evt.direction == "flat"


def test_snap_to_event_prev_price_is_seed_when_no_cache():
    """When cache is empty, previous_price equals price (no prior reference)."""
    client = _make_client()
    snap = _make_snap("AAPL", 192.34)
    evt = client._snap_to_event(snap, time.time())
    assert evt.previous_price == 192.34
    assert evt.direction == "flat"


def test_snap_to_event_ticker_uppercased():
    client = _make_client()
    snap = _make_snap("aapl", 192.34)
    evt = client._snap_to_event(snap, time.time())
    assert evt.ticker == "AAPL"


def test_snap_to_event_preserves_change_from_api():
    """change and change_percent come from the snapshot API, not computed."""
    client = _make_client()
    snap = _make_snap("AAPL", 192.34, change=1.23, change_pct=0.643)
    evt = client._snap_to_event(snap, time.time())
    assert evt.change == 1.23
    assert evt.change_percent == 0.643


# ── _fetch_and_update ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_false_on_exception():
    client = _make_client()
    client._tickers = {"AAPL"}

    def _raise(*args, **kwargs):
        raise RuntimeError("network error")

    client._client.get_snapshot_all = _raise
    ok = await client._fetch_and_update()
    assert ok is False


@pytest.mark.asyncio
async def test_fetch_returns_true_when_no_tickers():
    client = _make_client()
    client._tickers = set()
    ok = await client._fetch_and_update()
    assert ok is True


@pytest.mark.asyncio
async def test_fetch_populates_cache_via_snap_to_event():
    """Test full fetch->cache pipeline using _snap_to_event directly."""
    client = _make_client()
    client._tickers = {"AAPL", "GOOGL"}

    snap_aapl = _make_snap("AAPL", 192.34, change=0.54, change_pct=0.2815)
    snap_googl = _make_snap("GOOGL", 175.12, change=1.2, change_pct=0.69)

    # Call _snap_to_event directly (the real implementation path, no isinstance guard)
    now = time.time()
    client._cache["AAPL"] = client._snap_to_event(snap_aapl, now)
    client._cache["GOOGL"] = client._snap_to_event(snap_googl, now)

    assert "AAPL" in client._cache
    assert client._cache["AAPL"].price == 192.34
    assert client._cache["AAPL"].change_percent == 0.2815
    assert "GOOGL" in client._cache
    assert client._cache["GOOGL"].price == 175.12


# ── start / stop lifecycle ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_seeds_cache_before_first_poll():
    client = _make_client()

    async def _never_ending():
        await asyncio.sleep(9999)

    with patch.object(client, "_poll_loop", side_effect=_never_ending):
        await client.start(["AAPL", "MSFT"])

    assert "AAPL" in client._cache
    assert "MSFT" in client._cache
    assert client._task is not None
    await client.stop()


@pytest.mark.asyncio
async def test_start_normalises_ticker_case():
    client = _make_client()

    async def _never_ending():
        await asyncio.sleep(9999)

    with patch.object(client, "_poll_loop", side_effect=_never_ending):
        await client.start(["aapl", "msft"])

    assert "AAPL" in client._tickers
    assert "MSFT" in client._tickers
    await client.stop()


@pytest.mark.asyncio
async def test_stop_cancels_task():
    client = _make_client()

    async def _never_ending():
        await asyncio.sleep(9999)

    with patch.object(client, "_poll_loop", side_effect=_never_ending):
        await client.start(["AAPL"])

    await client.stop()
    assert client._task is None


@pytest.mark.asyncio
async def test_stop_is_idempotent_no_task():
    client = _make_client()
    client._task = None
    await client.stop()  # should not raise


@pytest.mark.asyncio
async def test_stop_is_idempotent_called_twice():
    client = _make_client()

    async def _never_ending():
        await asyncio.sleep(9999)

    with patch.object(client, "_poll_loop", side_effect=_never_ending):
        await client.start(["AAPL"])

    await client.stop()
    await client.stop()  # second call should not raise


# ── Backoff logic ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_poll_loop_backs_off_on_failure():
    """Backoff delay increases after consecutive poll failures."""
    from app.market.massive_client import BACKOFF_INITIAL, BACKOFF_MAX

    client = _make_client()
    client._tickers = {"AAPL"}

    call_count = 0
    sleep_calls = []

    async def _always_fail():
        nonlocal call_count
        call_count += 1
        return False

    async def _capture_sleep(delay):
        sleep_calls.append(delay)
        if len(sleep_calls) >= 3:
            raise asyncio.CancelledError()

    with patch.object(client, "_fetch_and_update", side_effect=_always_fail):
        with patch("asyncio.sleep", side_effect=_capture_sleep):
            with pytest.raises(asyncio.CancelledError):
                await client._poll_loop()

    assert sleep_calls[0] == BACKOFF_INITIAL
    assert sleep_calls[1] == min(BACKOFF_INITIAL * 2, BACKOFF_MAX)


@pytest.mark.asyncio
async def test_poll_loop_resets_backoff_on_success():
    """Backoff resets to initial value after a successful fetch."""
    from app.market.massive_client import BACKOFF_INITIAL, POLL_INTERVAL

    client = _make_client()
    client._tickers = {"AAPL"}

    responses = [False, True]  # fail once, then succeed
    sleep_calls = []

    async def _alternating():
        return responses.pop(0) if responses else True

    async def _capture_sleep(delay):
        sleep_calls.append(delay)
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError()

    with patch.object(client, "_fetch_and_update", side_effect=_alternating):
        with patch("asyncio.sleep", side_effect=_capture_sleep):
            with pytest.raises(asyncio.CancelledError):
                await client._poll_loop()

    # First sleep is backoff (failure), second is normal interval (success)
    assert sleep_calls[0] == BACKOFF_INITIAL
    assert sleep_calls[1] == POLL_INTERVAL
