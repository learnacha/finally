import { useEffect, useRef, useState, useCallback } from "react";
import { PriceMap, ConnectionStatus } from "../types";

export interface SSEState {
  prices: PriceMap;
  connectionStatus: ConnectionStatus;
  priceHistory: { [ticker: string]: { time: number; price: number }[] };
}

export function useSSE() {
  const [prices, setPrices] = useState<PriceMap>({});
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [priceHistory, setPriceHistory] = useState<{ [ticker: string]: { time: number; price: number }[] }>({});
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    setConnectionStatus("connecting");
    const es = new EventSource("/api/stream/prices");
    esRef.current = es;

    es.onopen = () => {
      setConnectionStatus("connected");
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as PriceMap;
        setPrices(data);

        // Update price history for sparklines / main chart
        setPriceHistory((prev) => {
          const now = Date.now();
          const updated = { ...prev };
          for (const ticker of Object.keys(data)) {
            const entry = data[ticker];
            const existing = updated[ticker] || [];
            updated[ticker] = [
              ...existing.slice(-300), // keep last 300 points
              { time: now, price: entry.price },
            ];
          }
          return updated;
        });
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setConnectionStatus("disconnected");
      // EventSource auto-reconnects; update status when it tries again
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
    };
  }, [connect]);

  return { prices, connectionStatus, priceHistory };
}
