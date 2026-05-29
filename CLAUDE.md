# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory.

The key document is PLAN.md, included in full below. The market data component has been completed and is summarized in the file planning/market_data_simulator.md, with more details in the planning/archive folder. Consult these docs only when required. The remainder of the platform is still to be developed. 
The key document is PLAN.md included in full here:

@planning/PLAN.md

## Current Implementation Status

### Completed: Market Data Backend (`backend/app/market/`)

The market data subsystem is fully implemented and tested (52/52 tests passing).

**Key classes and files:**
- `models.py` — `PriceUpdate` dataclass (immutable, with `change`, `change_percent`, `direction` properties)
- `cache.py` — `PriceCache` thread-safe in-memory store; tracks `version` for SSE change detection
- `interface.py` — `MarketDataSource` abstract base class
- `simulator.py` — `GBMSimulator` + `SimulatorDataSource`; uses Cholesky decomposition for sector-correlated moves
- `massive_client.py` — `MassiveDataSource`; polls Polygon.io REST API via the `massive` library
- `factory.py` — `create_market_data_source(cache)` selects Massive if `MASSIVE_API_KEY` is set, else simulator
- `stream.py` — `create_stream_router(cache)` returns a FastAPI router with SSE `/api/stream/prices` endpoint
- `seed_prices.py` — seed prices and GBM parameters per ticker

**To demo the simulator:**
```bash
cd backend
uv run market_data_demo.py
```

**To run tests:**
```bash
cd backend
uv run pytest tests/ -v
```

### Not Yet Started
- Backend: database, portfolio API, trade execution, LLM/chat, FastAPI app wiring
- Frontend: all of it
- Docker: Dockerfile, start/stop scripts
