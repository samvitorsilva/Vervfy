import { defineConfig } from '@playwright/test';

// Deliberately independent of the mock-service configuration.
export default defineConfig({
  testDir: './tests',
  testMatch: 'passkey-real.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  forbidOnly: true,
  reporter: 'list',
  outputDir: '/tmp/vervfy-passkey-real-results',
  projects: [{ name: 'chromium', metadata: { realPasskey: true } }],
  use: {
    browserName: 'chromium',
    baseURL: 'https://vervfy.test',
    ignoreHTTPSErrors: false,
    serviceWorkers: 'block',
    locale: 'en-US',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
});
