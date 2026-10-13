# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> artist photo editor previews and saves an uploaded photo with Commons credit
- Location: tests/smoke.spec.ts:294:5

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: expect(locator).toBeVisible() failed

Locator:  getByRole('heading', { name: 'Vervfy Test Artist' })
Expected: visible
Received: undefined

```

# Page snapshot

```yaml
- generic [active] [ref=f1e1]:
  - generic [ref=f1e2]:
    - generic [ref=f1e3]:
      - navigation "Main navigation" [ref=f1e4]:
        - generic [ref=f1e5]: Vervfy
        - button "Library" [ref=f1e8] [cursor=pointer]
        - button "Offline" [ref=f1e14] [cursor=pointer]
        - button "Playlists" [ref=f1e17] [cursor=pointer]
        - button "Artists" [ref=f1e21] [cursor=pointer]
        - button "Favorites" [ref=f1e27] [cursor=pointer]
        - button "Account" [ref=f1e30] [cursor=pointer]
        - button "Log out" [ref=f1e35] [cursor=pointer]
        - button "Shortcuts" [ref=f1e39] [cursor=pointer]
        - button "Add music" [ref=f1e44] [cursor=pointer]
      - generic [ref=f1e47]:
        - generic [ref=f1e48]:
          - button "Open account" [ref=f1e49] [cursor=pointer]
          - generic [ref=f1e50]:
            - generic [ref=f1e51]: Vervfy Test Artist
            - generic [ref=f1e52]: · 1
          - group "View mode" [ref=f1e53]:
            - button "Grid view" [pressed] [ref=f1e54] [cursor=pointer]
            - button "List view" [ref=f1e60] [cursor=pointer]
          - generic [ref=f1e63]:
            - textbox "Search library" [ref=f1e67]:
              - /placeholder: Search
            - generic [ref=f1e68]: /
        - generic [ref=f1e71]:
          - banner [ref=f1e72]:
            - figure [ref=f1e73]:
              - img "Vervfy Test Artist" [ref=f1e74]
            - generic [ref=f1e75]:
              - generic [ref=f1e76]: Artist
              - heading "Vervfy Test Artist" [level=1] [ref=f1e77]
              - generic [ref=f1e78]: 1 song in your library · 1 album
              - button "▶ Play artist" [ref=f1e79] [cursor=pointer]
              - button "Change photo" [ref=f1e81] [cursor=pointer]
          - region "Library information" [ref=f1e82]:
            - generic [ref=f1e83]:
              - generic [ref=f1e84]: Songs
              - strong [ref=f1e85]: "1"
            - generic [ref=f1e86]:
              - generic [ref=f1e87]: Albums
              - strong [ref=f1e88]: "1"
            - generic [ref=f1e89]:
              - generic [ref=f1e90]: Play time
              - strong [ref=f1e91]: 0 min
          - generic [ref=f1e92]:
            - heading "About" [level=2] [ref=f1e93]
            - paragraph [ref=f1e94]: Looking up artist details…
          - article [ref=f1e96]:
            - button "Play photo-smoke" [ref=f1e97] [cursor=pointer]
            - button "Add to queue" [ref=f1e101] [cursor=pointer]
            - button "Favorite" [ref=f1e104] [cursor=pointer]
            - button "More options for photo-smoke" [ref=f1e107] [cursor=pointer]
            - generic [ref=f1e112]: photo-smoke
            - button "Vervfy Test Artist" [ref=f1e114] [cursor=pointer]
    - region [aria-hidden]:
      - generic:
        - generic:
          - button:
            - generic: —
          - generic: —
      - generic:
        - generic:
          - button
          - button
          - button
          - button
          - button
        - generic:
          - generic: 0:00
          - slider
          - generic: 0:00
      - generic:
        - button
        - button
        - button
        - button
        - generic:
          - slider
    - complementary [aria-hidden] [ref=f1e115]:
      - generic [ref=f1e116]:
        - heading [level=3] [ref=f1e117]: Up next
        - generic [ref=f1e118]:
          - button [ref=f1e119] [cursor=pointer]
          - button [ref=f1e122] [cursor=pointer]
      - generic [ref=f1e126]:
        - paragraph [ref=f1e127]: Your queue is empty.
        - button [ref=f1e128] [cursor=pointer]: Add from library
    - status [ref=f1e129]:
      - generic [ref=f1e130]: Saved 1 track to your library.
  - generic [ref=f1e135] [cursor=pointer]:
    - button "Open Next.js Dev Tools" [ref=f1e136]
    - generic [ref=f1e140]:
      - button "Open issues overlay" [ref=f1e141]:
        - generic [ref=f1e142]:
          - generic [aria-hidden] [ref=f1e143]: "0"
          - generic [ref=f1e144]: "1"
        - generic [ref=f1e145]: Issue
      - button "Collapse issues badge" [ref=f1e146]
  - alert [ref=f1e149]
