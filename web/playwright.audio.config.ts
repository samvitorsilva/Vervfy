import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Build once with test-only BACKEND_URL and SITE_URL, then avoid dev compilation
// timing in playback/security assertions. Never points at a hosted environment.
export default defineConfig({
  ...base,
  testMatch: "audio-security.spec.ts",
  webServer: [
    { command: "node tests/mock-backend.mjs", url: "http://127.0.0.1:8100/__health", reuseExistingServer: false,
      env: { ...process.env, VERVFY_MOCK_SECURE_MEDIA: "1" } },
    {
      command: "node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100", reuseExistingServer: false,
      env: { ...process.env, BACKEND_URL: "http://127.0.0.1:8100", SITE_URL: "http://127.0.0.1:3100", VERVFY_ENVIRONMENT: "test" },
    },
  ],
});
