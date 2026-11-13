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
  const robotsText = await robots.text();
  expect(robotsText).toContain("Allow: /");
  expect(robotsText).toContain("Disallow: /api/");
  expect(robotsText).not.toContain("Disallow: /$");
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.status()).toBe(200);
  const xml = await sitemap.text();
  expect(xml.match(/<loc>/g)).toHaveLength(4);
  expect(xml).toMatch(/<loc>https?:\/\/[^<]+\/<\/loc>/);
  for (const path of ["privacy", "terms", "credits"]) expect(xml).toContain(`/${path}</loc>`);
  expect(xml).not.toMatch(/\/(login|register|api)\b/);
  for (const asset of ["/favicon.ico", "/apple-icon.png", "/gemini-svg.svg", "/icon-192.png", "/icon-512.png", "/manifest.webmanifest"]) {
    expect((await request.get(asset)).status()).toBe(200);
  }
  await page.goto("/login");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await page.goto("/");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /index/);
  const missing = await request.get("/audit-missing-page");
  expect(missing.status()).toBe(404);
});

test("homepage explains Vervfy publicly, translates its message, and links to sign-in and legal pages", async ({ page }) => {
  await page.route("**/api/me", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Not authenticated"}' }),
  );
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  const html = await response!.text();
  expect(html).toContain("Your personal music library, accessible from anywhere.");
  expect(html).toContain("Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.");
  expect(html).not.toContain("self-hosted");
  await expect(page.getByRole("heading", { level: 1, name: "Your personal music library, accessible from anywhere." })).toBeVisible();
  await expect(page.getByText("Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your music library" })).toBeVisible();
  await expect(page.getByText("Each account has its own separate music library.")).toBeVisible();
  await expect(page.locator(".player-mockup, .mini-stats, .mock-controls")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Create account" }).first()).toHaveAttribute("href", "/register");
  await expect(page.getByRole("link", { name: "Log in" }).first()).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Read the privacy policy" })).toHaveAttribute("href", "/privacy");
  await expect(page.getByRole("link", { name: "Privacy Policy", exact: true })).toHaveAttribute("href", "/privacy");
  await expect(page.getByRole("link", { name: "Terms and Conditions" })).toHaveAttribute("href", "/terms");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    "Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.",
  );
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /index/);

  const languageSelect = page.locator(".site-footer-language select");
  for (const [language, heading, description, privacyLink] of [
    ["pt-BR", "Sua biblioteca pessoal de música, acessível de qualquer lugar.", "Envie suas músicas, organize playlists e favoritos e encontre letras e informações sobre artistas em um só lugar.", "Leia a política de privacidade"],
    ["fr", "Votre bibliothèque musicale personnelle, accessible partout.", "Importez votre musique, organisez vos playlists et vos favoris, et retrouvez des paroles et des informations sur les artistes au même endroit.", "Lire la politique de confidentialité"],
    ["es", "Tu biblioteca personal de música, accesible desde cualquier lugar.", "Sube tu música, organiza listas y favoritos, y encuentra letras e información de artistas en un solo lugar.", "Lee la política de privacidad"],
    ["en", "Your personal music library, accessible from anywhere.", "Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.", "Read the privacy policy"],
  ]) {
    await languageSelect.selectOption(language);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByText(description, { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: privacyLink })).toBeVisible();
  }

  for (const viewport of [
    { width: 320, height: 568 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
    { width: 1280, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    const layout = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      viewport: innerWidth,
      headingTop: document.querySelector("h1")!.getBoundingClientRect().top,
      headerBottom: document.querySelector(".homepage-header")!.getBoundingClientRect().bottom,
      heroTop: document.querySelector(".landing-hero")!.getBoundingClientRect().top,
      brandLogoSize: document.querySelector(".homepage-brand img")!.getBoundingClientRect().width,
      brandFontSize: Number.parseFloat(getComputedStyle(document.querySelector(".homepage-brand")!).fontSize),
    }));
    expect(layout.width, `homepage at ${viewport.width}px`).toBeLessThanOrEqual(layout.viewport);
    expect(layout.headingTop, `homepage heading at ${viewport.width}px`).toBeGreaterThanOrEqual(0);
    expect(layout.heroTop - layout.headerBottom, `header-to-content gap at ${viewport.width}px`).toBeLessThan(56);
    expect(layout.brandLogoSize).toBe(42);
    expect(layout.brandFontSize).toBeGreaterThan(20);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  const footerLayout = await page.evaluate(() => {
    const footer = document.querySelector(".site-footer")!;
    const [language, copyright] = [...footer.children];
    return {
      languageTop: language.getBoundingClientRect().top,
      copyrightTop: copyright.getBoundingClientRect().top,
      privacyBottom: document.querySelector(".homepage-privacy")!.getBoundingClientRect().bottom,
      footerTop: footer.getBoundingClientRect().top,
    };
  });
  expect(footerLayout.languageTop).toBe(footerLayout.copyrightTop);
  expect(footerLayout.footerTop - footerLayout.privacyBottom).toBeLessThan(32);

  await page.setViewportSize({ width: 320, height: 568 });
  const homepage = page.locator(".homepage-page");
  await homepage.evaluate((element) => element.scrollTo(0, element.scrollHeight));
  expect(await homepage.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await expect(page.getByRole("link", { name: "Terms and Conditions" })).toBeInViewport();
});

test("homepage session-check error can be retried", async ({ page }) => {
  let attempts = 0;
  let retryRequested = false;
  await page.route("**/api/me", (route) => {
    attempts += 1;
    return route.fulfill({
      status: retryRequested ? 401 : 503,
      contentType: "application/json",
      body: '{"detail":"Not authenticated"}',
    });
  });
  await page.goto("/");
  await expect(page.locator(".homepage-error")).toContainText("Unable to confirm your sign-in status.");
  retryRequested = true;
  await page.locator(".homepage-error button").click();
  await expect(page.locator(".homepage-error")).toHaveCount(0);
  expect(attempts).toBeGreaterThan(0);
});

for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 844, height: 390 }, { width: 1280, height: 720 }]) {
  test(`auth and legal pages reflow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.route("**/api/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Not authenticated"}' }),
    );
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
