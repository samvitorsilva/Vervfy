import { test, expect } from "@playwright/test";

const key = "vervfy:account-action:v1";
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/library/listening") return route.fulfill({ status: 404, json: { detail: "Unavailable in this fixture" } });
    const json = path === "/api/csrf" ? { csrf_token: "test-csrf" }
      : path === "/api/library/state" ? { favorites: [], playlists: [] }
      : path === "/api/tracks" ? { tracks: [] } : [];
    return route.fulfill({ json });
  });
  await page.route("**/api/me", route => route.fulfill({ json: {
    id: "playwright-user", username: "playwright", email: "old@example.com",
    has_password: false, google_linked: true, google_oauth_enabled: true,
    created_at: 1700000000, photo_url: null, track_count: 0,
  } }));
  await page.goto("/?view=account");
  await expect(page.getByRole("heading", { name: "Sign-in & security" })).toBeVisible();
});

test("email address is read-only", async ({ page }) => {
  const section = page.locator('.acct-security-item').filter({ has: page.getByRole("heading", { name: "Email address" }) });
  await expect(section.getByText("old@example.com", { exact: true })).toBeVisible();
  await expect(section.locator("button, input, form")).toHaveCount(0);
});

for (const scenario of ["expired", "mismatch", "failed", "wrong-account", "missing"]) {
  test(`rejects ${scenario} continuation`, async ({ page }) => {
    let submissions = 0;
    await page.route("**/api/account/logout-all", route => { submissions++; return route.fulfill({ json: {} }); });
    if (scenario !== "missing") await page.evaluate(({ key, scenario }) => {
      sessionStorage.setItem(key, JSON.stringify({ action: scenario === "mismatch" ? "password_add" : "logout_all",
        accountId: scenario === "wrong-account" ? "other" : "playwright-user",
        createdAt: Date.now() - (scenario === "expired" ? 600000 : 0) }));
    }, { key, scenario });
    await page.goto(`/?view=account&google_reauth=${scenario === "failed" ? "failed" : "success"}&google_action=logout_all`);
    await expect(page.getByText(/cancelled or expired/)).toBeVisible();
    expect(submissions).toBe(0);
  });
}

test("password return requires fresh input and never persists credentials", async ({ page }) => {
  await page.evaluate(key => sessionStorage.setItem(key, JSON.stringify({ action: "password_add", accountId: "playwright-user", createdAt: Date.now() })), key);
  let submissions = 0;
  await page.route("**/api/account/password", route => { submissions++; return route.fulfill({ json: {} }); });
  await page.goto("/?view=account&google_reauth=success&google_action=password_add");
  await expect(page.getByText(/Enter your new password again/)).toBeVisible();
  expect(submissions).toBe(0);
  await expect(page.locator('[name="new_password"]')).toHaveValue("");
  await page.locator('[name="new_password"]').fill("new-secret-password");
  expect(await page.evaluate(key => sessionStorage.getItem(key), key)).toBeNull();
  await page.locator('#account-password-editor button[type=submit]').click();
  await expect(page.getByText("Password updated.")).toBeVisible();
  expect(submissions).toBe(1);
});

for (const action of ["logout_all", "account_delete"]) {
  test(`${action} resumes only the confirmed request`, async ({ page }) => {
    let submissions = 0;
    const endpoint = action === "logout_all" ? "**/api/account/logout-all" : "**/api/account";
    await page.route(endpoint, route => {
      submissions++;
      expect(route.request().postDataJSON()).toEqual(action === "logout_all" ? {} : { confirmation: "DELETE" });
      // A forged success URL cannot substitute for the server's single-use proof.
      return route.fulfill({ status: 403, json: { detail: "Recent Google verification required" } });
    });
    await page.evaluate(({ key, action }) => sessionStorage.setItem(key, JSON.stringify({
      action, accountId: "playwright-user", createdAt: Date.now(), confirmation: "DELETE",
    })), { key, action });
    await page.goto(`/?view=account&google_reauth=success&google_action=${action}`);
    await expect(page.getByText("Recent Google verification required", { exact: true })).toBeVisible();
    expect(submissions).toBe(1);
    expect(await page.evaluate(key => sessionStorage.getItem(key), key)).toBeNull();
  });
}

test("deletion cannot resume without explicit DELETE confirmation", async ({ page }) => {
  let submissions = 0;
  await page.route("**/api/account", route => { submissions++; return route.fulfill({ json: {} }); });
  await page.evaluate(key => sessionStorage.setItem(key, JSON.stringify({ action: "account_delete", accountId: "playwright-user", createdAt: Date.now() })), key);
  await page.goto("/?view=account&google_reauth=success&google_action=account_delete");
  await expect(page.getByText("Could not resume this action. Submit it again.")).toBeVisible();
  expect(submissions).toBe(0);
});

for (const action of ["password_add", "logout_all", "account_delete"]) {
  test(`${action} starts Google from the action button without storing secrets`, async ({ page }) => {
    let starts = 0;
    await page.route("**/api/account/google/reauth/start", async route => {
      starts++;
      expect(route.request().postDataJSON()).toEqual({ purpose: action });
      const saved = JSON.parse((await page.evaluate(key => sessionStorage.getItem(key), key))!);
      expect(saved.action).toBe(action);
      expect(Object.keys(saved).sort()).toEqual((action === "account_delete"
        ? ["action", "accountId", "createdAt", "confirmation"] : ["action", "accountId", "createdAt"]).sort());
      await route.fulfill({ json: { authorization_url: "https://accounts.google.com/test" } });
    });
    await page.route("https://accounts.google.com/**", route => route.fulfill({ contentType: "text/html", body: "Google" }));
    if (action === "password_add") {
      await page.getByRole("button", { name: "Add password", exact: true }).click();
      await page.locator('[name="new_password"]').fill("never-store-this-password");
      await page.locator('#account-password-editor button[type=submit]').click();
    } else if (action === "account_delete") {
      await page.getByRole("button", { name: "Delete account", exact: true }).click();
      await page.locator('[name="confirmation"]').fill("wrong");
      await page.locator('.acct-delete-form button[type=submit]').click();
      expect(starts).toBe(0);
      await page.locator('[name="confirmation"]').fill("DELETE");
      await page.locator('.acct-delete-form button[type=submit]').click();
    } else {
      await page.getByRole("button", { name: "Sign out of all devices", exact: true }).click();
    }
    await expect(page).toHaveURL("https://accounts.google.com/test");
    expect(starts).toBe(1);
  });
}

test("password-based account keeps current-password authentication", async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ json: {
    id: "playwright-user", username: "playwright", email: "old@example.com",
    has_password: true, google_linked: true, google_oauth_enabled: true,
    created_at: 1700000000, photo_url: null, track_count: 0,
  } }));
  let starts = 0;
  await page.route("**/api/account/google/reauth/start", route => { starts++; return route.fulfill({ status: 403 }); });
  await page.route("**/api/account/password", route => {
    expect(route.request().postDataJSON()).toEqual({ new_password: "new-secret-password", current_password: "current-secret" });
    return route.fulfill({ json: {} });
  });
  await page.goto("/?view=account");
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await page.getByLabel("Current password", { exact: true }).fill("current-secret");
  await page.locator('[name="new_password"]').fill("new-secret-password");
  await page.getByRole("button", { name: "Update password", exact: true }).click();
  await expect(page.getByText("Password updated.")).toBeVisible();
  expect(starts).toBe(0);
});
