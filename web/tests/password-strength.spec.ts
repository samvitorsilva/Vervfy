import { expect, test } from "@playwright/test";

const locales = [
  { code: "en", meter: "Password strength", empty: "Empty", weak: "Weak", strong: "Strong", rules: ["8 characters or more", "Upper and lower case", "A number", "A symbol"], warning: "Commonly guessed", pattern: "This is a commonly guessed pattern.", complete: "All requirements met.", met: "met", unmet: "not met" },
  { code: "pt-BR", meter: "Força da senha", empty: "Vazia", weak: "Fraca", strong: "Forte", rules: ["8 caracteres ou mais", "Letras maiúsculas e minúsculas", "Um número", "Um símbolo"], warning: "Fácil de adivinhar", pattern: "Este é um padrão fácil de adivinhar.", complete: "Todos os critérios foram atendidos.", met: "atendido", unmet: "não atendido" },
  { code: "fr", meter: "Robustesse du mot de passe", empty: "Vide", weak: "Faible", strong: "Forte", rules: ["8 caractères ou plus", "Majuscules et minuscules", "Un chiffre", "Un symbole"], warning: "Facile à deviner", pattern: "Ce modèle est facile à deviner.", complete: "Tous les critères sont satisfaits.", met: "satisfait", unmet: "non satisfait" },
  { code: "es", meter: "Seguridad de la contraseña", empty: "Vacía", weak: "Débil", strong: "Fuerte", rules: ["8 caracteres o más", "Mayúsculas y minúsculas", "Un número", "Un símbolo"], warning: "Fácil de adivinar", pattern: "Este patrón es fácil de adivinar.", complete: "Se cumplen todos los criterios.", met: "cumplido", unmet: "no cumplido" },
];

for (const path of ["/register", "/reset-password#token=strength-ui-test"]) {
  test(`password strength translates live on ${path.split("#")[0]}`, async ({ page }) => {
    await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "strength-ui-test" } }));
    const csrfLoaded = page.waitForResponse("**/api/csrf");
    await page.goto(path);
    await csrfLoaded;
    const password = page.locator("#password");
    const strength = page.locator("#password-strength");
    const meter = strength.getByRole("meter");
    const announcement = strength.locator('[aria-live="polite"]');
    for (const locale of locales) {
      await page.locator(".auth-language-select select").selectOption(locale.code);
      await expect(meter).toHaveAccessibleName(locale.meter);
      for (const rule of locale.rules) {
        await expect(strength.getByText(rule, { exact: true })).toBeVisible();
      }
      await password.fill("");
      await expect(meter).toHaveAttribute("aria-valuetext", locale.empty);
      await expect(strength.getByRole("listitem").first().locator(".sr-only")).toHaveText(locale.unmet);
      await password.fill("password");
      await expect(meter).toHaveAttribute("aria-valuetext", locale.weak);
      await expect(strength.getByText(locale.warning, { exact: true })).toBeVisible();
      await expect(announcement).toContainText(locale.pattern);
      await password.fill("r7!Kp2$vQ9#nL4@x");
      await expect(meter).toHaveAttribute("aria-valuetext", locale.strong);
      await expect(strength.getByRole("listitem").first().locator(".sr-only")).toHaveText(locale.met);
      await expect(announcement).toContainText(locale.complete);
    }
  });
}

