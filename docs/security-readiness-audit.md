# Security and website readiness audit — 2026-11-02

## Conclusion

**Decision: still blocked from controlled production verification.** The
landscape auth layout is resolved locally, and source review found no confirmed
authentication vulnerability. Two clean full Playwright runs passed 58 tests
each with 2 skips; a focused rerun passed all 4 selected tests, including the
long playback flow. The three previously reported failures did not reproduce.
Investigation found no confirmed root cause, so these runs do not establish that
the historical failures are permanently resolved. Live deployment settings,
production deletion, and legal/provider confirmations remain outstanding.
This is not a production-readiness certification.

The authentication source review found no actionable vulnerability in session
validation, CSRF, logout-all, account deletion ordering, or account isolation.
Source inspection and synthetic local tests do not prove production
configuration, database policies, provider permissions, or real-user behavior.
No production account, customer data, or production deletion was used.

## Checklist — 24 requested areas

| # | Area | Disposition | Evidence and remaining limit |
|---|---|---|---|
| 1 | Horizontal overflow | **PASS** | Browser checks at 320×568, 390×844, 844×390, and 1280×720; mobile-player measurements also found no horizontal overflow. |
| 2 | Internal links, navigation destinations, logo, contact links | **PASS / N/A** | Browser checks cover public navigation and the clickable brand logo. No public phone number or email address is supplied, so none was invented. |
| 3 | Mobile navigation | **PASS** | Local Playwright mobile navigation and keyboard-shortcut test passed. |
| 4 | Favicon and application icons | **PASS** | Production readiness test fetched the favicon, Apple icon, app icons, SVG brand mark, and manifest successfully. |
| 5 | Titles, descriptions, and page metadata | **PASS** | Production route checks verified descriptions and matching Open Graph descriptions for login, registration, privacy, terms, and credits. |
| 6 | Social previews, sitemap, and robots rules | **PASS** | Production test validated social-card metadata, 1200×630 PNG response, sitemap entries, and robots exclusions. |
| 7 | Footer, copyright year, and footer links | **PASS** | Public-page browser checks verified the footer and working links. |
| 8 | Branded 404 | **PASS** | Production readiness test received HTTP 404 for a missing route; the local smoke test verified its branded page and return navigation. |
| 9 | Image handling and optimization | **PARTIAL — LOW** | Fallbacks and lazy/async image behavior are present, but ESLint still reports 10 raw `<img>` uses. The Liquid Glass detector’s initial empty decorative image is populated or removed by its script; it was not confirmed broken. |
| 10 | Button behavior and success/error feedback | **PASS** | Local browser coverage exercised navigation, playlists, playback, track actions, provider failures, and account settings. |
| 11 | Form usability, labels, and input contrast | **PASS** | Login/registration and lyrics-editor labeling checks passed. Measured input border contrast is 4.05:1 against the input and 5.32:1 against its card. |
| 12 | Responsive public pages | **PASS (local)** | Production readiness tests passed at 320×568, 390×844, 844×390, and 1280×720. The earlier landscape auth-card clipping is resolved by top-aligning the card and enabling vertical scrolling in `web/src/app/auth.css`; the 844×390 test passed. Physical devices remain unverified. |
| 13 | Expanded mobile player, portrait and landscape | **PASS** | At 390×844 the player occupied the viewport with no horizontal overflow. At 844×390 its scroll region was 314px high with 699px of content; touch scrolling reached the 385px maximum and brought the Play control fully into view. Controls require scrolling in landscape. |
| 14 | Audio streaming and HTTP Range | **PASS** | Mock-backend browser flow passed playback, seeking, and ranged-response behavior, including the range path; no production storage was used. |
| 15 | Network recovery and signed-URL refresh | **PASS** | Local browser tests passed transient media recovery, hidden-page recovery, and a single expired signed-URL refresh. Cellular-device behavior remains unverified. |
| 16 | Retry, queue, seeking, and transitions | **PASS** | Browser tests passed bounded retry behavior, queue transitions, repeat/shuffle, and cancelled-seek behavior. |
| 17 | Offline downloads and IndexedDB account isolation | **PARTIAL — MEDIUM** | Account-scoped cleanup and synthetic two-account isolation passed locally. No production browser data was inspected; installed-device and production logout behavior remain unverified. |
| 18 | Authentication, sessions, CSRF, and tenant isolation | **PARTIAL — MEDIUM** | Scoped source review found no actionable vulnerability. Session-version mismatch and `/api/account/logout-all` now have direct regression tests; CSRF, revoked sessions, and synthetic account isolation are also covered locally. Production PostgreSQL/RLS, Redis, cookie, and secret settings were not independently checked. |
| 19 | Account deletion and session revocation | **PARTIAL — MEDIUM** | Source confirms session-version advancement and Redis revocation precede Storage and database deletion; Storage object paths and database rows are account-scoped. Backend failure tests and the local browser cleanup test pass. The production checklist remains manual and dedicated-synthetic-account-only; production deletion was not performed. |
| 20 | Upload limits, image validation, truncated JPEG | **PASS (local)** | Backend suite passed 130 tests; the focused truncated-JPEG pixel-data test passed 1/1 (10 deselected). This verifies local validation code, not production storage behavior. |
| 21 | Database/storage consistency, migrations, backup, recovery | **PARTIAL — MEDIUM** | Tenant-scoped cleanup and partial-failure paths were reviewed and locally tested. Live Supabase/PostgreSQL state, migration execution, backups, restore procedures, and retention were not verified. |
| 22 | Lyrics proxy, synchronization, and custom lyrics | **PASS (local)** | Eight JavaScript proxy tests and browser lyrics flows passed. Commercial permission from LRCLIB remains unconfirmed. |
| 23 | Artist data, artwork, provider failures, attribution, and rights | **PARTIAL — HIGH release blocker** | Mocked fallback/attribution behavior passed. Live provider availability, applicable terms, image rights, and commercial permissions require provider/rightsholder confirmation. |
| 24 | Service worker, deployment configuration, accessibility, and live performance | **PARTIAL** | Local service-worker, metadata, CSP, build, and viewport checks passed. Screen-reader/physical-device testing, live deployment overrides, and field Core Web Vitals were not verified. |

