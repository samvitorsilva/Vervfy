import { expect, test } from "@playwright/test";

const username = process.env.PLAYWRIGHT_USERNAME;
const password = process.env.PLAYWRIGHT_PASSWORD;
const externalBackend = Boolean(process.env.PLAYWRIGHT_BACKEND_URL);
const externalApp = Boolean(process.env.PLAYWRIGHT_BASE_URL);

function makeWav(): Buffer {
  const sampleRate = 22_050;
  const seconds = 6;
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

test("login page loads its CSRF token from the JSON API", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Log in" })).toBeEnabled({
    timeout: 30_000,
  });
});

test("login displays JSON authentication errors", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("invalid-user");
  await page.getByLabel("Password").fill("invalid-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.locator(".auth-error[role='alert']")).toHaveText(
    "Incorrect username or password",
  );
});

test("tablet and mobile can open the full now-playing screen", async ({ page }) => {
  await page.route("https://cdn-images.dzcdn.net/**", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="32" fill="#8b7fff"/></svg>',
    }),
  );
  await page.goto("/login");
  await page.evaluate(() => localStorage.removeItem("vervfy:list-mode"));
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.locator(".hidden-input").first().setInputFiles({
    name: "responsive-player.wav",
    mimeType: "audio/wav",
    buffer: makeWav(),
  });

  const track = page.locator(".card").filter({ hasText: "responsive-player" });
  await expect(track).toBeVisible();
  await page.getByRole("button", { name: "List view" }).click();
  await expect(page.locator(".list .row")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".list .row")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Grid view" }).click();
  await expect(track).toBeVisible();
  await track.click();
  const nowPlayingButton = page.locator(".now-track-open");
  await expect(nowPlayingButton).toBeVisible();

  for (const viewport of [
    { width: 360, height: 812 },
    { width: 768, height: 1024 },
  ]) {
    await page.setViewportSize(viewport);
    await nowPlayingButton.click();
    const player = page.getByRole("dialog", { name: "Now playing" });
    await expect(player).toBeVisible();
    await expect(player.locator(".mobile-player-art img")).toBeVisible();
    await expect(player.locator(".mobile-player-context strong")).toHaveText("Library");
    for (const label of ["Previous track", "Play", "Next track", "Shuffle", "Repeat: off", "Lyrics", "Queue"]) {
      await expect(player.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
    await expect(player.getByRole("button", { name: "Close player" })).toBeFocused();
    await player.getByRole("button", { name: "Close player" }).click();
    await expect(player).toHaveCount(0);
    await expect(nowPlayingButton).toBeFocused();
  }

  await page.getByRole("button", { name: "Artists" }).click();
  await nowPlayingButton.click();
  await expect(page.locator(".mobile-player-context strong")).toHaveText("Library");
  await page.getByRole("button", { name: "Close player" }).click();
  await page.getByRole("button", { name: "Library" }).click();

  await nowPlayingButton.click();
  const playerArtist = page.locator(".mobile-player-title-row .artist-link").first();
  const artistName = (await playerArtist.textContent())?.trim();
  expect(artistName).toBeTruthy();
  await playerArtist.click();
  await expect(page.locator(".artist-name")).toHaveText(artistName!);
  await page.getByRole("button", { name: "List view" }).click();
  const artistTrackRow = page.locator(".artist-page .list .row");
  await expect(artistTrackRow).toHaveCount(1);
  await artistTrackRow.getByRole("button", { name: "Add to queue" }).click();
  await expect(page.locator(".toasts .toast").last()).toContainText("Added “responsive-player” to the queue.");
  await artistTrackRow.getByRole("button", { name: "Favorite" }).click();
  await expect(artistTrackRow.getByRole("button", { name: "Remove favorite" })).toBeVisible();
  await artistTrackRow.getByRole("button", { name: "More options for responsive-player" }).click();
  const artistTrackMenu = page.getByRole("menu", { name: "Options for responsive-player" });
  await expect(artistTrackMenu.getByRole("menuitem", { name: "Play next" })).toBeVisible();
  await expect(artistTrackMenu.getByRole("menuitemcheckbox", { name: "Remove from liked songs" })).toBeVisible();
  await artistTrackMenu.getByRole("menuitem", { name: "Add to queue" }).click();
  await page.getByRole("button", { name: "Grid view" }).click();
  const artistPhoto = page.locator(".artist-photo");
  await expect(page.locator(".artist-bio")).toHaveText(
    "Vervfy Test Artist is a verified test profile.",
  );
  await expect(page.locator(".artist-info")).toContainText("Deezer fans: 10");
  await expect(page.locator(".artist-info")).toContainText("Genre: Pop");
  await expect(page.getByRole("link", { name: "Source page ↗" })).toHaveAttribute(
    "href",
    "https://example.com/artist",
  );
  await expect(artistPhoto).toHaveAttribute(
    "src",
    "https://cdn-images.dzcdn.net/verified-test-photo.jpg",
  );
  await expect
    .poll(() => artistPhoto.evaluate((image) => (image as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);

  await page.getByRole("button", { name: "Artists" }).click();
  const artistCardPhoto = page.locator(".artist-card-photo").first();
  await expect(artistCardPhoto).toHaveAttribute(
    "src",
    "https://cdn-images.dzcdn.net/verified-test-photo.jpg",
  );
  await expect
    .poll(() => artistCardPhoto.evaluate((image) => (image as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);

  await nowPlayingButton.click();
  await page.locator(".mobile-secondary").filter({ hasText: "Lyrics" }).click();
  const lyricsArtist = page.locator(".lyrics-meta .artist-link").first();
  await expect(lyricsArtist).toBeVisible();
  await lyricsArtist.click();
  await expect(page.locator(".artist-name")).toHaveText(artistName!);
});

test("expanded mobile player shows playback-synced lyric lines", async ({ page }) => {
  const track = {
    id: "responsive-preview-track",
    title: "synced-preview",
    artist: "Vervfy Test Artist",
    album: "Playwright Test Album",
    duration: 6,
    has_cover: false,
    cover_url: "",
    stream_url: "/api/tracks/responsive-preview-track/stream",
    custom_lyrics: null,
  };
  await page.route("**/api/tracks", (route) =>
    route.fulfill({ json: { tracks: [track] } }),
  );
  await page.route("**/api/tracks/responsive-preview-track/stream", (route) =>
    route.fulfill({ contentType: "audio/wav", body: makeWav() }),
  );
  await page.route("https://lrclib.net/api/get**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        trackName: track.title,
        artistName: track.artist,
        duration: track.duration,
        syncedLyrics: "[00:00.00]First lyric line\n[00:02.00]Second lyric line",
        plainLyrics: "First lyric line\nSecond lyric line",
      }),
    }),
  );

  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  const trackCard = page.locator(".card").filter({ hasText: track.title });
  await expect(trackCard).toBeVisible();
  await trackCard.click();
  await page.setViewportSize({ width: 360, height: 812 });
  await page.locator(".now-track-open").click();

  const player = page.getByRole("dialog", { name: "Now playing" });
  await expect(player).toBeVisible();
  await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.readyState))
    .toBeGreaterThan(0);
  await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.duration))
    .toBeGreaterThan(0);
  await page.locator("audio").evaluate((audio: HTMLAudioElement) => {
    audio.currentTime = 0;
  });
  const lyricsPreview = player.locator(".mobile-lyrics-preview");
  await expect(lyricsPreview.locator(".lyric-active")).toHaveText("First lyric line");
  await page.locator("audio").evaluate(async (audio: HTMLAudioElement) => {
    if (audio.paused) await audio.play();
  });
  await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.currentTime))
    .toBeGreaterThan(2);
  await expect(lyricsPreview.locator(".lyric-active")).toHaveText("Second lyric line");
  await expect(lyricsPreview.getByText("Synced to playback")).toBeVisible();

  await lyricsPreview.click();
  const lyricsDialog = page.getByRole("dialog", { name: "Lyrics" });
  await expect(lyricsDialog).toBeVisible();
  await expect(lyricsDialog).toContainText("Second lyric line");
  await page.setViewportSize({ width: 768, height: 1024 });
  const trackCardBounds = await lyricsDialog.locator(".lyrics-side").boundingBox();
  const lyricsPlayerBounds = await lyricsDialog.locator(".lyrics-player").boundingBox();
  expect(trackCardBounds?.width).toBeLessThan(260);
  expect(lyricsPlayerBounds?.height).toBeLessThan(100);
  await page.keyboard.press("Escape");
  await expect(lyricsDialog).toHaveCount(0);
  const nowbar = page.locator("#nowbar");
  const nowbarBounds = await nowbar.boundingBox();
  const transportBounds = await nowbar.locator(".transport").boundingBox();
  expect(nowbarBounds).not.toBeNull();
  expect(transportBounds).not.toBeNull();
  expect(
    Math.abs(
      nowbarBounds!.x + nowbarBounds!.width / 2 -
        (transportBounds!.x + transportBounds!.width / 2),
    ),
  ).toBeLessThan(1);
});

