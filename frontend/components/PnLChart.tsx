import React, { useRef, useEffect } from "react";
import { PortfolioSnapshot } from "../types";

interface PnLChartProps {
  history: PortfolioSnapshot[];
}

export function PnLChart({ history }: PnLChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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

    if (history.length < 2) {
      ctx.fillStyle = "#484f58";
      ctx.font = "11px monospace";
      ctx.textAlign = "center";
      ctx.fillText("P&L history will appear after trades", w / 2, h / 2);
      return;
    }

    const values = history.map((s) => s.total_value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const padL = 55;
    const padR = 8;
    const padT = 12;
    const padB = 24;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    const isUp = values[values.length - 1] >= values[0];
    const lineColor = isUp ? "#3fb950" : "#f85149";

    // Grid
    ctx.strokeStyle = "#21262d";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const y = padT + (i / 3) * plotH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + plotW, y);
      ctx.stroke();

      const val = max - (i / 3) * range;
      ctx.fillStyle = "#484f58";
      ctx.font = "9px monospace";
      ctx.textAlign = "right";
      ctx.fillText(`$${val >= 1000 ? (val / 1000).toFixed(1) + "k" : val.toFixed(0)}`, padL - 4, y + 3);
    }

    // Time labels
    ctx.fillStyle = "#484f58";
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    if (history.length >= 2) {
      const first = new Date(history[0].recorded_at);
      const last = new Date(history[history.length - 1].recorded_at);
      ctx.fillText(
        `${first.getHours().toString().padStart(2,"0")}:${first.getMinutes().toString().padStart(2,"0")}`,
        padL,
        h - 6
      );
      ctx.fillText(
        `${last.getHours().toString().padStart(2,"0")}:${last.getMinutes().toString().padStart(2,"0")}`,
        padL + plotW,
        h - 6
      );
    }

    // Line
    ctx.beginPath();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    for (let i = 0; i < values.length; i++) {
      const x = padL + (i / (values.length - 1)) * plotW;
      const y = padT + ((max - values[i]) / range) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill
    ctx.lineTo(padL + plotW, padT + plotH);
    ctx.lineTo(padL, padT + plotH);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, padT, 0, padT + plotH);
    gradient.addColorStop(0, lineColor + "40");
    gradient.addColorStop(1, lineColor + "05");
    ctx.fillStyle = gradient;
    ctx.fill();
  }, [history]);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      <canvas ref={canvasRef} style={{ position: "absolute", inset: 0 }} />
    </div>
  );
}