## Findings and severity

| Severity | Finding | Evidence / disposition |
|---|---|---|
| **MEDIUM** | Historical Playwright failures remain unexplained; the long flow is slow. | Two clean local full runs passed 58 tests with 2 skips, and a focused rerun passed all 4 selected tests. Both reported empty-library checks and the queue-panel alignment assertion passed. The 60-track mock playback flow passed in 5.3 minutes in the first full run, 5.2 minutes focused, and 5.1 minutes in the latest full run, below its existing 420-second limit. Investigation found one worker, serial execution, isolated Playwright browser contexts, a process-shared mock backend reset on successful local login, and server reuse disabled unless explicitly opted in. Library content renders asynchronously behind its loading skeleton; the heading assertions wait for the heading. The queue is fixed at `right: 0` and the test polls after opening. No test-isolation, server-reuse, asynchronous-rendering, or application defect was confirmed as the cause of the historical failures. No assertions or timeouts were weakened. |
| **HIGH — release blocker** | Commercial/provider and image-rights confirmation is incomplete. | LRCLIB commercial permission remains unconfirmed. Preserve TheAudioDB’s exact informal reply: “It's entirely up to you. Use our services as you like. Cheers, Zag.” It is not a formal commercial license or image-rights clearance. Confirm terms, attribution, commercial use, and image rights with providers/rightsholders. |
| **MEDIUM** | Production security and deletion controls need operator verification. | Confirm live HTTPS/Secure cookie behavior, Redis/session-secret configuration, database tenant controls/RLS, Storage bucket policy, and the complete deletion process using only the manual synthetic-account checklist. |
| **MEDIUM** | LGPD and operational confirmations are incomplete. | Hosting region, international-transfer basis/measures, retention schedule, incident-response ownership/procedure, migrations, backup, and restore were not evidenced for production and require operator/legal confirmation. |
| **LOW** | ESLint warnings remain. | ESLint: 16 warnings, 0 errors (10 dynamic/script-managed or blob/remote `<img>` uses, 5 intentional full-document auth/session navigations, and 1 root Google Fonts warning). Review found no safe justified change: image optimization needs loader/domain and behavior work, full reloads refresh auth/session state, and changing font loading would alter the app's font setup. Ruff is now clean; the two BLE001 catches were narrowed to expected provider, storage, and database failures. |

