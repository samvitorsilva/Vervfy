# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> tablet and mobile can open the full now-playing screen
- Location: tests/smoke.spec.ts:105:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('dialog', { name: 'Now playing' }).getByRole('button', { name: 'Play', exact: true })
Expected: visible
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('dialog', { name: 'Now playing' }).getByRole('button', { name: 'Play', exact: true }) with timeout 15000ms
  - waiting for getByRole('dialog', { name: 'Now playing' }).getByRole('button', { name: 'Play', exact: true })
  - Test ended.

```

```yaml
- navigation "Main navigation":
  - button "Library"
  - button "Offline"
  - button "Playlists": Lists
  - button "Artists"
  - button "Favorites": Liked
- button "Open account"
- text: Library
- group "View mode":
  - button "Grid view" [pressed]
  - button "List view"
- textbox "Search library":
  - /placeholder: Search
- text: /
- button "Add music"
- article:
  - button "Play responsive-player"
  - button "Add to queue"
  - button "Favorite"
  - button "More options for responsive-player"
  - text: responsive-player
  - button "Vervfy Test Artist"
- alert
- dialog "Now playing":
  - banner:
    - button "Close player"
    - text: PLAYING FROM
    - strong: Library
    - button "More options for responsive-player"
  - main:
    - heading "responsive-player" [level=2]
    - paragraph:
      - button "Vervfy Test Artist"
    - button "Favorite"
    - slider "Track progress"
    - text: 0:08 0:30
    - button "Shuffle"
    - button "Previous track"
    - button "Pause"
    - button "Next track"
    - 'button "Repeat: off"'
    - button "Open full lyrics":
      - text: Lyrics Open full lyrics
      - paragraph: No lyrics found for this track.
    - button "Lyrics"
    - button "Queue"
