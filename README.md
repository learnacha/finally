# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation with live market data, simulated portfolio management, and an LLM chat assistant that can analyze positions and execute trades on your behalf.

Built as a capstone project for an agentic AI coding course — constructed entirely by orchestrated AI coding agents.

---

## Features

- 📈 **Live price streaming** — prices flash green/red on tick via SSE
- 📊 **Sparkline mini-charts** — accumulated from the live stream since page load
- 💼 **Simulated portfolio** — start with $10,000 virtual cash, buy/sell at market price instantly
- 🗺️ **Portfolio heatmap** — treemap sized by weight, colored by P&L
- 🤖 **AI chat assistant** — ask questions, get analysis, and have the AI execute trades via natural language
- 🔍 **Watchlist management** — add/remove tickers manually or through the AI

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (TypeScript, static export) |
| Backend | FastAPI (Python, uv) |
| Database | SQLite (lazy-initialized, volume-mounted) |
| Real-time | Server-Sent Events (SSE) |
| AI | LiteLLM → OpenRouter → Cerebras (`openrouter/openai/gpt-oss-120b`) |
| Market data | Built-in GBM simulator (or Polygon.io via `MASSIVE_API_KEY`) |
| Deployment | Single Docker container on port 8000 |

## Quick Start

### Prerequisites
- Docker
- An [OpenRouter](https://openrouter.ai) API key

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/learnacha/finally.git
cd finally

# 2. Create your .env file
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=your-key-here

# 3. Start the app
./scripts/start_mac.sh        # macOS / Linux
# or
.\scripts\start_windows.ps1   # Windows PowerShell
```

Then open **http://localhost:8000** in your browser.

To stop:
```bash
./scripts/stop_mac.sh
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | ✅ Yes | OpenRouter API key for LLM chat |
| `MASSIVE_API_KEY` | No | Polygon.io key for real market data (simulator used if absent) |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |

## Project Structure

```
finally/
├── frontend/          # Next.js TypeScript app
├── backend/           # FastAPI uv project
│   └── db/            # Schema & seed logic
├── planning/          # Agent documentation & project spec
├── scripts/           # Start/stop scripts
├── test/              # Playwright E2E tests
├── db/                # SQLite volume mount (finally.db created at runtime)
├── Dockerfile
└── docker-compose.yml
```

## AI Chat

The AI assistant (FinAlly) can:
- Analyze your portfolio composition and P&L
- Suggest and **automatically execute** trades
- Add or remove tickers from your watchlist
- Answer questions about your positions

Trades execute immediately with no confirmation — it's simulated money, so the experience is fluid and agentic.

## Development

See [`planning/PLAN.md`](planning/PLAN.md) for the full project specification, architecture decisions, API contracts, and implementation reference.
