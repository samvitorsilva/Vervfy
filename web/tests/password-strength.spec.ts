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
      await password.fill("Birch!27");
      await expect(meter).toHaveAttribute("aria-valuetext", locale.strong);
      await expect(strength.getByRole("listitem").first().locator(".sr-only")).toHaveText(locale.met);
      await expect(announcement).toContainText(locale.complete);
    }
  });
}
