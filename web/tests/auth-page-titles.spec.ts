import { expect, test } from "@playwright/test";

const cases = [
  ["en", "Forgot password", "Reset password"],
  ["pt-BR", "Esqueceu a senha", "Redefinir senha"],
  ["fr", "Mot de passe oublié", "Réinitialiser le mot de passe"],
  ["es", "Contraseña olvidada", "Restablecer contraseña"],
] as const;

test("recovery page titles follow the selected language", async ({ page }) => {
  for (const [language, forgot, reset] of cases) {
    await page.goto("/forgot-password");
    await page.locator(".auth-language-select select").selectOption(language);
    await expect(page).toHaveTitle(`${forgot} | Vervfy`);
    await expect(page.locator("#auth-title")).toHaveText(forgot);
    await page.reload();
    await expect(page).toHaveTitle(`${forgot} | Vervfy`);
    await page.goto("/reset-password");
    await expect(page).toHaveTitle(`${reset} | Vervfy`);

  }
});