```

# Test source

```ts
  215 |   await expect(page.getByRole("link", { name: "Wikipedia" })).toBeVisible();
  216 |   await expect(page.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute(
  217 |     "href",
  218 |     "https://creativecommons.org/licenses/by-sa/4.0/",
  219 |   );
  220 |   await expect(page.getByRole("link", { name: "LRCLIB" })).toHaveAttribute(
  221 |     "href",
  222 |     "https://lrclib.net/",
  223 |   );
  224 | });
  225 | 
  226 | test("disabled LRCLIB lookup makes no external lyrics request", async ({ page }) => {
  227 |   let lrclibRequests = 0;
  228 |   await page.route("**/api/config", (route) =>
  229 |     route.fulfill({ json: { lyrics_provider_lrclib: false } }),
  230 |   );
  231 |   await page.route("https://lrclib.net/**", (route) => {
  232 |     lrclibRequests += 1;
  233 |     return route.abort();
  234 |   });
  235 |   await page.goto("/login");
  236 |   await page.getByLabel("Username").fill("playwright");
  237 |   await page.getByLabel("Password").fill("playwright-test-password");
  238 |   await page.getByRole("button", { name: "Log in" }).click();
  239 |   await expect(page).toHaveURL(/\/$/);
  240 |   await expect(page.getByRole("heading", { name: "Your library is empty" })).toBeVisible();
  241 |   await page.locator('input[type="file"][accept^="audio/"]').first().setInputFiles({
  242 |     name: "lyrics-disabled.wav",
  243 |     mimeType: "audio/wav",
  244 |     buffer: makeWav(),
  245 |   });
  246 |   await expect(page.locator(".card").filter({ hasText: "lyrics-disabled" })).toBeVisible();
  247 |   await page.locator(".card").filter({ hasText: "lyrics-disabled" }).click();
  248 |   await page.setViewportSize({ width: 360, height: 812 });
  249 |   await page.locator(".now-track-open").click();
  250 |   const player = page.getByRole("dialog", { name: "Now playing" });
  251 |   const lyricsPreview = player.locator(".mobile-lyrics-preview");
  252 |   await expect(lyricsPreview).toContainText("Paste your own lyrics.");
  253 |   await lyricsPreview.click();
  254 |   const lyricsDialog = page.getByRole("dialog", { name: "Lyrics" });
  255 |   await expect(lyricsDialog.getByRole("heading", { name: "Lyrics lookup is disabled." })).toBeVisible();
  256 |   expect(lrclibRequests).toBe(0);
  257 | });
  258 | 
  259 | test("track cover can be changed and reverted in the library", async ({ page }) => {
  260 |   await page.goto("/login");
  261 |   await page.getByLabel("Username").fill("playwright");
  262 |   await page.getByLabel("Password").fill("playwright-test-password");
  263 |   await page.getByRole("button", { name: "Log in" }).click();
  264 |   await expect(page).toHaveURL(/\/$/);
  265 |   await expect(page.getByRole("heading", { name: "Your library is empty" })).toBeVisible();
  266 |   await page.locator('input[type="file"][accept^="audio/"]').first().setInputFiles({
  267 |     name: "cover-flow.wav",
  268 |     mimeType: "audio/wav",
  269 |     buffer: makeWav(),
  270 |   });
  271 |   const track = page.locator(".card").filter({ hasText: "cover-flow" });
  272 |   await expect(track).toBeVisible();
  273 |   await track.getByRole("button", { name: "More options for cover-flow" }).click();
  274 |   await page.getByRole("menuitem", { name: "Add cover" }).click();
  275 |   const coverInput = page.locator('input[type="file"][accept="image/jpeg,image/png,image/webp"]');
  276 |   await coverInput.setInputFiles({
  277 |     name: "cover.png",
  278 |     mimeType: "image/png",
  279 |     buffer: Buffer.from(
  280 |       "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGMUCahgwAaYsIoOWgkAsMwA7Nwb4ScAAAAASUVORK5CYII=",
  281 |       "base64",
  282 |     ),
  283 |   });
  284 |   await expect(page.locator(".track-cover-preview")).toHaveAttribute("src", /^blob:/);
  285 |   await page.getByRole("button", { name: "Save cover" }).click();
  286 |   await expect(page.getByRole("dialog", { name: /Cover for/ })).toHaveCount(0);
  287 | 
  288 |   await track.getByRole("button", { name: "More options for cover-flow" }).click();
  289 |   await page.getByRole("menuitem", { name: "Change cover" }).click();
  290 |   await page.getByRole("button", { name: "Remove cover" }).click();
  291 |   await expect(page.getByRole("dialog", { name: /Cover for/ })).toHaveCount(0);
  292 | });
  293 | 
  294 | test("artist photo editor previews and saves an uploaded photo with Commons credit", async ({
  295 |   page,
  296 | }) => {
  297 |   test.skip(
  298 |     externalApp || externalBackend,
  299 |     "This photo editor smoke test uses the local mock backend.",
  300 |   );
  301 |   await page.goto("/login");
  302 |   await page.getByLabel("Username").fill("playwright");
  303 |   await page.getByLabel("Password").fill("playwright-test-password");
  304 |   await page.getByRole("button", { name: "Log in" }).click();
  305 |   await expect(page).toHaveURL(/\/$/);
  306 |   await expect(page.getByRole("heading", { name: "Your library is empty" })).toBeVisible();
  307 |   await page.locator('input[type="file"][accept^="audio/"]').first().setInputFiles({
  308 |     name: "photo-smoke.wav",
  309 |     mimeType: "audio/wav",
  310 |     buffer: makeWav(),
  311 |   });
  312 |   await expect(page.locator(".card").filter({ hasText: "photo-smoke" })).toBeVisible();
  313 |   await page.locator('.rail-btn[data-view="artists"]').click();
  314 |   await page.getByRole("button", { name: "Open artist page: Vervfy Test Artist" }).click();
> 315 |   await expect(page.getByRole("heading", { name: "Vervfy Test Artist" })).toBeVisible();
      |                                                                           ^ Error: expect(locator).toBeVisible() failed
  316 |   const credit = page.locator(".artist-photo-credit");
  317 |   await expect(credit).toContainText("Test Photographer");
  318 |   await expect(credit).toContainText("CC BY-SA 4.0");
  319 |   await expect(credit.getByRole("link", { name: "via Wikimedia Commons" })).toHaveAttribute(
  320 |     "href",
  321 |     "https://commons.wikimedia.org/wiki/File:Vervfy_Test.jpg",
  322 |   );
  323 | 
  324 |   await page.getByRole("button", { name: "Change photo" }).click();
  325 |   const editor = page.getByRole("dialog", { name: /Photo for Vervfy Test Artist/ });
  326 |   await expect(editor).toBeVisible();
  327 |   await editor.locator('input[type="file"]').setInputFiles({
  328 |     name: "artist.png",
  329 |     mimeType: "image/png",
  330 |     buffer: Buffer.from(
  331 |       "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGMUCahgwAaYsIoOWgkAsMwA7Nwb4ScAAAAASUVORK5CYII=",
  332 |       "base64",
  333 |     ),
  334 |   });
  335 |   await expect(editor.locator(".artist-photo-preview")).toHaveAttribute("src", /^blob:/);
  336 |   await editor.getByRole("button", { name: "Save photo" }).click();
  337 |   await expect(editor).toHaveCount(0);
  338 |   await expect(page.getByRole("button", { name: "Remove photo" })).toBeVisible();
  339 | });
  340 | 
  341 | test("expanded mobile player shows playback-synced lyric lines", async ({ page }) => {
  342 |   const track = {
  343 |     id: "responsive-preview-track",
  344 |     title: "synced-preview",
  345 |     artist: "Vervfy Test Artist",
  346 |     album: "Playwright Test Album",
  347 |     duration: 6,
  348 |     has_cover: false,
  349 |     cover_url: "",
  350 |     stream_url: "/api/tracks/responsive-preview-track/stream",
  351 |     custom_lyrics: null,
  352 |   };
  353 |   await page.route("**/api/tracks", (route) =>
  354 |     route.fulfill({ json: { tracks: [track] } }),
  355 |   );
  356 |   await page.route("**/api/tracks/responsive-preview-track/stream", (route) =>
  357 |     route.fulfill({ contentType: "audio/wav", body: makeWav() }),
  358 |   );
  359 |   let lrclibClientHeader = "";
  360 |   await page.route("https://lrclib.net/api/get**", (route) => {
  361 |     lrclibClientHeader = route.request().headers()["lrclib-client"] ?? "";
  362 |     return route.fulfill({
  363 |       contentType: "application/json",
  364 |       body: JSON.stringify({
  365 |         trackName: track.title,
  366 |         artistName: track.artist,
  367 |         duration: track.duration,
  368 |         syncedLyrics: "[00:00.00]First lyric line\n[00:02.00]Second lyric line",
  369 |         plainLyrics: "First lyric line\nSecond lyric line",
  370 |       }),
  371 |     });
  372 |   });
  373 | 
  374 |   await page.goto("/login");
  375 |   await page.getByLabel("Username").fill("playwright");
  376 |   await page.getByLabel("Password").fill("playwright-test-password");
  377 |   await page.getByRole("button", { name: "Log in" }).click();
  378 |   await expect(page).toHaveURL(/\/$/);
  379 |   const trackCard = page.locator(".card").filter({ hasText: track.title });
  380 |   await expect(trackCard).toBeVisible();
  381 |   await trackCard.click();
  382 |   await page.setViewportSize({ width: 360, height: 812 });
  383 |   await page.locator(".now-track-open").click();
  384 | 
  385 |   const player = page.getByRole("dialog", { name: "Now playing" });
  386 |   await expect(player).toBeVisible();
  387 |   await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.readyState))
  388 |     .toBeGreaterThan(0);
  389 |   await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.duration))
  390 |     .toBeGreaterThan(0);
  391 |   await page.locator("audio").evaluate((audio: HTMLAudioElement) => {
  392 |     audio.currentTime = 0;
  393 |   });
  394 |   const lyricsPreview = player.locator(".mobile-lyrics-preview");
  395 |   await expect(lyricsPreview.locator(".lyric-active")).toHaveText("First lyric line");
  396 |   await expect.poll(() => lrclibClientHeader).toBe(
  397 |     "Vervfy/1.0 (https://github.com/samvitorsilva/Verfy)",
  398 |   );
  399 |   await page.locator("audio").evaluate(async (audio: HTMLAudioElement) => {
  400 |     if (audio.paused) await audio.play();
  401 |   });
  402 |   await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.currentTime))
  403 |     .toBeGreaterThan(2);
  404 |   await expect(lyricsPreview.locator(".lyric-active")).toHaveText("Second lyric line");
  405 |   await expect(lyricsPreview.getByText("Synced to playback")).toBeVisible();
  406 | 
  407 |   await lyricsPreview.click();
  408 |   const lyricsDialog = page.getByRole("dialog", { name: "Lyrics" });
  409 |   await expect(lyricsDialog).toBeVisible();
  410 |   await expect(lyricsDialog).toContainText("Second lyric line");
  411 |   const phoneTrackCard = lyricsDialog.locator(".lyrics-side");
  412 |   const phoneCoverArt = lyricsDialog.locator(".lyrics-art");
  413 |   await expect.poll(() => phoneTrackCard.evaluate((element) => getComputedStyle(element).padding)).toBe("12px");
  414 |   const phoneCoverBounds = await phoneCoverArt.boundingBox();
  415 |   expect(phoneCoverBounds?.width).toBeCloseTo(96, 0);
```