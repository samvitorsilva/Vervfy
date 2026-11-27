import { test, expect, type Page } from "@playwright/test";

test.beforeEach(() => {
  test.skip(Boolean(process.env.PLAYWRIGHT_BASE_URL || process.env.PLAYWRIGHT_BACKEND_URL), "Synthetic local servers only; never run these mutations against a remote service.");
});

async function library(page: Page) {
  // Keep the production CSP intact. This synthetic HTTPS host never leaves the
  // test harness; its requests are fulfilled from our loopback fixture server.
  await page.context().route("https://audio-test.supabase.co/**", async route => {
    const response = await route.fetch({ url: route.request().url().replace("https://audio-test.supabase.co", "http://127.0.0.1:8100") });
    await route.fulfill({ response });
  });
  await page.route("**/api/tracks", route => route.fulfill({ json: { tracks: [{
    id: "playwright-track-1", title: "Security fixture", artist: "Test", album: "Test",
    duration: 30, has_cover: false, cover_source: "placeholder",
    cover_url: "/api/tracks/playwright-track-1/cover",
    stream_url: "/api/tracks/playwright-track-1/stream",
    lease_url: "/api/tracks/playwright-track-1/playback-lease",
  }] } }));
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Play Security fixture", exact: true })).toBeVisible();
}

const audioState = (page: Page) => page.locator("audio").evaluate((e: HTMLAudioElement) => ({
  time: e.currentTime, paused: e.paused, src: e.getAttribute("src"), rate: e.playbackRate,
}));

test("15-minute lease renews repeatedly without replacing a healthy native source", async ({ page }) => {
  await library(page);
  await page.clock.install();
  let leases = 0;
  page.on("response", response => { if (response.url().endsWith("/playback-lease")) leases++; });
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  const initial = await audioState(page);
  for (let cycle = 0; cycle < 3; cycle++) {
    await page.clock.fastForward(781_000);
    await expect.poll(() => leases).toBe(cycle + 2);
    expect((await audioState(page)).src).toBe(initial.src);
  }
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  const position = (await audioState(page)).time;
  await page.getByRole("slider", { name: "Track progress", exact: true }).press("ArrowRight");
  expect((await audioState(page)).time).toBeGreaterThan(position);
  expect((await audioState(page)).paused).toBe(true);
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).paused).toBe(false);
  expect((await audioState(page)).time).toBeGreaterThanOrEqual(position);
});

test("logout tears down every tab before a delayed logout response", async ({ page, context }) => {
  await library(page);
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  const other = await context.newPage();
  await other.goto("/");
  await expect(other.getByRole("button", { name: "Log out", exact: true }).first()).toBeVisible();
  await other.route("**/logout", async route => {
    await new Promise(resolve => setTimeout(resolve, 2500));
    await route.fulfill({ status: 503, json: { detail: "Synthetic delay" } });
  });
  await other.getByRole("button", { name: "Log out", exact: true }).first().click();
  await expect.poll(async () => (await audioState(page)).src).toBeNull();
  expect((await audioState(page)).paused).toBe(true);
  await expect(page.getByRole("button", { name: "Play Security fixture", exact: true })).toHaveCount(0);
});

test("downloaded audio works offline and logout unloads its blob without deleting the saved copy", async ({ page, context }) => {
  await library(page);
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page.getByRole("button", { name: "Download for offline listening", exact: true }).click();
  await expect(page.getByRole("button", { name: "Remove offline download", exact: true })).toBeVisible();
  await context.setOffline(true);
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).src?.startsWith("blob:")).toBe(true);
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  await page.evaluate(() => window.dispatchEvent(new StorageEvent("storage", { key: "vervfy:logout", newValue: "test" })));
  await expect.poll(async () => (await audioState(page)).src).toBeNull();
  const saved = await page.evaluate(() => new Promise<number>((resolve, reject) => {
    const request = indexedDB.open("auralis-db");
    request.onsuccess = () => {
      const db = request.result;
      const count = db.transaction("offlineTracks", "readonly").objectStore("offlineTracks").count();
      count.onsuccess = () => { resolve(count.result); db.close(); };
      count.onerror = () => reject(count.error);
    };
    request.onerror = () => reject(request.error);
  }));
  expect(saved).toBe(1);
  await context.setOffline(false);
});

