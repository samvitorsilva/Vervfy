import { expect, test } from "@playwright/test";
import {
  getBackendOrigin,
  validateStagingSiteUrl,
} from "../staging-backend-url";

const stagingApi = "https://vervfy-staging-api.onrender.com/";

test("accepts only the approved staging API origin", () => {
  expect(getBackendOrigin(stagingApi, "staging")).toBe(
    "https://vervfy-staging-api.onrender.com",
  );
});

test("rejects the production API for a staging build", () => {
  expect(() =>
    getBackendOrigin("https://vervfy.onrender.com", "staging"),
  ).toThrow("Staging BACKEND_URL must be the approved HTTPS staging API origin.");
});

test("rejects paths, credentials, and query parameters in staging URL", () => {
  for (const url of [
    "https://vervfy-staging-api.onrender.com/api",
    "https://user:pass@vervfy-staging-api.onrender.com",
    "https://vervfy-staging-api.onrender.com?target=production",
  ]) {
    expect(() => getBackendOrigin(url, "staging")).toThrow(
      "Staging BACKEND_URL must be the approved HTTPS staging API origin.",
    );
  }
});

test("requires the approved staging frontend origin", () => {
  expect(() =>
    validateStagingSiteUrl(
      "https://vervfy.onrender.com",
      "staging",
    ),
  ).toThrow(
    "Staging SITE_URL must be the approved HTTPS staging frontend origin.",
  );
  expect(() =>
    validateStagingSiteUrl(undefined, "staging"),
  ).toThrow("SITE_URL must be set to the staging frontend origin.");
  expect(() =>
    validateStagingSiteUrl(
      "https://vervfy-staging-web.onrender.com",
      "staging",
    ),
  ).not.toThrow();
});

test("keeps non-staging backend behavior unchanged", () => {
  expect(
    getBackendOrigin("https://vervfy.onrender.com", "production"),
  ).toBe("https://vervfy.onrender.com");
  expect(() => validateStagingSiteUrl(undefined, "production")).not.toThrow();
});
