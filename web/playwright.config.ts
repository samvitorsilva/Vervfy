import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
const useExternalServer = Boolean(process.env.PLAYWRIGHT_BASE_URL);
const backendURL = process.env.PLAYWRIGHT_BACKEND_URL ?? "http://127.0.0.1:8100";

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
                reuseExistingServer: !process.env.CI,
                timeout: 30_000,
              },
            ]),
        {
          command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            BACKEND_URL: backendURL,
          },
        },
      ],
});
