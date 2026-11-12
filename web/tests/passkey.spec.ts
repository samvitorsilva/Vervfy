import { expect, test, type Page, type Route } from "@playwright/test";

const csrfToken = "playwright-csrf-token";
const challenge = Buffer.alloc(32, 7).toString("base64url");
const identifier = "A".repeat(43);
const externalServer = Boolean(
  process.env.PLAYWRIGHT_BASE_URL || process.env.PLAYWRIGHT_BACKEND_URL,
);

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function signInAndOpenAccount(page: Page) {
  const localUrl = new URL(
    process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
  );
  localUrl.hostname = "localhost";
  localUrl.pathname = "/login";
  await page.goto(localUrl.href);
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  const accountLoaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/me" && response.ok(),
  );
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await accountLoaded;
  await page.getByRole("button", { name: "Open account" }).click();
  await expect(
    page.getByRole("heading", { name: "Sign-in & security" }),
  ).toBeVisible();
}

async function enableVirtualAuthenticator(page: Page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  });
  return cdp;
}

async function mockPasskeyApi(
  page: Page,
  options: {
    enabled: boolean;
    enrolled?: boolean;
    rejectAuthorization?: boolean;
    expireSession?: boolean;
    expireAction?: string;
    hasPassword?: boolean;
  },
) {
  let credentialId: string | null = null;
  const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
  let recoveryCodesRemaining = 0;
  const passkeyCount = options.enrolled ? 1 : 0;

  await page.route("**/api/account/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const body = request.postDataJSON() as Record<string, unknown> | null;
    if (path === "/api/account/security-methods" && method === "GET") {
      if (!options.enabled) return json(route, 404, { detail: "Not found" });
      return json(route, 200, {
        has_password: options.hasPassword ?? true,
        google_linked: false,
        passkey_count: credentialId ? 1 : passkeyCount,
        recovery_codes_remaining: recoveryCodesRemaining,
      });
    }
    if (path === "/api/account/passkeys/enrollment-eligibility" && method === "GET") {
      if (!options.enabled) return json(route, 404, { detail: "Not found" });
      return json(route, 200, {
        eligible: !credentialId && !options.enrolled,
        reason: credentialId || options.enrolled ? "maximum_passkeys_reached" : null,
        passkey_count: credentialId ? 1 : passkeyCount,
      });
    }
    if (path.startsWith("/api/account/passkeys/")) {
      if (!options.enabled) return json(route, 404, { detail: "Not found" });
      if (method !== "GET") {
        expect(request.headers()["x-csrf-token"]).toBe(csrfToken);
        calls.push({ path, body: body ?? {} });
      }
      if (path.endsWith("/registration/authorize")) {
        if (options.expireSession) {
          return json(route, 401, { detail: "Session expired" });
        }
        if (options.rejectAuthorization) {
          return json(route, 403, { detail: "CSRF token invalid" });
        }
        return json(route, 200, { authorization_id: identifier });
      }
      if (path.endsWith("/registration/options")) {
        return json(route, 200, {
          challenge_id: identifier,
          options: {
            challenge,
            rp: { id: "localhost", name: "Vervfy" },
            user: {
              id: Buffer.alloc(32, 3).toString("base64url"),
              name: "playwright",
              displayName: "Playwright Test",
            },
            pubKeyCredParams: [{ type: "public-key", alg: -7 }],
            authenticatorSelection: {
              residentKey: "required",
              userVerification: "required",
            },
            timeout: 60_000,
          },
        });
      }
      if (path.endsWith("/registration/complete")) {
        credentialId = String(body?.response && (body.response as Record<string, unknown>).rawId);
        return json(route, 200, { registered: true });
      }
      if (path.endsWith("/action-intents")) {
        return json(route, 200, { intent_id: identifier });
      }
      if (path.endsWith("/options")) {
        return json(route, 200, {
          challenge_id: identifier,
          options: {
            challenge,
            rpId: "localhost",
            userVerification: "required",
            allowCredentials: credentialId
              ? [{ type: "public-key", id: credentialId, transports: ["internal"] }]
              : [],
            timeout: 60_000,
          },
        });
      }
      if (path.endsWith("/complete")) {
        if (options.expireAction && path.includes(`/actions/${options.expireAction}/`)) {
          return json(route, 400, { detail: "Passkey request could not be completed" });
        }
        return json(route, 200, { proof_id: identifier });
      }
      if (path.endsWith("/recovery/codes")) {
        expect(Object.keys(body ?? {}).sort()).toEqual(["intent_id", "proof_id"]);
        recoveryCodesRemaining = 8;
        return json(route, 200, { recovery_codes: ["a".repeat(64), "b".repeat(64)] });
      }
      return json(route, 404, { detail: "Not found" });
    }
    if (path === "/api/account/email" && method === "PUT") {
      calls.push({ path, body: body ?? {} });
      return json(route, 200, { email: body?.email });
    }
    if (path === "/api/account/password" && method === "POST") {
      calls.push({ path, body: body ?? {} });
      return json(route, 200, { ok: true });
    }
    if (path === "/api/account/logout-all" && method === "POST") {
      calls.push({ path, body: body ?? {} });
      return json(route, 200, { ok: true });
    }
    return route.continue();
  });

  return calls;
}

