"""Tests for GBMSimulator."""

from app.market.seed_prices import SEED_PRICES
from app.market.simulator import GBMSimulator


class TestGBMSimulator:

    def test_step_returns_all_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        result = sim.step()
        assert set(result.keys()) == {"AAPL", "GOOGL"}

    def test_prices_are_positive(self):
        sim = GBMSimulator(tickers=["AAPL"])
        for _ in range(1000):
            assert sim.step()["AAPL"] > 0

    def test_initial_prices_match_seeds(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_add_remove_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("TSLA")
        assert "TSLA" in sim.step()
        sim.remove_ticker("TSLA")
        assert "TSLA" not in sim.step()

    def test_empty_step(self):
        assert GBMSimulator(tickers=[]).step() == {}

    def test_prices_change_over_time(self):
        sim = GBMSimulator(tickers=["AAPL"])
        initial = sim.get_price("AAPL")
        for _ in range(100):
            sim.step()
        assert sim.get_price("AAPL") != initial

    def test_pairwise_correlation_tech(self):
        assert GBMSimulator._pairwise_correlation("AAPL", "GOOGL") == 0.6

    def test_pairwise_correlation_finance(self):
        assert GBMSimulator._pairwise_correlation("JPM", "V") == 0.5

    def test_pairwise_correlation_tsla(self):
        assert GBMSimulator._pairwise_correlation("TSLA", "AAPL") == 0.3
