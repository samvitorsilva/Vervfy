import { expect, test } from "@playwright/test";
import { homepageFeatures, homepageSeo } from "../src/lib/homepage-seo";
import { SUPPORTED_LANGUAGES } from "../src/lib/language";

const canonicalHome = new URL("/", process.env.SEO_EXPECTED_SITE_URL ?? process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100").href;
const headings = {
  en: "Vervfy — your personal music library, accessible from anywhere.",
  "pt-BR": "Vervfy — sua biblioteca pessoal de música, acessível de qualquer lugar.",
  fr: "Vervfy — votre bibliothèque musicale personnelle, accessible partout.",
  es: "Vervfy — tu biblioteca personal de música, accesible desde cualquier lugar.",
};

for (const language of SUPPORTED_LANGUAGES) {
  test(`server-rendered homepage SEO in ${language}`, async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false, locale: language });
    const page = await context.newPage();
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", language);
    await expect(page.locator("h1")).toHaveText(headings[language]);
    expect(homepageSeo[language].description.match(/Vervfy/g)).toHaveLength(1);
    await expect(page).toHaveTitle(homepageSeo[language].title);
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      await expect(page.locator(selector)).toHaveAttribute("content", homepageSeo[language].description);
    }
    expect(await page.locator('link[rel="canonical"]').count()).toBe(1);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(new URL(canonical!).href).toBe(canonicalHome);
    const scripts = page.locator('script[type="application/ld+json"]');
    await expect(scripts).toHaveCount(1);
    const data = JSON.parse((await scripts.textContent())!);
    expect(data["@context"]).toBe("https://schema.org");
    expect(data["@graph"]).toHaveLength(2);
    const websites = data["@graph"].filter((entity: { "@type": string }) => entity["@type"] === "WebSite");
    const apps = data["@graph"].filter((entity: { "@type": string }) => entity["@type"] === "SoftwareApplication");
    expect(websites).toEqual([{ "@type": "WebSite", "@id": `${canonicalHome}#website`, name: "Vervfy", url: canonicalHome }]);
    expect(apps).toHaveLength(1);
    const schema = apps[0];
    expect(schema.name).toBe("Vervfy");
    expect(schema.url).toBe(canonicalHome);
    expect(schema).not.toHaveProperty("aggregateRating");
    expect(schema).not.toHaveProperty("review");
    expect(schema.description).toBe(homepageSeo[language].description);
    expect(schema.featureList).toEqual(homepageFeatures[language]);
    expect(schema.inLanguage).toBe(language);
    expect(new URL(schema.url).origin).toBe(new URL(canonical!).origin);
    await context.close();
  });
}

test("language switching preserves consistent homepage metadata", async ({ page, baseURL }) => {
  await page.context().addCookies([
    { name: "vervfy-language", value: "en", url: new URL(baseURL!).origin },
  ]);
  await page.route("**/api/me", route => route.fulfill({ status: 401, body: "{}" }));
  const sessionCheck = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/me");
  await page.goto("/");
  await sessionCheck;
  for (const language of SUPPORTED_LANGUAGES) {
    await page.locator(".site-footer-language select").selectOption(language);
    await expect(page.locator("html")).toHaveAttribute("lang", language);
    await expect(page.locator("h1")).toHaveText(headings[language]);
    await expect(page).toHaveTitle(homepageSeo[language].title);
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      await expect(page.locator(selector)).toHaveAttribute("content", homepageSeo[language].description);
    }
  }
});

test("only public pages appear in the sitemap and auth pages remain noindex", async ({ request }) => {
  const xml = await (await request.get("/sitemap.xml")).text();
  const urls = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => new URL(match[1]));
  expect(urls.map(url => url.pathname)).toEqual(["/", "/privacy", "/terms", "/credits", "/features"]);
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain(`Sitemap: ${urls[0].origin}/sitemap.xml`);
  for (const path of ["/login", "/register", "/forgot-password", "/reset-password"]) {
    expect(await (await request.get(path)).text()).toMatch(/name="robots" content="noindex/);
    expect(robots).toContain(`Disallow: ${path}`);
  }
});

test("public page canonicals match the configured origin and sitemap", async ({ browser, request }) => {
  const xml = await (await request.get("/sitemap.xml")).text();
  const urls = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map(match => match[1]);
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  for (const path of ["/", "/privacy", "/terms", "/credits", "/features"]) {
    const expected = new URL(path, canonicalHome).href;
    expect(urls).toContain(expected);
    const response = await page.goto(path, { waitUntil: "domcontentloaded" });
    expect(response?.status()).toBe(200);
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(new URL(canonical!).href).toBe(expected);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
  }
  await context.close();
});
