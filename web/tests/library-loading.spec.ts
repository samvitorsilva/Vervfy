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
      const contrast = await loader.evaluate(element => {
        const luminance = (color: string) => {
          const rgb = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(channel => {
            const value = channel / 255;
            return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
          });
          return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
        };
        const text = luminance(getComputedStyle(element.querySelector(".homepage-transition-caption")!).color);
        const background = luminance(getComputedStyle(element).backgroundColor);
        return (Math.max(text, background) + .05) / (Math.min(text, background) + .05);
      });
      expect(contrast).toBeGreaterThanOrEqual(4.5);
      await expect(page.locator(".rail")).toHaveCount(0);
      await expect(page.locator(".app-shell-skeleton")).toHaveCount(0);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({ width, height: 844 });
        await expect(loader).toBeInViewport();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      }
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      await expect(loader.locator(".homepage-transition-caption")).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
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
