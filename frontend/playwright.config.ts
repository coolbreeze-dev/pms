import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:4174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        'PORTFOLIO_E2E_DB_PATH=/tmp/household-portfolio-e2e-playwright.db PORTFOLIO_BACKEND_PORT=8010 CORS_ORIGINS=\'["http://127.0.0.1:4174"]\' ../scripts/dev-e2e-backend.sh',
      url: "http://127.0.0.1:8010/api/health",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command:
        "PORTFOLIO_FRONTEND_PORT=4174 VITE_API_BASE_URL=http://127.0.0.1:8010 ../scripts/dev-e2e-frontend.sh",
      url: "http://127.0.0.1:4174",
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
