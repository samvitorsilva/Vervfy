Warning: truncated output (original token count: 29279)
Total output lines: 2780

import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const username = process.env.PLAYWRIGHT_USERNAME;
const password = process.env.PLAYWRIGHT_PASSWORD;
const externalBackend = Boolean(process.env.PLAYWRIGHT_BACKEND_URL);
const externalApp = Boolean(process.env.PLAYWRIGHT_BASE_URL);

function makeWav(seconds = 6): Buffer {
  const sampleRate = 22_050;
  const sampleCount = sampleRate * seconds;
  const dataSize = sampleCount * 2;
  const wav = Buffer.alloc(44 + dataSize);

  wav.write("RIFF", 0);
  wav.writeUInt32LE(36 + dataSize, 4);
  wav.write("WAVE", 8);
  wav.write("fmt ", 12);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(sampleRate, 24);
  wav.writeUInt32LE(sampleRate * 2, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(dataSize, 40);

  for (let index = 0; index < sampleCount; index += 1) {
    const sample = Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 0.15;
    wav.writeInt16LE(Math.round(sample * 32_767), 44 + index * 2);
  }
  return wav;
}

test("document language follows the saved locale and language changes", async ({ page }) => {
  test.skip(
    externalApp,
    "This regression test checks the local server-rendered document language.",
  );
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.removeItem("vervfy:language");
    document.cookie = "vervfy-language=fr; Path=/";
  });
  await page.reload();

  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  await expect(page.getByRole("heading", { name: "Bon retour" })).toBeVisible();
  const languageSelect = page.locator(".auth-language-select select");
  for (const [value, language, heading] of [
    ["es", "es", "Qué bueno verte de nuevo"],
    ["pt-BR", "pt-BR", "Que bom ter você de volta!"],
    ["en", "en", "Welcome back"],
    ["fr", "fr", "Bon retour"],
  ]) {
    await languageSelect.selectOption(value);
    await expect(page.locator("html")).toHaveAttribute("lang", language);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
});

test("public routes have useful metadata, a working footer, and a branded 404", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(page).toHaveTitle("Log in | Vervfy");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    "Log in to your Vervfy account to access your music library.",
  );
  await expect(page.locator(".site-footer")).toContainText(
    `© ${new Date().getFullYear()} Vervfy`,
  );
  await expect(
    page.locator(".site-footer a").filter({ hasText: "View credits" }),
  ).toHaveAttribute("href", "/credits");
  await expect(
    page.locator(".site-footer a").filter({ hasText: "Privacy Policy" }),
  ).toHaveAttribute("href", "/privacy");
  await expect(
    page.locator(".site-footer a").filter({ hasText: "Terms and Conditions" }),
  ).toHaveAttribute("href", "/terms");

  await page.goto("/register");
  await expect(page).toHaveTitle("Create an account | Vervfy");
  await page.goto("/credits");
  await expect(page).toHaveTitle("Credits and data sources | Vervfy");
  await page.goto("/privacy");
  await expect(page).toHaveTitle("Privacy Policy | Vervfy");
  await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible();
  await expect(
    page.getByText(/This document describes the current implementation/),
  ).toBeVisible();
  await expect(
    page.getByText(/Google sign-in requests OpenID Connect identity/),
  ).toBeVisible();
  await expect(
    page.getByText(/not a promise of immediate physical erasure/),
  ).toBeVisible();
  const privacyContactLinks = page.getByRole("link", { name: "vervfy.dev@proton.me" });
  await expect(privacyContactLinks).toHaveCount(2);
  for (let index = 0; index < 2; index += 1) {
    await expect(privacyContactLinks.nth(index)).toHaveAttribute(
      "href",
      "mailto:vervfy.dev@proton.me",
    );
  }
  await page.goto("/terms");
  await expect(page).toHaveTitle("Terms and Conditions | Vervfy");
  await expect(page.getByRole("heading", { name: "Terms and Conditions" })).toBeVisible();
  await expect(
    page.getByText(/does not provide a licensed music catalogue/),
  ).toBeVisible();
  await expect(page.getByText(/restrict or suspend an account/)).toBeVisible();
  await expect(
    page.getByText(/Nothing here limits mandatory consumer or data-protection rights/),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Privacy Policy" }).first()).toHaveAttribute(
    "href",
    "/privacy",
  );
  const manifestResponse = await page.request.get("/manifest.webmanifest");
  expect(manifestResponse.ok()).toBe(true);
  const manifest = await manifestResponse.json();
  expect(manifest.icons).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ src: "/brand-icon-192.png", sizes: "192x192" }),
      expect.objectContaining({ src: "/brand-icon-512.png", sizes: "512x512" }),
    ]),
  );
  for (const iconPath of ["/favicon.ico", "/brand-icon-180.png", "/brand-icon-192.png", "/brand-icon-512.png"]) {
    expect((await page.request.get(iconPath)).ok(), iconPath).toBe(true);
  }

  const missingPage = await page.goto("/this-page-does-not-exist");
  expect(missingPage?.status()).toBe(404);
  await expect(page).toHaveTitle("Page not found | Vervfy");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Back to Vervfy/ })).toHaveAttribute(
    "href",
    "/",
  );
});

