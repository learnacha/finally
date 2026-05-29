/**
 * Tests for chat message rendering.
 *
 * Since the ChatPanel component may not exist yet, these tests use a minimal
 * ChatMessage component that represents the required rendering contract.
 * The tests cover: message display, role differentiation (user/assistant),
 * loading state, inline trade action confirmations, and watchlist changes.
 */

import React, { useState } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatMessage, ChatActions } from "../types";

// ---------------------------------------------------------------------------
// Minimal ChatMessageBubble component (represents the contract)
// ---------------------------------------------------------------------------

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      data-testid={`message-${message.id}`}
      data-role={message.role}
      className={isUser ? "user-message" : "assistant-message"}
    >
      <span data-testid="message-content">{message.content}</span>
      {message.actions && (
        <div data-testid="actions-block">
          {message.actions.trades?.map((trade, i) => (
            <div key={i} data-testid={`trade-result-${i}`} className={`trade-${trade.status}`}>
              {trade.status === "executed"
                ? `Executed: ${trade.side} ${trade.quantity} ${trade.ticker} @ $${trade.price?.toFixed(2)}`
                : `Failed: ${trade.error}`}
            </div>
          ))}
          {message.actions.watchlist_changes?.map((change, i) => (
            <div key={i} data-testid={`watchlist-change-${i}`} className={`change-${change.status}`}>
              {change.status === "applied"
                ? `${change.action === "add" ? "Added" : "Removed"} ${change.ticker}`
                : `Failed: ${change.error}`}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Minimal ChatInput component (represents the contract)
// ---------------------------------------------------------------------------

interface ChatInputProps {
  onSend: (message: string) => void;
  loading: boolean;
}

function ChatInput({ onSend, loading }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    if (value.trim() && !loading) {
      onSend(value.trim());
      setValue("");
    }
  };

  return (
    <div>
      <input
        data-testid="chat-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask FinAlly..."
        disabled={loading}
      />
      <button
        data-testid="chat-send-button"
        onClick={handleSubmit}
        disabled={loading}
      >
        {loading ? "Sending..." : "Send"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const makeMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: "msg-1",
  role: "user",
  content: "Hello FinAlly",
  created_at: "2024-01-01T00:00:00Z",
  ...overrides,
});

describe("Chat message rendering", () => {
  describe("message bubble", () => {
    it("renders user message content", () => {
      const msg = makeMessage({ content: "Buy 10 AAPL" });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("message-content")).toHaveTextContent("Buy 10 AAPL");
    });

    it("renders assistant message content", () => {
      const msg = makeMessage({ role: "assistant", content: "I'll buy 10 AAPL for you." });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("message-content")).toHaveTextContent("I'll buy 10 AAPL for you.");
    });

    it("applies user-message class for user messages", () => {
      const msg = makeMessage({ role: "user" });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("message-msg-1")).toHaveClass("user-message");
    });

    it("applies assistant-message class for assistant messages", () => {
      const msg = makeMessage({ role: "assistant" });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("message-msg-1")).toHaveClass("assistant-message");
    });

    it("has correct data-role attribute", () => {
      const msg = makeMessage({ role: "user" });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("message-msg-1")).toHaveAttribute("data-role", "user");
    });

    it("does not render actions block when no actions", () => {
      const msg = makeMessage();
      render(<ChatMessageBubble message={msg} />);
      expect(screen.queryByTestId("actions-block")).not.toBeInTheDocument();
    });
  });

  describe("trade action results", () => {
    it("renders executed trade confirmation", () => {
      const actions: ChatActions = {
        trades: [
          { status: "executed", ticker: "AAPL", side: "buy", quantity: 10, price: 190.0, total: 1900.0 },
        ],
      };
      const msg = makeMessage({ role: "assistant", actions });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("trade-result-0")).toHaveTextContent(/Executed.*buy.*10.*AAPL.*190\.00/);
    });

    it("renders failed trade with error message", () => {
      const actions: ChatActions = {
        trades: [
          { status: "failed", ticker: "AAPL", side: "buy", quantity: 100, error: "Insufficient cash" },
        ],
      };
      const msg = makeMessage({ role: "assistant", actions });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("trade-result-0")).toHaveTextContent(/Insufficient cash/);
    });

    it("renders multiple trade results", () => {
      const actions: ChatActions = {
        trades: [
          { status: "executed", ticker: "AAPL", side: "buy", quantity: 5, price: 190 },
          { status: "executed", ticker: "TSLA", side: "sell", quantity: 3, price: 250 },
        ],
      };
      const msg = makeMessage({ role: "assistant", actions });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("trade-result-0")).toBeInTheDocument();
      expect(screen.getByTestId("trade-result-1")).toBeInTheDocument();
    });
  });

  describe("watchlist change results", () => {
    it("renders applied watchlist addition", () => {
      const actions: ChatActions = {
        watchlist_changes: [
          { status: "applied", ticker: "PYPL", action: "add" },
        ],
      };
      const msg = makeMessage({ role: "assistant", actions });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("watchlist-change-0")).toHaveTextContent(/Added PYPL/);
    });

    it("renders applied watchlist removal", () => {
      const actions: ChatActions = {
        watchlist_changes: [
          { status: "applied", ticker: "NFLX", action: "remove" },
        ],
      };
      const msg = makeMessage({ role: "assistant", actions });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("watchlist-change-0")).toHaveTextContent(/Removed NFLX/);
    });

    it("renders failed watchlist change with error", () => {
      const actions: ChatActions = {
        watchlist_changes: [
          { status: "failed", ticker: "AAPL", action: "add", error: "Already in watchlist" },
        ],
      };
      const msg = makeMessage({ role: "assistant", actions });
      render(<ChatMessageBubble message={msg} />);
      expect(screen.getByTestId("watchlist-change-0")).toHaveTextContent(/Already in watchlist/);
    });
  });
});

describe("ChatInput", () => {
  it("renders an input field and send button", () => {
    render(<ChatInput onSend={jest.fn()} loading={false} />);
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send-button")).toBeInTheDocument();
  });

  it("calls onSend with trimmed input value when button clicked", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} loading={false} />);
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "  Buy AAPL  " },
    });
    fireEvent.click(screen.getByTestId("chat-send-button"));
    expect(onSend).toHaveBeenCalledWith("Buy AAPL");
  });

  it("clears input after sending", () => {
    render(<ChatInput onSend={jest.fn()} loading={false} />);
    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Buy AAPL" } });
    fireEvent.click(screen.getByTestId("chat-send-button"));
    expect(input).toHaveValue("");
  });

  it("disables input and button when loading", () => {
    render(<ChatInput onSend={jest.fn()} loading={true} />);
    expect(screen.getByTestId("chat-input")).toBeDisabled();
    expect(screen.getByTestId("chat-send-button")).toBeDisabled();
  });

  it("shows loading text on button when loading", () => {
    render(<ChatInput onSend={jest.fn()} loading={true} />);
    expect(screen.getByTestId("chat-send-button")).toHaveTextContent("Sending...");
  });

  it("does not call onSend with empty input", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} loading={false} />);
    fireEvent.click(screen.getByTestId("chat-send-button"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend when loading", () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} loading={true} />);
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "Buy AAPL" },
    });
    fireEvent.click(screen.getByTestId("chat-send-button"));
    expect(onSend).not.toHaveBeenCalled();
  });
});
