import { expect, test } from "@playwright/test";

for (const path of ["/register", "/reset-password#token=visibility-test"]) {
  test(`new passwords can be revealed and hidden on ${path.split("#")[0]}`, async ({ page }) => {
    await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "visibility-test" } }));
    const submissions: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST") submissions.push(request.url());
    });
    await page.goto(path, { waitUntil: "networkidle" });
    const password = page.locator("#password");
    await password.fill("r7!Kp2$vQ9#nL4@x");
    const meter = page.getByRole("meter");
    await expect(meter).toHaveAttribute("aria-valuenow", "4");
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
      await expect(meter).toHaveAttribute("aria-valuenow", "4");
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
