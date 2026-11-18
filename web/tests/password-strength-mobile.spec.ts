import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 });
for (const path of ["/register", "/reset-password#token=mobile-test"]) {
  test(`password strength works on phone ${path.split("#")[0]}`, async ({ page }) => {
    await page.route("**/api/csrf", (route) => route.fulfill({ json: { csrf_token: "mobile-test" } }));
    await page.goto(path);
    await page.locator(".auth-language-select select").selectOption("fr");
    const password = page.locator("#password");
    await password.fill("Birch!27");
    const meter = page.getByRole("meter");
    await expect(meter).toHaveAttribute("aria-valuetext", "Forte");
    await expect(meter).toBeInViewport();
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      const metrics = await page.evaluate(() => ({
        viewport: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        meterHeight: document.querySelector('[role="meter"]')?.getBoundingClientRect().height,
        checkHeight: document.querySelector(".password-strength-check")?.getBoundingClientRect().height,
      }));
      expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewport);
      expect(metrics.meterHeight).toBe(6);
      expect(metrics.checkHeight).toBe(14);
    }
  });
}
