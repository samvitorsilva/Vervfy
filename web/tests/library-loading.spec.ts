import { expect, test } from "@playwright/test";

for (const locale of [
  { code: "en", label: "Loading your music library" },
  { code: "pt-BR", label: "Carregando sua biblioteca de música…" },
  { code: "fr", label: "Chargement de votre bibliothèque musicale…" },
  { code: "es", label: "Cargando tu biblioteca de música…" },
]) {
  test(`initial library loading has no skeleton sidebar (${locale.code})`, async ({ page, baseURL }) => {
    const origin = new URL(baseURL!).origin;
    await page.context().addCookies([
      { name: "auralis_session", value: "test-ui-hint", url: origin },
      { name: "vervfy_playwright_session", value: "authenticated", url: origin },
      { name: "vervfy-language", value: locale.code, url: origin },
    ]);
    let release: () => void = () => {};
    const gate = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/api/me", async route => {
      await gate;
      await route.continue();
    });
    try {
      await page.goto("/?view=account", { waitUntil: "domcontentloaded" });
      const loader = page.locator(".homepage-transition:visible");
      await expect(loader).toBeVisible();
      await expect(loader).toHaveAccessibleName(locale.label);
      await expect(loader).toHaveAttribute("aria-busy", "true");
      await expect(loader.locator(".homepage-transition-caption")).toHaveText(locale.label);
      await expect(page.locator(".rail")).toHaveCount(0);
      await expect(page.locator(".app-shell-skeleton")).toHaveCount(0);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({ width, height: 844 });
        await expect(loader).toBeInViewport();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      }
      await page.emulateMedia({ reducedMotion: "reduce" });
      await expect(loader.locator(".homepage-transition-progress span")).toHaveCSS("animation-name", "none");
    } finally {
      release();
    }
    await expect(page.getByRole("navigation")).toBeVisible();
    await expect(page.locator(".rail button[data-view='account']")).toHaveAttribute("aria-current", "page");
    await expect(page.locator(".homepage-transition:visible")).toHaveCount(0);
  });
}