for (const path of ["/register", "/reset-password#token=strength-regression"]) {
  test(`strength estimates locally and clears stale announcements on ${path.split("#")[0]}`, async ({ page }) => {
    await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "strength-regression" } }));
    const csrfLoaded = page.waitForResponse("**/api/csrf");
    await page.goto(path);
    await csrfLoaded;
    await page.locator(".auth-language-select select").selectOption("en");
    await page.emulateMedia({ reducedMotion: "reduce" });
    const password = page.locator("#password");
    const strength = page.locator("#password-strength");
    const meter = strength.getByRole("meter");
    const announcement = strength.locator('[aria-live="polite"]');
    const requests: string[] = [];
    page.on("request", (request) => {
      if (["fetch", "xhr"].includes(request.resourceType())) {
        // Registration can finish loading its public provider configuration here.
        if (request.method() === "GET" && new URL(request.url()).pathname === "/api/config") return;
        // Production Link navigation prefetches are unrelated to estimation.
        if (request.method() === "GET" && request.headers()["rsc"] === "1"
          && new URL(request.url()).origin === new URL(page.url()).origin
          && ["/forgot-password", "/login", "/privacy", "/terms", "/credits"].includes(new URL(request.url()).pathname)) return;
        requests.push(request.url());
      }
    });

    // Passing every composition rule must not make predictable passwords strong.
    for (const value of ["Password1!", "Qwerty123!", "abcabcabcabc", "987654321"]) {
      await password.fill(value);
      await expect(meter).toHaveAttribute("aria-valuenow", "1");
      await expect(meter).toHaveAttribute("aria-valuetext", "Weak");
      await expect(announcement).toBeEmpty();
      await expect(announcement).toContainText("commonly guessed pattern");
    }
    await password.fill("Password1!");
    for (const rule of await strength.getByRole("listitem").all()) {
      await expect(rule.locator(".sr-only")).toHaveText("met");
    }
    await expect(announcement).toContainText("All requirements met.");

    // Even an edit producing identical feedback starts a fresh debounce.
    await password.fill("Password2!");
    await expect(announcement).toBeEmpty();
    // Observe the silence window before the 700ms announcement debounce.
    await page.waitForTimeout(200);
    await expect(announcement).toBeEmpty();
    await expect(announcement).toContainText("Password strength weak.");

    await password.fill("r7!Kp2$vQ9#nL4@x");
    await expect(meter).toHaveAttribute("aria-valuenow", "4");
    await expect(announcement).toBeEmpty();
    await page.waitForTimeout(200);
    await page.locator(".auth-language-select select").selectOption("fr");
    await expect(announcement).toBeEmpty();
    await page.waitForTimeout(200);
    await expect(announcement).toBeEmpty();
    await expect(announcement).toContainText("Tous les critères sont satisfaits.");
    await expect(announcement).not.toContainText("Password strength");

    // Long passphrases can be strong while checklist requirements remain unmet.
    await password.fill("violet meadow lantern orbit");
    await expect(meter).toHaveAttribute("aria-valuenow", "4");
    await expect(meter).toHaveAttribute("aria-valuemax", "4");
    await expect(strength.getByRole("listitem").nth(1).locator(".sr-only")).toHaveText("non satisfait");
    await password.fill("");
    await expect(meter).toHaveAttribute("aria-valuenow", "0");
    await expect(announcement).toBeEmpty();
    await page.waitForTimeout(800);
    await expect(announcement).toBeEmpty();
    expect(requests).toEqual([]);
  });
}

for (const path of ["/register", "/reset-password#token=byte-boundary"]) {
  test(`password validation counts UTF-8 bytes on ${path.split("#")[0]}`, async ({ page }) => {
    await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "byte-boundary" } }));
    await page.goto(path);
    await page.locator(".auth-language-select select").selectOption("en");
    const password = page.locator("#password");
    const warning = page.getByRole("alert").filter({ hasText: "72 UTF-8 bytes" });
    for (const value of ["a".repeat(72), "é".repeat(36), "😀".repeat(18)]) {
      await password.fill("");
      await expect(page.getByRole("meter")).toHaveAttribute("aria-valuenow", "0");
      await password.fill(value);
      await expect(password).toHaveValue(value);
      await expect(password).toHaveAttribute("aria-invalid", "false");
      await expect(warning).toHaveCount(0);
      await password.fill(`${value}a`);
      await expect(password).toHaveValue(`${value}a`);
      await expect(password).toHaveAttribute("aria-invalid", "true");
      await expect(warning).toBeVisible();
    }
    // The minimum counts Unicode characters, rather than UTF-16 code units.
    await password.fill("😀".repeat(7));
    await expect(password).toHaveAttribute("aria-invalid", "true");
    await password.fill("😀".repeat(8));
    await expect(password).toHaveAttribute("aria-invalid", "false");
    await expect(warning).toHaveCount(0);
  });
}
