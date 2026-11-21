import { expect, test } from "@playwright/test";

for (const path of ["/login", "/register", "/reset-password#token=visibility-test"]) {
  test(`passwords can be revealed and hidden on ${path.split("#")[0]}`, async ({ page }) => {
    await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "visibility-test" } }));
    const submissions: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST") submissions.push(request.url());
    });
    await page.goto(path, { waitUntil: "networkidle" });
    const password = page.locator("#password");
    await password.fill("r7!Kp2$vQ9#nL4@x");
    const meter = page.getByRole("meter");
    if (path !== "/login") await expect(meter).toHaveAttribute("aria-valuenow", "4");
    for (const [locale, show, hide] of [
      ["en", "Show password", "Hide password"],
      ["pt-BR", "Mostrar senha", "Ocultar senha"],
      ["fr", "Afficher le mot de passe", "Masquer le mot de passe"],
      ["es", "Mostrar contraseña", "Ocultar contraseña"],
    ]) {
      await page.locator(".auth-language-select select").selectOption(locale);
      await expect(password).toHaveAttribute("type", "password");
      const toggle = page.getByRole("button", { name: show, exact: true });
      await expect(toggle).toHaveAttribute("aria-controls", "password");
      await password.focus();
      await page.keyboard.press("Tab");
      await expect(toggle).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(password).toHaveAttribute("type", "text");
      await expect(password).toHaveAttribute("spellcheck", "false");
      await expect(password).toHaveValue("r7!Kp2$vQ9#nL4@x");
      if (path !== "/login") await expect(meter).toHaveAttribute("aria-valuenow", "4");
      await page.getByRole("button", { name: hide, exact: true }).click();
      await expect(password).toHaveAttribute("type", "password");
    }
    await page.locator(".auth-language-select select").selectOption("en");
    if (path.startsWith("/reset")) {
      const confirmation = page.locator("#confirmation");
      await confirmation.fill("r7!Kp2$vQ9#nL4@x");
      await page.getByRole("button", { name: "Show confirmation password", exact: true }).click();
      await expect(confirmation).toHaveAttribute("type", "text");
      await expect(password).toHaveAttribute("type", "password");
      await expect(confirmation).toHaveAttribute("aria-invalid", "false");
      await page.getByRole("button", { name: "Hide confirmation password", exact: true }).click();
      await expect(confirmation).toHaveAttribute("type", "password");
    }
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      const toggle = page.getByRole("button", { name: "Show password", exact: true });
      await toggle.scrollIntoViewIfNeeded();
      await expect(toggle).toBeInViewport();
      const bounds = await toggle.boundingBox();
      expect(bounds?.width).toBeGreaterThanOrEqual(44);
      expect(bounds?.height).toBeGreaterThanOrEqual(44);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await toggle.click();
      await expect(password).toHaveAttribute("type", "text");
      await page.getByRole("button", { name: "Hide password", exact: true }).click();
    }
    expect(submissions).toEqual([]);
  });
}

for (const googleLinked of [false, true]) {
  test(`every account password can be toggled independently (Google ${googleLinked ? "linked" : "unlinked"})`, async ({ page, baseURL }) => {
    const origin = new URL(baseURL!).origin;
    await page.context().addCookies([
      { name: "vervfy_playwright_session", value: "authenticated", url: origin },
      { name: "auralis_session", value: "test-ui-hint", url: origin },
    ]);
    await page.route(/^https:\/\//, route => route.abort());
    await page.route("**/api/me", route => route.fulfill({ json: {
      id: "playwright-user", username: "playwright", email: null, has_password: true,
      google_linked: googleLinked, google_oauth_enabled: true, created_at: 1_700_000_000,
      photo_url: null, track_count: 0,
    } }));
    await page.route("**/api/account/security-methods", route => route.fulfill({ json: {
      has_password: true, google_linked: googleLinked, passkey_count: 0, recovery_codes_remaining: 0,
    } }));
    await page.route("**/api/account/passkeys/enrollment-eligibility", route => route.fulfill({ json: {
      eligible: true, reason: null, passkey_count: 0,
    } }));
    const mutations: string[] = [];
    page.on("request", request => {
      if (["POST", "PUT", "DELETE"].includes(request.method())) mutations.push(request.url());
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Open account", exact: true }).click();
    await page.locator('.acct-security-item').filter({ has: page.getByRole("heading", { name: "Email address", exact: true }) }).getByRole("button", { name: "Edit", exact: true }).click();
    await page.getByRole("button", { name: "Change password", exact: true }).click();
    await page.getByRole("button", { name: googleLinked ? "Unlink Google" : "Link Google", exact: true }).click();
    await page.getByRole("button", { name: "Sign out of all devices", exact: true }).click();
    await page.getByRole("button", { name: "Delete account", exact: true }).click();
    const fields = page.locator(".account-view .auth-password-input");
    // Email, current/new password, Google proof, passkey proof, sessions, deletion.
    await expect(fields).toHaveCount(7);
    const identifiers = await fields.locator("input").evaluateAll(inputs => inputs.map(input => input.id));
    expect(new Set(identifiers).size).toBe(7);
    for (let index = 0; index < 7; index++) {
      const field = fields.nth(index);
      const input = field.locator("input");
      await expect(input).toHaveAccessibleName(/password/i);
      await expect(input).toHaveAttribute("type", "password");
      await input.fill("synthetic-account-password");
      const toggle = field.getByRole("button", { name: "Show password", exact: true });
      await expect(toggle).toHaveAttribute("aria-controls", identifiers[index]);
      await input.focus();
      await page.keyboard.press("Tab");
      await expect(toggle).toBeFocused();
      await page.keyboard.press("Space");
      await expect(input).toHaveAttribute("type", "text");
      await expect(input).toHaveValue("synthetic-account-password");
      await expect(fields.locator('input[type="password"]')).toHaveCount(6);
      await field.getByRole("button", { name: "Hide password", exact: true }).click();
      await expect(input).toHaveAttribute("type", "password");
    }
    await page.setViewportSize({ width: 320, height: 844 });
    for (const toggle of await fields.getByRole("button", { name: "Show password", exact: true }).all()) {
      await toggle.scrollIntoViewIfNeeded();
      await expect(toggle).toBeInViewport();
      const bounds = await toggle.boundingBox();
      expect(bounds?.width).toBeGreaterThanOrEqual(44);
      expect(bounds?.height).toBeGreaterThanOrEqual(44);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(mutations).toEqual([]);
  });
}
