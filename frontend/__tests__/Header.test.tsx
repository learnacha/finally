/**
 * Tests for the Header component.
 *
 * Covers: portfolio value display, cash balance, P&L display with colors,
 * connection status indicator (green/yellow/red dot + label).
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { Header } from "../components/Header";
import { Portfolio, ConnectionStatus } from "../types";

const mockPortfolio: Portfolio = {
  cash_balance: 5000.0,
  total_value: 12345.67,
  total_pnl: 2345.67,
  positions: [],
};

describe("Header", () => {
  describe("portfolio value display", () => {
    it("shows the portfolio total value formatted as currency", () => {
      render(<Header portfolio={mockPortfolio} connectionStatus="connected" />);
      expect(screen.getByText("$12,345.67")).toBeInTheDocument();
    });

    it("shows the cash balance", () => {
      render(<Header portfolio={mockPortfolio} connectionStatus="connected" />);
      expect(screen.getByText("$5,000.00")).toBeInTheDocument();
    });

    it("shows positive P&L with plus sign", () => {
      render(<Header portfolio={mockPortfolio} connectionStatus="connected" />);
      expect(screen.getByText("+$2,345.67")).toBeInTheDocument();
    });

    it("shows negative P&L with minus sign (no double minus)", () => {
      const portfolio: Portfolio = {
        ...mockPortfolio,
        total_pnl: -500.0,
      };
      render(<Header portfolio={portfolio} connectionStatus="connected" />);
      // The component shows abs value with negative styling
      expect(screen.getByText("-$500.00")).toBeInTheDocument();
    });

    it("shows zero P&L as +$0.00", () => {
      const portfolio: Portfolio = {
        ...mockPortfolio,
        total_pnl: 0,
      };
      render(<Header portfolio={portfolio} connectionStatus="connected" />);
      expect(screen.getByText("+$0.00")).toBeInTheDocument();
    });

    it("renders $0.00 portfolio value when portfolio is null", () => {
      render(<Header portfolio={null} connectionStatus="connected" />);
      // Should gracefully show zeroes
      expect(screen.getAllByText("$0.00").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("connection status", () => {
    it("shows LIVE label when connected", () => {
      render(<Header portfolio={null} connectionStatus="connected" />);
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });

    it("shows CONNECTING label when connecting", () => {
      render(<Header portfolio={null} connectionStatus="connecting" />);
      expect(screen.getByText("CONNECTING")).toBeInTheDocument();
    });

    it("shows DISCONNECTED label when disconnected", () => {
      render(<Header portfolio={null} connectionStatus="disconnected" />);
      expect(screen.getByText("DISCONNECTED")).toBeInTheDocument();
    });
  });

  describe("app branding", () => {
    it("shows FIN and ALLY text", () => {
      render(<Header portfolio={null} connectionStatus="connected" />);
      expect(screen.getByText("FIN")).toBeInTheDocument();
      expect(screen.getByText("ALLY")).toBeInTheDocument();
    });

    it("shows the workstation subtitle", () => {
      render(<Header portfolio={null} connectionStatus="connected" />);
      expect(screen.getByText(/AI TRADING WORKSTATION/i)).toBeInTheDocument();
    });
  });
});
