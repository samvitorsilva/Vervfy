# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> tablet and mobile can open the full now-playing screen
- Location: tests/smoke.spec.ts:78:5

# Error details

```
Error: expect(locator).toHaveAttribute(expected) failed

Locator: getByRole('link', { name: 'CC BY-SA 4.0' })
Expected: "https://creativecommons.org/licenses/by-sa/4.0/"
Error: strict mode violation: getByRole('link', { name: 'CC BY-SA 4.0' }) resolved to 2 elements:
    1) <a target="_blank" rel="noopener noreferrer" href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a> aka getByRole('figure').getByRole('link', { name: 'CC BY-SA' })
    2) <a target="_blank" rel="noopener noreferrer" href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a> aka getByRole('link', { name: 'CC BY-SA' }).nth(1)

Call log:
  - Expect "toHaveAttribute" getByRole('link', { name: 'CC BY-SA 4.0' }) with timeout 15000ms
  - waiting for getByRole('link', { name: 'CC BY-SA 4.0' })

```

# Page snapshot

```yaml
- generic [ref=f2e1]:
  - generic [ref=f2e2]:
    - generic [ref=f2e3]:
      - navigation "Main navigation" [ref=f2e4]:
        - button "Library" [ref=f2e7] [cursor=pointer]
        - button "Offline" [ref=f2e13] [cursor=pointer]
        - button "Playlists" [ref=f2e16] [cursor=pointer]
        - button "Artists" [ref=f2e20] [cursor=pointer]
        - button "Favorites" [ref=f2e26] [cursor=pointer]
        - button "Account" [ref=f2e29] [cursor=pointer]
        - button "Log out" [ref=f2e34] [cursor=pointer]
        - button "Add music" [ref=f2e38] [cursor=pointer]
      - generic [ref=f2e41]:
        - generic [ref=f2e42]:
          - button "Open account" [ref=f2e43] [cursor=pointer]
          - generic [ref=f2e44]:
            - generic [ref=f2e45]: Vervfy Test Artist
            - generic [ref=f2e46]: · 1
          - group "View mode" [ref=f2e47]:
            - button "Grid view" [active] [pressed] [ref=f2e48] [cursor=pointer]
            - button "List view" [ref=f2e54] [cursor=pointer]
          - generic [ref=f2e57]:
            - textbox "Search library" [ref=f2e61]:
              - /placeholder: Search
            - generic [ref=f2e62]: /
        - generic [ref=f2e65]:
          - banner [ref=f2e66]:
            - figure [ref=f2e67]:
              - img "Vervfy Test Artist" [ref=f2e68]
              - generic [ref=f2e70]:
                - text: Test Photographer ·
                - link "CC BY-SA 4.0" [ref=f2e71] [cursor=pointer]:
                  - /url: https://creativecommons.org/licenses/by-sa/4.0/
                - text: ·
                - link "via Wikimedia Commons" [ref=f2e72] [cursor=pointer]:
                  - /url: https://commons.wikimedia.org/wiki/File:Vervfy_Test.jpg
                - text: · Resized for display ·
                - link "Report this photo" [ref=f2e73] [cursor=pointer]:
                  - /url: https://github.com/samvitorsilva/Verfy/issues
            - generic [ref=f2e74]:
              - generic [ref=f2e75]: Artist
              - heading "Vervfy Test Artist" [level=1] [ref=f2e76]
              - generic [ref=f2e77]: 1 song in your library · 1 album
              - button "▶ Play artist" [ref=f2e78] [cursor=pointer]
              - button "Change photo" [ref=f2e80] [cursor=pointer]
          - region "Library information" [ref=f2e81]:
            - generic [ref=f2e82]:
              - generic [ref=f2e83]: Songs
              - strong [ref=f2e84]: "1"
            - generic [ref=f2e85]:
              - generic [ref=f2e86]: Albums
              - strong [ref=f2e87]: "1"
            - generic [ref=f2e88]:
              - generic [ref=f2e89]: Play time
              - strong [ref=f2e90]: 0 min
          - generic [ref=f2e91]:
            - heading "About" [level=2] [ref=f2e92]
            - paragraph [ref=f2e93]: Vervfy Test Artist is a verified test profile.
            - paragraph [ref=f2e94]:
              - 'link "Source: Wikipedia" [ref=f2e95] [cursor=pointer]':
                - /url: https://en.wikipedia.org/wiki/Vervfy_Test_Artist
              - text: ·
              - link "CC BY-SA 4.0" [ref=f2e96] [cursor=pointer]:
                - /url: https://creativecommons.org/licenses/by-sa/4.0/
              - text: · Shortened or adapted
            - generic [ref=f2e97]: "Genre: Pop"
          - article [ref=f2e100]:
            - button "Play responsive-player" [ref=f2e101] [cursor=pointer]
            - button "Add to queue" [ref=f2e105] [cursor=pointer]
            - button "Remove favorite" [ref=f2e108] [cursor=pointer]
            - button "More options for responsive-player" [ref=f2e111] [cursor=pointer]
            - generic [ref=f2e116]: responsive-player
            - button "Vervfy Test Artist" [ref=f2e118] [cursor=pointer]
    - region "Now playing" [ref=f2e119]:
      - generic [ref=f2e120]:
        - generic [ref=f2e123]:
          - button "Open player for responsive-player" [ref=f2e124] [cursor=pointer]:
            - generic [ref=f2e125]: responsive-player
          - button "Vervfy Test Artist" [ref=f2e127] [cursor=pointer]
        - button "Remove favorite" [pressed] [ref=f2e128] [cursor=pointer]
      - generic [ref=f2e131]:
        - generic [ref=f2e132]:
          - button "Shuffle" [ref=f2e133] [cursor=pointer]
          - button "Previous track" [ref=f2e136] [cursor=pointer]
          - button "Play" [ref=f2e139] [cursor=pointer]
          - button "Next track" [ref=f2e142] [cursor=pointer]
          - 'button "Repeat: off" [ref=f2e145] [cursor=pointer]'
        - generic [ref=f2e148]:
          - generic [ref=f2e149]: 0:06
          - slider "Track progress" [ref=f2e150] [cursor=pointer]
          - generic [ref=f2e154]: 0:06
      - generic [ref=f2e155]:
        - button "Lyrics" [ref=f2e156] [cursor=pointer]
        - button "Visualizer" [ref=f2e160] [cursor=pointer]
        - button "Queue" [ref=f2e164] [cursor=pointer]
        - button "Mute" [ref=f2e167] [cursor=pointer]
    - complementary [aria-hidden] [ref=f2e171]:
      - generic [ref=f2e172]:
        - heading [level=3] [ref=f2e173]: Up next
        - generic [ref=f2e174]:
          - button [ref=f2e175] [cursor=pointer]
          - button [ref=f2e178] [cursor=pointer]
      - generic [ref=f2e181]:
        - generic [ref=f2e182]:
          - button [ref=f2e183]
          - button [ref=f2e191] [cursor=pointer]:
            - generic [ref=f2e192]: responsive-player
            - generic [ref=f2e193]: Vervfy Test Artist
          - button [ref=f2e194] [cursor=pointer]
        - generic [ref=f2e197]:
          - button [ref=f2e198]
          - button [ref=f2e206] [cursor=pointer]:
            - generic [ref=f2e207]: responsive-player
            - generic [ref=f2e208]: Vervfy Test Artist
          - button [ref=f2e209] [cursor=pointer]
        - generic [ref=f2e212]:
          - button [ref=f2e213]
          - button [ref=f2e221] [cursor=pointer]:
            - generic [ref=f2e222]: responsive-player
            - generic [ref=f2e223]: Vervfy Test Artist
          - button [ref=f2e224] [cursor=pointer]
  - generic [ref=f2e231] [cursor=pointer]:
    - button "Open Next.js Dev Tools" [ref=f2e232]
    - generic [ref=f2e236]:
      - button "Open issues overlay" [ref=f2e237]:
        - generic [ref=f2e238]:
          - generic [aria-hidden] [ref=f2e239]: "0"
          - generic [ref=f2e240]: "1"
        - generic [ref=f2e241]: Issue
      - button "Collapse issues badge" [ref=f2e242]
  - alert [ref=f2e245]
```