test("disabled feature stays unavailable in account settings", async ({ page }) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  await mockPasskeyApi(page, { enabled: false });
  await signInAndOpenAccount(page);
  const passkeySection = page.locator(".acct-security-item").filter({
    has: page.getByRole("heading", { name: "Passkeys" }),
  });
  await expect(
    passkeySection.getByText("Passkeys are not enabled for this service."),
  ).toBeVisible();
  await expect(
    passkeySection.getByRole("button", { name: "Add a passkey" }),
  ).toHaveCount(0);
});

test("enrollment, recovery setup, email change, and logout-all use the virtual authenticator", async ({
  page,
}) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  const calls = await mockPasskeyApi(page, { enabled: true });
  await signInAndOpenAccount(page);
  const cdp = await enableVirtualAuthenticator(page);

  await page.getByLabel("Current password").last().fill("playwright-test-password");
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Passkey added." }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Set up recovery codes" }).click();
  await expect(page.getByRole("heading", { name: "Recovery codes" })).toBeVisible();
  await expect(page.getByText("a".repeat(64))).toBeVisible();
  await page.getByRole("button", { name: "Hide and clear codes" }).click();
  await expect(page.getByText("a".repeat(64))).toHaveCount(0);

  const emailSection = page.locator(".acct-security-item").filter({
    has: page.getByRole("heading", { name: "Email address" }),
  });
  await emailSection.getByRole("button", { name: "Edit" }).click();
  await emailSection.getByLabel("Email address").fill("new@example.test");
  await emailSection.getByRole("button", { name: "Save email with passkey" }).click();
  await expect(emailSection.getByText("new@example.test")).toBeVisible();
  const emailIntent = calls.find(
    (call) => call.path.endsWith("/action-intents") && call.body.action === "email_change",
  );
  expect(emailIntent?.body.email).toBe("new@example.test");
  const emailMutation = calls.find((call) => call.path === "/api/account/email");
  expect(emailMutation?.body).toMatchObject({
    email: "new@example.test",
    passkey_intent_id: identifier,
    passkey_proof_id: identifier,
  });

  await page.getByRole("button", { name: "Sign out of all devices" }).first().click();
  await page.getByRole("button", { name: "Sign out of all devices with passkey" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const logoutIntent = calls.find(
    (call) => call.path.endsWith("/action-intents") && call.body.action === "logout_all",
  );
  expect(logoutIntent).toBeTruthy();
  const logoutMutation = calls.find((call) => call.path === "/api/account/logout-all");
  expect(logoutMutation?.body).toMatchObject({
    passkey_intent_id: identifier,
    passkey_proof_id: identifier,
  });
  const browserSecrets = await page.evaluate(() => ({
    url: location.href,
    localStorage: Object.values(localStorage),
    sessionStorage: Object.values(sessionStorage),
  }));
  expect(JSON.stringify(browserSecrets)).not.toContain(identifier);
  expect(JSON.stringify(browserSecrets)).not.toContain("a".repeat(64));
  await cdp.send("WebAuthn.disable");
});

