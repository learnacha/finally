/**
 * E2E Test: Watchlist CRUD
 *
 * Verifies:
 * - Adding a ticker to the watchlist
 * - Removing a ticker from the watchlist
 * - Duplicate add is rejected gracefully
 */

import { test, expect } from "@playwright/test";

test.describe("Watchlist management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Wait for default tickers to appear
    await expect(page.getByText("AAPL").first()).toBeVisible({ timeout: 10000 });
  });

  test("can add a new ticker to the watchlist", async ({ page }) => {
    // Find the add ticker input (look for placeholder text)
    const tickerInput = page.getByPlaceholder(/add ticker|ticker symbol|enter ticker/i);
    await tickerInput.fill("COIN");

    // Submit via button or Enter key
    const addButton = page.getByRole("button", { name: /add/i }).first();
    await addButton.click();

    // COIN should now appear in the watchlist
    await expect(page.getByText("COIN").first()).toBeVisible({ timeout: 5000 });
  });

  test("can remove a ticker from the watchlist", async ({ page }) => {
    // Find the remove button for NFLX
    const nflxRow = page.locator("[data-ticker='NFLX'], [data-testid='watchlist-row-NFLX']").first();

    // Try clicking a remove/delete button in the NFLX row
    // The button might be revealed on hover
    await nflxRow.hover();
    const removeButton = nflxRow.getByRole("button", { name: /remove|delete|×|✕/i });
    await removeButton.click();

    // NFLX should no longer be visible (or should show a count of 9)
    await expect(page.getByText("NFLX")).not.toBeVisible({ timeout: 5000 });
  });

  test("watchlist API returns 10 tickers on fresh start", async ({ request }) => {
    const response = await request.get("/api/watchlist");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(10);
  });

  test("watchlist API add ticker returns 201 or 200", async ({ request }) => {
    const response = await request.post("/api/watchlist", {
      data: { ticker: "PYPL" },
    });
    expect([200, 201]).toContain(response.status());
  });

  test("watchlist API delete ticker returns 200 or 204", async ({ request }) => {
    // First add the ticker to be sure it exists
    await request.post("/api/watchlist", { data: { ticker: "TESTDELETE" } });

    const response = await request.delete("/api/watchlist/TESTDELETE");
    expect([200, 204]).toContain(response.status());
  });

  test("watchlist API returns 409 for duplicate ticker", async ({ request }) => {
    // AAPL is already in the default watchlist
    const response = await request.post("/api/watchlist", {
      data: { ticker: "AAPL" },
    });
    expect([409, 400]).toContain(response.status());
  });
});
