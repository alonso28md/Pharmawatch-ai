import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs against the production build in mock mode (served under /app like FastAPI does):
 * deterministic, no backend, no model calls.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5174/app/",
    trace: "retain-on-failure",
    locale: "es-ES",
    colorScheme: "light",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run build:mock && npx vite preview --mode mock --outDir dist-mock --port 5174 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5174/app/",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
