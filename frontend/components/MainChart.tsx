import React, { useRef, useEffect } from "react";
import { PriceMap } from "../types";

interface MainChartProps {
  ticker: string;
  priceHistory: { [ticker: string]: { time: number; price: number }[] };
  prices: PriceMap;
}

export function MainChart({ ticker, priceHistory, prices }: MainChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const data = priceHistory[ticker] || [];
  const currentPrice = prices[ticker];

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = container.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, w, h);

    if (data.length < 2) {
      ctx.fillStyle = "#484f58";
      ctx.font = "12px monospace";
      ctx.textAlign = "center";
      ctx.fillText("Waiting for price data...", w / 2, h / 2);
      return;
    }

    const prices_ = data.map((d) => d.price);
    const min = Math.min(...prices_);
    const max = Math.max(...prices_);
    const range = max - min || 1;

    const padL = 60;
    const padR = 16;
    const padT = 24;
    const padB = 32;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    // Determine color based on overall trend
    const isUp = prices_[prices_.length - 1] >= prices_[0];
    const lineColor = isUp ? "#3fb950" : "#f85149";

    // Draw grid lines
    const gridCount = 4;
    ctx.strokeStyle = "#21262d";
    ctx.lineWidth = 1;
    for (let i = 0; i <= gridCount; i++) {
      const y = padT + (i / gridCount) * plotH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + plotW, y);
      ctx.stroke();

      // Y-axis labels
      const price = max - (i / gridCount) * range;
      ctx.fillStyle = "#484f58";
      ctx.font = "10px monospace";
      ctx.textAlign = "right";
      ctx.fillText(`$${price.toFixed(2)}`, padL - 4, y + 3);
    }

    // Draw X-axis time labels (show first, middle, last)
    ctx.fillStyle = "#484f58";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    const timeIndices = [0, Math.floor(data.length / 2), data.length - 1];
    for (const idx of timeIndices) {
      const x = padL + (idx / (data.length - 1)) * plotW;
      const t = new Date(data[idx].time);
      const label = `${t.getHours().toString().padStart(2, "0")}:${t.getMinutes().toString().padStart(2, "0")}:${t.getSeconds().toString().padStart(2, "0")}`;
      ctx.fillText(label, x, h - 8);
    }

    // Draw the price line
    ctx.beginPath();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    for (let i = 0; i < data.length; i++) {
      const x = padL + (i / (data.length - 1)) * plotW;
      const y = padT + ((max - data[i].price) / range) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill area
    ctx.lineTo(padL + plotW, padT + plotH);
    ctx.lineTo(padL, padT + plotH);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, padT, 0, padT + plotH);
    gradient.addColorStop(0, lineColor + "30");
    gradient.addColorStop(1, lineColor + "05");
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw current price line
    if (data.length > 0) {
      const lastPrice = data[data.length - 1].price;
      const y = padT + ((max - lastPrice) / range) * plotH;
      ctx.strokeStyle = "#ecad0a";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + plotW, y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Price label on right
      ctx.fillStyle = "#ecad0a";
      ctx.font = "bold 10px monospace";
      ctx.textAlign = "left";
      ctx.fillText(`$${lastPrice.toFixed(2)}`, padL + plotW + 2, y + 3);
    }
  }, [data, ticker]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      <div
        style={{
          padding: "8px 12px",
          borderBottom: "1px solid #30363d",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          flexShrink: 0,
        }}
      >
        <span style={{ color: "#ecad0a", fontSize: "14px", fontWeight: 700 }}>{ticker}</span>
        {currentPrice && (
          <>
            <span
              style={{
                color: currentPrice.direction === "up" ? "#3fb950" : currentPrice.direction === "down" ? "#f85149" : "#e6edf3",
                fontSize: "18px",
                fontWeight: 600,
              }}
            >
              ${currentPrice.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span
              style={{
                color: currentPrice.change >= 0 ? "#3fb950" : "#f85149",
                fontSize: "12px",
              }}
            >
              {currentPrice.change >= 0 ? "+" : ""}
              {currentPrice.change.toFixed(2)} ({currentPrice.change_percent >= 0 ? "+" : ""}
              {currentPrice.change_percent.toFixed(2)}%)
            </span>
          </>
        )}
        <span style={{ color: "#484f58", fontSize: "10px", marginLeft: "auto" }}>
          {data.length} data points
        </span>
      </div>
      <div ref={containerRef} style={{ flex: 1, position: "relative" }}>
        <canvas ref={canvasRef} style={{ position: "absolute", inset: 0 }} />
      </div>
    </div>
  );
}
