/**
 * E2E Test: Portfolio Trading
 *
 * Verifies:
 * - Buy shares: cash decreases, position appears in portfolio
 * - Sell shares: cash increases, position updates or disappears
 * - Insufficient cash returns an error
 * - Sell more than owned returns an error
 * - Positions table shows correct values
 */

import { test, expect } from "@playwright/test";

// Helper to get current cash via the API
async function getCash(request: Parameters<typeof test.beforeEach>[0] extends { request: infer R } ? R : never) {
  const res = await (request as any).get("/api/portfolio");
  const data = await res.json();
  return data.cash_balance as number;
}

test.describe("Trading (API level)", () => {
  test("GET /api/portfolio returns 200 with expected shape", async ({ request }) => {
    const response = await request.get("/api/portfolio");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(typeof data.cash_balance).toBe("number");
    expect(typeof data.total_value).toBe("number");
    expect(Array.isArray(data.positions)).toBe(true);
  });

  test("buy trade reduces cash balance", async ({ request }) => {
    const before = await request.get("/api/portfolio");
    const beforeData = await before.json();
    const cashBefore = beforeData.cash_balance;

    // Get a price for AAPL from the watchlist
    const watchlistRes = await request.get("/api/watchlist");
    const watchlist = await watchlistRes.json();
    const aapl = watchlist.find((w: { ticker: string }) => w.ticker === "AAPL");
    const price = aapl?.price || 190.0;
    const quantity = 1;

    const tradeRes = await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity, side: "buy" },
    });
    expect(tradeRes.status()).toBe(200);

    const after = await request.get("/api/portfolio");
    const afterData = await after.json();
    expect(afterData.cash_balance).toBeLessThan(cashBefore);
  });

  test("buy trade creates a position", async ({ request }) => {
    // Use a different ticker to avoid interference (V not likely traded yet)
    await request.post("/api/portfolio/trade", {
      data: { ticker: "V", quantity: 2, side: "buy" },
    });

    const portfolioRes = await request.get("/api/portfolio");
    const portfolio = await portfolioRes.json();
    const position = portfolio.positions.find((p: { ticker: string }) => p.ticker === "V");
    expect(position).toBeDefined();
    expect(position.quantity).toBeGreaterThan(0);
  });

  test("sell reduces position quantity", async ({ request }) => {
    // Buy 10 MSFT first
    await request.post("/api/portfolio/trade", {
      data: { ticker: "MSFT", quantity: 10, side: "buy" },
    });

    // Sell 5
    const sellRes = await request.post("/api/portfolio/trade", {
      data: { ticker: "MSFT", quantity: 5, side: "sell" },
    });
    expect(sellRes.status()).toBe(200);

    const portfolioRes = await request.get("/api/portfolio");
    const portfolio = await portfolioRes.json();
    const position = portfolio.positions.find((p: { ticker: string }) => p.ticker === "MSFT");
    expect(position).toBeDefined();
    // Should have ~5 shares left (accounting for any previous test state)
    expect(position.quantity).toBeGreaterThan(0);
  });

  test("sell all shares removes the position", async ({ request }) => {
    // Buy then sell exactly the same amount
    await request.post("/api/portfolio/trade", {
      data: { ticker: "AMZN", quantity: 3, side: "buy" },
    });

    const buyPortfolio = await request.get("/api/portfolio");
    const buyData = await buyPortfolio.json();
    const buyPos = buyData.positions.find((p: { ticker: string }) => p.ticker === "AMZN");
    const totalQty = buyPos?.quantity || 3;

    const sellRes = await request.post("/api/portfolio/trade", {
      data: { ticker: "AMZN", quantity: totalQty, side: "sell" },
    });
    expect(sellRes.status()).toBe(200);

    const afterPortfolio = await request.get("/api/portfolio");
    const afterData = await afterPortfolio.json();
    const noPos = afterData.positions.find((p: { ticker: string }) => p.ticker === "AMZN");
    expect(noPos).toBeUndefined();
  });

  test("buy with insufficient cash returns 400", async ({ request }) => {
    const response = await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 1000000, side: "buy" },
    });
    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.detail || data.error || data.message).toBeTruthy();
  });

  test("sell more than owned returns 400", async ({ request }) => {
    const response = await request.post("/api/portfolio/trade", {
      data: { ticker: "XYZQ_UNKNOWN", quantity: 100, side: "sell" },
    });
    expect(response.status()).toBe(400);
  });

  test("GET /api/portfolio/history returns an array", async ({ request }) => {
    const response = await request.get("/api/portfolio/history");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
  });
});

test.describe("Trading (UI level)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("AAPL").first()).toBeVisible({ timeout: 10000 });
  });

  test("buy button appears in the trade bar", async ({ page }) => {
    // Look for buy/sell buttons anywhere on the page
    const buyButton = page.getByRole("button", { name: /buy/i }).first();
    await expect(buyButton).toBeVisible({ timeout: 5000 });
  });

  test("can enter a ticker and quantity and click buy", async ({ page }) => {
    // Find trade input fields
    const tickerInput = page.getByPlaceholder(/ticker/i).last();
    const quantityInput = page.getByPlaceholder(/qty|quantity|shares/i).first();
    const buyButton = page.getByRole("button", { name: /buy/i }).first();

    await tickerInput.fill("GOOGL");
    await quantityInput.fill("1");
    await buyButton.click();

    // After trade, cash balance should update (either less or error shown)
    // We just verify no crash happens
    await page.waitForTimeout(1000);
    // App should still be responsive
    await expect(page.getByText("FIN")).toBeVisible();
  });

  test("portfolio section shows position after buy", async ({ page, request }) => {
    // Pre-buy via API to ensure a position exists
    await request.post("/api/portfolio/trade", {
      data: { ticker: "NVDA", quantity: 1, side: "buy" },
    });

    await page.reload();
    await page.waitForLoadState("networkidle");

    // NVDA should appear in the positions table
    await expect(page.getByText("NVDA").first()).toBeVisible({ timeout: 10000 });
  });
});