test("account settings expose privacy requests and clear cached lyrics on deletion", async ({
  page, baseURL,
}) => {
  await page.route(/^https:\/\//, route => route.abort());
  await page.context().addCookies([
    { name: "vervfy_playwright_session", value: "authenticated", url: baseURL! },
    { name: "auralis_session", value: "test-ui-hint", url: baseURL! },
  ]);
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    localStorage.setItem(
      "vervfy:lrclib:v4:cached-track",
      JSON.stringify({ savedAt: Date.now(), lyrics: { text: "cached lyrics" } }),
    );
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve, reject) => {
        const request = indexedDB.open("auralis-db", 2);
        request.onupgradeneeded = () => {
          const database = request.result;
          if (!database.objectStoreNames.contains("kv")) database.createObjectStore("kv");
          if (!database.objectStoreNames.contains("handles")) database.createObjectStore("handles");
          if (!database.objectStoreNames.contains("offlineTracks")) {
            database.createObjectStore("offlineTracks", { keyPath: "id" });
          }
        };
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
          const database = request.result;
          const transaction = database.transaction("offlineTracks", "readwrite");
          const store = transaction.objectStore("offlineTracks");
          store.put({
            id: "playwright-user:offline-track",
            accountId: "playwright-user",
            trackId: "offline-track",
            audio: new Blob(["account audio"]),
          });
          store.put({
            id: "another-user:offline-track",
            accountId: "another-user",
            trackId: "offline-track",
            audio: new Blob(["other account audio"]),
          });
          transaction.oncomplete = () => {
            database.close();
            resolve();
          };
          transaction.onerror = () => reject(transaction.error);
          transaction.onabort = () => reject(transaction.error);
        };
      }),
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open account" }).click();

  await expect(page.getByRole("heading", { name: "Privacy & data requests" })).toBeVisible();
  await expect(page.getByRole("link", { name: "View privacy options" })).toHaveAttribute(
    "href",
    "/privacy",
  );
  await page.getByRole("button", { name: "Delete account" }).first().click();
  await page.getByLabel("Current password").fill("playwright-test-password");
  await page.getByLabel("Type DELETE to confirm").fill("DELETE");
  await page.route("**/api/account", async (route) => {
    if (route.request().method() === "DELETE") {
      await route.fulfill({ json: { ok: true } });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Hold to delete account" }).focus();
  await page.keyboard.down("Space");

  await expect(page).toHaveURL(/\/login\?account_deleted=1$/);
  await page.keyboard.up("Space");
  await expect
    .poll(() =>
      page.evaluate(() =>
        localStorage.getItem("vervfy:lrclib:v4:cached-track"),
      ),
    )
    .toBeNull();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          new Promise<string[]>((resolve, reject) => {
            const request = indexedDB.open("auralis-db", 2);
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
              const database = request.result;
              const transaction = database.transaction("offlineTracks", "readonly");
              const read = transaction.objectStore("offlineTracks").getAll();
              read.onsuccess = () => {
                resolve(
                  read.result.map(
                    (record: { accountId: string }) => record.accountId,
                  ),
                );
              };
              read.onerror = () => reject(read.error);
              transaction.oncomplete = () => database.close();
            };
          }),
      ),
    )
    .toEqual(["another-user"]);
});