Playwright reuses local servers only when `PLAYWRIGHT_REUSE_SERVER=1` is
explicitly set; the recorded run started its own local mock backend and Next.js
development server. The library's async loading and the queue panel's CSS
transition are real, but neither caused a failure in the current runs. The
long test remains expensive and the earlier failures' root cause cannot be
claimed as resolved without reproducing them. The suite passed two consecutive
full local runs and one focused rerun, but the prior intermittent failures mean
it cannot be called genuinely stable on this evidence alone.

## Authentication assessment

The scoped source review found no confirmed exploitable vulnerability in
authentication, CSRF, logout-all, account deletion, or tenant-scoped
operations. `current_user_row` rejects missing or malformed session identifiers
and versions, rejects a version mismatch before Redis validation, and rejects
revoked/expired sessions. Mutations use session-bound CSRF validation;
logout-all bumps the user's session version and clears the current session.
Two new regression tests directly cover logout-all version bump/current-session
clearing and stale-version rejection. Existing tests cover CSRF failure,
session revocation, per-user revocation, cross-account object access, and
account deletion failure handling. Live Redis behavior, cookie flags, applied
RLS migrations, and deployment secrets remain unverified.

The short-landscape auth-card issue is resolved locally: `auth.css` enables
top alignment and vertical scrolling at short heights, and the 844×390
Playwright layout test passes. This is not a physical-device test.

## Account-deletion readiness

Source order is session-version bump → Redis session revocation → account-ID
scoped Storage object deletion → account-scoped database cleanup/commit →
client cleanup after successful API response. Failure to revoke stops before
Storage or database deletion; Storage/database partial failures are surfaced
for an exact-account retry. Browser cleanup filters `offlineTracks` by the
deleted `accountId`, and a browser test confirms a synthetic other-account
record remains. The local browser test stubs the API success, so it does not
verify server-side deletion. Follow
`docs/account-deletion-production-checklist.md` manually only with explicit
authorization and a dedicated synthetic account. Do not use production
customer/maintainer accounts or run broad data scans.

## Verification evidence

| Check | Result |
|---|---|
| Full local Playwright suite, first clean run | **58 passed, 0 failed, 2 skipped** (60 total) in 20.7 minutes. The skipped tests require a separately configured local API and backend credentials; no production target was used. |
| Full local Playwright suite, post-change run | **58 passed, 0 failed, 2 skipped** (60 total) in 17.0 minutes. The 60-track flow passed in 5.1 minutes, below its unchanged 420-second timeout. The two skipped tests still require a separately configured local API and backend credentials; no production target was used. |
| Focused Playwright rerun | **4 passed, 0 failed, 0 skipped** in 6.3 minutes: brand logo/empty library, tablet/mobile player, mobile navigation, and the 60-track mock playback flow. The long flow took 5.2 minutes. |
| Account-deletion browser cleanup test | **1 passed, 0 failed, 0 skipped**. The API success is stubbed; this validates browser-local lyrics/IndexedDB cleanup only, not server deletion. |
| Production `website-readiness.spec.ts` | **6 passed, 0 failed, 0 skipped**: social previews, crawl rules, assets, 404, anonymous LRCLIB denial, and 320×568 / 390×844 / 844×390 / 1280×720 page layouts. |
| Synthetic account-isolation browser/API test | **1 passed, 0 failed, 0 skipped** using two synthetic accounts, local SQLite, disabled external providers/storage, and a temporary database. |
| Responsive auth/legal focused tests after landscape correction | **4 passed, 0 failed, 0 skipped**. |
| Production build | **Passed** with reserved local-test `SITE_URL=https://vervfy.example`. Next.js compiled, type-checked, generated 16 static pages, and listed the App Router routes including `/opengraph-image`, `/robots.txt`, and `/sitemap.xml`. |
| TypeScript | **Passed** (`npx tsc --noEmit`, and during the production build). |
| ESLint | **0 errors, 16 warnings**. Reviewed all warnings; none were safely actionable without changing auth/session navigation, dynamic image loading, or root font behavior. |
| Ruff | **Passed; 0 findings**. |
| Backend pytest | **130 passed, 0 failed, 0 skipped; 69 subtests; 5 warnings**. |
| Authentication/deletion regression tests | **19 passed, 0 failed, 0 skipped; 1 warning**. Includes route-level logout-all version-bump/current-cookie clearing and stale-version rejection tests. |
| Cover-art regression tests | **21 passed, 0 failed, 0 skipped**. Added a check that unexpected provider programming errors are not swallowed by fallback handling. |
| Truncated-JPEG focused test | **1 passed, 0 failed, 10 deselected; 2 warnings**. |
| Lyrics proxy tests | **8 passed, 0 failed, 0 skipped**. |
| Production client bundle scan | **70 files inspected, 0 source maps, 1 environment file observed, 0 configured privileged values, 0 findings**. |
| `git diff --check` | Passed after the final report update. |

