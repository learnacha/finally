"""Tests for SimulatorMarketClient."""
import asyncio
import math

import pytest

from app.market.simulator import (
    DEFAULT_CONFIG,
    TICKER_CONFIGS,
    SimulatorMarketClient,
)
from app.market.models import DEFAULT_TICKERS, SEED_PRICES


# ── Helpers ────────────────────────────────────────────────────────────────

def _run_ticks(sim: SimulatorMarketClient, n: int) -> None:
    """Drive `n` synchronous ticks without the async loop."""
    for _ in range(n):
        sim._step()


# ── Initialization tests ───────────────────────────────────────────────────

def test_initial_prices_match_seed():
    sim = SimulatorMarketClient(seed=1)
    for ticker in ["AAPL", "MSFT", "GOOGL"]:
        sim._init_ticker(ticker)
    for ticker in ["AAPL", "MSFT", "GOOGL"]:
        assert sim._prices[ticker] == SEED_PRICES[ticker]
        assert sim._open_prices[ticker] == SEED_PRICES[ticker]


@pytest.mark.asyncio
async def test_initial_events_emitted_on_start():
    sim = SimulatorMarketClient(seed=2)
    await sim.start(["AAPL", "GOOGL"])
    prices = sim.get_all_prices()
    assert "AAPL" in prices
    assert "GOOGL" in prices
    await sim.stop()


def test_tickers_property_sorted():
    sim = SimulatorMarketClient(seed=3)
    sim._init_ticker("TSLA")
    sim._init_ticker("AAPL")
    sim._init_ticker("MSFT")
    assert sim.tickers == ["AAPL", "MSFT", "TSLA"]


# ── Price validity tests ───────────────────────────────────────────────────

def test_prices_always_positive_after_many_ticks():
    sim = SimulatorMarketClient(seed=42)
    for t in DEFAULT_TICKERS:
        sim._init_ticker(t)
    _run_ticks(sim, 1000)
    for ticker in DEFAULT_TICKERS:
        assert sim._prices[ticker] > 0, f"{ticker} price went non-positive"


def test_price_floor_enforced():
    """Price must never drop below PRICE_FLOOR even under extreme conditions."""
    from app.market.simulator import PRICE_FLOOR
    sim = SimulatorMarketClient(seed=7)
    sim._init_ticker("TSLA")
    sim._prices["TSLA"] = 0.001
    sim._open_prices["TSLA"] = 0.001
    _run_ticks(sim, 100)
    assert sim._prices["TSLA"] >= PRICE_FLOOR


def test_cache_populated_after_step():
    sim = SimulatorMarketClient(seed=5)
    sim._init_ticker("AAPL")
    sim._emit_initial_events()
    _run_ticks(sim, 1)
    evt = sim.get_price("AAPL")
    assert evt is not None
    assert evt.price > 0


# ── PriceEvent field correctness ───────────────────────────────────────────

def test_direction_reflects_prev_tick():
    """direction == 'up' iff price > previous_price, etc."""
    sim = SimulatorMarketClient(seed=10)
    sim._init_ticker("AAPL")
    sim._emit_initial_events()
    _run_ticks(sim, 500)

    evt = sim.get_price("AAPL")
    assert evt is not None
    if evt.price > evt.previous_price:
        assert evt.direction == "up"
    elif evt.price < evt.previous_price:
        assert evt.direction == "down"
    else:
        assert evt.direction == "flat"


def test_change_percent_session_relative():
    """change_percent = (price - open_price) / open_price * 100."""
    sim = SimulatorMarketClient(seed=11)
    sim._init_ticker("AAPL")
    sim._emit_initial_events()
    _run_ticks(sim, 50)

    evt = sim.get_price("AAPL")
    open_price = sim._open_prices["AAPL"]
    expected_pct = (evt.price - open_price) / open_price * 100
    assert abs(evt.change_percent - expected_pct) < 1e-6


def test_change_is_price_minus_open():
    """change = price - open_price (session-relative, not tick delta)."""
    sim = SimulatorMarketClient(seed=12)
    sim._init_ticker("MSFT")
    sim._emit_initial_events()
    _run_ticks(sim, 30)

    evt = sim.get_price("MSFT")
    open_price = sim._open_prices["MSFT"]
    assert abs(evt.change - (evt.price - open_price)) < 1e-9


def test_initial_change_percent_is_zero():
    """On first emit (price == open), change_percent must be 0."""
    sim = SimulatorMarketClient(seed=13)
    sim._init_ticker("AAPL")
    sim._emit_initial_events()
    evt = sim.get_price("AAPL")
    assert evt.change_percent == 0.0
    assert evt.change == 0.0


# ── Single-tick shock bound ────────────────────────────────────────────────

def test_single_tick_change_bounded():
    """No single tick should move price by more than 15% (2× event max + GBM)."""
    sim = SimulatorMarketClient(seed=99)
    sim._init_ticker("TSLA")  # highest volatility
    sim._emit_initial_events()

    for _ in range(5000):
        prev = sim._prices["TSLA"]
        sim._step()
        curr = sim._prices["TSLA"]
        ratio = abs(curr - prev) / prev
        assert ratio < 0.15, f"Single-tick move too large: {ratio:.4%}"


# ── Add / remove ticker ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_ticker_appears_in_prices():
    sim = SimulatorMarketClient(seed=20)
    await sim.start(["AAPL"])
    sim.add_ticker("NVDA")
    prices = sim.get_all_prices()
    assert "NVDA" in prices
    await sim.stop()


def test_add_ticker_idempotent():
    sim = SimulatorMarketClient(seed=21)
    sim._init_ticker("AAPL")
    sim._emit_initial_events()
    sim.add_ticker("AAPL")  # already tracked
    assert sim.tickers.count("AAPL") == 1


