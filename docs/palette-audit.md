# Navy and logo-turquoise palette audit

`design-tokens.json` is the shared color source for the web app, canvas artwork, metadata, email templates, and native shell. Run `python3 scripts/generate_design_tokens.py` after editing it. Authentication retains its separate role layer in `web/src/app/auth-tokens.css`, with references to shared colors rather than duplicate base values.

## Restored appearance

The original navy backgrounds and cool-white typography come from Git commit `fde57bdca8629a776014c91682b4c2188257ed11`, before the graphite theme:

- Background: `#0C0E14`.
- Surface/sidebar: `#12151E`; artwork surface: `#161925`.
- Primary text: `#F2F3F7`; secondary: `#C0C5D1`; muted: `#A0A8BA`.
- Exact logo gradient: `#08E7BE` to `#02DFB6`, read directly from the unchanged official SVG.
- Danger remains `#FF6B7A`. Password-strength danger/caution/success colors remain unchanged.

Original surface declarations were restored for the sidebar, topbar, search controls, ordinary buttons, artwork cards, and playlists. Graphite/teal surface overrides were removed. The shared accent replaces the temporary pale-blue exceptions and intermediate turquoise values. Neutral controls retain their own fills; there is no blanket button recoloring. Primary actions retain their turquoise gradient on hover; hover brightness is centralized at 75% of normal, while the default fill matches the logo.

Layout sizes, spacing, fonts, component structure, and functionality were retained. Glass blur, saturation, refraction, opacity values, and responsive rules remain in place; their neutral highlights use the original white. Placeholder text explicitly uses the existing muted role for legibility. Logo assets, the Google identity mark, and user artwork are unchanged. The offline shell cache version was advanced to refresh cached tokens.

## Verification

- 59 palette, shared-logo identity, auth scope, contrast, generation, and branded email checks passed. These include AA text/background pairings and representative tinted controls, alerts, and gradient button endpoints.
- TypeScript `--noEmit` passed.
- ESLint completed with zero errors and 17 existing warnings.
- Ruff passed for the token generator and palette test modules.
- Both existing Node test files for skeleton layout and toast translation passed.
- Global CSS parsing and `git diff --check` passed.
- Responsive screenshots and axe checks were attempted with Playwright. The sandbox denied its local mock-backend socket (`EPERM`, `127.0.0.1:8100`), so no rendered visual or browser accessibility pass is claimed.
- The production Turbopack build timed out after 90 seconds. The webpack fallback failed while parsing TypeScript `--showConfig` subprocess output, although the direct TypeScript check passed. No successful production build is claimed.
- Apple SDK compilation and email-client/device visual review were not available in this Linux workspace.

Rendered contrast over arbitrary artwork and client-specific email rendering still require browser/device verification. The verification limitations above remain applicable to this release.
