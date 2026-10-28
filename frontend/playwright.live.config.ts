import { defineConfig, devices } from "@playwright/test";

/**
 * Smoke against a real backend serving the production build at /app (no mocks).
 * Start the backend yourself (DEMO_MODE=true, API_KEY set, ANTHROPIC_API_KEY empty) and run
 *   LIVE_BASE_URL=http://127.0.0.1:8000 LIVE_API_KEY=... npx playwright test -c playwright.live.config.ts
 * It never submits /ask or /report, so it makes no model calls.
 */
export default defineConfig({
  testDir: "./e2e-live",
  outputDir: "./test-results",
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `${process.env.LIVE_BASE_URL ?? "http://127.0.0.1:8000"}/app/`,
    locale: "es-ES",
    colorScheme: "light",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