test("opening the library with an expired session returns to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("service worker serves the offline fallback without caching backend APIs", async ({
  page,
  context,
}) => {
  await page.goto("/login");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await expect
    .poll(() =>
      page.evaluate(() => navigator.serviceWorker.controller !== null),
    )
    .toBe(true);
  await expect
    .poll(() =>
      page.evaluate(async () => (await fetch("/api/csrf")).status),
    { timeout: 10_000 },
    )
    .toBe(200);

  await context.setOffline(true);
  const offlineApiResult = await page.evaluate(async () => {
    try {
      return (await fetch("/api/csrf")).status;
    } catch {
      return null;
    }
  });
  expect(offlineApiResult).toBeNull();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "You’re offline" })).toBeVisible();
});

test("mobile navigation and keyboard shortcuts remain usable", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This interaction test uses the local mock backend.",
  );

  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.setViewportSize({ width: 360, height: 812 });

  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(navigation).toBeVisible();
  await expect(navigation.locator("[data-view]:visible")).toHaveCount(4);
  await expect(navigation.locator('[data-view="library"]')).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);

  await page.keyboard.press("?");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toHaveCount(0);

  await navigation.getByRole("button", { name: "Favorites" }).click();
  await expect(navigation.locator('[data-view="favorites"]')).toHaveAttribute(
    "aria-current",
    "page",
  );

  await navigation.getByRole("button", { name: "Playlists" }).click();
  await page.getByRole("button", { name: "New playlist" }).first().click();
  const playlistName = `Mobile playlist ${Date.now()}`;
  const playlistNameInput = page.getByLabel("Playlist name");
  await expect(playlistNameInput).toBeFocused();
  await playlistNameInput.fill(playlistName);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.locator(".view-title")).toContainText(playlistName);
  await expect(page.getByRole("heading", { name: "This playlist is empty" })).toBeVisible();
  await page.getByRole("button", { name: "All playlists" }).click();
  await expect(page.getByRole("button", { name: `Open playlist ${playlistName}` })).toBeVisible();
  await page.getByRole("textbox", { name: "Search playlists" }).fill("missing playlist");
  await expect(page.getByRole("heading", { name: "No playlists found" })).toBeVisible();
  await page.getByRole("button", { name: "Clear search" }).click();
  await page.getByRole("button", { name: `Open playlist ${playlistName}` }).click();
  const horizontalOverflow = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    elements: [...document.querySelectorAll<HTMLElement>("body *")]
      .map((element) => ({
        tag: element.tagName,
        className: element.className,
        left: Math.round(element.getBoundingClientRect().left),
        right: Math.round(element.getBoundingClientRect().right),
        width: Math.round(element.getBoundingClientRect().width),
      }))
      .filter((element) => element.right > window.innerWidth + 1 || element.left < -1)
      .slice(0, 10),
  }));
  expect(horizontalOverflow.documentWidth, JSON.stringify(horizontalOverflow)).toBeLessThanOrEqual(
    horizontalOverflow.viewportWidth,
  );
});

