/**
 * E2E Test: SSE Resilience
 *
 * Verifies:
 * - App shows connected status when SSE stream is working
 * - App shows disconnected/reconnecting when connection drops
 * - App recovers and shows connected again after reconnection
 */

import { test, expect } from "@playwright/test";

test.describe("SSE streaming resilience", () => {
  test("app initially shows LIVE connection status", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("LIVE")).toBeVisible({ timeout: 15000 });
  });

  test("SSE endpoint /api/stream/prices is reachable and streams data", async ({ page }) => {
    // Capture SSE events via the page's EventSource
    const priceUpdateReceived = page.waitForFunction(
      () => {
        return new Promise<boolean>((resolve) => {
          const es = new EventSource("/api/stream/prices");
          es.onmessage = (e) => {
            es.close();
            try {
              const data = JSON.parse(e.data);
              resolve(Object.keys(data).length > 0);
            } catch {
              resolve(false);
            }
          };
          es.onerror = () => {
            es.close();
            resolve(false);
          };
          setTimeout(() => {
            es.close();
            resolve(false);
          }, 10000);
        });
      },
      {},
      { timeout: 15000 }
    );

    await page.goto("/");
    const received = await priceUpdateReceived;
    expect(received).toBe(true);
  });

  test("SSE price data has correct JSON structure", async ({ page }) => {
    await page.goto("/");

    // Intercept the SSE event and verify its structure
    const priceData = await page.evaluate(
      () =>
        new Promise<Record<string, unknown>>((resolve, reject) => {
          const es = new EventSource("/api/stream/prices");
          const timer = setTimeout(() => {
            es.close();
            reject(new Error("Timeout waiting for SSE message"));
          }, 10000);

          es.onmessage = (e) => {
            clearTimeout(timer);
            es.close();
            try {
              resolve(JSON.parse(e.data));
            } catch (err) {
              reject(err);
            }
          };

          es.onerror = () => {
            clearTimeout(timer);
            es.close();
            reject(new Error("SSE connection error"));
          };
        })
    );

    // Should have at least one ticker
    const tickers = Object.keys(priceData);
    expect(tickers.length).toBeGreaterThan(0);

    // Each ticker should have required fields
    const firstTicker = priceData[tickers[0]] as Record<string, unknown>;
    expect(typeof firstTicker.price).toBe("number");
    expect(typeof firstTicker.ticker).toBe("string");
    expect(["up", "down", "flat"]).toContain(firstTicker.direction);
  });

  test("app shows disconnected status when offline and recovers", async ({ page, context }) => {
    await page.goto("/");
    await expect(page.getByText("LIVE")).toBeVisible({ timeout: 15000 });

    // Simulate network disconnect
    await context.setOffline(true);

    // Wait for the disconnected state to appear
    await expect(page.getByText("DISCONNECTED")).toBeVisible({ timeout: 10000 });

    // Restore network
    await context.setOffline(false);

    // App should reconnect (EventSource auto-reconnects)
    await expect(page.getByText("LIVE")).toBeVisible({ timeout: 20000 });
  });
});
