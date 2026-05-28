# Massive (Polygon.io) API Reference

> Polygon.io rebranded to **Massive** in October 2025. The Python package name changed from `polygon-api-client` to `massive`. Existing API keys, accounts, and endpoints are fully backward-compatible.

---

## Overview

Massive provides real-time and end-of-day stock market data for 10,000+ US equities via a REST API and WebSocket streams. In FinAlly, we use the REST API to poll snapshot data (current price, daily change) for the user's watchlist tickers.

**Official docs:** https://massive.com/docs  
**API key dashboard:** https://massive.com/dashboard/api-keys

---

## Installation

```bash
pip install -U massive
```

Requires Python 3.9+.

---

## Authentication

### Recommended: environment variable

```bash
export MASSIVE_API_KEY="your_api_key_here"
```

```python
from massive import RESTClient

client = RESTClient()  # reads MASSIVE_API_KEY automatically
```

### Inline (for testing only — never commit keys)

```python
client = RESTClient(api_key="your_api_key_here")
```

---

## Rate Limits

| Plan | Requests/min | Data Recency |
|------|-------------|--------------|
| Free (Basic) | 5 | End-of-day only |
| Starter / Developer | 5 | 15-minute delayed |
| Advanced | Unlimited | Real-time |
| Business | Unlimited | Real-time + Fair Market Value |

**FinAlly default poll interval:** every 15 seconds on free/starter tiers (fits within 5 req/min for a single snapshot call).

---

## Key REST Endpoints

### 1. Full Market Snapshot — Multiple Tickers

Retrieve current price, daily change, and OHLCV data for a comma-separated list of tickers in a single request. This is the primary endpoint used in FinAlly.

**HTTP:**
```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT
```

**Python client:**
```python
from massive import RESTClient
from massive.rest.models import TickerSnapshot, Agg, LastTrade

client = RESTClient()

# Fetch snapshots for specific tickers
tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
snapshots = client.get_snapshot_all("stocks", tickers=tickers)

for snap in snapshots:
    if isinstance(snap, TickerSnapshot):
        price = snap.last_trade.price if snap.last_trade else (snap.day.close if snap.day else None)
        print(
            f"{snap.ticker:<6} "
            f"${price:<10.2f} "
            f"change: {snap.todays_change:+.2f} "
            f"({snap.todays_change_perc:+.3f}%)"
        )
```

**Response fields (per ticker):**

| Field | Python attr | Type | Description |
|-------|-------------|------|-------------|
| `ticker` | `snap.ticker` | str | Ticker symbol, e.g. `"AAPL"` |
| `day.c` | `snap.day.close` | float | Current day closing/latest price |
| `day.o` | `snap.day.open` | float | Day open price |
| `day.h` | `snap.day.high` | float | Day high |
| `day.l` | `snap.day.low` | float | Day low |
| `day.v` | `snap.day.volume` | float | Day volume |
| `day.vw` | `snap.day.vwap` | float | Volume-weighted average price |
| `prevDay.c` | `snap.prev_day.close` | float | Previous close (for % change baseline) |
| `min.c` | `snap.min.close` | float | Most recent minute close |
| `lastTrade.p` | `snap.last_trade.price` | float | Price of the last trade |
| `lastTrade.s` | `snap.last_trade.size` | int | Size of the last trade |
| `lastTrade.t` | `snap.last_trade.timestamp` | int | Nanosecond timestamp |
| `lastQuote.P` | `snap.last_quote.ask_price` | float | Ask price |
| `lastQuote.p` | `snap.last_quote.bid_price` | float | Bid price |
| `todaysChange` | `snap.todays_change` | float | Dollar change vs previous close |
| `todaysChangePerc` | `snap.todays_change_perc` | float | % change vs previous close |
| `updated` | `snap.updated` | int | Last update timestamp (nanoseconds) |

**Sample raw JSON response:**
```json
{
  "count": 2,
  "status": "OK",
  "tickers": [
    {
      "ticker": "AAPL",
      "day": {
        "c": 192.34,
        "h": 194.10,
        "l": 191.20,
        "o": 191.95,
        "v": 54231876,
        "vw": 192.71
      },
      "prevDay": {
        "c": 191.80,
        "h": 193.50,
        "l": 190.20,
        "o": 190.50,
        "v": 48750000
      },
      "min": {
        "c": 192.30,
        "h": 192.45,
        "l": 192.10,
        "o": 192.15,
        "v": 12500
      },
      "lastTrade": {
        "p": 192.34,
        "s": 100,
        "t": 1748260800123456789
      },
      "lastQuote": {
        "P": 192.35,
        "p": 192.33
      },
      "todaysChange": 0.54,
      "todaysChangePerc": 0.2815,
      "updated": 1748260800123456789
    }
  ]
}
```

---

### 2. Single Ticker Snapshot

```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}
```

```python
snap = client.get_snapshot(ticker="AAPL")

print(snap.ticker)             # "AAPL"
print(snap.last_trade.price)   # 192.34
print(snap.todays_change_perc) # 0.2815
print(snap.day.volume)         # 54231876
```

