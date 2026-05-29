import React from "react";
import { ConnectionStatus, Portfolio } from "../types";

interface HeaderProps {
  portfolio: Portfolio | null;
  connectionStatus: ConnectionStatus;
}

export function Header({ portfolio, connectionStatus }: HeaderProps) {
  const statusColor =
    connectionStatus === "connected"
      ? "#3fb950"
      : connectionStatus === "connecting"
      ? "#ecad0a"
      : "#f85149";

  const statusLabel =
    connectionStatus === "connected"
      ? "LIVE"
      : connectionStatus === "connecting"
      ? "CONNECTING"
      : "DISCONNECTED";

  const totalValue = portfolio?.total_value ?? 0;
  const cashBalance = portfolio?.cash ?? 0;
  const totalPnl = portfolio?.total_unrealized_pnl ?? 0;
  const pnlColor = totalPnl >= 0 ? "#3fb950" : "#f85149";
  const pnlSign = totalPnl >= 0 ? "+" : "";

  return (
    <header
      style={{
        background: "#161b22",
        borderBottom: "1px solid #30363d",
        padding: "0 16px",
        height: "48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <span
          style={{
            color: "#ecad0a",
            fontWeight: 700,
            fontSize: "18px",
            letterSpacing: "2px",
          }}
        >
          FIN
        </span>
        <span
          style={{
            color: "#209dd7",
            fontWeight: 700,
            fontSize: "18px",
            letterSpacing: "2px",
          }}
        >
          ALLY
        </span>
        <span
          style={{
            color: "#484f58",
            fontSize: "11px",
            marginLeft: "4px",
          }}
        >
          AI TRADING WORKSTATION
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <span style={{ color: "#484f58", fontSize: "10px", textTransform: "uppercase" }}>
            Portfolio Value
          </span>
          <span style={{ color: "#e6edf3", fontSize: "16px", fontWeight: 600 }}>
            ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div
          style={{
            width: "1px",
            height: "28px",
            background: "#30363d",
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <span style={{ color: "#484f58", fontSize: "10px", textTransform: "uppercase" }}>
            Cash
          </span>
          <span style={{ color: "#e6edf3", fontSize: "14px" }}>
            ${cashBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div
          style={{
            width: "1px",
            height: "28px",
            background: "#30363d",
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <span style={{ color: "#484f58", fontSize: "10px", textTransform: "uppercase" }}>
            P&amp;L
          </span>
          <span style={{ color: pnlColor, fontSize: "14px", fontWeight: 600 }}>
            {pnlSign}${Math.abs(totalPnl).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div
          style={{
            width: "1px",
            height: "28px",
            background: "#30363d",
          }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: statusColor,
              boxShadow: `0 0 6px ${statusColor}`,
            }}
          />
          <span style={{ color: statusColor, fontSize: "10px", fontWeight: 600 }}>
            {statusLabel}
          </span>
        </div>
      </div>
    </header>
  );
}
