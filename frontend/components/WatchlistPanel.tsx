import React, { useState, useEffect, useRef } from "react";
import { PriceMap, WatchlistEntry } from "../types";
import { Sparkline } from "./Sparkline";

interface WatchlistPanelProps {
  watchlist: WatchlistEntry[];
  prices: PriceMap;
  priceHistory: { [ticker: string]: { time: number; price: number }[] };
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  onAddTicker: (ticker: string) => Promise<boolean>;
  onRemoveTicker: (ticker: string) => Promise<boolean>;
}

function PriceCell({
  ticker,
  price,
  direction,
}: {
  ticker: string;
  price: number | undefined;
  direction: "up" | "down" | "unchanged" | undefined;
}) {
  const [flashClass, setFlashClass] = useState("");
  const prevPriceRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (price === undefined) return;
    if (prevPriceRef.current !== undefined && prevPriceRef.current !== price) {
      const cls = direction === "up" ? "price-flash-up" : direction === "down" ? "price-flash-down" : "";
      if (cls) {
        setFlashClass(cls);
        const timer = setTimeout(() => setFlashClass(""), 600);
        return () => clearTimeout(timer);
      }
    }
    prevPriceRef.current = price;
  }, [price, direction]);

  const priceColor =
    direction === "up"
      ? "#3fb950"
      : direction === "down"
      ? "#f85149"
      : "#e6edf3";

  return (
    <span
      className={flashClass}
      style={{
        color: priceColor,
        fontWeight: 600,
        padding: "1px 4px",
        borderRadius: "3px",
        transition: "color 0.3s",
      }}
    >
      {price !== undefined
        ? `$${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : "—"}
    </span>
  );
}

export function WatchlistPanel({
  watchlist,
  prices,
  priceHistory,
  selectedTicker,
  onSelectTicker,
  onAddTicker,
  onRemoveTicker,
}: WatchlistPanelProps) {
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    setAdding(true);
    await onAddTicker(t);
    setNewTicker("");
    setAdding(false);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "8px 12px",
          borderBottom: "1px solid #30363d",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <span style={{ color: "#ecad0a", fontSize: "11px", fontWeight: 700, letterSpacing: "1px" }}>
          WATCHLIST
        </span>
        <span style={{ color: "#484f58", fontSize: "10px" }}>{watchlist.length} tickers</span>
      </div>

      {/* Column headers */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "52px 1fr 64px 80px 20px",
          padding: "4px 12px",
          borderBottom: "1px solid #21262d",
          flexShrink: 0,
        }}
      >
        {["TICKER", "PRICE", "CHG%", "CHART", ""].map((h) => (
          <span key={h} style={{ color: "#484f58", fontSize: "9px", letterSpacing: "0.5px" }}>
            {h}
          </span>
        ))}
      </div>

      {/* Watchlist rows */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {watchlist.map((entry) => {
          const priceData = prices[entry.ticker];
          const history = priceHistory[entry.ticker] || [];
          const isSelected = selectedTicker === entry.ticker;
          const changePct = priceData?.change_percent;
          const pctColor = changePct === undefined ? "#484f58" : changePct >= 0 ? "#3fb950" : "#f85149";
          const pctStr =
            changePct === undefined
              ? "—"
              : `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;

          return (
            <div
              key={entry.ticker}
              onClick={() => onSelectTicker(entry.ticker)}
              style={{
                display: "grid",
                gridTemplateColumns: "52px 1fr 64px 80px 20px",
                padding: "5px 12px",
                cursor: "pointer",
                background: isSelected ? "#21262d" : "transparent",
                borderLeft: isSelected ? "2px solid #209dd7" : "2px solid transparent",
                borderBottom: "1px solid #21262d",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  color: isSelected ? "#209dd7" : "#e6edf3",
                  fontSize: "12px",
                  fontWeight: 700,
                }}
              >
                {entry.ticker}
              </span>
              <PriceCell
                ticker={entry.ticker}
                price={priceData?.price}
                direction={priceData?.direction}
              />
              <span style={{ color: pctColor, fontSize: "11px" }}>{pctStr}</span>
              <div>
                {history.length >= 2 ? (
                  <Sparkline
                    data={history}
                    width={76}
                    height={24}
                    positive={changePct !== undefined ? changePct >= 0 : undefined}
                  />
                ) : (
                  <div style={{ width: 76, height: 24 }} />
                )}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveTicker(entry.ticker);
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#484f58",
                  cursor: "pointer",
                  padding: "0",
                  fontSize: "14px",
                  lineHeight: 1,
                }}
                title="Remove"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>

      {/* Add ticker form */}
      <form
        onSubmit={handleAdd}
        style={{
          padding: "8px 12px",
          borderTop: "1px solid #30363d",
          display: "flex",
          gap: "6px",
          flexShrink: 0,
        }}
      >
        <input
          type="text"
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          placeholder="Add ticker..."
          maxLength={8}
          style={{
            flex: 1,
            background: "#21262d",
            border: "1px solid #30363d",
            borderRadius: "4px",
            color: "#e6edf3",
            padding: "4px 8px",
            fontSize: "11px",
            fontFamily: "inherit",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={adding || !newTicker.trim()}
          style={{
            background: "#209dd7",
            border: "none",
            borderRadius: "4px",
            color: "#0d1117",
            padding: "4px 10px",
            fontSize: "11px",
            fontWeight: 700,
            cursor: "pointer",
            opacity: adding || !newTicker.trim() ? 0.5 : 1,
          }}
        >
          +
        </button>
      </form>
    </div>
  );
}
