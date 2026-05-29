"""FinAlly Market Data Demo.

Run with:
  uv run market_data_demo.py           # auto: live if MASSIVE_API_KEY set, else simulator
  uv run market_data_demo.py sim       # force simulator
  uv run market_data_demo.py live      # force live (requires MASSIVE_API_KEY)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import deque

from dotenv import load_dotenv
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

load_dotenv()

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.seed_prices import SEED_PRICES
from app.market.simulator import SimulatorDataSource

SPARK_CHARS = "▁▂▃▄▅▆▇█"
TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
DURATION = 60  # seconds


def sparkline(values: list[float]) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    spread = hi - lo
    if spread == 0:
        return SPARK_CHARS[3] * len(values)
    n = len(SPARK_CHARS) - 1
    return "".join(SPARK_CHARS[int((v - lo) / spread * n)] for v in values)


def format_price(price: float) -> str:
    if price >= 1000:
        return f"{price:,.2f}"
    return f"{price:.2f}"


def build_table(cache: PriceCache, history: dict[str, deque]) -> Table:
    table = Table(
        expand=True,
        border_style="bright_black",
        header_style="bold bright_white",
        pad_edge=True,
        padding=(0, 1),
    )
    table.add_column("Ticker", style="bold bright_white", width=8)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Change", justify="right", width=9)
    table.add_column("Chg %", justify="right", width=8)
    table.add_column("", width=3)
    table.add_column("Sparkline", width=42, no_wrap=True)

    for ticker in TICKERS:
        update = cache.get(ticker)
        if update is None:
            table.add_row(ticker, "---", "---", "---", "", "")
            continue

        if update.direction == "up":
            color = "green"
            arrow = "[bold green]▲[/]"
        elif update.direction == "down":
            color = "red"
            arrow = "[bold red]▼[/]"
        else:
            color = "bright_black"
            arrow = "[bright_black]─[/]"

        price_str = f"[{color}]${format_price(update.price)}[/]"
        change_str = f"[{color}]{update.change:+.2f}[/]"
        pct_str = f"[{color}]{update.change_percent:+.2f}%[/]"
        vals = list(history.get(ticker, []))
        spark_str = f"[bright_cyan]{sparkline(vals)}[/]" if len(vals) > 1 else ""

        table.add_row(ticker, price_str, change_str, pct_str, arrow, spark_str)

    return table


def build_event_log(events: deque) -> Panel:
    text = Text()
    for evt in events:
        text.append(evt)
        text.append("\n")
    if not events:
        text.append("Watching for notable moves (>1% change)...", style="bright_black italic")
    return Panel(text, title="[bold bright_yellow]Recent Events[/]", border_style="bright_black", height=8)


def build_dashboard(cache: PriceCache, history: dict[str, deque], events: deque, start_time: float) -> Layout:
    elapsed = time.time() - start_time
    remaining = max(0, DURATION - elapsed)

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=10),
    )

    header_text = Text.assemble(
        ("  FinAlly ", "bold bright_yellow"),
        ("Market Data Demo", "bold bright_white"),
        ("  |  ", "bright_black"),
        (f"{elapsed:5.1f}s elapsed", "bright_cyan"),
        ("  |  ", "bright_black"),
        (f"{remaining:4.1f}s remaining", "bright_cyan"),
        ("  |  ", "bright_black"),
        (f"{len(cache)} tickers", "bright_white"),
        ("  |  ", "bright_black"),
        ("Ctrl+C to exit", "bright_black italic"),
    )
    layout["header"].update(Panel(header_text, border_style="bright_yellow"))
    layout["body"].update(Panel(build_table(cache, history), title="[bold bright_white]Live Prices[/]", border_style="bright_black"))
    layout["footer"].update(build_event_log(events))
    return layout


def print_summary(cache: PriceCache) -> None:
    console = Console()
    console.print()
    console.print("[bold bright_yellow]  FinAlly[/] [bold]Session Summary[/]")
    console.print()

    table = Table(border_style="bright_black", header_style="bold bright_white", expand=False)
    table.add_column("Ticker", style="bold bright_white", width=8)
    table.add_column("Seed Price", justify="right", width=12)
    table.add_column("Final Price", justify="right", width=12)
    table.add_column("Session Change", justify="right", width=14)

    for ticker in TICKERS:
        seed = SEED_PRICES.get(ticker, 0)
        update = cache.get(ticker)
        if update is None:
            continue
        final = update.price
        session_change = ((final - seed) / seed) * 100 if seed else 0
        color = "green" if session_change > 0 else "red" if session_change < 0 else "bright_black"
        table.add_row(ticker, f"${format_price(seed)}", f"[{color}]${format_price(final)}[/]", f"[{color}]{session_change:+.2f}%[/]")

    console.print(table)
    console.print()


async def run() -> None:
    cache = PriceCache()
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"

    if arg == "sim":
        source = SimulatorDataSource(price_cache=cache)
        mode = "GBM Simulator (forced)"
    elif arg == "live":
        from app.market.massive_client import MassiveDataSource
        api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
        if not api_key:
            Console().print("[bold red]Error:[/] MASSIVE_API_KEY not set in .env")
            return
        source = MassiveDataSource(api_key=api_key, price_cache=cache)
        mode = "Massive (live, forced)"
    else:
        source = create_market_data_source(cache)
        mode = "Massive (live)" if os.environ.get("MASSIVE_API_KEY", "").strip() else "GBM Simulator"

    Console().print(f"[bold bright_yellow]Market data source:[/] [bright_white]{mode}[/]")
    history: dict[str, deque] = {t: deque(maxlen=40) for t in TICKERS}
    events: deque = deque(maxlen=12)

    await source.start(TICKERS)
    start_time = time.time()

    for ticker in TICKERS:
        update = cache.get(ticker)
        if update:
            history[ticker].append(update.price)

    try:
        with Live(build_dashboard(cache, history, events, start_time), refresh_per_second=4, screen=True) as live:
            last_version = cache.version
            while time.time() - start_time < DURATION:
                await asyncio.sleep(0.25)
                if cache.version == last_version:
                    continue
                last_version = cache.version

                for ticker in TICKERS:
                    update = cache.get(ticker)
                    if update is None:
                        continue
                    history[ticker].append(update.price)
                    if abs(update.change_percent) > 1.0:
                        direction = "▲" if update.direction == "up" else "▼"
                        color = "green" if update.direction == "up" else "red"
                        timestamp = time.strftime("%H:%M:%S")
                        events.appendleft(
                            f"[bright_black]{timestamp}[/]  "
                            f"[bold {color}]{direction} {ticker}[/]  "
                            f"[{color}]{update.change_percent:+.2f}%[/]  "
                            f"${format_price(update.price)}"
                        )

                live.update(build_dashboard(cache, history, events, start_time))
    except KeyboardInterrupt:
        pass
    finally:
        await source.stop()

    print_summary(cache)


if __name__ == "__main__":
    asyncio.run(run())
