"""
Tests for LLM structured output models and parsing.

Covers: valid schema parsing, optional field defaults, malformed/partial
responses, action result models, and the ActionResults aggregator.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.llm.models import (
    ActionResults,
    LLMResponse,
    TradeAction,
    TradeResult,
    WatchlistChange,
    WatchlistChangeResult,
)


# ---------------------------------------------------------------------------
# TradeAction
# ---------------------------------------------------------------------------


class TestTradeAction:
    def test_valid_buy(self):
        t = TradeAction(ticker="AAPL", side="buy", quantity=10)
        assert t.ticker == "AAPL"
        assert t.side == "buy"
        assert t.quantity == 10

    def test_valid_sell(self):
        t = TradeAction(ticker="GOOGL", side="sell", quantity=5.5)
        assert t.side == "sell"

    def test_invalid_side(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAPL", side="hold", quantity=10)

    def test_zero_quantity_invalid(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAPL", side="buy", quantity=0)

    def test_negative_quantity_invalid(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAPL", side="buy", quantity=-5)

    def test_fractional_quantity(self):
        t = TradeAction(ticker="AAPL", side="buy", quantity=0.001)
        assert t.quantity == 0.001

    def test_from_dict(self):
        data = {"ticker": "MSFT", "side": "buy", "quantity": 3}
        t = TradeAction.model_validate(data)
        assert t.ticker == "MSFT"


# ---------------------------------------------------------------------------
# WatchlistChange
# ---------------------------------------------------------------------------


class TestWatchlistChange:
    def test_valid_add(self):
        w = WatchlistChange(ticker="PYPL", action="add")
        assert w.action == "add"

    def test_valid_remove(self):
        w = WatchlistChange(ticker="NFLX", action="remove")
        assert w.action == "remove"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            WatchlistChange(ticker="AAPL", action="toggle")

    def test_from_dict(self):
        data = {"ticker": "TSLA", "action": "add"}
        w = WatchlistChange.model_validate(data)
        assert w.ticker == "TSLA"


# ---------------------------------------------------------------------------
# LLMResponse — valid schemas
# ---------------------------------------------------------------------------


class TestLLMResponseValid:
    def test_message_only(self):
        resp = LLMResponse(message="Hello!")
        assert resp.message == "Hello!"
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_full_response(self):
        resp = LLMResponse(
            message="I'll buy AAPL for you.",
            trades=[{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            watchlist_changes=[{"ticker": "PYPL", "action": "add"}],
        )
        assert len(resp.trades) == 1
        assert resp.trades[0].ticker == "AAPL"
        assert len(resp.watchlist_changes) == 1

    def test_multiple_trades(self):
        resp = LLMResponse(
            message="Rebalancing your portfolio.",
            trades=[
                {"ticker": "AAPL", "side": "buy", "quantity": 5},
                {"ticker": "TSLA", "side": "sell", "quantity": 3},
            ],
        )
        assert len(resp.trades) == 2

    def test_multiple_watchlist_changes(self):
        resp = LLMResponse(
            message="Updating watchlist.",
            watchlist_changes=[
                {"ticker": "PYPL", "action": "add"},
                {"ticker": "NFLX", "action": "remove"},
            ],
        )
        assert len(resp.watchlist_changes) == 2
        actions = [w.action for w in resp.watchlist_changes]
        assert "add" in actions
        assert "remove" in actions

    def test_empty_arrays_explicit(self):
        resp = LLMResponse(message="Just chatting.", trades=[], watchlist_changes=[])
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_parse_from_json_string(self):
        raw = json.dumps({
            "message": "Buy 10 AAPL",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [],
        })
        resp = LLMResponse.model_validate_json(raw)
        assert resp.trades[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# LLMResponse — malformed / partial input
# ---------------------------------------------------------------------------


class TestLLMResponseMalformed:
    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            LLMResponse(trades=[], watchlist_changes=[])

    def test_invalid_trade_side_in_response(self):
        with pytest.raises(ValidationError):
            LLMResponse(
                message="test",
                trades=[{"ticker": "AAPL", "side": "hold", "quantity": 10}],
            )

    def test_trade_missing_ticker(self):
        with pytest.raises(ValidationError):
            LLMResponse(
                message="test",
                trades=[{"side": "buy", "quantity": 10}],
            )

    def test_trade_missing_quantity(self):
        with pytest.raises(ValidationError):
            LLMResponse(
                message="test",
                trades=[{"ticker": "AAPL", "side": "buy"}],
            )

    def test_watchlist_change_missing_action(self):
        with pytest.raises(ValidationError):
            LLMResponse(
                message="test",
                watchlist_changes=[{"ticker": "AAPL"}],
            )

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            LLMResponse.model_validate_json("not valid json at all")

    def test_extra_fields_allowed_or_ignored(self):
        """Extra fields in the JSON should not crash Pydantic (extra='ignore' default)."""
        raw = json.dumps({
            "message": "Hello",
            "trades": [],
            "watchlist_changes": [],
            "unknown_field": "some value",
        })
        # This should not raise — Pydantic ignores extra fields by default
        resp = LLMResponse.model_validate_json(raw)
        assert resp.message == "Hello"


# ---------------------------------------------------------------------------
# Action result models
# ---------------------------------------------------------------------------


class TestTradeResult:
    def test_executed(self):
        r = TradeResult(
            status="executed",
            ticker="AAPL",
            side="buy",
            quantity=10,
            price=190.5,
            total=1905.0,
            error=None,
        )
        assert r.status == "executed"
        assert r.total == 1905.0

    def test_failed(self):
        r = TradeResult(
            status="failed",
            ticker="AAPL",
            side="buy",
            quantity=1000,
            price=None,
            total=None,
            error="Insufficient cash",
        )
        assert r.status == "failed"
        assert r.error == "Insufficient cash"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            TradeResult(
                status="pending",
                ticker="AAPL",
                side="buy",
                quantity=10,
            )


class TestWatchlistChangeResult:
    def test_applied(self):
        r = WatchlistChangeResult(status="applied", ticker="PYPL", action="add", error=None)
        assert r.status == "applied"

    def test_failed(self):
        r = WatchlistChangeResult(
            status="failed", ticker="PYPL", action="add", error="Already exists"
        )
        assert r.error == "Already exists"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            WatchlistChangeResult(status="applied", ticker="PYPL", action="noop")


class TestActionResults:
    def test_empty_results(self):
        ar = ActionResults()
        assert ar.trades == []
        assert ar.watchlist_changes == []

    def test_with_results(self):
        ar = ActionResults(
            trades=[
                TradeResult(
                    status="executed",
                    ticker="AAPL",
                    side="buy",
                    quantity=10,
                    price=190.0,
                    total=1900.0,
                )
            ],
            watchlist_changes=[
                WatchlistChangeResult(status="applied", ticker="PYPL", action="add")
            ],
        )
        assert len(ar.trades) == 1
        assert len(ar.watchlist_changes) == 1

    def test_serializes_to_json(self):
        ar = ActionResults(
            trades=[
                TradeResult(
                    status="executed",
                    ticker="AAPL",
                    side="buy",
                    quantity=5,
                    price=190.0,
                    total=950.0,
                )
            ]
        )
        raw = ar.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["trades"][0]["ticker"] == "AAPL"
        assert parsed["trades"][0]["status"] == "executed"

    def test_round_trip_json(self):
        ar = ActionResults(
            watchlist_changes=[
                WatchlistChangeResult(status="applied", ticker="TSLA", action="remove")
            ]
        )
        raw = ar.model_dump_json()
        ar2 = ActionResults.model_validate_json(raw)
        assert ar2.watchlist_changes[0].ticker == "TSLA"


# ---------------------------------------------------------------------------
# Mock LLM response parsing
# ---------------------------------------------------------------------------


class TestMockLLMBehavior:
    """Simulate what LLM_MOCK=true would return and verify it parses correctly."""

    MOCK_RESPONSE = {
        "message": "I'm in mock mode. Here's a test response.",
        "trades": [],
        "watchlist_changes": [],
    }

    def test_mock_response_parses(self):
        resp = LLMResponse.model_validate(self.MOCK_RESPONSE)
        assert "mock" in resp.message.lower()
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_mock_response_with_trade(self):
        mock_with_trade = {
            "message": "Mock: buying AAPL.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}],
            "watchlist_changes": [],
        }
        resp = LLMResponse.model_validate(mock_with_trade)
        assert resp.trades[0].ticker == "AAPL"

    def test_mock_response_with_watchlist_change(self):
        mock_with_change = {
            "message": "Mock: adding PYPL to watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
        resp = LLMResponse.model_validate(mock_with_change)
        assert resp.watchlist_changes[0].ticker == "PYPL"


# ---------------------------------------------------------------------------
# Chat message storage tests
# ---------------------------------------------------------------------------


class TestChatMessageStorage:
    """Test that ActionResults can be correctly stored and retrieved as JSON in the DB."""

    def test_actions_json_roundtrip(self):
        ar = ActionResults(
            trades=[
                TradeResult(
                    status="executed",
                    ticker="NVDA",
                    side="buy",
                    quantity=2,
                    price=500.0,
                    total=1000.0,
                )
            ],
            watchlist_changes=[
                WatchlistChangeResult(status="applied", ticker="COIN", action="add")
            ],
        )
        # Store as JSON string (as it would be in DB)
        json_str = ar.model_dump_json()
        # Retrieve and parse
        recovered = ActionResults.model_validate_json(json_str)
        assert recovered.trades[0].ticker == "NVDA"
        assert recovered.trades[0].status == "executed"
        assert recovered.watchlist_changes[0].ticker == "COIN"

    def test_null_actions_acceptable(self):
        """When no actions were taken, actions column is None (null in DB)."""
        # Verify ActionResults with empty lists
        ar = ActionResults()
        assert ar.trades == []
        assert ar.watchlist_changes == []
