import { expect, test } from "@playwright/test";

test("social previews, crawl rules and existing brand assets are valid", async ({ page, request }) => {
  for (const path of ["/login", "/register", "/privacy", "/terms", "/credits"]) {
    await page.goto(path);
    const description = await page.locator('meta[name="description"]').getAttribute("content");
    expect(description!.length).toBeGreaterThan(20);
    await expect(page.locator('meta[property="og:description"]')).toHaveAttribute("content", description!);
    await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute("content", "summary_large_image");
    const imageUrl = await page.locator('meta[property="og:image"]').first().getAttribute("content");
    expect(new URL(imageUrl!).protocol).toMatch(/^https?:$/);
    const image = await request.get(new URL(imageUrl!).pathname);
    expect(image.status()).toBe(200);
    expect(image.headers()["content-type"]).toContain("image/png");
    const bytes = await image.body();
    expect(bytes.readUInt32BE(16)).toBe(1200);
    expect(bytes.readUInt32BE(20)).toBe(630);
  }
  const robots = await request.get("/robots.txt");
  expect(robots.status()).toBe(200);
  expect(await robots.text()).toContain("Disallow: /api/");
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.status()).toBe(200);
  const xml = await sitemap.text();
  expect(xml.match(/<loc>/g)).toHaveLength(3);
  for (const path of ["privacy", "terms", "credits"]) expect(xml).toContain(`/${path}</loc>`);
  expect(xml).not.toMatch(/\/(login|register|api)\b/);
  for (const asset of ["/favicon.ico", "/apple-icon.png", "/gemini-svg.svg", "/icon-192.png", "/icon-512.png", "/manifest.webmanifest"]) {
    expect((await request.get(asset)).status()).toBe(200);
  }
  await page.goto("/login");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  const missing = await request.get("/audit-missing-page");
  expect(missing.status()).toBe(404);
});

for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 844, height: 390 }, { width: 1280, height: 720 }]) {
  test(`auth and legal pages reflow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    for (const path of ["/login", "/register", "/privacy", "/terms", "/credits"]) {
      await page.goto(path, { waitUntil: "domcontentloaded" });
      await expect(page.locator("h1")).toBeVisible();
      const layout = await page.evaluate(() => ({
        width: document.documentElement.scrollWidth,
        viewport: innerWidth,
        headingTop: document.querySelector("h1")!.getBoundingClientRect().top,
        brandTop: document.querySelector(".auth-brand")?.getBoundingClientRect().top ?? 0,
        missingAlt: document.querySelectorAll("img:not([alt])").length,
      }));
      expect(layout.width, `${path} at ${viewport.width}px`).toBeLessThanOrEqual(layout.viewport);
      expect(layout.headingTop, `${path} heading must remain reachable`).toBeGreaterThanOrEqual(0);
      expect(layout.brandTop, `${path} must not clip the top of the form`).toBeGreaterThanOrEqual(0);
      expect(layout.missingAlt).toBe(0);
    }
  });
}

test("anonymous lyrics requests are rejected by the server proxy", async ({ request }) => {
  const result = await request.get("/api/lyrics/lrclib/search?q=synthetic-audit");
  expect(result.status()).toBe(401);
  expect(result.headers()["cache-control"]).toBe("no-store");
});