test("passkey creates a password and an expired assertion cannot change email", async ({
  page,
}) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  await page.route("**/api/me", async (route) => {
    const response = await route.fetch();
    const account = await response.json();
    await route.fulfill({ response, json: { ...account, has_password: false } });
  });
  const calls = await mockPasskeyApi(page, {
    enabled: true,
    hasPassword: false,
    expireAction: "email_change",
  });
  await signInAndOpenAccount(page);
  const cdp = await enableVirtualAuthenticator(page);
  await page.getByLabel("Current password").last().fill("playwright-test-password");
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Passkey added." }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Change password" }).click();
  await page.getByLabel("Create password (min 8 characters)").fill("new-password-123");
  await page.getByRole("button", { name: "Create password with passkey" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Password updated." }),
  ).toBeVisible();
  expect(calls.find((call) => call.path.endsWith("/action-intents"))?.body).toMatchObject({
    action: "password_add",
    new_password: "new-password-123",
  });
  expect(calls.find((call) => call.path === "/api/account/password")?.body).toMatchObject({
    new_password: "new-password-123",
    passkey_intent_id: identifier,
    passkey_proof_id: identifier,
  });

  const emailSection = page.locator(".acct-security-item").filter({
    has: page.getByRole("heading", { name: "Email address" }),
  });
  await emailSection.getByRole("button", { name: "Edit" }).click();
  await emailSection.getByLabel("Email address").fill("expired@example.test");
  await emailSection.getByRole("button", { name: "Save email with passkey" }).click();
  await expect(
    page.getByRole("status").filter({
      hasText: "Passkey verification failed or expired. Start a new attempt.",
    }),
  ).toBeVisible();
  expect(calls.some((call) => call.path === "/api/account/email")).toBe(false);
  await cdp.send("WebAuthn.disable");
});

test("unsupported browsers receive an accessible explanation", async ({ page }) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  await page.addInitScript(() => {
    Object.defineProperty(window, "PublicKeyCredential", { value: undefined });
  });
  await mockPasskeyApi(page, { enabled: true });
  await signInAndOpenAccount(page);
  await expect(
    page.getByRole("status").filter({
      hasText: "Passkeys are not supported in this browser or connection.",
    }),
  ).toBeVisible();
});

test("an expired session interrupts enrollment", async ({ page }) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  await mockPasskeyApi(page, { enabled: true, expireSession: true });
  await signInAndOpenAccount(page);
  await page.getByLabel("Current password").last().fill("playwright-test-password");
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("a failed registration authorization reports a retryable CSRF failure", async ({
  page,
}) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  const calls = await mockPasskeyApi(page, {
    enabled: true,
    rejectAuthorization: true,
  });
  await signInAndOpenAccount(page);
  await page.getByLabel("Current password").last().fill("playwright-test-password");
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "CSRF token invalid" }),
  ).toBeVisible();
  expect(calls.filter((call) => call.path.endsWith("/registration/authorize"))).toHaveLength(2);
});

test("cancelled WebAuthn ceremony shows a clear retry message", async ({ page }) => {
  test.skip(externalServer, "Passkey browser tests run only against local mock services.");
  await page.addInitScript(() => {
    Object.defineProperty(Object.getPrototypeOf(navigator.credentials), "create", {
      configurable: true,
      value: () => Promise.reject(new DOMException("User cancelled", "NotAllowedError")),
    });
  });
  await mockPasskeyApi(page, { enabled: true });
  await signInAndOpenAccount(page);
  await page.getByLabel("Current password").last().fill("playwright-test-password");
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(
    page.getByRole("status").filter({
      hasText: "Passkey request cancelled or timed out. Start again.",
    }),
  ).toBeVisible();
});
