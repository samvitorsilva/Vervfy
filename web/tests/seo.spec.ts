import { expect, test } from "@playwright/test";
import { homepageFeatures, homepageSeo } from "../src/lib/homepage-seo";
import { SUPPORTED_LANGUAGES } from "../src/lib/language";

for (const language of SUPPORTED_LANGUAGES) {
  test(`server-rendered homepage SEO in ${language}`, async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false, locale: language });
    const page = await context.newPage();
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", language);
    await expect(page.locator("h1")).toBeVisible();
    await expect(page).toHaveTitle(homepageSeo[language].title);
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      await expect(page.locator(selector)).toHaveAttribute("content", homepageSeo[language].description);
    }
    expect(await page.locator('link[rel="canonical"]').count()).toBe(1);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(new URL(canonical!).pathname).toBe("/");
    const schema = JSON.parse((await page.locator('script[type="application/ld+json"]').textContent())!);
    expect(schema.description).toBe(homepageSeo[language].description);
    expect(schema.featureList).toEqual(homepageFeatures[language]);
    expect(schema.inLanguage).toBe(language);
    expect(new URL(schema.url).origin).toBe(new URL(canonical!).origin);
    await context.close();
  });
}

test("language switching preserves consistent homepage metadata", async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ status: 401, body: "{}" }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  for (const language of SUPPORTED_LANGUAGES) {
    await page.locator(".site-footer-language select").selectOption(language);
    await expect(page).toHaveTitle(homepageSeo[language].title);
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      await expect(page.locator(selector)).toHaveAttribute("content", homepageSeo[language].description);
    }
  }
});

test("only public pages appear in the sitemap and auth pages remain noindex", async ({ request }) => {
  const xml = await (await request.get("/sitemap.xml")).text();
  const urls = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => new URL(match[1]));
  expect(urls.map(url => url.pathname)).toEqual(["/", "/privacy", "/terms", "/credits"]);
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain(`Sitemap: ${urls[0].origin}/sitemap.xml`);
  for (const path of ["/login", "/register", "/forgot-password", "/reset-password"]) {
    expect(await (await request.get(path)).text()).toMatch(/name="robots" content="noindex/);
    expect(robots).toContain(`Disallow: ${path}`);
  }
});
