import { expect, test } from "@playwright/test";

const locales = [
  { code: "en", reset: "This reset link is invalid or has expired", verify: "This verification link is invalid or has expired", csrf: "Could not load the form." },
  { code: "fr", reset: "Ce lien de réinitialisation est invalide ou expiré.", verify: "Ce lien de vérification est invalide ou expiré.", csrf: "Impossible de charger le formulaire." },
  { code: "es", reset: "Este enlace de restablecimiento no es válido o ha caducado.", verify: "Este enlace de verificación no es válido o ha caducado.", csrf: "No se pudo cargar el formulario." },
  { code: "pt-BR", reset: "Este link de redefinição é inválido ou expirou.", verify: "Este link de verificação é inválido ou expirou.", csrf: "Não foi possível carregar o formulário." },
];

test("registration login link is underlined, contrasting, and keyboard visible", async ({ page }) => {
  await page.goto("/register");
  const link = page.locator('.auth-footer a[href="/login"]');
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const locale of locales) {
      await page.locator(".auth-language-select select").selectOption(locale.code);
      // Check the normal appearance, without a hover or focus cue.
      await page.locator("#password").focus();
      await page.mouse.move(0, 0);
      await link.scrollIntoViewIfNeeded();
      await expect(link).toHaveCSS("text-decoration-line", "underline");
      const contrast = await link.evaluate((element) => {
        const luminance = (color: string) => {
          const rgb = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map((channel) => {
            const value = channel / 255;
            return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
          });
          return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
        };
        const foreground = luminance(getComputedStyle(element).color);
        const background = luminance(getComputedStyle(element.closest(".auth-card")!).backgroundColor);
        return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
      });
      expect(contrast).toBeGreaterThanOrEqual(4.5);
      await link.focus();
      await expect(link).toBeFocused();
      await expect(link).toHaveCSS("text-decoration-line", "underline");
      await expect(link).toHaveCSS("outline-style", "solid");
      await expect(link).toHaveCSS("outline-width", "2px");
    }
  }
});

for (const mode of ["reset", "verify"] as const) {
  for (const knownError of [true, false]) {
    test(`${mode} link errors translate live with ${knownError ? "known keys" : "fallback keys"}`, async ({ page }) => {
      const token = `synthetic-${mode}-do-not-log`;
      const password = "synthetic-password-do-not-log";
      const consoleMessages: string[] = [];
      page.on("console", (message) => consoleMessages.push(message.text()));
      const messageKey = mode === "reset"
        ? "This reset link is invalid or has expired"
        : "This verification link is invalid or has expired";
      let submissions = 0;
      await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "regression-csrf" } }));
      await page.route(`**/api/auth/${mode === "reset" ? "reset-password" : "verify-reset-email"}`, (route) => {
        submissions += 1;
        return route.fulfill({ status: 400, json: { detail: knownError ? messageKey : "Untranslated upstream failure" } });
      });
      await page.goto(`/reset-password#${mode === "reset" ? "token" : "verify"}=${token}`);
      await page.locator(".auth-language-select select").selectOption("en");
      if (mode === "reset") {
        await page.locator("#password").fill(password);
        await page.locator("#confirmation").fill(password);
      }
      await page.locator(".auth-submit").click();
      const alert = page.locator(".auth-error[role='alert']");
      await expect(alert).toHaveText(knownError ? messageKey : "Untranslated upstream failure");
      for (const locale of locales.slice(1)) {
        await page.locator(".auth-language-select select").selectOption(locale.code);
        await expect(alert).toHaveText(locale[mode]);
      }
      await expect(page).toHaveURL(/\/reset-password$/);
      expect(submissions).toBe(1);
      expect(consoleMessages.join("\n")).not.toContain(token);
      expect(consoleMessages.join("\n")).not.toContain(password);
    });
  }
}

test("reset form load errors translate live without refetching", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/csrf", (route) => {
    requests += 1;
    return route.fulfill({ status: 503, json: { detail: "Untranslated upstream failure" } });
  });
  await page.goto("/reset-password#token=synthetic-load-error");
  const alert = page.locator(".auth-error[role='alert']");
  for (const locale of locales) {
    await page.locator(".auth-language-select select").selectOption(locale.code);
    await expect(alert).toHaveText(locale.code === "en" ? "Untranslated upstream failure" : locale.csrf);
    await expect(page.locator(".auth-submit")).toBeDisabled();
  }
  expect(requests).toBe(1);
});