test("brand logo returns to the library view", async ({ page }) => {
  await logInToMockLibrary(page);
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect(page.locator(".view-title")).toHaveText("Library");
  await expect(page.locator(".home-profile-avatar")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your library is empty" })).toBeVisible();
  await page.getByRole("navigation", { name: "Main navigation" })
    .getByRole("button", { name: "Playlists" })
    .click();
  await expect(page.locator(".view-title")).toHaveText("Playlists");
  await page.getByRole("link", { name: "Vervfy" }).click();
  await expect(page.locator(".view-title")).toHaveText("Library");
});

async function loadMockPlaybackTrack(
  page: Page,
  title: string,
  trackNumber: number,
  artist = "Vervfy Test Artist",
): Promise<Locator> {
  const id = `playwright-track-${trackNumber}`;
  await page.route("**/api/tracks", (route) =>
    route.fulfill({
      json: {
        tracks: [
          {
            id,
            title,
            artist,
            album: "Playwright Test Album",
            duration: 30,
            has_cover: false,
            cover_source: "placeholder",
            cover_url: `/api/tracks/${id}/cover`,
            stream_url: `/api/tracks/${id}/stream`,
            custom_lyrics: null,
          },
        ],
      },
    }),
  );
  await page.reload();
  const trackCard = page.locator(".card").filter({ hasText: title });
  await expect(trackCard).toBeVisible();
  return trackCard;
}

async function logInToMockLibrary(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("permanent API client errors are not retried", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This retry regression test uses the local mock backend.",
  );
  let trackRequests = 0;
  await page.route("**/api/tracks", async (route) => {
    trackRequests += 1;
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid request" }),
    });
  });
  await logInToMockLibrary(page);
  await expect.poll(() => trackRequests).toBeGreaterThan(0);
  const initialRequests = trackRequests;
  await page.waitForTimeout(2_500);
  expect(trackRequests).toBe(initialRequests);
});

async function loadMockPlaybackQueue(
  page: Page,
  titles: string[],
  firstTrackNumber: number,
  coverSource: "placeholder" | "musicbrainz" = "placeholder",
): Promise<Locator[]> {
  const tracks = titles.map((title, index) => {
    const id = `playwright-track-${firstTrackNumber + index}`;
    return {
      id,
      title,
      artist: "Vervfy Test Artist",
      album: "Playwright Test Album",
      duration: 6,
      has_cover: false,
      cover_source: coverSource,
      cover_url: `/api/tracks/${id}/cover`,
      stream_url: `/api/tracks/${id}/stream`,
      custom_lyrics: null,
    };
  });
  await page.route("**/api/tracks", (route) =>
    route.fulfill({ json: { tracks } }),
  );
  await page.route("**/api/tracks/*/stream", (route) =>
    route.fulfill({ contentType: "audio/wav", body: makeWav() }),
  );
  await page.reload();
  const cards = titles.map((title) =>
    page.locator(".card").filter({ hasText: title }),
  );
  for (const card of cards) await expect(card).toBeVisible();
  return cards;
}

test("playlist add-songs dialog searches and filters the library", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic playlist test uses the local mock backend.",
  );
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await loadMockPlaybackTrack(page, "Miles & Miles", 57, "AJ Vitanza");

  await page.getByRole("button", { name: "Playlists" }).click();
  await page.getByRole("button", { name: "New playlist" }).first().click();
  await page.getByLabel("Playlist name").fill("Searchable playlist");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page.getByRole("button", { name: "Add songs" }).click();

  const dialog = page.getByRole("dialog", { name: "Add tracks to playlist" });
  const search = dialog.getByRole("searchbox", { name: "Search songs, artists, or albums" });
  await expect(search).toBeVisible();
  await search.fill("AJ Vitanza");
  const trackRow = dialog.locator(".qp-row");
  await expect(trackRow).toHaveCount(1);
  await expect(trackRow).toContainText("Miles & Miles");
  await search.fill("nothing matches this");
  await expect(dialog.getByText("No tracks match your search.")).toBeVisible();
  await search.fill("Playwright Test Album");
  await expect(trackRow).toHaveCount(1);
  await trackRow.click();
  await expect(trackRow).toHaveCount(0);
  await expect(page.locator(".toasts .toast").last()).toContainText(
    "Added “Miles & Miles” to the playlist.",
  );
});