# Test source

```ts
  83  |   await page.getByRole("button", { name: "Log in" }).click();
  84  |   await expect(page).toHaveURL(/\/$/);
  85  |   await expect(page.getByRole("heading", { name: "Your library is empty" })).toBeVisible();
  86  |   await page.locator('input[type="file"][accept^="audio/"]').first().setInputFiles({
  87  |     name: "responsive-player.wav",
  88  |     mimeType: "audio/wav",
  89  |     buffer: makeWav(),
  90  |   });
  91  | 
  92  |   const track = page.locator(".card").filter({ hasText: "responsive-player" });
  93  |   await expect(track).toBeVisible();
  94  |   await page.getByRole("button", { name: "List view" }).click();
  95  |   await expect(page.locator(".list .row")).toHaveCount(1);
  96  |   await page.reload();
  97  |   await expect(page.locator(".list .row")).toHaveCount(1);
  98  |   await expect(page.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");
  99  |   await page.getByRole("button", { name: "Grid view" }).click();
  100 |   await expect(track).toBeVisible();
  101 |   await track.click();
  102 |   const nowPlayingButton = page.locator(".now-track-open");
  103 |   await expect(nowPlayingButton).toBeVisible();
  104 |   const expectNowbarOnTop = async () => {
  105 |     const nowbar = page.locator("#nowbar");
  106 |     const isOnTop = await nowbar.evaluate((bar) => {
  107 |       const rect = bar.getBoundingClientRect();
  108 |       const topmostElement = document.elementFromPoint(
  109 |         rect.left + rect.width / 2,
  110 |         rect.top + rect.height / 2,
  111 |       );
  112 |       return topmostElement !== null && bar.contains(topmostElement);
  113 |     });
  114 |     expect(isOnTop).toBe(true);
  115 |   };
  116 | 
  117 |   for (const viewport of [
  118 |     { width: 360, height: 812 },
  119 |     { width: 768, height: 1024 },
  120 |   ]) {
  121 |     await page.setViewportSize(viewport);
  122 |     await nowPlayingButton.click();
  123 |     const player = page.getByRole("dialog", { name: "Now playing" });
  124 |     await expect(player).toBeVisible();
  125 |     await expect(player.locator(".mobile-player-art img")).toBeVisible();
  126 |     await expect(player.locator(".mobile-player-context strong")).toHaveText("Library");
  127 |     for (const label of ["Previous track", "Play", "Next track", "Shuffle", "Repeat: off", "Lyrics", "Queue"]) {
  128 |       await expect(player.getByRole("button", { name: label, exact: true })).toBeVisible();
  129 |     }
  130 |     await expect(player.getByRole("button", { name: "Close player" })).toBeFocused();
  131 |     await player.getByRole("button", { name: "Close player" }).click();
  132 |     await expect(player).toHaveCount(0);
  133 |     await expect(nowPlayingButton).toBeFocused();
  134 |     const playerRegions = await page.locator("#nowbar").evaluate((element) =>
  135 |       [".now-track", ".transport", ".now-extra"].map((selector) => {
  136 |         const rect = element.querySelector(selector)!.getBoundingClientRect();
  137 |         return { left: rect.left, right: rect.right };
  138 |       }),
  139 |     );
  140 |     expect(playerRegions[0].right).toBeLessThanOrEqual(playerRegions[1].left + 1);
  141 |     expect(playerRegions[1].right).toBeLessThanOrEqual(playerRegions[2].left + 1);
  142 |   }
  143 | 
  144 |   await page.getByRole("button", { name: "Artists" }).click();
  145 |   await expectNowbarOnTop();
  146 |   await nowPlayingButton.click();
  147 |   await expect(page.locator(".mobile-player-context strong")).toHaveText("Library");
  148 |   await page.getByRole("button", { name: "Close player" }).click();
  149 |   await page.getByRole("button", { name: "Library" }).click();
  150 | 
  151 |   await nowPlayingButton.click();
  152 |   const playerArtist = page.locator(".mobile-player-title-row .artist-link").first();
  153 |   const artistName = (await playerArtist.textContent())?.trim();
  154 |   expect(artistName).toBeTruthy();
  155 |   await playerArtist.click();
  156 |   await expect(page.locator(".artist-name")).toHaveText(artistName!);
  157 |   await expectNowbarOnTop();
  158 |   await page.getByRole("button", { name: "List view" }).click();
  159 |   const artistTrackRow = page.locator(".artist-page .list .row");
  160 |   await expect(artistTrackRow).toHaveCount(1);
  161 |   await artistTrackRow.getByRole("button", { name: "Add to queue" }).click();
  162 |   await expect(page.locator(".toasts .toast").last()).toContainText("Added “responsive-player” to the queue.");
  163 |   await artistTrackRow.getByRole("button", { name: "Favorite" }).click();
  164 |   await expect(artistTrackRow.getByRole("button", { name: "Remove favorite" })).toBeVisible();
  165 |   await artistTrackRow.getByRole("button", { name: "More options for responsive-player" }).click();
  166 |   const artistTrackMenu = page.getByRole("menu", { name: "Options for responsive-player" });
  167 |   await expect(artistTrackMenu.getByRole("menuitem", { name: "Play next" })).toBeVisible();
  168 |   await expect(artistTrackMenu.getByRole("menuitemcheckbox", { name: "Remove from liked songs" })).toBeVisible();
  169 |   await artistTrackMenu.getByRole("menuitem", { name: "Add to queue" }).click();
  170 |   await page.getByRole("button", { name: "Grid view" }).click();
  171 |   const artistAvatar = page.getByRole("img", { name: "Vervfy Test Artist" });
  172 |   await expect(page.locator(".artist-bio")).toHaveText(
  173 |     "Vervfy Test Artist is a verified test profile.",
  174 |   );
  175 |   await expect(page.locator(".artist-info")).toContainText("Genre: Pop");
  176 |   await expect(page.locator(".artist-info")).not.toContainText(/followers|fans/i);
  177 |   await expect(page.locator(".artist-info img")).toHaveCount(0);
  178 |   await expect(artistAvatar).toBeVisible();
  179 |   await expect(page.getByRole("link", { name: "Source: Wikipedia" })).toHaveAttribute(
  180 |     "href",
  181 |     "https://en.wikipedia.org/wiki/Vervfy_Test_Artist",
  182 |   );
> 183 |   await expect(page.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute(
      |                                                                  ^ Error: expect(locator).toHaveAttribute(expected) failed
  184 |     "href",
  185 |     "https://creativecommons.org/licenses/by-sa/4.0/",
  186 |   );
  187 |   await expect(page.getByText(/Artist photos may be uploaded by you/)).toBeVisible();
  188 |   await expect(page.getByRole("link", { name: "Wikimedia Commons" })).toHaveAttribute(
  189 |     "href",
  190 |     "https://commons.wikimedia.org/",
  191 |   );
  192 |   await expect(page.locator(".artist-source")).toContainText("Shortened or adapted");
  193 | 
  194 |   await page.getByRole("button", { name: "Artists" }).click();
  195 |   const artistCardAvatar = page.locator(".artist-card-photo").first();
  196 |   await expect(artistCardAvatar).toBeVisible();
  197 |   const artistCardCredit = page.locator(".artist-card-photo-credit");
  198 |   await expect(artistCardCredit).toHaveCount(0);
  199 | 
  200 |   await nowPlayingButton.click();
  201 |   await page.locator(".mobile-secondary").filter({ hasText: "Lyrics" }).click();
  202 |   const lyricsArtist = page.locator(".lyrics-meta .artist-link").first();
  203 |   await expect(lyricsArtist).toBeVisible();
  204 |   await lyricsArtist.click();
  205 |   await expect(page.locator(".artist-name")).toHaveText(artistName!);
  206 | });
  207 | 
  208 | test("public credits page keeps the nonce CSP and lists attribution", async ({ page }) => {
  209 |   const response = await page.goto("/credits");
  210 |   const csp = response?.headers()["content-security-policy"] ?? "";
  211 |   expect(csp).toContain("script-src 'self' 'nonce-");
  212 |   expect(csp).toContain("img-src 'self' data: blob:");
  213 |   expect(csp).not.toMatch(/img-src[^;]*https:/);
  214 |   await expect(page.getByRole("heading", { name: "Credits and data sources" })).toBeVisible();
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
```