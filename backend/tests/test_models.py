"""Tests for PriceEvent model and seed data."""
import time

import pytest

from app.market.models import (
    DEFAULT_TICKERS,
    SEED_PRICES,
    PriceEvent,
)


def test_price_event_to_dict_shape():
    evt = PriceEvent(
        ticker="AAPL",
        price=192.3456789,
        previous_price=191.8,
        change=0.5456789,
        change_percent=0.2844,
        direction="up",
        timestamp=1234567890.123,
    )
    d = evt.to_dict()
    assert set(d.keys()) == {
        "ticker", "price", "previous_price", "change",
        "change_percent", "direction", "timestamp",
    }


def test_price_event_to_dict_rounds_to_4dp():
    evt = PriceEvent(
        ticker="MSFT",
        price=415.123456,
        previous_price=414.999999,
        change=0.123456,
        change_percent=0.029752,
        direction="up",
        timestamp=time.time(),
    )
    d = evt.to_dict()
    assert d["price"] == round(415.123456, 4)
    assert d["previous_price"] == round(414.999999, 4)
    assert d["change"] == round(0.123456, 4)
    assert d["change_percent"] == round(0.029752, 4)


def test_price_event_direction_values():
    for direction in ("up", "down", "flat"):
        evt = PriceEvent("AAPL", 100.0, 100.0, 0.0, 0.0, direction, time.time())
        assert evt.to_dict()["direction"] == direction


def test_seed_prices_all_positive():
    for ticker, price in SEED_PRICES.items():
        assert price > 0, f"{ticker} seed price should be positive"


def test_seed_prices_reasonable_range():
    for ticker, price in SEED_PRICES.items():
        assert 1.0 <= price <= 10000.0, f"{ticker} seed price {price} out of expected range"


def test_default_tickers_match_seed_prices():
    assert set(DEFAULT_TICKERS) == set(SEED_PRICES.keys())


def test_default_tickers_count():
    assert len(DEFAULT_TICKERS) == 10


def test_default_tickers_are_strings():
    for ticker in DEFAULT_TICKERS:
        assert isinstance(ticker, str)
        assert ticker.isupper()
