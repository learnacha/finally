import React, { useState } from "react";
import type { NextPage } from "next";
import Head from "next/head";
import { Header } from "../components/Header";
import { WatchlistPanel } from "../components/WatchlistPanel";
import { MainChart } from "../components/MainChart";
import { PortfolioHeatmap } from "../components/PortfolioHeatmap";
import { PnLChart } from "../components/PnLChart";
import { PositionsTable } from "../components/PositionsTable";
import { TradeBar } from "../components/TradeBar";
import { ChatPanel } from "../components/ChatPanel";
import { useSSE } from "../hooks/useSSE";
import { usePortfolio } from "../hooks/usePortfolio";
import { useWatchlist } from "../hooks/useWatchlist";

type BottomTab = "positions" | "heatmap" | "pnl";

const Home: NextPage = () => {
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [chatOpen, setChatOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>("positions");

  const { prices, connectionStatus, priceHistory } = useSSE();
  const { portfolio, history, fetchPortfolio, executeTrade } = usePortfolio();
  const { watchlist, fetchWatchlist, addTicker, removeTicker } = useWatchlist();

  const positions = portfolio?.positions || [];

  const tabStyle = (active: boolean) => ({
    padding: "4px 12px",
    fontSize: "10px",
    fontWeight: 700 as const,
    letterSpacing: "0.5px",
    cursor: "pointer",
    background: "none",
    border: "none",
    borderBottom: active ? "2px solid #209dd7" : "2px solid transparent",
    color: active ? "#209dd7" : "#484f58",
    fontFamily: "inherit",
  });

  return (
    <>
      <Head>
        <title>FinAlly — AI Trading Workstation</title>
        <meta name="description" content="AI-powered trading workstation" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          background: "#0d1117",
          color: "#e6edf3",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <Header portfolio={portfolio} connectionStatus={connectionStatus} />

        {/* Main content area */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* Left: Watchlist */}
          <div
            style={{
              width: "280px",
              flexShrink: 0,
              borderRight: "1px solid #30363d",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <WatchlistPanel
              watchlist={watchlist}
              prices={prices}
              priceHistory={priceHistory}
              selectedTicker={selectedTicker}
              onSelectTicker={setSelectedTicker}
              onAddTicker={addTicker}
              onRemoveTicker={removeTicker}
            />
          </div>

          {/* Center + right columns */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* Top: Main chart */}
            <div
              style={{
                flex: "0 0 55%",
                borderBottom: "1px solid #30363d",
                overflow: "hidden",
              }}
            >
              <MainChart
                ticker={selectedTicker}
                priceHistory={priceHistory}
                prices={prices}
              />
            </div>

            {/* Trade bar */}
            <TradeBar
              prices={prices}
              selectedTicker={selectedTicker}
              onTrade={executeTrade}
              cashBalance={portfolio?.cash ?? 0}
            />

            {/* Bottom tabs: positions / heatmap / P&L */}
            <div
              style={{
                display: "flex",
                borderBottom: "1px solid #30363d",
                background: "#161b22",
                flexShrink: 0,
              }}
            >
              <button style={tabStyle(bottomTab === "positions")} onClick={() => setBottomTab("positions")}>
                POSITIONS
              </button>
              <button style={tabStyle(bottomTab === "heatmap")} onClick={() => setBottomTab("heatmap")}>
                HEATMAP
              </button>
              <button style={tabStyle(bottomTab === "pnl")} onClick={() => setBottomTab("pnl")}>
                P&amp;L CHART
              </button>
            </div>

            {/* Bottom panel content */}
            <div style={{ flex: 1, overflow: "hidden" }}>
              {bottomTab === "positions" && (
                <PositionsTable positions={positions} />
              )}
              {bottomTab === "heatmap" && (
                <PortfolioHeatmap positions={positions} />
              )}
              {bottomTab === "pnl" && (
                <PnLChart history={history} />
              )}
            </div>
          </div>

          {/* Right: Chat panel (when open) */}
          {chatOpen && (
            <div
              style={{
                width: "320px",
                flexShrink: 0,
                borderLeft: "1px solid #30363d",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              <ChatPanel
                isOpen={chatOpen}
                onToggle={() => setChatOpen(false)}
                onWatchlistChange={fetchWatchlist}
                onPortfolioChange={fetchPortfolio}
              />
            </div>
          )}
        </div>

        {/* Floating chat button when closed */}
        {!chatOpen && (
          <ChatPanel
            isOpen={false}
            onToggle={() => setChatOpen(true)}
            onWatchlistChange={fetchWatchlist}
            onPortfolioChange={fetchPortfolio}
          />
        )}
      </div>
    </>
  );
};

export default Home;
