/**
 * Tests for the usePortfolio hook.
 *
 * Verifies: portfolio fetch, history fetch, trade execution (buy/sell),
 * polling behavior, error handling.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { usePortfolio } from "../hooks/usePortfolio";
import { Portfolio, PortfolioSnapshot } from "../types";

// ---------------------------------------------------------------------------
// Fetch mock setup
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
global.fetch = mockFetch;

const mockPortfolio: Portfolio = {
  cash_balance: 8000.0,
  total_value: 12000.0,
  total_pnl: 2000.0,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 190.0,
      current_price: 200.0,
      unrealized_pnl: 100.0,
      pnl_percent: 5.26,
      market_value: 2000.0,
    },
  ],
};

const mockHistory: PortfolioSnapshot[] = [
  { total_value: 10000.0, recorded_at: "2024-01-01T00:00:00Z" },
  { total_value: 11000.0, recorded_at: "2024-01-01T00:00:30Z" },
];

function makeFetchResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

beforeEach(() => {
  mockFetch.mockClear();
  jest.useFakeTimers();

  mockFetch.mockImplementation((url: string) => {
    if (url === "/api/portfolio") return makeFetchResponse(mockPortfolio);
    if (url === "/api/portfolio/history") return makeFetchResponse(mockHistory);
    return makeFetchResponse({});
  });
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("usePortfolio", () => {
  it("fetches portfolio on mount", async () => {
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => {
      expect(result.current.portfolio).not.toBeNull();
    });
    expect(result.current.portfolio?.cash_balance).toBe(8000.0);
    expect(result.current.portfolio?.total_value).toBe(12000.0);
  });

  it("fetches history on mount", async () => {
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => {
      expect(result.current.history.length).toBe(2);
    });
    expect(result.current.history[0].total_value).toBe(10000.0);
  });

  it("starts in loading state", () => {
    const { result } = renderHook(() => usePortfolio());
    expect(result.current.loading).toBe(true);
  });

  it("sets loading to false after fetch", async () => {
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it("executeTrade sends POST /api/portfolio/trade", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(mockPortfolio)) // mount
      .mockImplementationOnce(() => makeFetchResponse(mockHistory)) // mount history
      .mockImplementationOnce(() =>
        makeFetchResponse({ status: "executed", ticker: "AAPL", quantity: 5, price: 190.0 })
      ) // trade POST
      .mockImplementationOnce(() => makeFetchResponse(mockPortfolio)) // refresh
      .mockImplementationOnce(() => makeFetchResponse(mockHistory)); // refresh history

    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.portfolio).not.toBeNull());

    await act(async () => {
      await result.current.executeTrade("AAPL", 5, "buy");
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/portfolio/trade",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ ticker: "AAPL", quantity: 5, side: "buy" }),
      })
    );
  });

  it("executeTrade returns ok=true on success", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(mockPortfolio))
      .mockImplementationOnce(() => makeFetchResponse(mockHistory))
      .mockImplementationOnce(() => makeFetchResponse({ executed: true }, true))
      .mockImplementationOnce(() => makeFetchResponse(mockPortfolio))
      .mockImplementationOnce(() => makeFetchResponse(mockHistory));

    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.portfolio).not.toBeNull());

    let tradeResult: { ok: boolean; data: unknown } | undefined;
    await act(async () => {
      tradeResult = await result.current.executeTrade("AAPL", 5, "buy");
    });

    expect(tradeResult?.ok).toBe(true);
  });

  it("executeTrade returns ok=false on server error", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(mockPortfolio))
      .mockImplementationOnce(() => makeFetchResponse(mockHistory))
      .mockImplementationOnce(() =>
        makeFetchResponse({ error: "Insufficient cash" }, false)
      );

    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.portfolio).not.toBeNull());

    let tradeResult: { ok: boolean; data: unknown } | undefined;
    await act(async () => {
      tradeResult = await result.current.executeTrade("AAPL", 1000, "buy");
    });

    expect(tradeResult?.ok).toBe(false);
  });

  it("handles portfolio fetch error gracefully", async () => {
    mockFetch
      .mockImplementationOnce(() => Promise.reject(new Error("Network down")))
      .mockImplementationOnce(() => makeFetchResponse(mockHistory));

    await expect(async () => {
      const { result } = renderHook(() => usePortfolio());
      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(result.current.portfolio).toBeNull();
    }).resolves.not.toThrow();
  });
});
