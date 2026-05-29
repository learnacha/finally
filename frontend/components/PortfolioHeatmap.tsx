import React, { useMemo } from "react";
import { Position } from "../types";

interface PortfolioHeatmapProps {
  positions: Position[];
}

interface TreemapNode {
  ticker: string;
  value: number;
  pnlPercent: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

function computeTreemap(
  items: { ticker: string; value: number; pnlPercent: number }[],
  x: number,
  y: number,
  w: number,
  h: number
): TreemapNode[] {
  if (items.length === 0) return [];

  const total = items.reduce((s, i) => s + i.value, 0);
  if (total === 0) return [];

  const result: TreemapNode[] = [];

  // Simple squarified-like layout: split into two halves
  type Item = { ticker: string; value: number; pnlPercent: number };
  function layout(
    items: Item[],
    x: number,
    y: number,
    w: number,
    h: number
  ) {
    if (items.length === 0) return;
    if (items.length === 1) {
      result.push({ ...items[0], x, y, w, h });
      return;
    }

    const total = items.reduce((s, i) => s + i.value, 0);
    let half = 0;
    let splitIdx = 0;
    for (let i = 0; i < items.length; i++) {
      half += items[i].value;
      if (half >= total / 2) {
        splitIdx = i + 1;
        break;
      }
    }
    if (splitIdx === 0) splitIdx = 1;
    if (splitIdx >= items.length) splitIdx = items.length - 1;

    const leftSum = items.slice(0, splitIdx).reduce((s, i) => s + i.value, 0);
    const ratio = leftSum / total;

    if (w >= h) {
      // Split horizontally
      layout(items.slice(0, splitIdx), x, y, w * ratio, h);
      layout(items.slice(splitIdx), x + w * ratio, y, w * (1 - ratio), h);
    } else {
      // Split vertically
      layout(items.slice(0, splitIdx), x, y, w, h * ratio);
      layout(items.slice(splitIdx), x, y + h * ratio, w, h * (1 - ratio));
    }
  }

  layout(items, x, y, w, h);
  return result;
}

function pnlToColor(pnlPercent: number): string {
  if (Math.abs(pnlPercent) < 0.5) return "#2d3748";
  if (pnlPercent > 0) {
    const intensity = Math.min(pnlPercent / 10, 1);
    const g = Math.round(80 + intensity * 105);
    return `rgb(0, ${g}, 40)`;
  } else {
    const intensity = Math.min(-pnlPercent / 10, 1);
    const r = Math.round(100 + intensity * 148);
    return `rgb(${r}, 0, 0)`;
  }
}

export function PortfolioHeatmap({ positions }: PortfolioHeatmapProps) {
  const items = useMemo(
    () =>
      positions
        .filter((p) => p.market_value > 0)
        .sort((a, b) => b.market_value - a.market_value)
        .map((p) => ({
          ticker: p.ticker,
          value: p.market_value,
          pnlPercent: p.pnl_percent,
        })),
    [positions]
  );

  const nodes = useMemo(
    () => computeTreemap(items, 0, 0, 100, 100),
    [items]
  );

  if (positions.length === 0 || items.length === 0) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "#484f58", fontSize: "12px" }}>No positions</span>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: "4px 12px 8px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ flex: 1, position: "relative" }}>
        {nodes.map((node) => {
          const gap = 2;
          return (
            <div
              key={node.ticker}
              style={{
                position: "absolute",
                left: `${node.x}%`,
                top: `${node.y}%`,
                width: `calc(${node.w}% - ${gap}px)`,
                height: `calc(${node.h}% - ${gap}px)`,
                background: pnlToColor(node.pnlPercent),
                border: "1px solid #30363d",
                borderRadius: "3px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden",
                cursor: "default",
              }}
              title={`${node.ticker}: ${node.pnlPercent >= 0 ? "+" : ""}${node.pnlPercent.toFixed(2)}%`}
            >
              {node.w > 8 && node.h > 6 && (
                <>
                  <span
                    style={{
                      color: "#e6edf3",
                      fontSize: Math.max(9, Math.min(14, node.w * 0.8)) + "px",
                      fontWeight: 700,
                    }}
                  >
                    {node.ticker}
                  </span>
                  {node.h > 10 && (
                    <span
                      style={{
                        color: node.pnlPercent >= 0 ? "#3fb950" : "#f85149",
                        fontSize: Math.max(8, Math.min(11, node.w * 0.6)) + "px",
                      }}
                    >
                      {node.pnlPercent >= 0 ? "+" : ""}
                      {node.pnlPercent.toFixed(1)}%
                    </span>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
