import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { featuresContent } from "../src/lib/features-content";
import { SUPPORTED_LANGUAGES } from "../src/lib/language";

const axeSource = readFileSync(resolve("node_modules/axe-core/axe.min.js"), "utf8");
const canonical = new URL("/features", process.env.SEO_EXPECTED_SITE_URL ?? process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100").href;

for (const language of SUPPORTED_LANGUAGES) {
  test(`features are public and server-rendered in ${language}`, async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false, locale: language });
    const page = await context.newPage();
    const response = await page.goto("/features", { waitUntil: "domcontentloaded" });
    expect(response?.status()).toBe(200);
    const content = featuresContent[language];
    await expect(page.locator("html")).toHaveAttribute("lang", language);
    await expect(page.locator("h1")).toHaveText(content.heading);
    await expect(page).toHaveTitle(`${content.title} | Vervfy`);
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      await expect(page.locator(selector)).toHaveAttribute("content", content.description);
    }
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", canonical);
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute("content", canonical);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
    await expect(page.locator("main h2")).toHaveCount(7);
    for (const [heading, body] of content.sections) {
      await expect(page.getByRole("heading", { level: 2, name: heading, exact: true })).toBeVisible();
      await expect(page.getByText(body, { exact: true })).toBeVisible();
    }
    await expect(page.locator('main a[href="/"]').first()).toBeVisible();
    await expect(page.locator('script[type="application/ld+json"]')).toHaveCount(0);
    await context.close();
  });
}

test("features metadata and content stay localized when switching languages", async ({ page }) => {
  let accountRequests = 0;
  await page.route("**/api/**", route => {
    accountRequests++;
    return route.fulfill({ status: 401, body: "{}" });
  });
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/features");
  for (const language of SUPPORTED_LANGUAGES) {
    await page.locator(".site-footer-language select").selectOption(language);
    await expect(page.locator("h1")).toHaveText(featuresContent[language].heading);
    expect(await page.locator(".features-page").evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await expect(page).toHaveTitle(`${featuresContent[language].title} | Vervfy`);
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      await expect(page.locator(selector)).toHaveAttribute("content", featuresContent[language].description);
    }
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", canonical);
  }
  await page.reload();
  await expect(page.locator("h1")).toHaveText(featuresContent.es.heading);
  expect(accountRequests).toBe(0);
});

test("homepage and features have discoverable internal links", async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ status: 401, body: "{}" }));
  await page.goto("/");
  await page.getByRole("link", { name: featuresContent.en.link }).click();
  await expect(page).toHaveURL(/\/features$/);
  await expect(page.locator("h1")).toHaveText(featuresContent.en.heading);
  await page.locator('main a[href="/"]').first().click();
  await expect(page.locator("h1")).toContainText("Vervfy");
  await expect(page).toHaveURL(/\/$/);
});

test("features are accessible and responsive", async ({ page }) => {
  await page.goto("/features");
  await expect(page.locator("#nowbar")).toHaveCount(0);
  await page.evaluate(axeSource);
  const violations = await page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: () => Promise<{ violations: { id: string; impact: string }[] }> } }).axe;
    return (await axe.run()).violations.map(({ id, impact }) => ({ id, impact }));
  });
  expect(violations).toEqual([]);
  for (const width of [320, 390, 768, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.locator("h1")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator(".features-page").evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.locator(".features-page").evaluate(element => { element.scrollTop = element.scrollHeight; });
    await expect(page.locator('.features-actions a[href="/register"]')).toBeInViewport();
    await page.locator(".features-page").evaluate(element => { element.scrollTop = 0; });
  }
  await page.screenshot({ path: "/tmp/vervfy-features-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "/tmp/vervfy-features-mobile.png" });
});