test("track three-dots menu stays within the viewport", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic menu test uses the local mock backend.",
  );
  await page.setViewportSize({ width: 390, height: 640 });
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  const trackCard = await loadMockPlaybackTrack(page, "menu-position", 58);
  await trackCard.getByRole("button", { name: "More options for menu-position" }).click();

  const menu = page.getByRole("menu", { name: "Options for menu-position" });
  await expect(menu).toBeVisible();
  const bounds = await menu.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      width: window.innerWidth,
      height: window.innerHeight,
    };
  });
  expect(bounds.left).toBeGreaterThanOrEqual(0);
  expect(bounds.top).toBeGreaterThanOrEqual(0);
  expect(bounds.right).toBeLessThanOrEqual(bounds.width);
  expect(bounds.bottom).toBeLessThanOrEqual(bounds.height);
  await expect(menu.getByRole("menuitem", { name: "Remove from library" })).toBeVisible();
});

test("sleep timer can be scheduled and cancelled from the player", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic timer test uses the local mock backend.",
  );
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  const trackCard = await loadMockPlaybackTrack(page, "sleep-timer", 59);
  await trackCard.click();

  const timerButton = page.getByRole("button", { name: "Sleep timer" });
  await expect(timerButton).toBeEnabled();
  await timerButton.click();
  const timerDialog = page.getByRole("dialog", { name: "Sleep timer" });
  await timerDialog.getByRole("button", { name: "10 minutes" }).click();
  await expect(timerButton).toHaveAttribute("aria-pressed", "true");

  await timerButton.click();
  await expect(timerDialog.getByText(/Time remaining:/)).toBeVisible();
  await timerDialog.getByRole("button", { name: "Turn off timer" }).click();
  await expect(timerButton).toHaveAttribute("aria-pressed", "false");

  await timerButton.click();
  await timerDialog.getByRole("button", { name: "At end of track" }).click();
  await expect(timerButton).toHaveAttribute("aria-pressed", "true");
  await page.locator("audio").evaluate((element) => {
    element.dispatchEvent(new Event("ended"));
  });
  await expect(timerButton).toHaveAttribute("aria-pressed", "false");
});

test("sleep timer is available from the mobile and tablet player menu", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic timer test uses the local mock backend.",
  );
  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  const trackCard = await loadMockPlaybackTrack(page, "mobile-sleep-timer", 60);
  await trackCard.click();

  for (const width of [768, 360]) {
    await page.setViewportSize({ width, height: width === 768 ? 1024 : 812 });
    await expect(page.locator("#nowbar .player-control-sleep-timer")).toBeHidden();
    await page.locator(".now-track-open").click();
    const player = page.getByRole("dialog", { name: "Now playing" });
    await player.getByRole("button", { name: "More options for mobile-sleep-timer" }).click();
    const menu = page.getByRole("menu", { name: "Options for mobile-sleep-timer" });
    await menu.getByRole("menuitem", { name: "Sleep timer" }).click();

    const timer = page.getByRole("dialog", { name: "Sleep timer" });
    await expect(timer).toBeVisible();
    await expect(timer).toHaveAttribute("aria-modal", "true");
    await timer.getByRole("button", { name: "10 minutes" }).click();
    await expect(timer).toHaveCount(0);

    await player.getByRole("button", { name: "More options for mobile-sleep-timer" }).click();
    await page.getByRole("menuitem", { name: "Sleep timer" }).click();
    await expect(timer.getByText(/Time remaining:/)).toBeVisible();
    await timer.getByRole("button", { name: "Turn off timer" }).click();
    await expect(timer).toHaveCount(0);
    await player.getByRole…19279 tokens truncated…t-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await loadMockPlaybackTrack(page, "artist-bio-unavailable", 55);
  await page.route("**/api/artists/profile?*", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
  );

  await page.getByRole("button", { name: "Artists" }).click();
  await page.locator(".artist-card-open").filter({ hasText: "Vervfy Test Artist" }).click();

  const about = page.locator(".artist-info");
  await expect(about).toHaveAttribute("aria-busy", "false", { timeout: 15_000 });
  await expect(about.locator(".artist-bio")).toHaveText(
    "No artist information is available yet.",
  );
  await expect(about.locator(".artist-bio")).not.toContainText("Looking up");
});

