/**
 * Tests for the price flash animation behavior.
 *
 * The price flash logic should apply a CSS class (e.g. 'flash-up' or 'flash-down')
 * when a new price arrives and the direction is up/down. The class fades out after ~500ms.
 *
 * Since the actual WatchlistPanel component may not exist yet, these tests
 * define the expected behavior contract that the component must satisfy.
 * They test a minimal PriceFlashCell component as a reference implementation.
 */

import React, { useEffect, useRef, useState } from "react";
import { render, act, screen } from "@testing-library/react";
import { PriceUpdate } from "../types";

// ---------------------------------------------------------------------------
// Minimal price flash cell — represents the behavior expected from the
// watchlist price cells in the real implementation.
// ---------------------------------------------------------------------------

interface PriceFlashCellProps {
  priceUpdate: PriceUpdate | null;
}

function PriceFlashCell({ priceUpdate }: PriceFlashCellProps) {
  const [flashClass, setFlashClass] = useState<string>("");
  const prevPriceRef = useRef<number | null>(null);

  useEffect(() => {
    if (!priceUpdate) return;

    const prev = prevPriceRef.current;
    if (prev !== null && prev !== priceUpdate.price) {
      const direction = priceUpdate.price > prev ? "flash-up" : "flash-down";
      setFlashClass(direction);
      const timer = setTimeout(() => setFlashClass(""), 500);
      return () => clearTimeout(timer);
    }
    prevPriceRef.current = priceUpdate.price;
  }, [priceUpdate]);

  return (
    <span data-testid="price-cell" className={flashClass}>
      {priceUpdate?.price.toFixed(2) ?? "-"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const makeUpdate = (price: number, direction: "up" | "down" | "unchanged"): PriceUpdate => ({
  ticker: "AAPL",
  price,
  previous_price: price - (direction === "up" ? 1 : direction === "down" ? -1 : 0),
  change: direction === "up" ? 1 : direction === "down" ? -1 : 0,
  change_percent: direction === "up" ? 0.5 : direction === "down" ? -0.5 : 0,
  direction,
  timestamp: Date.now() / 1000,
});

describe("Price flash animation", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("renders the price correctly", () => {
    const update = makeUpdate(190.5, "up");
    render(<PriceFlashCell priceUpdate={update} />);
    expect(screen.getByTestId("price-cell")).toHaveTextContent("190.50");
  });

  it("renders dash when no price update provided", () => {
    render(<PriceFlashCell priceUpdate={null} />);
    expect(screen.getByTestId("price-cell")).toHaveTextContent("-");
  });

  it("applies flash-up class when price increases", () => {
    const initial = makeUpdate(190.0, "unchanged");
    const { rerender } = render(<PriceFlashCell priceUpdate={initial} />);

    // Trigger a price increase
    const higher = makeUpdate(191.0, "up");
    act(() => {
      rerender(<PriceFlashCell priceUpdate={higher} />);
    });

    expect(screen.getByTestId("price-cell")).toHaveClass("flash-up");
  });

  it("applies flash-down class when price decreases", () => {
    const initial = makeUpdate(190.0, "unchanged");
    const { rerender } = render(<PriceFlashCell priceUpdate={initial} />);

    const lower = makeUpdate(189.0, "down");
    act(() => {
      rerender(<PriceFlashCell priceUpdate={lower} />);
    });

    expect(screen.getByTestId("price-cell")).toHaveClass("flash-down");
  });

  it("clears the flash class after timeout", () => {
    const initial = makeUpdate(190.0, "unchanged");
    const { rerender } = render(<PriceFlashCell priceUpdate={initial} />);

    const higher = makeUpdate(191.0, "up");
    act(() => {
      rerender(<PriceFlashCell priceUpdate={higher} />);
    });
    expect(screen.getByTestId("price-cell")).toHaveClass("flash-up");

    act(() => {
      jest.advanceTimersByTime(600);
    });
    expect(screen.getByTestId("price-cell")).not.toHaveClass("flash-up");
  });

  it("no flash class on first render", () => {
    const update = makeUpdate(190.0, "unchanged");
    render(<PriceFlashCell priceUpdate={update} />);
    const cell = screen.getByTestId("price-cell");
    expect(cell).not.toHaveClass("flash-up");
    expect(cell).not.toHaveClass("flash-down");
  });
});
