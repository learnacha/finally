/**
 * Tests for the useWatchlist hook.
 *
 * Verifies: initial fetch, add ticker, remove ticker, deduplication prevention,
 * graceful error handling.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { useWatchlist } from "../hooks/useWatchlist";

// ---------------------------------------------------------------------------
// Fetch mock setup
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
global.fetch = mockFetch;

function makeFetchResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

const defaultWatchlist = [
  { ticker: "AAPL", price: 190.0, change_percent: 0.5 },
  { ticker: "GOOGL", price: 175.0, change_percent: -0.2 },
];

beforeEach(() => {
  mockFetch.mockClear();
  mockFetch.mockImplementation((url: string) => {
    if (url === "/api/watchlist") {
      return makeFetchResponse(defaultWatchlist);
    }
    return makeFetchResponse({});
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWatchlist", () => {
  it("fetches watchlist on mount", async () => {
    const { result } = renderHook(() => useWatchlist());
    await waitFor(() => {
      expect(result.current.watchlist.length).toBe(2);
    });
    expect(mockFetch).toHaveBeenCalledWith("/api/watchlist");
  });

  it("returns correct ticker symbols", async () => {
    const { result } = renderHook(() => useWatchlist());
    await waitFor(() => {
      expect(result.current.watchlist.length).toBe(2);
    });
    const tickers = result.current.watchlist.map((w) => w.ticker);
    expect(tickers).toContain("AAPL");
    expect(tickers).toContain("GOOGL");
  });

  it("addTicker calls POST /api/watchlist and refreshes", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(defaultWatchlist)) // initial load
      .mockImplementationOnce(() => makeFetchResponse({}, true)) // POST
      .mockImplementationOnce(() =>
        makeFetchResponse([...defaultWatchlist, { ticker: "TSLA", price: 200 }])
      ); // refresh

    const { result } = renderHook(() => useWatchlist());
    await waitFor(() => {
      expect(result.current.watchlist.length).toBe(2);
    });

    await act(async () => {
      await result.current.addTicker("TSLA");
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/watchlist", expect.objectContaining({
      method: "POST",
    }));

    await waitFor(() => {
      expect(result.current.watchlist.length).toBe(3);
    });
  });

  it("addTicker returns true on success", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(defaultWatchlist))
      .mockImplementationOnce(() => makeFetchResponse({}, true))
      .mockImplementationOnce(() => makeFetchResponse(defaultWatchlist));

    const { result } = renderHook(() => useWatchlist());
    await waitFor(() => expect(result.current.watchlist.length).toBe(2));

    let success: boolean | undefined;
    await act(async () => {
      success = await result.current.addTicker("TSLA");
    });
    expect(success).toBe(true);
  });

  it("addTicker returns false on server error", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(defaultWatchlist))
      .mockImplementationOnce(() => makeFetchResponse({}, false)); // 409 or error

    const { result } = renderHook(() => useWatchlist());
    await waitFor(() => expect(result.current.watchlist.length).toBe(2));

    let success: boolean | undefined;
    await act(async () => {
      success = await result.current.addTicker("AAPL"); // duplicate
    });
    expect(success).toBe(false);
  });

  it("removeTicker calls DELETE and refreshes", async () => {
    mockFetch
      .mockImplementationOnce(() => makeFetchResponse(defaultWatchlist))
      .mockImplementationOnce(() => makeFetchResponse({}, true)) // DELETE
      .mockImplementationOnce(() =>
        makeFetchResponse([{ ticker: "GOOGL", price: 175.0, change_percent: -0.2 }])
      ); // refresh

    const { result } = renderHook(() => useWatchlist());
    await waitFor(() => expect(result.current.watchlist.length).toBe(2));

    await act(async () => {
      await result.current.removeTicker("AAPL");
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/watchlist/AAPL", expect.objectContaining({
      method: "DELETE",
    }));

    await waitFor(() => {
      expect(result.current.watchlist.length).toBe(1);
    });
  });

  it("handles fetch error gracefully without throwing", async () => {
    mockFetch.mockImplementationOnce(() => Promise.reject(new Error("Network error")));

    // Should not throw
    await expect(async () => {
      const { result } = renderHook(() => useWatchlist());
      await waitFor(() => {
        // watchlist stays empty on error
        expect(result.current.watchlist).toEqual([]);
      });
    }).resolves.not.toThrow();
  });
});