test("cancelled seeks preserve the playhead and the lyrics editor is labeled", async ({
  page,
}) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic playback test uses the local mock backend.",
  );
  await logInToMockLibrary(page);
  const trackCard = await loadMockPlaybackTrack(page, "cancelled-seek", 57);
  await trackCard.click();
  const audio = page.locator("audio");
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(0.5);

  const cancelSeek = async (seekBar: Locator) => {
    const bounds = await seekBar.boundingBox();
    expect(bounds).not.toBeNull();
    const seekY = (bounds?.y ?? 0) + (bounds?.height ?? 0) / 2;
    await page.mouse.move((bounds?.x ?? 0) + (bounds?.width ?? 0) * 0.1, seekY);
    await page.mouse.down();
    await expect
      .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused))
      .toBe(true);
    const pausedAt = await audio.evaluate((element) => (element as HTMLAudioElement).currentTime);
    const cancelX = (bounds?.x ?? 0) + (bounds?.width ?? 0) * 0.9;
    await page.mouse.move(cancelX, seekY);
    const timeAtCancellation = await seekBar.evaluate(
      (element, point) => {
        element.dispatchEvent(
          new PointerEvent("pointercancel", {
            bubbles: true,
            pointerId: 1,
            isPrimary: true,
            clientX: point.x,
            clientY: point.y,
          }),
        );
        const audio = document.querySelector("audio");
        return {
          currentTime: audio?.currentTime ?? 0,
          timestamp: performance.now(),
        };
      },
      { x: cancelX, y: seekY },
    );
    expect(timeAtCancellation.currentTime).toBeCloseTo(pausedAt, 1);
    await expect
      .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused))
      .toBe(false);
    await page.mouse.up();
    await audio.evaluate((element) => (element as HTMLAudioElement).pause());
    const afterCancel = await audio.evaluate((element, cancelledAt) => {
      const player = element as HTMLAudioElement;
      return {
        currentTime: player.currentTime,
        playbackRate: player.playbackRate,
        elapsed: (performance.now() - cancelledAt) / 1000,
      };
    }, timeAtCancellation.timestamp);
    expect(afterCancel.currentTime).toBeLessThanOrEqual(
      pausedAt + afterCancel.elapsed * afterCancel.playbackRate + 0.25,
    );
  };
  await cancelSeek(page.locator('.nowbar [aria-label="Track progress"]'));

  await page.locator('.nowbar button[aria-label="Lyrics"]').click();
  const lyricsDialog = page.getByRole("dialog", { name: "Lyrics" });
  await expect(lyricsDialog).toBeVisible();
  await lyricsDialog.getByRole("button", { name: "Play", exact: true }).click();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(
    false,
  );
  await cancelSeek(lyricsDialog.locator('[aria-label="Track progress"]'));
  await lyricsDialog.getByRole("button", { name: /Paste lyrics|Edit lyrics/ }).click();
  await expect(lyricsDialog.getByRole("textbox", { name: "Lyrics" })).toBeVisible();
});

