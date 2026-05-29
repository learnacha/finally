import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, ChatActions } from "../types";

interface ChatPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  onWatchlistChange?: () => void;
  onPortfolioChange?: () => void;
}

function ActionBadge({ actions }: { actions: ChatActions }) {
  const trades = actions.trades || [];
  const wlChanges = actions.watchlist_changes || [];
  if (trades.length === 0 && wlChanges.length === 0) return null;

  return (
    <div
      style={{
        marginTop: "6px",
        padding: "6px 8px",
        background: "#21262d",
        borderRadius: "4px",
        fontSize: "10px",
        borderLeft: "2px solid #ecad0a",
      }}
    >
      {trades.map((t, i) => (
        <div
          key={i}
          style={{
            color: t.status === "executed" ? "#3fb950" : "#f85149",
            marginBottom: "2px",
          }}
        >
          {t.status === "executed" ? "✓" : "✗"} {t.side?.toUpperCase()} {t.quantity} {t.ticker}
          {t.price ? ` @ $${t.price.toFixed(2)}` : ""}
          {t.error ? ` — ${t.error}` : ""}
        </div>
      ))}
      {wlChanges.map((w, i) => (
        <div
          key={i}
          style={{
            color: w.status === "applied" ? "#209dd7" : "#f85149",
            marginBottom: "2px",
          }}
        >
          {w.status === "applied" ? "✓" : "✗"} Watchlist: {w.action} {w.ticker}
          {w.error ? ` — ${w.error}` : ""}
        </div>
      ))}
    </div>
  );
}

export function ChatPanel({ isOpen, onToggle, onWatchlistChange, onPortfolioChange }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      const data = await res.json();
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.message || "Sorry, I couldn't process that.",
        actions: data.actions,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Trigger refresh if actions were taken
      if (data.actions?.trades?.some((t: { status: string }) => t.status === "executed")) {
        onPortfolioChange?.();
      }
      if (data.actions?.watchlist_changes?.some((w: { status: string }) => w.status === "applied")) {
        onWatchlistChange?.();
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Connection error. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        style={{
          position: "fixed",
          bottom: "16px",
          right: "16px",
          width: "44px",
          height: "44px",
          borderRadius: "50%",
          background: "#753991",
          border: "none",
          color: "#e6edf3",
          fontSize: "18px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 2px 12px rgba(117,57,145,0.5)",
          zIndex: 1000,
        }}
        title="Open AI Chat"
      >
        ✦
      </button>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#161b22",
      }}
    >
      {/* Header */}
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
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#753991", fontSize: "14px" }}>✦</span>
          <span style={{ color: "#e6edf3", fontSize: "12px", fontWeight: 700 }}>AI ASSISTANT</span>
        </div>
        <button
          onClick={onToggle}
          style={{
            background: "none",
            border: "none",
            color: "#484f58",
            cursor: "pointer",
            fontSize: "16px",
            padding: "0",
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        {messages.length === 0 && (
          <div style={{ color: "#484f58", fontSize: "11px", textAlign: "center", marginTop: "24px" }}>
            <div style={{ fontSize: "24px", marginBottom: "8px" }}>✦</div>
            <div>Ask me about your portfolio,</div>
            <div>market analysis, or to execute trades.</div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: "90%",
                padding: "8px 10px",
                borderRadius: "8px",
                background:
                  msg.role === "user" ? "#753991" : "#21262d",
                color: "#e6edf3",
                fontSize: "12px",
                lineHeight: "1.5",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {msg.content}
            </div>
            {msg.role === "assistant" && msg.actions && (
              <ActionBadge actions={msg.actions} />
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start" }}>
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "8px",
                background: "#21262d",
                color: "#484f58",
                fontSize: "12px",
              }}
            >
              <span style={{ animation: "none" }}>Thinking</span>
              <span
                style={{
                  display: "inline-block",
                  marginLeft: "4px",
                  animation: "blink 1s step-end infinite",
                }}
              >
                ...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={sendMessage}
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
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask FinAlly..."
          disabled={loading}
          style={{
            flex: 1,
            background: "#21262d",
            border: "1px solid #30363d",
            borderRadius: "4px",
            color: "#e6edf3",
            padding: "6px 10px",
            fontSize: "12px",
            fontFamily: "inherit",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            background: "#753991",
            border: "none",
            borderRadius: "4px",
            color: "#e6edf3",
            padding: "6px 12px",
            fontSize: "12px",
            fontWeight: 700,
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            opacity: loading || !input.trim() ? 0.5 : 1,
            fontFamily: "inherit",
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
