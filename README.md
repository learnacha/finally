# FinAlly — AI Trading Workstation

An AI-powered trading terminal with live streaming prices, a simulated portfolio, and an LLM chat assistant that can analyze positions and execute trades on your behalf.

> Built entirely by orchestrated AI coding agents as a capstone project for an agentic AI coding course.

![Dark terminal-inspired UI with watchlist, charts, portfolio heatmap, and AI chat panel]

---

## Quick Start

```bash
cp .env.example .env          # Add your OPENROUTER_API_KEY
./scripts/start_mac.sh        # Builds image and opens http://localhost:8000
```

On Windows:
```powershell
.\scripts\start_windows.ps1
```

No login, no signup. You get $10,000 in virtual cash immediately.

---

## Features

- **Live price stream** — tickers flash green/red on every tick via SSE
- **Sparkline charts** — mini price charts built live from the stream since page load
- **Buy & sell** — market orders, instant fill, no confirmation
- **Portfolio heatmap** — treemap sized by weight, colored by P&L
- **P&L chart** — total portfolio value over time
- **AI chat assistant** — ask questions, get analysis, have the AI execute trades for you

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (TypeScript, static export) |
| Backend | FastAPI + Python (managed with `uv`) |
| Database | SQLite (lazy-initialized, volume-mounted) |
| Real-time | Server-Sent Events (`/api/stream/prices`) |
| AI | LiteLLM → OpenRouter → Cerebras (`gpt-oss-120b`) |
| Market data | Built-in GBM simulator (or Polygon.io via `MASSIVE_API_KEY`) |
| Container | Single Docker container on port 8000 |

---

## Environment Variables

```bash
OPENROUTER_API_KEY=   # Required — powers the AI chat assistant
MASSIVE_API_KEY=      # Optional — real market data via Polygon.io (simulator used if unset)
LLM_MOCK=false        # Set true for deterministic responses in tests
```

---

## Project Structure

```
finally/
├── frontend/          # Next.js static export
├── backend/           # FastAPI + uv project
├── planning/          # Agent documentation and project spec
├── scripts/           # start/stop scripts for Mac and Windows
├── test/              # Playwright E2E tests
├── db/                # SQLite volume mount target (finally.db created at runtime)
└── Dockerfile         # Multi-stage build (Node → Python)
```

---

## Running Tests

```bash
cd test && docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

Tests run with `LLM_MOCK=true` by default for speed and reproducibility.
