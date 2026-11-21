# Vervfy web app

This directory contains Vervfy's Next.js frontend. Browser API requests are
proxied to the FastAPI backend, so set `BACKEND_URL` to that service before
starting or building the app. For local development, copy `.env.example` to
`.env.local` and point it at the local backend.

```bash
npm ci
npm run dev
```

The Playwright suite starts a local mock backend and Next.js development
server by default. It requires Chromium; in a fresh environment install it
with `npx playwright install chromium`. CI runs the same suite after installing
Chromium system dependencies.

Run the frontend checks from this directory:

```bash
npm run lint
npx tsc --noEmit
npm run build
npm run test:e2e
```

The Render deployment is defined in the repository-root `render.yaml`.

For production, explicitly set `SITE_URL=https://vervfy.com` in the frontend
hosting environment (including Vercel). Canonicals, social URLs, JSON-LD,
robots.txt, and sitemap entries share this origin. Use the staging frontend
origin for staging deployments. The Render frontend blueprint sets the
production origin explicitly.

SEO checks: `npx playwright test tests/seo.spec.ts tests/website-readiness.spec.ts`.
These cover server-rendered content without JavaScript in English, Brazilian
Portuguese, French, and Spanish, language-switch metadata, public sitemap
entries, and authentication page exclusions. The public routes are `/`,
`/privacy`, `/terms`, and `/credits`; account data is served through protected
API routes and never listed in the sitemap. Robots rules are crawler guidance,
not access control. Authentication pages retain their existing noindex metadata
and robots exclusions.

After deployment, inspect the homepage and submit `https://vervfy.com/sitemap.xml`
in Google Search Console. Check Google's selected canonical and indexing status;
crawlable HTML alone does not establish that a page is indexed. Language variants
currently share URLs selected by cookie/request headers, so no separate-language
hreflang URLs are advertised. Consider distinct public locale URLs if multilingual
search visibility becomes a priority. The application describes personal uploads,
not a public music streaming or download catalog.