The test/build results above are local evidence only. They are not a production
penetration test, legal review, production deletion, or live Core Web Vitals
measurement.

## Contrast and local lab performance

Input-border contrast was rechecked by reading computed browser colors:
**4.05:1** against the input background and **5.32:1** against the containing
card. Other measured text contrast ratios were 16.44:1 for the auth title,
10.55:1 for the subtitle/labels/footer links, and 7.64:1 for the password hint.

`web/scripts/readiness-measurements.mjs` ran three samples at each viewport
against the locally served production build:

| Viewport | TTFB | LCP | CLS | Max observed Event Timing duration | Transferred bytes |
|---|---:|---:|---:|---:|---:|
| 1280×720 | 16.7–23.5 ms | 480–552 ms | 0.00182–0.00241 | 32–56 ms | 238,701–238,706 |
| 390×844 | 18.0–24.9 ms | 360–364 ms | 0.00657–0.00711 | 24–40 ms | 238,687–238,700 |

These are local lab samples, not live Core Web Vitals. The event durations are
observed Event Timing entries, not field INP; no real-user telemetry or live
production CWV data was available.

## Source inspection vs. automated evidence vs. external confirmation

- **Source inspection:** The current code contains request-size and upload
  validation, image decoding/pixel checks, account-scoped deletion paths,
  session-version/revocation handling, and an authenticated/flagged/rate-limited
  LRCLIB proxy. Session validation rejects absent/malformed session IDs and
  versions, mismatched versions, and revoked sessions. Mutating requests use
  session-bound CSRF validation. Logout-all advances the version, while account
  deletion advances it and revokes sessions before any file or row deletion.
  Database and Storage paths are selected by authenticated account ID. This
  describes the repository, not the live service settings.
- **Automated local evidence:** The tests above use synthetic fixtures, mocks,
  local browser runs, and temporary SQLite. They support the behaviors they
  exercised; they do not prove live Redis, PostgreSQL/RLS, Supabase Storage,
  provider availability, or operator procedures. Browser deletion coverage
  stubs successful API deletion and verifies account-scoped IndexedDB cleanup;
  it does not prove actual production row/object removal.
- **Live production/legal confirmation still required:** Verify deployment
  overrides and HTTPS/cookie behavior, Redis and session secrets, database
  tenant enforcement/RLS, Storage policies, migrations/backups/restore and
  retention, hosting region and international-transfer details, the LGPD
  retention schedule and incident-response procedure, production deletion,
  live monitoring/CWV, and provider/legal permissions. Do not use production
  accounts or customer data for deletion verification.

## Modified files and preserved work

The preceding cleanup added route-level logout-all and stale-session-version
regression tests, clarified immutable FastAPI dependency defaults for Ruff,
bound loop variables in Wikipedia callback tests, removed unused code,
narrowed expected media-parser exceptions, and made shebang scripts
executable. Ruff went from 91 findings to 2. This stabilization follow-up
resolved those last two BLE001 findings: provider fallback catches now handle
expected network/configuration errors, and per-record migration recovery
handles SQLAlchemy, storage/runtime, OS, and value errors. Unexpected provider
programming errors now surface; a cover-art regression test verifies that
behavior. Provider endpoints and integrations were not changed. No frontend,
Google OAuth, or provider integration settings were changed.

Files changed by this stabilization follow-up: `cover_art.py`,
`scripts/migrate_audio_to_storage.py`, `tests/test_cover_art.py`, and this
report. Existing worktree changes, including authentication fixes and the two
session regression tests, were preserved.

Files changed by this cleanup: `ruff.toml`, `artist_images.py`, `audio_store.py`,
`library.py`, `scripts/migrate_local_data.py`, `server.py`,
`scripts/backfill_cover_storage.py`, `scripts/backfill_covers.py`,
`scripts/migrate_audio_to_storage.py`, `scripts/move_audio_to_storage.py`,
`scripts/upload_worker.py`, `tests/test_artist_images.py`,
`tests/test_artist_profiles.py`, `tests/test_security_regressions.py`, and
this report. The shebang scripts and `server.py` gained executable mode only.
All pre-existing uncommitted work, including account deletion/session
revocation, its production checklist, website readiness work, the exact
TheAudioDB response, and LRCLIB's unconfirmed commercial permission status,
remains preserved.

