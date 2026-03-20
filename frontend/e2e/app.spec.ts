import { expect, test, type Page } from "@playwright/test";

const password = process.env.AUTH_PASSWORD?.trim() || "open-sesame";

async function unlock(page: Page) {
  await page.goto("/");
  const dashboardLink = page.getByRole("link", { name: "Dashboard" });
  try {
    await dashboardLink.waitFor({ state: "visible", timeout: 5_000 });
    return;
  } catch {
    // Password auth is enabled in this path, so continue into the unlock flow.
  }

  const passwordInput = page.getByLabel("Password");
  await passwordInput.waitFor({ state: "visible", timeout: 10_000 });
  await passwordInput.fill(password);
  await expect(page.getByRole("button", { name: "Unlock app" })).toBeEnabled();
  await page.getByRole("button", { name: "Unlock app" }).click();
  await expect(dashboardLink).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await unlock(page);
});

test("unlocks the app and renders the dashboard analytics", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Portfolio vs. benchmarks" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Daily return quality over the trailing year" })).toBeVisible();
  await expect(page.getByText("Sharpe")).toBeVisible();
  await expect(page.getByText("Dividend outlook")).toBeVisible();

  await page.getByRole("button", { name: "retirement" }).click();
  await expect(page.getByText("Category: retirement").first()).toBeVisible();

  await page.getByRole("button", { name: "1Y" }).click();
  await expect(page.getByText("Relative edge over the past year")).toBeVisible();
});

test("creates and removes a transaction from the investments page", async ({ page }) => {
  await page.getByRole("link", { name: "Investments" }).click();
  await expect(page.getByRole("heading", { name: /Track contributions, withdrawals/i })).toBeVisible();

  await page.getByLabel("Account").selectOption({ label: "Vanguard Taxable" });
  await page.getByLabel("Type").selectOption("deposit");
  await page.getByLabel("Ticker").fill("CASH");
  await page.getByLabel("Date").fill("2026-03-17");
  await page.getByLabel("Total amount").fill("525");
  await page.getByLabel("Notes").fill("E2E deposit");
  await page.getByRole("button", { name: "Create transaction" }).click();

  const row = page.locator("tr", { has: page.getByText("E2E deposit") });
  await expect(row).toBeVisible();

  await row.getByLabel("Delete CASH transaction").click();
  await expect(row).toHaveCount(0);
});

test("previews and commits a spreadsheet import from settings", async ({ page }) => {
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Preview CSV or Excel holdings before commit" })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "e2e-import.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "ticker,shares,cost basis,purchase date,currency\nVXUS,4,250.5,2026-03-01,USD\nBND,6,430.2,2026-03-02,USD\n",
    ),
  });
  await page.getByRole("button", { name: "Preview import" }).click();

  await expect(page.getByText("Rows: 2")).toBeVisible();
  await expect(page.getByRole("cell", { name: "VXUS" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "BND" })).toBeVisible();

  const commitPanel = page.locator("article.panel").filter({ hasText: "Choose where the imported lots land" });
  await page.getByLabel("Mode").selectOption("new");
  await commitPanel.locator('input[name="name"]').fill("E2E Import Account");
  await commitPanel.locator('input[name="brokerage"]').fill("Playwright");
  await page.getByRole("button", { name: "Commit import" }).click();

  await expect(page.getByText(/Imported 2 holding\(s\)/)).toBeVisible();

  await page.getByRole("link", { name: "Accounts" }).click();
  await expect(page.getByText("E2E Import Account")).toBeVisible();
});