test("real HTTP Range requests reject the same capability after wall-clock expiry", async ({ request }) => {
  const issued = await request.post("http://127.0.0.1:8100/__test/short-lived-media");
  const { url } = await issued.json();
  const before = await request.get(url, { headers: { Range: "bytes=0-1", "Cache-Control": "no-cache" } });
  expect(before.status()).toBe(206);
  expect(before.headers()["cache-control"]).toContain("no-store");
  await new Promise(resolve => setTimeout(resolve, 1600));
  const after = await request.get(url, { headers: { Range: "bytes=0-1", "Cache-Control": "no-cache" } });
  expect(after.status()).toBe(403);
});

test("a late lease response cannot restart playback after logout", async ({ page }) => {
  await library(page);
  let release = () => {};
  let requested = false;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/playback-lease", async route => {
    requested = true;
    await gate;
    const now = Date.now() / 1000;
    await route.fulfill({ json: { url: "https://audio-test.supabase.co/storage/v1/object/sign/songs/playwright-track-1.wav?token=late", serverTime: now, expiresAt: now + 900 } }).catch(() => {});
  });
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(() => requested).toBe(true);
  await page.evaluate(() => window.dispatchEvent(new StorageEvent("storage", { key: "vervfy:logout", newValue: "test" })));
  release();
  await expect.poll(async () => (await audioState(page)).src).toBeNull();
  await page.waitForTimeout(200);
  expect((await audioState(page)).paused).toBe(true);
  expect((await audioState(page)).src).toBeNull();
});

test("a renewal 401 tears down a healthy player and requests sign-in", async ({ page }) => {
  await library(page);
  await page.clock.install();
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  await page.route("**/playback-lease", route => route.fulfill({ status: 401, json: { detail: "Session revoked" } }));
  await page.clock.fastForward(781_000);
  await expect(page).toHaveURL(/\/login$/);
  await expect.poll(async () => (await audioState(page)).src).toBeNull();
  expect((await audioState(page)).paused).toBe(true);
});

test("legacy bytes remain playable through authenticated application streaming", async ({ page }) => {
  await library(page);
  await page.route("**/playback-lease", route => route.fulfill({ status: 409, json: { detail: "Legacy audio" } }));
  await page.route("**/api/tracks/playwright-track-1/stream", async route => {
    const response = await route.fetch({ url: "http://127.0.0.1:8100/storage/v1/object/sign/songs/playwright-track-1.wav?token=legacy-fixture" });
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  expect((await audioState(page)).src).toContain("/api/tracks/playwright-track-1/stream");
});

test("three successive expired media requests recover on the same track with bounded renewal", async ({ page, request }) => {
  await library(page);
  let leases = 0;
  page.on("response", response => { if (response.url().endsWith("/playback-lease")) leases++; });
  await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
  await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
  for (let cycle = 0; cycle < 3; cycle++) {
    const before = leases;
    await request.post("http://127.0.0.1:8100/__test/expire-issued-media");
    await page.locator("audio").evaluate((e: HTMLAudioElement) => { e.load(); void e.play().catch(() => {}); });
    await expect.poll(() => leases).toBe(before + 1);
    await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
    expect((await audioState(page)).paused).toBe(false);
    await expect(page.locator(".now-title")).toHaveText("Security fixture");
  }
});

test.describe("mobile background lifecycle simulation", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  test("hidden native audio continues and foreground recovery preserves intent", async ({ page }) => {
    await library(page);
    await page.getByRole("button", { name: "Play Security fixture", exact: true }).click();
    await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(0);
    const before = await audioState(page);
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await expect.poll(async () => (await audioState(page)).time).toBeGreaterThan(before.time + 0.25);
    expect((await audioState(page)).src).toBe(before.src);
    await page.locator("audio").evaluate((e: HTMLAudioElement) => e.pause());
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await expect.poll(async () => (await audioState(page)).paused).toBe(false);
    expect((await audioState(page)).time).toBeGreaterThanOrEqual(before.time);
  });
});