The following dirty-worktree inventory was preserved. Ruff safe autofixes in
this continuation touched Python files within this inventory; the other
pre-existing changes, including account deletion/session revocation, were
preserved.

- Backend/config: `.env.example`, `artist_images.py`, `audio_store.py`,
  `auth.py`, `cover_art.py`, `database.py`, `db.py`, `library.py`, `migrate.py`,
  `request_limits.py`, `server.py`, and `upload_queue.py`.
- Migrations: `alembic/env.py` and
  `alembic/versions/0001_postgres_persistence.py`,
  `0002_profile_photo.py`, `0003_track_size.py`, `0004_session_version.py`,
  `0005_storage_path.py`, `0006_tenant_integrity.py`,
  `0007_row_level_security.py`, `0008_upload_jobs.py`,
  `0009_upload_retry_count.py`, `0010_verified_account_email.py`,
  `0011_playlist_position.py`, `0012_artist_image_cache.py`,
  `0013_artist_catalog.py`,
  `0014_user_covers_remove_artist_catalog.py`, `0015_artist_photos.py`,
  `0016_audiodb_artist_images.py`, `0017_track_covers.py`,
  `0018_cover_checked_at.py`, `0019_track_listens.py`, and
  `0020_playlist_last_played.py`.
- Backend scripts: `scripts/backfill_cover_storage.py`,
  `scripts/backfill_covers.py`,
  `scripts/migrate_audio_to_storage.py`, `scripts/migrate_local_data.py`,
  `scripts/move_audio_to_storage.py`, `scripts/rebuild_covers.py`, and
  `scripts/upload_worker.py`.
- Documentation: `docs/account-deletion-production-checklist.md`,
  `docs/google-oauth-readiness.md`, `docs/third-party-data.md`, and this report.
- Backend tests: `tests/lrclib-proxy.test.mjs`, `tests/readiness_backend.py`,
  `tests/test_album_covers.py`, `tests/test_artist_images.py`,
  `tests/test_artist_photos.py`, `tests/test_artist_profiles.py`,
  `tests/test_audio_stream_redirect.py`,
  `tests/test_cover_art.py`, `tests/test_provider_regression_guard.py`,
  `tests/test_readiness_security.py`, `tests/test_rebuild_covers.py`,
  `tests/test_security_regressions.py`, `tests/test_track_covers.py`,
  `tests/test_track_listens.py`, and `tests/test_upload_metadata.py`.
- Web configuration/assets: `web/AGENTS.md`, `web/next.config.ts`,
  `web/playwright.config.ts`, `web/public/liquid-glass.js`,
  `web/scripts/audit-client-secrets.mjs`,
  `web/scripts/readiness-measurements.mjs`.
- Web routes/styles: `web/src/app/(auth)/login/page.tsx`,
  `web/src/app/(auth)/register/page.tsx`, `web/src/app/(player)/page.tsx`,
  `web/src/app/auth.css`, `web/src/app/credits/page.tsx`,
  `web/src/app/layout.tsx`, `web/src/app/opengraph-image.tsx`,
  `web/src/app/privacy/page.tsx`, `web/src/app/robots.ts`,
  `web/src/app/sitemap.ts`, `web/src/app/styles.css`,
  `web/src/app/terms/page.tsx`.
- Web components/libs/tests: `web/src/components/account-settings.tsx`,
  `web/src/components/legal-document.tsx`,
  `web/src/components/library-app.tsx`,
  `web/src/components/lyrics-overlay.tsx`,
  `web/src/components/privacy-policy-content.tsx`,
  `web/src/components/terms-content.tsx`, `web/src/lib/i18n.tsx`,
  `web/src/lib/lrclib-proxy.ts`, `web/src/lib/page-metadata.ts`,
  `web/src/lib/site-metadata.ts`, `web/tests/account-isolation.spec.ts`,
  `web/tests/mock-backend.mjs`, `web/tests/smoke.spec.ts`,
  `web/tests/website-readiness.spec.ts`, and
  `web/test-results/.last-run.json`.
- Tooling configuration: `ruff.toml`.

The production account-deletion procedure remains manual and synthetic-account
only. This report does not declare Vervfy production-ready.
