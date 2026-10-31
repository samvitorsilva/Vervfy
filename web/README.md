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