---

### 3. Last Trade (most recent single price)

```python
trade = client.get_last_trade(ticker="AAPL")
print(trade.price)      # 192.34
print(trade.size)       # 100 (shares)
print(trade.timestamp)  # nanosecond unix timestamp
```

---

### 4. Last Quote (bid/ask)

```python
quote = client.get_last_quote(ticker="AAPL")
print(quote.ask_price)  # 192.35
print(quote.bid_price)  # 192.33
```

---

### 5. Historical Aggregates (OHLCV bars)

For end-of-day price history (not used in FinAlly's main path, but useful for backtesting or chart seeding):

```python
from datetime import date

aggs = []
for bar in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",        # "minute", "hour", "day", "week", "month"
    from_="2024-01-01",
    to=str(date.today()),
    limit=365
):
    aggs.append(bar)

for bar in aggs:
    print(f"{bar.timestamp}  O:{bar.open}  H:{bar.high}  L:{bar.low}  C:{bar.close}  V:{bar.volume}")
```

---

### 6. Unified Snapshot (multi-asset class)

Retrieve stocks, options, forex, and crypto in a single call:

```
GET /v3/snapshot?ticker.any_of=AAPL,GOOGL&type=stocks
```

```python
# Returns up to 250 tickers across asset classes
results = client.get_unified_snapshot(
    ticker_any_of="AAPL,GOOGL,MSFT",
    asset_type="stocks"
)
```

---

## Deriving Price Change for SSE Stream

The SSE price event requires `change` and `change_percent`. Extract them from the snapshot:

```python
def snapshot_to_price_event(snap: TickerSnapshot, prev_price: float | None) -> dict:
    """Convert a Massive snapshot to a FinAlly SSE price event."""
    import time
    
    # Best current price: lastTrade → day close → prevDay close
    price = None
    if snap.last_trade and snap.last_trade.price:
        price = snap.last_trade.price
    elif snap.day and snap.day.close:
        price = snap.day.close
    elif snap.prev_day and snap.prev_day.close:
        price = snap.prev_day.close
    
    if price is None:
        return None

    # Use todaysChange for daily baseline; fall back to tick-level delta
    change = snap.todays_change or 0.0
    change_pct = snap.todays_change_perc or 0.0
    
    # Tick-level direction vs last poll
    if prev_price is not None:
        direction = "up" if price > prev_price else ("down" if price < prev_price else "flat")
    else:
        direction = "up" if change > 0 else ("down" if change < 0 else "flat")

    return {
        "ticker": snap.ticker,
        "price": price,
        "previous_price": prev_price if prev_price is not None else price - change,
        "change": change,
        "change_percent": change_pct,
        "direction": direction,
        "timestamp": time.time(),
    }
```

---

## Complete FinAlly-Style Polling Loop

```python
import asyncio
import time
from massive import RESTClient
from massive.rest.models import TickerSnapshot

POLL_INTERVAL_SECONDS = 15  # safe for free tier (5 req/min)

client = RESTClient()  # uses MASSIVE_API_KEY env var

async def poll_prices(tickers: list[str], price_cache: dict) -> None:
    """Poll Massive snapshot API and update in-memory price cache."""
    while True:
        try:
            snapshots = client.get_snapshot_all("stocks", tickers=tickers)
            now = time.time()
            
            for snap in snapshots:
                if not isinstance(snap, TickerSnapshot):
                    continue
                
                prev = price_cache.get(snap.ticker, {}).get("price")
                price = (
                    (snap.last_trade.price if snap.last_trade else None)
                    or (snap.day.close if snap.day else None)
                    or (snap.prev_day.close if snap.prev_day else None)
                )
                if price is None:
                    continue
                
                change = snap.todays_change or 0.0
                change_pct = snap.todays_change_perc or 0.0
                direction = "up" if price > (prev or price) else (
                    "down" if price < (prev or price) else "flat"
                )
                
                price_cache[snap.ticker] = {
                    "ticker": snap.ticker,
                    "price": price,
                    "previous_price": prev or price,
                    "change": change,
                    "change_percent": change_pct,
                    "direction": direction,
                    "timestamp": now,
                }
        
        except Exception as e:
            print(f"[massive] Poll error: {e}")
        
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
```

---

## Error Handling

```python
from massive.exceptions import AuthorizationError, BadResponse, NoResultsError

try:
    snaps = client.get_snapshot_all("stocks", tickers=["AAPL"])
except AuthorizationError:
    print("Invalid or missing MASSIVE_API_KEY")
except NoResultsError:
    print("No data returned (market may be closed or ticker invalid)")
except BadResponse as e:
    print(f"API error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Plan Selection Guide for FinAlly

| Scenario | Recommended Plan | Notes |
|----------|-----------------|-------|
| Demo / development | Free (5 req/min) | Use 15s poll, delayed data fine |
| Classroom demo | Starter | 15-min delay, stable |
| Live trading demo | Advanced | Real-time prices |

For the FinAlly simulator (default), no API key is needed. Only set `MASSIVE_API_KEY` when real market data is desired.
