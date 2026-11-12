import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
const useExternalServer = Boolean(process.env.PLAYWRIGHT_BASE_URL);
const backendURL = process.env.PLAYWRIGHT_BACKEND_URL ?? "http://127.0.0.1:8100";
const useProductionServer = process.env.PLAYWRIGHT_USE_PRODUCTION_SERVER === "1";
// Avoid silently reusing stale local processes; opt in only for a known server.
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVER === "1";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: useExternalServer
    ? undefined
    : [
        ...(process.env.PLAYWRIGHT_BACKEND_URL
          ? []
          : [
              {
                command: "node tests/mock-backend.mjs",
                url: "http://127.0.0.1:8100/__health",
                reuseExistingServer,
                timeout: 30_000,
              },
            ]),
        {
          command: useProductionServer
            ? "npm run build && npm run start -- --hostname 127.0.0.1 --port 3100"
            : "npm run dev -- --webpack --hostname 127.0.0.1 --port 3100",
          url: baseURL,
          reuseExistingServer,
          timeout: 180_000,
          env: {
            ...process.env,
            BACKEND_URL: backendURL,
            SITE_URL: baseURL,
            VERVFY_ENVIRONMENT: "test",
          },
        },
      ],
});
