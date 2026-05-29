import { useState, useEffect, useCallback } from "react";
import { WatchlistEntry } from "../types";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch("/api/watchlist");
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data);
      }
    } catch {
      // ignore
    }
  }, []);

  const addTicker = useCallback(
    async (ticker: string) => {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker }),
      });
      if (res.ok) {
        await fetchWatchlist();
      }
      return res.ok;
    },
    [fetchWatchlist]
  );

  const removeTicker = useCallback(
    async (ticker: string) => {
      const res = await fetch(`/api/watchlist/${ticker}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await fetchWatchlist();
      }
      return res.ok;
    },
    [fetchWatchlist]
  );

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  return { watchlist, fetchWatchlist, addTicker, removeTicker };
}