test("mock-backend login, upload, playback, seeking, playlist, and Range flow", async ({
  page,
}) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic full-flow test uses the local mock backend.",
  );
  test.setTimeout(420_000);
  const wav = makeWav(1);
  const hydrationErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && /hydrated|hydration mismatch/i.test(message.text())) {
      hydrationErrors.push(message.text());
    }
  });

  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password", { exact: true }).fill("playwright-test-password");
  const accountLoaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/me" &&
      response.ok(),
  );
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await accountLoaded;
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect.poll(() => hydrationErrors).toEqual([]);
  await expect
    .poll(() => page.locator(".side-panel").evaluate((element) => getComputedStyle(element).position))
    .toBe("fixed");
  await expect
    .poll(() => page.locator(".shell").evaluate((element) => Math.round(element.getBoundingClientRect().height)))
    .toBeGreaterThanOrEqual(await page.evaluate(() => window.innerHeight - 2));
  await expect(page.locator(".home-profile-avatar img")).toBeVisible();
  await expect
    .poll(() => page.locator(".side-panel").evaluate((element) => element.hasAttribute("inert") && element.getAttribute("aria-hidden") === "true"))
    .toBe(true);

  await page.getByRole("button", { name: "Playlists" }).click();
  await expect(page.locator(".view-title")).toHaveText("Playlists");
  await page.getByRole("button", { name: "New playlist" }).first().click();
  await page.getByLabel("Playlist name").fill(`Playwright ${Date.now()}`);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.locator(".view-title")).toContainText("Playwright");

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const audioInputs = page.locator(".hidden-input[type='file']");
  await expect(audioInputs).toHaveCount(2);
  await expect(audioInputs.nth(0)).toHaveAttribute(
    "accept",
    "audio/*,.mp3,.m4a,.wav,.flac,.ogg,.oga,.aac,.opus,.weba",
  );
  await expect(audioInputs.nth(1)).toHaveAttribute(
    "accept",
    "audio/*,.mp3,.m4a,.wav,.flac,.ogg,.oga,.aac,.opus,.weba",
  );
  await page.locator(".hidden-input").first().setInputFiles(
    [
      ...Array.from({ length: 60 }, (_, index) => ({
        name: `pw-batch-${String(index + 1).padStart(2, "0")}.wav`,
        mimeType: "audio/wav",
        buffer: wav,
      })),
      { name: "not-a-song.mp4", mimeType: "video/mp4", buffer: Buffer.from("video") },
      { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("notes") },
    ],
  );

  await expect(page.locator(".toasts .toast").last()).toContainText("Saved 60 tracks", {
    timeout: 10_000,
  });
  await expect(page.locator(".card")).toHaveCount(60, { timeout: 150_000 });
  const trackCard = page.locator(".card").filter({ hasText: "pw-batch-01" });
  await expect(trackCard).toBeVisible();
  await trackCard.getByRole("button", { name: "More options for pw-batch-01" }).click();
  const trackMenu = page.getByRole("menu", { name: "Options for pw-batch-01" });
  await expect(trackMenu.getByRole("menuitem", { name: "Play next" })).toBeVisible();
  await expect(trackMenu.getByRole("menuitem", { name: "Add to playlist" })).toBeVisible();
  await expect(trackMenu.getByRole("menuitem", { name: "Download for offline" })).toBeVisible();
  await expect(trackMenu.getByRole("menuitem", { name: "View artist: Vervfy Test Artist" })).toBeVisible();
  await trackMenu.getByRole("menuitem", { name: "Download for offline" }).click();
  await expect(page.locator(".toasts .toast").last()).toContainText(
    "Downloaded “pw-batch-01” for offline listening.",
  );
  await page.reload();
  await expect(trackCard).toBeVisible();
  await trackCard.getByRole("button", { name: "More options for pw-batch-01" }).click();
  const savedTrackMenu = page.getByRole("menu", { name: "Options for pw-batch-01" });
  await savedTrackMenu.getByRole("menuitem", { name: "Remove offline download" }).click();
  await expect(page.locator(".toasts .toast").last()).toContainText(
    "Removed “pw-batch-01” from offline storage.",
  );
  await trackCard.getByRole("button", { name: "More options for pw-batch-01" }).click();
  await expect(page.getByRole("menuitem", { name: "Download for offline" })).toBeVisible();
  const savedArtistMenuItem = page
    .getByRole("menu", { name: "Options for pw-batch-01" })
    .getByRole("menuitem", { name: "View artist: Vervfy Test Artist" });
  await expect(savedArtistMenuItem).toBeVisible();
  await savedArtistMenuItem.click();
  await expect(page.getByRole("heading", { name: "Vervfy Test Artist" })).toBeVisible();
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await expect(trackCard).toBeVisible();
  const playbackRange = page.waitForRequest((request) =>
    /\/api\/tracks\/playwright-track-\d+\/stream$/.test(request.url()) &&
    request.headers().range === "bytes=0-"
  );
  await page.locator(".card").filter({ hasText: "pw-batch-60" }).click();
  await playbackRange;
  const audio = page.locator("audio");
  await expect(page.locator(".now-title")).toHaveText("pw-batch-60");
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(0);
  await page.locator("audio").evaluate((element) => {
    element.dispatchEvent(new Event("ended"));
  });
  await expect(page.locator(".now-title")).toHaveText("pw-batch-01");
  await audio.evaluate((element) => {
    (element as HTMLAudioElement).playbackRate = 0.1;
  });
  await page.locator('.nowbar button[title="Queue"]').click();
  await expect(page.getByRole("complementary", { name: "Up next" })).toHaveClass(/open/);
  await expect
    .poll(() => page.locator(".side-panel").evaluate((element) => !element.hasAttribute("inert") && !element.hasAttribute("aria-hidden")))
    .toBe(true);
  await expect
    .poll(() => page.locator(".side-panel").evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return Math.round(window.innerWidth - rect.right);
    }))
    .toBe(0);
  await page.getByRole("button", { name: "Close queue" }).click();

  await page.getByRole("button", { name: "Repeat: off" }).click();
  await expect(page.getByRole("button", { name: "Repeat: all" })).toBeVisible();
  await page.getByRole("button", { name: "Repeat: all" }).click();
  await expect(page.getByRole("button", { name: "Repeat: one" })).toBeVisible();
  await page.getByRole("button", { name: "Repeat: one" }).click();
  await expect(page.getByRole("button", { name: "Repeat: off" })).toBeVisible();

  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).duration))
    .toBeGreaterThan(5);
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(0);
  const content = page.locator(".content");
  await content.evaluate((element) => element.scrollTo(0, 500));
  await expect
    .poll(() => content.evaluate((element) => element.scrollTop))
    .toBe(500);
  await page.waitForTimeout(750);
  const expectedScrollPosition = await content.evaluate(
    (element) => Math.min(500, element.scrollHeight - element.clientHeight),
  );
  await expect
    .poll(() => content.evaluate((element) => element.scrollTop))
    .toBe(expectedScrollPosition);
  await page.locator("#nowbar").getByRole("button", { name: "Pause", exact: true }).click();
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused))
    .toBe(true);
  await page.setViewportSize({ width: 360, height: 812 });
  await page.locator('.nowbar button[aria-label="Lyrics"]').click();
  await expect(page.getByRole("dialog", { name: "Lyrics" })).toBeVisible();
  const lyricsControls = page.locator(".lyrics-player");
  for (const label of ["Previous track", "Play", "Next track", "Shuffle", "Repeat: off"]) {
    await expect(lyricsControls.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
  await audio.evaluate((element) => {
    const player = element as HTMLAudioElement;
    player.currentTime = 1;
    player.playbackRate = 0.25;
  });
  await lyricsControls.getByRole("button", { name: "Play", exact: true }).click();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(false);
  const lyricsSeek = page.locator('.lyrics-overlay [aria-label="Track progress"]');
  await expect(lyricsSeek).toBeVisible();
  const lyricsSeekBounds = await lyricsSeek.boundingBox();
  expect(lyricsSeekBounds).not.toBeNull();
  const lyricsSeekY = (lyricsSeekBounds?.y ?? 0) + (lyricsSeekBounds?.height ?? 0) / 2;
  await page.mouse.move((lyricsSeekBounds?.x ?? 0) + (lyricsSeekBounds?.width ?? 0) * 0.2, lyricsSeekY);
  await page.mouse.down();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(true);
  const lyricsPausedAt = await audio.evaluate((element) => (element as HTMLAudioElement).currentTime);
  await page.mouse.move((lyricsSeekBounds?.x ?? 0) + (lyricsSeekBounds?.width ?? 0) * 0.75, lyricsSeekY, { steps: 4 });
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeCloseTo(lyricsPausedAt, 1);
  await page.mouse.up();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(false);
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(3.5);
  await lyricsControls.getByRole("button", { name: "Pause", exact: true }).click();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(true);
  await audio.evaluate((element) => { (element as HTMLAudioElement).playbackRate = 1; });
  await lyricsSeek.focus();
  await page.keyboard.press("End");
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(5.5);
  await audio.evaluate((element) => { (element as HTMLAudioElement).currentTime = 1; });
  await page.getByRole("button", { name: "Close lyrics" }).click();
  await page.setViewportSize({ width: 1280, height: 900 });

  await page.locator('.nowbar button[aria-label="Play"]').click();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(
    false,
  );

  const seekBar = page.locator('.nowbar [aria-label="Track progress"]');
  const progressMotion = await page.locator(".nowbar .seek-fill, .nowbar .seek-thumb").evaluateAll(
    (elements) => elements.map((element) => {
      const style = getComputedStyle(element);
      return {
        property: style.transitionProperty.split(",")[0].trim(),
        duration: style.transitionDuration.split(",")[0].trim(),
      };
    }),
  );
  expect(progressMotion).toEqual([
    { property: "width", duration: "0.25s" },
    { property: "opacity", duration: "0.12s" },
  ]);
  const bounds = await seekBar.boundingBox();
  expect(bounds).not.toBeNull();
  const seekY = (bounds?.y ?? 0) + (bounds?.height ?? 0) / 2;
  await page.mouse.move((bounds?.x ?? 0) + (bounds?.width ?? 0) * 0.2, seekY);
  await page.mouse.down();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(true);
  const pausedAt = await audio.evaluate((element) => (element as HTMLAudioElement).currentTime);
  await page.mouse.move((bounds?.x ?? 0) + (bounds?.width ?? 0) * 0.75, seekY, { steps: 4 });
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeCloseTo(pausedAt, 1);
  await page.mouse.up();
  await expect.poll(() => audio.evaluate((element) => (element as HTMLAudioElement).paused)).toBe(false);
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(3.5);
  await audio.evaluate((element) => (element as HTMLAudioElement).pause());

  const streamUrl = await audio.evaluate((element) => (element as HTMLAudioElement).currentSrc);
  const rangeStatus = await page.evaluate(async (url) => {
    const response = await fetch(url, {
      headers: { Range: "bytes=0-1" },
      cache: "no-store",
    });
    return {
      status: response.status,
      contentRange: response.headers.get("Content-Range"),
    };
  }, streamUrl);
  expect(rangeStatus.status).toBe(206);
  expect(rangeStatus.contentRange).toMatch(/^bytes 0-1\//);
});

test("real-backend login, upload, playback, seek, playlist, and Range flow", async ({ page }) => {
  test.skip(
    !username || !password || !externalBackend,
    "Set PLAYWRIGHT_BACKEND_URL, PLAYWRIGHT_USERNAME, and PLAYWRIGHT_PASSWORD for a real backend.",
  );

  await page.goto("/login");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page)
    .toHaveURL(/\/$/, { timeout: 15_000 })
    .catch(async () => {
      const message = await page.getByRole("alert").textContent().catch(() => null);
      throw new Error(
        message
          ? `FastAPI rejected the test login: ${message.trim()}`
          : `Login did not redirect to the app (current URL: ${page.url()}).`,
      );
    });
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();

  await page.getByRole("button", { name: "Playlists", exact: true }).click();
  await page.getByRole("button", { name: "New playlist" }).first().click();
  await page.getByLabel("Playlist name").fill(`Playwright ${Date.now()}`);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.locator(".view-title")).toContainText("Playwright");

  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.locator(".hidden-input").first().setInputFiles({
    name: "playwright-smoke.wav",
    mimeType: "audio/wav",
    buffer: makeWav(),
  });

  const trackCard = page.locator(".card").filter({ hasText: "playwright-smoke" });
  await expect(trackCard).toBeVisible({ timeout: 75_000 });
  await trackCard.click();

  const audio = page.locator("audio");
  await expect
    .poll(
      () =>
        audio.evaluate((element) => (element as HTMLAudioElement).duration),
      { timeout: 30_000 },
    )
    .toBeGreaterThan(5);
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(0);
  await page.locator('.nowbar button[title="Play/Pause"]').click();

  const seekBar = page.locator('.nowbar [aria-label="Track progress"]');
  const bounds = await seekBar.boundingBox();
  expect(bounds).not.toBeNull();
  await seekBar.click({
    position: { x: (bounds?.width ?? 0) * 0.75, y: (bounds?.height ?? 0) / 2 },
  });
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(3.5);

  const streamUrl = await audio.evaluate((element) => (element as HTMLAudioElement).currentSrc);
  const rangeStatus = await page.evaluate(async (url) => {
    const response = await fetch(url, {
      headers: { Range: "bytes=0-1" },
      cache: "no-store",
    });
    return {
      status: response.status,
      contentRange: response.headers.get("Content-Range"),
    };
  }, streamUrl);
  expect(rangeStatus.status).toBe(206);
});
