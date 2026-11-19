# Vervfy interaction details: 20-item review

Reviewed and updated November 18, 2026. Changes are local and have not been deployed.

| # | Detail | Result |
|---|---|---|
| 1 | Skeletons instead of spinners | Library, list, artist, playlist, recap and account skeletons already exist. Added a shared streamed page skeleton in `web/src/app/loading.tsx`. Playback buffering and pull-to-refresh indicators remain because they indicate an active operation, not an empty page. |
| 2 | Optimistic updates | Favorites, playlists, queue changes and playlist membership already update before server confirmation. Track and playlist removal now hide immediately during an Undo window. Existing metadata saves serialize changes and merge version conflicts; failed saves notify and retain local intent for retry. |
| 3 | Command menu | Added Cmd+K / Ctrl+K and a visible Commands button. Search navigation, upload, shortcut help and songs; use arrows, Enter or Escape. Native modal focus trapping, return focus and screen-reader selection are supported. Sensitive modal forms take priority over the global shortcut. |
| 4 | Keyboard hints | Existing search hint and shortcut help remain. Added the command shortcut beside its button, in shortcut help, and in accessibility metadata, plus navigation hints inside the menu. Modified shortcuts do not trigger unrelated player actions. |
| 5 | Undo toasts | Replaced track and playlist delete confirmation popups with immediate hiding and an eight-second Undo window. Hover or keyboard focus pauses the countdown. Multiple removals have separate Undo actions; once committed they cannot be undone. Track failures show an error and reveal the track again. Account erasure still requires explicit confirmation because that action is irreversible and security-sensitive. |
| 6 | Stale-while-revalidate | Loaded content stays visible during refresh, reconnect and return-to-tab checks. Recent library snapshots stay in memory for five minutes and are replayed only after `/api/me` confirms the same account. Refresh failure keeps existing content. Overlapping refreshes are coalesced, local edits are preserved, and an account change clears the previous account’s content and playback. No private response is placed in a public/shared cache. |
| 7 | Pre-rendering | Public pages already render their initial content on the server; the public homepage keeps the private player in a separate lazy bundle. Added a loading boundary that supports streaming and Next’s automatic loading-shell prefetch. Full static generation/shared HTML caching is deliberately not enabled: the root reads language/session cookies and fresh CSP nonces. This is server rendering, not build-time static generation. |
| 8 | Blurred placeholders | Artist-photo and song-cover loading changes, including the added blurred placeholders, were reverted at the owner’s request. Original image loading, fallback and shimmer behavior is restored. |
| 9 | View transitions | Added React 19.3 transitions around route content, browser view transitions for library view changes and same-origin document transitions where supported. Unsupported browsers change views normally; reduced motion disables animation. |
| 10 | Mobile sheet dismissal | Added downward header drags for the expanded player, queue, shortcut sheet, library picker, playlist picker, playlist add sheet and sleep timer. Inputs/buttons and body scrolling keep their own gestures. Form editors retain explicit close controls to avoid losing unsaved text accidentally. |
| 11 | Interruptible animation | Rapid view changes skip the previous view animation. Dragged sheets follow the finger, can cancel and snap back, and can be grabbed again during snap-back without jumping to the starting position. Existing button transitions already reverse from their current state. |
| 12 | Predictive/native back | Library views now create real browser history entries, including safe deep links, and restore on Back/Forward. Enabled WKWebView back/forward navigation gestures in the Apple wrappers. Gesture previews and Android predictive-back visuals belong to the browser/OS; web code cannot guarantee them everywhere. Apple changes need an Apple build/device check. |
| 13 | Larger tap targets | Mobile size increases were reverted at the owner’s request. Existing button/link dimensions are restored; new command and Undo controls retain their own base styling. |
| 14 | Safe areas | Existing dock/player safe-area spacing remains. Enabled `viewport-fit=cover` and added safe-area padding for public pages, command menu, sheets and Undo toasts. |
| 15 | One-time-code autofill | Not applicable today: recovery uses email links; passkey setup displays recovery codes but has no OTP-entry field. No fake code form or inappropriate autofill attribute was added to passwords or account-deletion confirmation. |
| 16 | Tabular numbers | Expanded tabular numerals across the app, including playback times, counts and future counters. Existing account/recap numeric styling remains. There is no pricing screen. |
| 17 | Balanced headlines | Added balanced wrapping to headings and pretty wrapping to public description text. Exact word placement still depends on font, language and screen width; arbitrary long words cannot universally be kept with the previous word on narrow screens. |
| 18 | Continuous corners | Added progressive `corner-shape: squircle` for cards and dialogs. Existing rounded corners remain the fallback where smooth-corner support is unavailable. |
| 19 | Idempotency and double taps | No payments or charging flow exists, so there is no payment endpoint to protect with an idempotency key. Added a synchronous guard against starting overlapping upload batches. Existing server uploads use account-scoped content IDs, duplicate-recording checks and fenced queued attempts; metadata writes use version checks. This does not introduce a generic idempotency-key protocol for future payment endpoints. |
| 20 | Safe triangle for submenus | Not applicable to current menus: playlist/artist actions open by click, and playlist selection opens a dialog; no hover-driven cascading submenu closes on mouseleave. A safe-triangle algorithm would be dead code until a hover submenu exists. |

## Validation

- TypeScript compilation and targeted ESLint checks pass; lint reports existing image/font warnings.
- Existing notification translation checks pass (2 tests).
- Added six browser regression cases for command keyboard/focus/history, Undo and exactly-once deletion, background refresh, mobile dismissal, malformed deep links and account isolation.
- Browser tests could not run: the sandbox rejects binding the mock server to `127.0.0.1:8100` with `EPERM`.
- Production build could not complete: Next reports that it cannot parse the TypeScript subprocess’s `--showConfig` output. Direct TypeScript checking succeeds; a diagnostic call confirms that the subprocess returns empty output in this environment. This is not a successful production build.
- Apple gestures and visual layouts require an Apple/browser device pass; no Apple SDK is available here.

## Main implementation

`web/src/components/command-menu.tsx`, `web/src/lib/ui/`, `web/src/components/library-app.tsx`, `web/src/components/root-providers.tsx`, `web/src/components/resilient-image.tsx`, `web/src/app/loading.tsx`, `web/src/app/layout.tsx`, `web/src/app/styles.css`, `web/src/lib/i18n.tsx`, `web/src/store/player-store.ts`, and `apple/Vervfy/VervfyWebView.swift`.

Undo commits on page exit or component removal, using keepalive for small state/delete requests. As with other web writes, abruptly killing a browser or losing the network can prevent an in-flight request from completing; playlist save failures retain local intent and show the existing sync error when the page remains open.
