import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(process.cwd() + "/package.json");
const axe = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

for (const width of [390, 1440]) {
  test(`shared palette, contrast and responsive pages at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/", "/login", "/register", "/forgot-password", "/reset-password", "/reset-password#token=palette-audit", "/privacy", "/terms", "/credits", "/missing-palette-audit", "/offline.html"]) {
      await page.goto(path);
      await page.evaluate(() => document.fonts.ready);
      await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--bg").trim())).toBe("#0C0E14");
      const auth = page.locator(".auth-page");
      if (await auth.count()) {
        await expect(auth).toHaveCSS("background-color", "rgb(12, 14, 20)");
        await expect(page.locator(".auth-card")).toHaveCSS("background-color", "rgb(18, 21, 30)");
        if (await page.locator(".auth-submit").count()) {
          await expect(page.locator(".auth-submit")).toHaveCSS("background-image", "linear-gradient(125deg, rgb(8, 231, 190), rgb(2, 223, 182))");
        }
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.addScriptTag({ content: axe });
      const violations = await page.evaluate(async () => {
        const engine = (window as unknown as { axe: { run: (options: object) => Promise<{ violations: { id: string; nodes: { target: string[]; failureSummary: string }[] }[] }> } }).axe;
        const result = await engine.run({ runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] } });
        return result.violations.map(({ id, nodes }) => ({ id, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) }));
      });
      expect(violations, `${path}: ${JSON.stringify(violations)}`).toEqual([]);
      await page.keyboard.press("Tab");
      const focus = await page.evaluate(() => {
        const element = document.activeElement;
        if (!element || element === document.body) return true;
        const style = getComputedStyle(element);
        return style.outlineStyle !== "none" && parseFloat(style.outlineWidth) >= 2;
      });
      expect(focus, `${path}: keyboard focus must be visible`).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`${path.replace(/\W/g, "_") || "home"}-${width}.png`), fullPage: true });
    }
  });
}

for (const width of [390, 1440]) {
  test(`authenticated views share the palette at ${width}px`, async ({ page, baseURL }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.context().addCookies([
      { name: "auralis_session", value: "test-ui-hint", url: new URL(baseURL!).origin },
      { name: "vervfy_playwright_session", value: "authenticated", url: new URL(baseURL!).origin },
    ]);
    for (const view of ["library", "favorites", "playlists", "artists", "account"]) {
      await page.goto(`/?view=${view}`);
      await expect(page.locator("#app")).toBeVisible();
      await expect(page.locator("body")).toHaveCSS("color", "rgb(242, 243, 247)");
      await expect(page.locator("body")).toHaveCSS("background-color", "rgb(12, 14, 20)");
      if (width > 640) {
        await expect(page.locator(".rail")).toHaveCSS("background-color", "rgb(18, 21, 30)");
      }
      await page.addScriptTag({ content: axe });
      const contrast = await page.evaluate(async () => {
        const engine = (window as unknown as { axe: { run: (options: object) => Promise<{ violations: unknown[] }> } }).axe;
        return (await engine.run({ runOnly: ["color-contrast"] })).violations;
      });
      expect(contrast, `${view}: text contrast`).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`${view}-${width}.png`), fullPage: true });
    }
  });
}
