import React, { useState } from "react";
import { PriceMap } from "../types";

interface TradeBarProps {
  prices: PriceMap;
  selectedTicker: string;
  onTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<{ ok: boolean; data: unknown }>;
  cashBalance: number;
}

export function TradeBar({ prices, selectedTicker, onTrade, cashBalance }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker);
  const [quantity, setQuantity] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  // Sync ticker when selectedTicker changes (but only if user hasn't typed)
  React.useEffect(() => {
    setTicker(selectedTicker);
  }, [selectedTicker]);

  const currentPrice = prices[ticker.toUpperCase()];
  const qty = parseFloat(quantity);
  const estimatedValue = currentPrice && !isNaN(qty) ? qty * currentPrice.price : null;

  const handleTrade = async (side: "buy" | "sell") => {
    if (!ticker || isNaN(qty) || qty <= 0) {
      setMessage({ text: "Enter a valid ticker and quantity", ok: false });
      return;
    }
    setLoading(true);
    setMessage(null);
    const result = await onTrade(ticker.toUpperCase(), qty, side);
    setLoading(false);
    if (result.ok) {
      setMessage({
        text: `${side.toUpperCase()} ${qty} ${ticker.toUpperCase()} executed`,
        ok: true,
      });
      setQuantity("");
    } else {
      const err = (result.data as { detail?: string })?.detail || "Trade failed";
      setMessage({ text: err, ok: false });
    }
    setTimeout(() => setMessage(null), 3000);
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "6px 12px",
        background: "#161b22",
        borderTop: "1px solid #30363d",
        flexShrink: 0,
      }}
    >
      <span style={{ color: "#484f58", fontSize: "10px", fontWeight: 700, letterSpacing: "1px", whiteSpace: "nowrap" }}>
        TRADE
      </span>

      <input
        type="text"
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder="TICKER"
        maxLength={8}
        style={{
          width: "72px",
          background: "#21262d",
          border: "1px solid #30363d",
          borderRadius: "4px",
          color: "#ecad0a",
          padding: "4px 8px",
          fontSize: "12px",
          fontFamily: "inherit",
          fontWeight: 700,
          outline: "none",
          textAlign: "center",
        }}
      />

      <input
        type="number"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Quantity"
        min="0"
        step="1"
        style={{
          width: "90px",
          background: "#21262d",
          border: "1px solid #30363d",
          borderRadius: "4px",
          color: "#e6edf3",
          padding: "4px 8px",
          fontSize: "12px",
          fontFamily: "inherit",
          outline: "none",
        }}
      />

      {currentPrice && (
        <span style={{ color: "#484f58", fontSize: "10px", whiteSpace: "nowrap" }}>
          @${currentPrice.price.toFixed(2)}
          {estimatedValue !== null && (
            <> = ${estimatedValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}</>
          )}
        </span>
      )}

      <button
        onClick={() => handleTrade("buy")}
        disabled={loading}
        style={{
          background: "#1a4731",
          border: "1px solid #3fb950",
          borderRadius: "4px",
          color: "#3fb950",
          padding: "4px 14px",
          fontSize: "11px",
          fontWeight: 700,
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.6 : 1,
          letterSpacing: "0.5px",
          fontFamily: "inherit",
        }}
      >
        BUY
      </button>

      <button
        onClick={() => handleTrade("sell")}
        disabled={loading}
        style={{
          background: "#3d1515",
          border: "1px solid #f85149",
          borderRadius: "4px",
          color: "#f85149",
          padding: "4px 14px",
          fontSize: "11px",
          fontWeight: 700,
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.6 : 1,
          letterSpacing: "0.5px",
          fontFamily: "inherit",
        }}
      >
        SELL
      </button>

      {message && (
        <span
          style={{
            fontSize: "11px",
            color: message.ok ? "#3fb950" : "#f85149",
            marginLeft: "8px",
          }}
        >
          {message.text}
        </span>
      )}

      <span style={{ color: "#484f58", fontSize: "10px", marginLeft: "auto", whiteSpace: "nowrap" }}>
        Cash: ${cashBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
    </div>
  );
}
