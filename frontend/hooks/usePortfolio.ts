import { useState, useEffect, useCallback } from "react";
import { Portfolio, PortfolioSnapshot } from "../types";

export function usePortfolio() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await fetch("/api/portfolio");
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch("/api/portfolio/history");
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch {
      // ignore
    }
  }, []);

  const executeTrade = useCallback(
    async (ticker: string, quantity: number, side: "buy" | "sell") => {
      const res = await fetch("/api/portfolio/trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, quantity, side }),
      });
      const data = await res.json();
      if (res.ok) {
        await fetchPortfolio();
        await fetchHistory();
      }
      return { ok: res.ok, data };
    },
    [fetchPortfolio, fetchHistory]
  );

  useEffect(() => {
    fetchPortfolio();
    fetchHistory();
    // Poll portfolio every 5s
    const interval = setInterval(() => {
      fetchPortfolio();
      fetchHistory();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchPortfolio, fetchHistory]);

  return { portfolio, history, loading, fetchPortfolio, executeTrade };
}
