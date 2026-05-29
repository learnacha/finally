/**
 * Tests for portfolio calculation helper functions.
 *
 * These are pure functions that compute derived values shown in the UI:
 * - Unrealized P&L per position
 * - Portfolio weight (% of total value)
 * - Total portfolio value
 * - P&L percentage
 */

import { Position, Portfolio } from "../types";

// ---------------------------------------------------------------------------
// Helper functions (mirrors what the UI components compute)
// ---------------------------------------------------------------------------

function computeUnrealizedPnl(position: Position): number {
  return (position.current_price - position.avg_cost) * position.quantity;
}

function computePnlPercent(position: Position): number {
  if (position.avg_cost === 0) return 0;
  return ((position.current_price - position.avg_cost) / position.avg_cost) * 100;
}

function computeMarketValue(position: Position): number {
  return position.current_price * position.quantity;
}

function computePortfolioWeight(position: Position, totalValue: number): number {
  if (totalValue === 0) return 0;
  return (computeMarketValue(position) / totalValue) * 100;
}

function computeTotalPortfolioValue(portfolio: Portfolio): number {
  const positionsValue = portfolio.positions.reduce(
    (sum, p) => sum + computeMarketValue(p),
    0
  );
  return portfolio.cash_balance + positionsValue;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const makePosition = (overrides: Partial<Position> = {}): Position => ({
  ticker: "AAPL",
  quantity: 10,
  avg_cost: 190.0,
  current_price: 200.0,
  unrealized_pnl: 100.0,
  pnl_percent: 5.26,
  market_value: 2000.0,
  ...overrides,
});

describe("Portfolio calculations", () => {
  describe("unrealized P&L", () => {
    it("calculates positive P&L correctly", () => {
      const pos = makePosition({ avg_cost: 190, current_price: 200, quantity: 10 });
      expect(computeUnrealizedPnl(pos)).toBeCloseTo(100.0);
    });

    it("calculates negative P&L correctly", () => {
      const pos = makePosition({ avg_cost: 200, current_price: 190, quantity: 10 });
      expect(computeUnrealizedPnl(pos)).toBeCloseTo(-100.0);
    });

    it("returns 0 when price equals avg cost", () => {
      const pos = makePosition({ avg_cost: 190, current_price: 190, quantity: 10 });
      expect(computeUnrealizedPnl(pos)).toBe(0);
    });

    it("handles fractional shares", () => {
      const pos = makePosition({ avg_cost: 100, current_price: 110, quantity: 0.5 });
      expect(computeUnrealizedPnl(pos)).toBeCloseTo(5.0);
    });
  });

  describe("P&L percentage", () => {
    it("calculates positive percentage gain", () => {
      const pos = makePosition({ avg_cost: 100, current_price: 110, quantity: 10 });
      expect(computePnlPercent(pos)).toBeCloseTo(10.0);
    });

    it("calculates negative percentage loss", () => {
      const pos = makePosition({ avg_cost: 100, current_price: 90, quantity: 10 });
      expect(computePnlPercent(pos)).toBeCloseTo(-10.0);
    });

    it("returns 0% when avg_cost is 0 (avoid division by zero)", () => {
      const pos = makePosition({ avg_cost: 0, current_price: 100, quantity: 10 });
      expect(computePnlPercent(pos)).toBe(0);
    });
  });

  describe("market value", () => {
    it("calculates market value as price * quantity", () => {
      const pos = makePosition({ current_price: 200, quantity: 10 });
      expect(computeMarketValue(pos)).toBe(2000);
    });

    it("handles fractional quantities", () => {
      const pos = makePosition({ current_price: 200, quantity: 0.5 });
      expect(computeMarketValue(pos)).toBe(100);
    });
  });

  describe("portfolio weight", () => {
    it("calculates weight as fraction of total portfolio value", () => {
      const pos = makePosition({ current_price: 100, quantity: 50 }); // $5000
      const weight = computePortfolioWeight(pos, 10000);
      expect(weight).toBe(50);
    });

    it("returns 0 when total value is 0", () => {
      const pos = makePosition();
      expect(computePortfolioWeight(pos, 0)).toBe(0);
    });

    it("all weights sum to 100% for a fully-invested portfolio", () => {
      const positions = [
        makePosition({ ticker: "AAPL", current_price: 100, quantity: 50 }), // $5000
        makePosition({ ticker: "GOOGL", current_price: 50, quantity: 100 }), // $5000
      ];
      const total = 10000;
      const totalWeight = positions.reduce(
        (sum, p) => sum + computePortfolioWeight(p, total),
        0
      );
      expect(totalWeight).toBeCloseTo(100);
    });
  });

  describe("total portfolio value", () => {
    it("sums cash balance and all positions", () => {
      const portfolio: Portfolio = {
        cash_balance: 5000,
        total_value: 12000,
        total_pnl: 2000,
        positions: [
          makePosition({ current_price: 200, quantity: 10 }), // $2000
          makePosition({ ticker: "GOOGL", current_price: 500, quantity: 10 }), // $5000
        ],
      };
      expect(computeTotalPortfolioValue(portfolio)).toBe(12000);
    });

    it("equals cash balance when no positions", () => {
      const portfolio: Portfolio = {
        cash_balance: 10000,
        total_value: 10000,
        total_pnl: 0,
        positions: [],
      };
      expect(computeTotalPortfolioValue(portfolio)).toBe(10000);
    });
  });

  describe("change_percent display formatting", () => {
    it("formats positive change with + prefix", () => {
      const change = 2.345;
      const formatted = (change >= 0 ? "+" : "") + change.toFixed(2) + "%";
      expect(formatted).toBe("+2.35%");
    });

    it("formats negative change without extra minus", () => {
      const change = -1.234;
      const formatted = (change >= 0 ? "+" : "") + change.toFixed(2) + "%";
      expect(formatted).toBe("-1.23%");
    });

    it("formats zero change as +0.00%", () => {
      const change = 0;
      const formatted = (change >= 0 ? "+" : "") + change.toFixed(2) + "%";
      expect(formatted).toBe("+0.00%");
    });
  });
});
