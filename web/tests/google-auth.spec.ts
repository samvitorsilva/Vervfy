import { expect, test, type Page } from "@playwright/test";

const backendURL = process.env.PLAYWRIGHT_BACKEND_URL ?? "http://127.0.0.1:8100";

async function setGoogleOAuthEnabled(
  page: Page,
  enabled: boolean,
) {
  const response = await page.request.post(
    `${backendURL}/__test/google-oauth-enabled`,
    { data: { enabled } },
  );
  expect(response.status()).toBe(204);
}

test("Google sign-in and sign-up render initially when OAuth is enabled", async ({
  page,
}) => {
  await setGoogleOAuthEnabled(page, false);
  await page.goto("/login");
  await expect(page.getByRole("link", { name: "Continue with Google" })).toHaveCount(0);

  await setGoogleOAuthEnabled(page, true);
  const loginResponse = await page.goto("/login");
  expect(await loginResponse?.text()).toContain("Continue with Google");
  await expect(page.getByRole("link", { name: "Continue with Google" })).toHaveAttribute(
    "href",
    "/api/auth/google/start?purpose=login",
  );

  const registerResponse = await page.goto("/register");
  expect(await registerResponse?.text()).toContain("Continue with Google");
  await expect(page.getByRole("link", { name: "Continue with Google" })).toHaveAttribute(
    "href",
    "/api/auth/google/start?purpose=signup",
  );
  await expect(page.getByLabel("Password")).toBeVisible();
});

test("Google onboarding asks only for a unique username", async ({ page }) => {
  await setGoogleOAuthEnabled(page, true);
  await page.goto("/register?google=complete");

  await expect(
    page.getByRole("heading", { name: "Choose your username" }),
  ).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toHaveCount(0);
  await expect(page.getByLabel("Email (optional, not used to sign in)")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
});

test("account settings expose explicit Google unlinking with password proof", async ({
  page,
}) => {
  await page.route("**/api/me", async (route) => {
    await route.fulfill({
      json: {
        id: "playwright-user",
        username: "playwright",
        email: null,
        has_password: true,
        google_linked: true,
        google_oauth_enabled: true,
        created_at: 1_700_000_000,
        photo_url: null,
        track_count: 0,
      },
    });
  });
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  const accountLoaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/me" &&
      response.ok(),
  );
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await accountLoaded;
  await page.getByRole("button", { name: "Open account" }).click();

  await expect(page.getByText("Google is linked to this account.")).toBeVisible();
  await page.getByRole("button", { name: "Unlink Google" }).click();
  await expect(page.getByLabel("Current password").last()).toBeVisible();
  await expect(page.getByText("You must keep at least one sign-in method.")).toBeVisible();
});