test("liquid glass stays translucent and limits active surfaces", async ({ page }) => {
  test.skip(
    externalApp || externalBackend,
    "This interaction test uses the local mock backend.",
  );

  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect(page.locator(".rail.glass")).toBeVisible();
  await expect
    .poll(() =>
      page.locator(".rail.glass").evaluate((element) => getComputedStyle(element).backgroundColor),
    )
    .toBe("rgba(15, 18, 28, 0.3)");

  const glassState = await page.evaluate(() => {
    const rail = document.querySelector<HTMLElement>(".rail.glass");
    if (!rail) return null;
    const computed = getComputedStyle(rail);
    const filterUrl = rail.style.getPropertyValue("--glass-filter-url");
    const filterId = filterUrl.match(/#([^)]+)/)?.[1];
    const mapSource = filterId
      ? document.querySelector<SVGImageElement>(`#${CSS.escape(filterId)} feImage`)?.getAttribute("href")
      : null;
    return {
      background: computed.backgroundColor,
      backdropFilter: computed.backdropFilter,
      boxShadow: computed.boxShadow,
      glassCount: document.querySelectorAll(".glass").length,
      refract: rail.classList.contains("refract"),
      chrome: "chrome" in window,
      supportsRefraction: CSS.supports(
        "backdrop-filter",
        "blur(3px) url(#lg) saturate(170%)",
      ),
      mapSource,
    };
  });

  expect(glassState).not.toBeNull();
  expect(glassState?.background).toBe("rgba(15, 18, 28, 0.3)");
  expect(glassState?.backdropFilter).toMatch(/blur\((18|3)px\)/);
  expect(glassState?.boxShadow).toContain("inset");
  expect(glassState?.glassCount).toBeLessThanOrEqual(4);
  if (glassState?.chrome && glassState.supportsRefraction) {
    expect(glassState.refract).toBe(true);
    expect(glassState.mapSource).toMatch(/^data:image\/svg\+xml/);
  } else {
    expect(glassState?.refract).toBe(false);
  }

  await page.getByRole("button", { name: "Playlists" }).click();
  await page.getByRole("button", { name: "New playlist" }).first().click();
  await expect(page.getByRole("dialog", { name: "New playlist" })).toBeVisible();
  await expect(page.locator(".queue-picker-card.glass")).toBeVisible();
  await expect
    .poll(() => page.locator(".glass").count())
    .toBeLessThanOrEqual(4);
});

test("mock-backend login, upload, playback, seeking, playlist, and Range flow", async ({
  page,
}) => {
  test.skip(
    externalApp || externalBackend,
    "This deterministic full-flow test uses the local mock backend.",
  );
  test.setTimeout(180_000);
  const hydrationErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && /hydrated|hydration mismatch/i.test(message.text())) {
      hydrationErrors.push(message.text());
    }
  });

  await page.goto("/login");
  await page.getByLabel("Username").fill("playwright");
  await page.getByLabel("Password").fill("playwright-test-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect.poll(() => hydrationErrors).toEqual([]);
  await expect
    .poll(() => page.locator(".side-panel").evaluate((element) => getComputedStyle(element).position))
    .toBe("fixed");
  await expect
    .poll(() => page.locator(".rail").evaluate((element) => Math.round(element.getBoundingClientRect().height)))
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
  const wav = makeWav();
  await page.locator(".hidden-input").first().setInputFiles(
    Array.from({ length: 60 }, (_, index) => ({
      name: `pw-batch-${String(index + 1).padStart(2, "0")}.wav`,
      mimeType: "audio/wav",
      buffer: wav,
    })),
  );

  await expect(page.locator(".card")).toHaveCount(60, { timeout: 150_000 });
  await expect(page.locator(".toasts .toast").last()).toContainText("Saved 60 tracks", {
    timeout: 10_000,
  });
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
  await trackCard.click();
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

  const audio = page.locator("audio");
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).duration))
    .toBeGreaterThan(5);
  await expect
    .poll(() => audio.evaluate((element) => (element as HTMLAudioElement).currentTime))
    .toBeGreaterThan(0);
  const content = page.locator(".content");
  await content.evaluate((element) => element.scrollTo(0, 500));
  const scrollPosition = await content.evaluate((element) => element.scrollTop);
  expect(scrollPosition).toBeGreaterThan(0);
  await page.waitForTimeout(750);
  await expect.poll(() => content.evaluate((element) => element.scrollTop)).toBe(scrollPosition);
  await audio.evaluate((element) => (element as HTMLAudioElement).pause());
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

  await page.locator('.nowbar button[title="Play/Pause"]').click();

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
    { property: "left", duration: "0.25s" },
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
  await page.getByLabel("Password").fill(password!);
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
  expect(rangeStatus.contentRange).toMatch(/^bytes 0-1\//);
});
