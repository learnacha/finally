import React from "react";
import { Position } from "../types";

interface PositionsTableProps {
  positions: Position[];
}

export function PositionsTable({ positions }: PositionsTableProps) {
  if (positions.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
        }}
      >
        <span style={{ color: "#484f58", fontSize: "12px" }}>No open positions</span>
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto", height: "100%" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "11px",
        }}
      >
        <thead>
          <tr style={{ borderBottom: "1px solid #30363d" }}>
            {["TICKER", "QTY", "AVG COST", "CURRENT", "MKT VALUE", "UNRLZD P&L", "CHG%"].map((h) => (
              <th
                key={h}
                style={{
                  color: "#484f58",
                  textAlign: h === "TICKER" ? "left" : "right",
                  padding: "4px 8px",
                  fontWeight: 600,
                  letterSpacing: "0.5px",
                  fontSize: "9px",
                  whiteSpace: "nowrap",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => {
            const pnlColor = pos.unrealized_pnl >= 0 ? "#3fb950" : "#f85149";
            const pnlSign = pos.unrealized_pnl >= 0 ? "+" : "";

            return (
              <tr
                key={pos.ticker}
                style={{
                  borderBottom: "1px solid #21262d",
                }}
              >
                <td
                  style={{
                    color: "#209dd7",
                    fontWeight: 700,
                    padding: "5px 8px",
                  }}
                >
                  {pos.ticker}
                </td>
                <td style={{ color: "#e6edf3", textAlign: "right", padding: "5px 8px" }}>
                  {pos.quantity % 1 === 0 ? pos.quantity.toFixed(0) : pos.quantity.toFixed(4)}
                </td>
                <td style={{ color: "#e6edf3", textAlign: "right", padding: "5px 8px" }}>
                  ${pos.avg_cost.toFixed(2)}
                </td>
                <td style={{ color: "#e6edf3", textAlign: "right", padding: "5px 8px" }}>
                  ${pos.current_price.toFixed(2)}
                </td>
                <td style={{ color: "#e6edf3", textAlign: "right", padding: "5px 8px" }}>
                  ${pos.market_value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
                <td
                  style={{
                    color: pnlColor,
                    fontWeight: 600,
                    textAlign: "right",
                    padding: "5px 8px",
                  }}
                >
                  {pnlSign}${Math.abs(pos.unrealized_pnl).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
                <td
                  style={{
                    color: pnlColor,
                    textAlign: "right",
                    padding: "5px 8px",
                  }}
                >
                  {pos.pnl_percent >= 0 ? "+" : ""}
                  {pos.pnl_percent.toFixed(2)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
