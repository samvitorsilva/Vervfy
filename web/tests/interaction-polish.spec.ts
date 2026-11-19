import { expect, test, type Page } from "@playwright/test";

const first = { id: "first", title: "First song", artist: "First artist", album: "Album", duration: 60, has_cover: false, cover_source: "placeholder", cover_url: "/api/tracks/first/cover", stream_url: "/api/tracks/first/stream" };
const second = { ...first, id: "second", title: "Second song" };

async function library(page: Page) {
  let tracks = [first, second];
  let deletes = 0;
  let block = false;
  let release: (() => void) | undefined;
  await page.context().addCookies([{ name: "auralis_session", value: "test-hint-only", url: "http://127.0.0.1:3100" }]);
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/me") return route.fulfill({ json: { id: "account-one", username: "Tester", has_password: true } });
    if (path === "/api/csrf") return route.fulfill({ json: { csrf_token: "test-csrf" } });
    if (path === "/api/tracks" && route.request().method() === "GET") {
      if (block) await new Promise<void>((resolve) => { release = resolve; });
      return route.fulfill({ json: { tracks } });
    }
    if (path === "/api/tracks/first" && route.request().method() === "DELETE") {
      deletes++;
      tracks = tracks.filter((track) => track.id !== first.id);
      return route.fulfill({ json: { ok: true } });
    }
    if (path === "/api/library/state") return route.fulfill({ headers: { ETag: '"v1"' }, json: { favorites: [], playlists: [] } });
    if (path === "/api/library/listening") return route.fulfill({ json: { lastPlayedAt: {}, month: { playCount: 0, topTracks: [], topArtists: [] }, year: { playCount: 0, topTracks: [], topArtists: [] }, monthStart: 0, asOf: 0, yearLabel: "2026" } });
    if (path === "/api/tracks/covers") return route.fulfill({ json: { covers: {}, pending: false } });
    if (path === "/api/artists/images") return route.fulfill({ json: { artists: {} } });
    if (path === "/api/config") return route.fulfill({ json: {} });
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });
  await page.goto("/");
  await expect(page.locator(".card")).toHaveCount(2);
  return { get deletes() { return deletes; }, block: () => { block = true; }, release: () => { block = false; release?.(); } };
}

test("command search supports keyboard selection, focus restoration and browser back", async ({ page }) => {
  await library(page);
  await page.getByRole("button", { name: "Open command menu" }).focus();
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Command menu", exact: true });
  await expect(dialog).toBeVisible();
  await page.getByRole("combobox").fill("Artists");
  await page.keyboard.press("Enter");
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".view-title")).toHaveText("Artists");
  await expect(page.getByRole("button", { name: "Open command menu" })).toBeFocused();
  await page.goBack();
  await expect(page.locator(".view-title")).toHaveText("Library");
  await page.goForward();
  await expect(page.locator(".view-title")).toHaveText("Artists");
});

test("Undo prevents a durable deletion; expiry sends exactly one delete", async ({ page }) => {
  const backend = await library(page);
  await page.clock.install();
  await page.getByRole("button", { name: "More options for First song", exact: true }).click();
  await page.getByRole("menuitem", { name: "Remove from library", exact: true }).click();
  await expect(page.locator(".card")).toHaveCount(1);
  expect(backend.deletes).toBe(0);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".card")).toHaveCount(2);
  await page.clock.fastForward(9000);
  expect(backend.deletes).toBe(0);
  await page.getByRole("button", { name: "More options for First song", exact: true }).click();
  await page.getByRole("menuitem", { name: "Remove from library", exact: true }).click();
  await page.clock.fastForward(8100);
  await expect.poll(() => backend.deletes).toBe(1);
  await expect(page.locator(".card")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Undo", exact: true })).toHaveCount(0);
});

test("refresh preserves loaded content while the network is pending", async ({ page }) => {
  const backend = await library(page);
  backend.block();
  try {
    const request = page.waitForRequest((request) => new URL(request.url()).pathname === "/api/tracks");
    await page.evaluate(() => window.dispatchEvent(new Event("vervfy:refresh")));
    await request;
    await expect(page.locator(".card")).toHaveCount(2);
    await expect(page.locator(".app-skeleton-track-grid")).toHaveCount(0);
  } finally { backend.release(); }
  await expect(page.locator(".content")).toHaveAttribute("data-loaded", "true");
});

test.describe("mobile sheet behavior", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: "reduce" });
  test("dragging a sheet header dismisses it", async ({ page }) => {
    await library(page);
    const command = page.getByRole("button", { name: "Open command menu" });
    await command.click();
    await page.getByRole("combobox").fill("Keyboard shortcuts");
    await page.keyboard.press("Enter");
    const sheet = page.locator(".shortcuts-dialog");
    await expect(sheet).toBeVisible();
    const header = await sheet.locator(".sheet-drag-handle").boundingBox();
    const x = header!.x + header!.width / 2;
    const y = header!.y + 15;
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y + 140 }] });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect(sheet).toHaveCount(0);
    await expect(page.locator("meta[name=viewport]")).toHaveAttribute("content", /viewport-fit=cover/);
  });
});

test("malformed artist deep links cannot crash the library", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await library(page);
  await page.goto("/?view=artist:%25");
  await expect(page.locator(".view-title")).toHaveText("Library");
  expect(errors).toEqual([]);
});

test("a changed account cannot see the previous account while refreshing", async ({ page }) => {
  await library(page);
  let release: (() => void) | undefined;
  await page.route("**/api/me", (route) => route.fulfill({ json: { id: "account-two", username: "Other account", has_password: true } }));
  await page.route("**/api/tracks", async (route) => {
    await new Promise<void>((resolve) => { release = resolve; });
    return route.fulfill({ json: { tracks: [] } });
  });
  try {
    await page.evaluate(() => window.dispatchEvent(new Event("vervfy:refresh")));
    await expect(page.locator(".app-skeleton-track-grid")).toBeVisible();
    await expect(page.getByText("First song", { exact: true })).not.toBeVisible();
  } finally { release?.(); }
  await expect(page.locator(".content")).toHaveAttribute("data-loaded", "true");
  await expect(page.locator(".card")).toHaveCount(0);
});