@pytest.mark.asyncio
async def test_remove_ticker_disappears_immediately():
    sim = SimulatorMarketClient(seed=22)
    await sim.start(["AAPL", "GOOGL"])
    sim.remove_ticker("AAPL")
    prices = sim.get_all_prices()
    assert "AAPL" not in prices
    assert "GOOGL" in prices
    await sim.stop()


def test_remove_nonexistent_ticker_is_noop():
    sim = SimulatorMarketClient(seed=23)
    sim._init_ticker("AAPL")
    sim.remove_ticker("NOTREAL")  # should not raise
    assert "AAPL" in sim.tickers


@pytest.mark.asyncio
async def test_get_price_case_insensitive():
    sim = SimulatorMarketClient(seed=24)
    await sim.start(["AAPL"])
    assert sim.get_price("aapl") is not None
    assert sim.get_price("AAPL") is not None
    await sim.stop()


# ── Determinism ────────────────────────────────────────────────────────────

def test_seed_determinism():
    """Two instances with the same seed produce identical price sequences."""
    sim_a = SimulatorMarketClient(seed=42)
    sim_b = SimulatorMarketClient(seed=42)

    for t in ["AAPL", "GOOGL", "MSFT"]:
        sim_a._init_ticker(t)
        sim_b._init_ticker(t)

    sim_a._emit_initial_events()
    sim_b._emit_initial_events()

    for _ in range(20):
        sim_a._step()
        sim_b._step()

    for ticker in ["AAPL", "GOOGL", "MSFT"]:
        assert sim_a._prices[ticker] == sim_b._prices[ticker]


def test_different_seeds_produce_different_sequences():
    sim_a = SimulatorMarketClient(seed=1)
    sim_b = SimulatorMarketClient(seed=9999)
    sim_a._init_ticker("AAPL")
    sim_b._init_ticker("AAPL")
    for _ in range(10):
        sim_a._step()
        sim_b._step()
    # Prices must diverge (with overwhelming probability for different seeds)
    assert sim_a._prices["AAPL"] != sim_b._prices["AAPL"]


# ── Sector correlation ─────────────────────────────────────────────────────

def test_sector_correlation_tech_stocks():
    """AAPL and MSFT (both 'tech') should be positively correlated."""
    sim = SimulatorMarketClient(seed=77)
    for t in ["AAPL", "MSFT"]:
        sim._init_ticker(t)
    sim._emit_initial_events()

    aapl_returns = []
    msft_returns = []
    prev_aapl = sim._prices["AAPL"]
    prev_msft = sim._prices["MSFT"]

    for _ in range(2000):
        sim._step()
        curr_aapl = sim._prices["AAPL"]
        curr_msft = sim._prices["MSFT"]
        aapl_returns.append(math.log(curr_aapl / prev_aapl))
        msft_returns.append(math.log(curr_msft / prev_msft))
        prev_aapl = curr_aapl
        prev_msft = curr_msft

    n = len(aapl_returns)
    mean_a = sum(aapl_returns) / n
    mean_m = sum(msft_returns) / n
    cov = sum((a - mean_a) * (m - mean_m) for a, m in zip(aapl_returns, msft_returns)) / n
    std_a = math.sqrt(sum((a - mean_a) ** 2 for a in aapl_returns) / n)
    std_m = math.sqrt(sum((m - mean_m) ** 2 for m in msft_returns) / n)
    corr = cov / (std_a * std_m) if std_a > 0 and std_m > 0 else 0.0

    assert corr > 0.3, f"Expected AAPL/MSFT correlation > 0.3, got {corr:.3f}"


# ── Start / stop lifecycle ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_creates_background_task():
    sim = SimulatorMarketClient(seed=30)
    await sim.start(["AAPL"])
    assert sim._task is not None
    assert not sim._task.done()
    await sim.stop()


@pytest.mark.asyncio
async def test_stop_cancels_task():
    sim = SimulatorMarketClient(seed=31)
    await sim.start(["AAPL"])
    await sim.stop()
    assert sim._task is None


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    sim = SimulatorMarketClient(seed=32)
    await sim.start(["AAPL"])
    await sim.stop()
    await sim.stop()  # second stop should not raise


@pytest.mark.asyncio
async def test_prices_update_over_time():
    sim = SimulatorMarketClient(seed=33)
    await sim.start(["AAPL"])
    first = sim.get_price("AAPL").price
    await asyncio.sleep(1.5)  # ~3 ticks
    second = sim.get_price("AAPL").price
    await sim.stop()
    # Prices should have changed (astronomically unlikely to stay identical)
    assert first != second


# ── Unknown ticker uses DEFAULT_CONFIG ────────────────────────────────────

def test_unknown_ticker_uses_default_config():
    sim = SimulatorMarketClient(seed=40)
    sim._init_ticker("ZZZZ")
    assert sim._prices["ZZZZ"] == DEFAULT_CONFIG.seed_price
    assert "ZZZZ" in sim.tickers


# ── All prices remain valid after many ticks ──────────────────────────────

def test_all_default_tickers_valid_after_5000_ticks():
    sim = SimulatorMarketClient(seed=55)
    for t in DEFAULT_TICKERS:
        sim._init_ticker(t)
    sim._emit_initial_events()
    _run_ticks(sim, 5000)

    prices = sim.get_all_prices()
    assert len(prices) == len(DEFAULT_TICKERS)
    for ticker, evt in prices.items():
        assert evt.price > 0
        assert evt.direction in ("up", "down", "flat")
        assert isinstance(evt.change_percent, float)