```

# Test source

```ts
  69  |   await page.goto("/login");
  70  |   await page.getByLabel("Username").fill("invalid-user");
  71  |   await page.getByLabel("Password").fill("invalid-password");
  72  |   await page.getByRole("button", { name: "Log in" }).click();
  73  |   await expect(page.locator(".auth-error[role='alert']")).toHaveText(
  74  |     "Incorrect username or password",
  75  |   );
  76  |   await expect(page.getByLabel("Password")).toHaveAttribute("aria-invalid", "true");
  77  |   await expect(page.getByLabel("Password")).toBeFocused();
  78  | });
  79  | 
  80  | test("registration gives live password length and byte-limit guidance", async ({ page }) => {
  81  |   await page.goto("/register");
  82  |   const password = page.getByLabel("Password");
  83  |   const hint = page.locator("#password-hint");
  84  | 
  85  |   await expect(hint).toHaveText("Use at least 8 characters.");
  86  |   await password.fill("short");
  87  |   await expect(hint).toHaveText("Add 3 more characters to meet the 8-character minimum.");
  88  |   await expect(password).toHaveAttribute("aria-invalid", "true");
  89  | 
  90  |   await password.fill("long-enough");
  91  |   await expect(hint).toHaveText("Password meets the 8-character minimum.");
  92  |   await expect(password).toHaveAttribute("aria-invalid", "false");
  93  | 
  94  |   await password.fill("é".repeat(36));
  95  |   await expect(hint).toHaveText("Password meets the 8-character minimum.");
  96  |   await expect(password).toHaveAttribute("aria-invalid", "false");
  97  | 
  98  |   await password.fill(`${"é".repeat(36)}a`);
  99  |   await expect(hint).toHaveText(
  100 |     "Password must be 72 UTF-8 bytes or fewer. Remove some characters.",
  101 |   );
  102 |   await expect(password).toHaveAttribute("aria-invalid", "true");
  103 | });
  104 | 
  105 | test("tablet and mobile can open the full now-playing screen", async ({ page }) => {
  106 |   await page.goto("/login");
  107 |   await page.evaluate(() => localStorage.removeItem("vervfy:list-mode"));
  108 |   await page.getByLabel("Username").fill("playwright");
  109 |   await page.getByLabel("Password").fill("playwright-test-password");
  110 |   await page.getByRole("button", { name: "Log in" }).click();
  111 |   await expect(page).toHaveURL(/\/$/);
  112 |   await expect(page.getByRole("heading", { name: "Your library is empty" })).toBeVisible();
  113 |   await page.locator('input[type="file"][accept^="audio/"]').first().setInputFiles({
  114 |     name: "responsive-player.wav",
  115 |     mimeType: "audio/wav",
  116 |     buffer: makeWav(),
  117 |   });
  118 | 
  119 |   const track = page.locator(".card").filter({ hasText: "responsive-player" });
  120 |   await expect(track).toBeVisible();
  121 |   const fallbackCover = track.locator(".card-art .generated-aura");
  122 |   await expect(fallbackCover).toBeVisible();
  123 |   await expect(fallbackCover.locator("text")).toHaveCount(0);
  124 |   await expect(fallbackCover.locator(".generated-aura-first")).toHaveCSS(
  125 |     "animation-name",
  126 |     "generatedAuraDrift",
  127 |   );
  128 |   await page.getByRole("button", { name: "List view" }).click();
  129 |   await expect(page.locator(".list .row")).toHaveCount(1);
  130 |   await page.reload();
  131 |   await expect(page.locator(".list .row")).toHaveCount(1);
  132 |   await expect(page.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");
  133 |   await page.getByRole("button", { name: "Grid view" }).click();
  134 |   await expect(track).toBeVisible();
  135 |   await track.click();
  136 |   const nowPlayingButton = page.locator(".now-track-open");
  137 |   await expect(nowPlayingButton).toBeVisible();
  138 |   const expectNowbarOnTop = async () => {
  139 |     const nowbar = page.locator("#nowbar");
  140 |     const isOnTop = await nowbar.evaluate((bar) => {
  141 |       const rect = bar.getBoundingClientRect();
  142 |       const topmostElement = document.elementFromPoint(
  143 |         rect.left + rect.width / 2,
  144 |         rect.top + rect.height / 2,
  145 |       );
  146 |       return topmostElement !== null && bar.contains(topmostElement);
  147 |     });
  148 |     expect(isOnTop).toBe(true);
  149 |   };
  150 | 
  151 |   for (const viewport of [
  152 |     { width: 360, height: 812 },
  153 |     { width: 768, height: 1024 },
  154 |   ]) {
  155 |     await page.setViewportSize(viewport);
  156 |     await nowPlayingButton.click();
  157 |     const player = page.getByRole("dialog", { name: "Now playing" });
  158 |     await expect(player).toBeVisible();
  159 |     await expect(player.locator(".mobile-player-art img, .mobile-player-art .generated-aura")).toBeVisible();
  160 |     await expect(player.locator(".mobile-player-context strong")).toHaveText("Library");
  161 |     const playerMenuButton = player.getByRole("button", { name: "More options for responsive-player" });
  162 |     await playerMenuButton.click();
  163 |     const playerMenu = page.getByRole("menu", { name: "Options for responsive-player" });
  164 |     await expect(playerMenu).toBeVisible();
  165 |     await expect(playerMenu.getByRole("menuitem", { name: "Edit track details" })).toBeVisible();
  166 |     await playerMenuButton.click();
  167 |     await expect(playerMenu).toHaveCount(0);
  168 |     for (const label of ["Previous track", "Play", "Next track", "Shuffle", "Repeat: off", "Lyrics", "Queue"]) {
> 169 |       await expect(player.getByRole("button", { name: label, exact: true })).toBeVisible();
      |                                                                              ^ Error: expect(locator).toBeVisible() failed
  170 |     }
  171 |     await expect(player.getByRole("button", { name: "Close player" })).toBeFocused();
  172 |     await player.getByRole("button", { name: "Close player" }).click();
  173 |     await expect(player).toHaveCount(0);
  174 |     await expect(nowPlayingButton).toBeFocused();
  175 |     const playerRegions = await page.locator("#nowbar").evaluate((element) =>
  176 |       [".now-track", ".transport", ".now-extra"].map((selector) => {
  177 |         const rect = element.querySelector(selector)!.getBoundingClientRect();
  178 |         return { left: rect.left, right: rect.right };
  179 |       }),
  180 |     );
  181 |     expect(playerRegions[0].right).toBeLessThanOrEqual(playerRegions[1].left + 1);
  182 |     expect(playerRegions[1].right).toBeLessThanOrEqual(playerRegions[2].left + 1);
  183 |     if (viewport.width === 360) {
  184 |       expect(
  185 |         await page.evaluate(
  186 |           () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  187 |         ),
  188 |       ).toBe(false);
  189 |     }
  190 |   }
  191 | 
  192 |   await nowPlayingButton.click();
  193 |   await page.getByRole("button", { name: "More options for responsive-player" }).click();
  194 |   await page.getByRole("menuitem", { name: "Edit track details" }).click();
  195 |   const trackDetails = page.getByRole("dialog", { name: "Track details" });
  196 |   await expect(trackDetails).toBeVisible();
  197 |   await expect(page.getByRole("dialog", { name: "Now playing" })).toHaveCount(0);
  198 |   await trackDetails.getByRole("button", { name: "Close" }).click();
  199 | 
  200 |   await page.getByRole("button", { name: "Artists" }).click();
  201 |   await expectNowbarOnTop();
  202 |   await nowPlayingButton.click();
  203 |   await expect(page.locator(".mobile-player-context strong")).toHaveText("Library");
  204 |   await page.getByRole("button", { name: "Close player" }).click();
  205 |   await page.getByRole("button", { name: "Library" }).click();
  206 | 
  207 |   await nowPlayingButton.click();
  208 |   const playerArtist = page.locator(".mobile-player-title-row .artist-link").first();
  209 |   const artistName = (await playerArtist.textContent())?.trim();
  210 |   expect(artistName).toBeTruthy();
  211 |   await playerArtist.click();
  212 |   await expect(page.locator(".artist-name")).toHaveText(artistName!);
  213 |   await expectNowbarOnTop();
  214 |   await page.getByRole("button", { name: "List view" }).click();
  215 |   const artistTrackRow = page.locator(".artist-page .list .row");
  216 |   await expect(artistTrackRow).toHaveCount(1);
  217 |   await artistTrackRow.getByRole("button", { name: "Add to queue" }).click();
  218 |   await expect(page.locator(".toasts .toast").last()).toContainText("Added “responsive-player” to the queue.");
  219 |   await artistTrackRow.getByRole("button", { name: "Favorite" }).click();
  220 |   await expect(artistTrackRow.getByRole("button", { name: "Remove favorite" })).toBeVisible();
  221 |   await artistTrackRow.getByRole("button", { name: "More options for responsive-player" }).click();
  222 |   const artistTrackMenu = page.getByRole("menu", { name: "Options for responsive-player" });
  223 |   await expect(artistTrackMenu.getByRole("menuitem", { name: "Play next" })).toBeVisible();
  224 |   await expect(artistTrackMenu.getByRole("menuitemcheckbox", { name: "Remove from liked songs" })).toBeVisible();
  225 |   await artistTrackMenu.getByRole("menuitem", { name: "Add to queue" }).click();
  226 |   await page.getByRole("button", { name: "Grid view" }).click();
  227 |   const artistAvatar = page.getByRole("img", { name: "Vervfy Test Artist" });
  228 |   await expect(page.locator(".artist-bio")).toHaveText(
  229 |     "Vervfy Test Artist is a verified test profile.",
  230 |   );
  231 |   await expect(page.locator(".artist-info")).toContainText("Genre: Pop");
  232 |   await expect(page.locator(".artist-info")).not.toContainText(/followers|fans/i);
  233 |   await expect(page.locator(".artist-info img")).toHaveCount(0);
  234 |   await expect(artistAvatar).toBeVisible();
  235 |   await expect(page.getByRole("link", { name: "Source: Wikipedia" })).toHaveAttribute(
  236 |     "href",
  237 |     "https://en.wikipedia.org/wiki/Vervfy_Test_Artist",
  238 |   );
  239 |   await expect(page.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute(
  240 |     "href",
  241 |     "https://creativecommons.org/licenses/by-sa/4.0/",
  242 |   );
  243 |   await expect(page.getByText(/Artist image URLs and IDs are supplied by TheAudioDB/)).toBeVisible();
  244 |   await expect(page.getByRole("link", { name: "TheAudioDB" })).toHaveAttribute(
  245 |     "href",
  246 |     "https://www.theaudiodb.com/",
  247 |   );
  248 |   await expect(page.locator(".artist-source")).toContainText("Shortened or adapted");
  249 | 
  250 |   await page.getByRole("button", { name: "Artists" }).click();
  251 |   const artistCardAvatar = page.locator(".artist-card-photo").first();
  252 |   await expect(artistCardAvatar).toBeVisible();
  253 |   await nowPlayingButton.click();
  254 |   await page.locator(".mobile-secondary").filter({ hasText: "Lyrics" }).click();
  255 |   const lyricsArtist = page.locator(".lyrics-meta .artist-link").first();
  256 |   await expect(lyricsArtist).toBeVisible();
  257 |   await lyricsArtist.click();
  258 |   await expect(page.locator(".artist-name")).toHaveText(artistName!);
  259 | });
  260 | 
  261 | test("public credits page keeps the nonce CSP and lists attribution", async ({ page }) => {
  262 |   const response = await page.goto("/credits");
  263 |   const csp = response?.headers()["content-security-policy"] ?? "";
  264 |   expect(csp).toContain("script-src 'self' 'nonce-");
  265 |   expect(csp).toContain("img-src 'self' data: blob:");
  266 |   expect(csp).toContain("media-src 'self' blob: https://*.supabase.co");
  267 |   expect(csp).toContain("https://*.theaudiodb.com");
  268 |   await expect(page.getByRole("heading", { name: "Credits and data sources" })).toBeVisible();
  269 |   await expect(page.getByRole("link", { name: "Wikipedia" })).toBeVisible();
```