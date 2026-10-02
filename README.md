# Vervfy

A self-hosted music player for the web, built with a modern design that feels unique and user-friendly.

Upload your own files, organize them into playlists, look up lyrics and artist bio, and listen through a player that doesn't feel like an afterthought.

---

## What it does

Vervfy is a self-hosted music player with a Next.js App Router frontend in
`web/` and a FastAPI backend for authentication, library data, uploads, and
audio streaming. Next.js is the only user-facing frontend.

Here's roughly what's in there:

**Library**
Drag-and-drop uploads (whole folders, where the browser allows it), automatic metadata reading, album art extraction — and if a track has no cover, one gets generated so your library doesn't look empty. You can search, remove tracks, and stream everything straight from the backend. Supported formats include MP3, M4A/MP4, AAC, FLAC, OGG/OGA, Opus, WAV, and WebM audio.

**Player**
The basics you'd expect — play/pause, next/previous, seeking, volume, mute — plus a queue system with an "up next" view, shuffle and repeat, a mini player for when you want it out of the way, system media controls where supported, and keyboard shortcuts for everything (see below). Playback supports authenticated byte-range seeking.

**Organization**
Favorite tracks, build playlists, and keep it all sorted per user. Libraries are kept fully separate between accounts.

**Lyrics**
This ended up being one of the more involved parts. Vervfy checks embedded ID3 lyrics first (plain and synced), then falls back to an online lookup through LRCLIB. Lyrics scroll in sync with playback and highlight the current line. Custom lyrics can be pasted or typed in and are saved to the account.

**Visualizer**
A Web Audio API–based visualizer that reacts to whatever's currently playing.

**Accounts**
Its own auth system — registration, username-and-password login, logout, optional account email, account password changes, bcrypt-hashed passwords, session-based auth, CSRF protection, and rate limiting. Email is account information only and is not used for sign-in or password recovery. Every user gets their own isolated library.

**Artist info**
Artist profiles prefer manually checked entries, then use an exact Deezer artist match tied to a title in the user's library before fetching a matching Wikipedia summary. Portraits use the same catalog/title verification, with a manually verified portrait for the ambiguous artist Dave. The profile shows its source, and artist lookup failures leave the library usable.

**As a web app**
It's built to feel like an app, not a website: responsive on desktop, tablet, and mobile, a mini player, account-backed sync, and full keyboard navigation. The keyboard-shortcuts button is hidden on touch-sized layouts, while physical keyboards still work. Audio and online lyrics require an active connection.

---

## Stack

**Backend** — Python, FastAPI, Uvicorn, SQLAlchemy, PostgreSQL (Supabase), Alembic, bcrypt, Starlette sessions, python-multipart

**Audio/media** — Mutagen for metadata and ID3 handling, Pillow for artwork

**Frontend** — Next.js App Router, React, TypeScript, Zustand, CSS, Web Audio API

---

## Project layout

```text
vervfy/
├── auth.py            # accounts, sessions, CSRF, throttling
├── library.py         # tracks, metadata, artwork, lyrics storage
├── server.py           # the FastAPI app itself — routes, streaming, uploads
├── requirements.txt
│
├── web/               # Next.js app; proxies same-origin requests to FastAPI
│   ├── src/app/
│   ├── src/components/
│   └── public/
│
├── render.yaml        # Separate Next.js Render web service
├── data/
│
└── README.md
```

---

## Hosted app

The FastAPI backend is deployed at
https://vervfy-app.onrender.com. The Next.js frontend is deployed as a separate
Render web service and proxies browser API requests to that backend.

---

## Persistent data and deployment

Vervfy stores accounts, bcrypt password hashes, profile photos, tracks/audio,
cover art, custom lyrics, favorites, and playlists in PostgreSQL. Profile
photos are limited to 5 MB and can be JPEG, PNG, WebP, or GIF. 

### Deploying on Render

The root `render.yaml` defines the `vervfy-next` Node web service. Create or
update a Render Blueprint from this repository to deploy it. It uses
`web/` as its root directory and sets `BACKEND_URL` to the existing FastAPI
service. Render assigns the Next.js service its own public URL; use that URL
for the new frontend rather than the FastAPI service URL.

For local development, copy `web/.env.example` to `web/.env.local`, set
`BACKEND_URL` to the FastAPI URL, then run:

```sh
cd web
npm ci
npm run dev
```

`BACKEND_URL` is required at build and runtime. Requests from the browser stay
same-origin through Next.js rewrites; audio streams and uploads still go
directly through those rewrites to FastAPI.

#### Next.js browser smoke tests

Install the Playwright browser once with `cd web && npx playwright install chromium`,
then run `npm run test:e2e`. The login UI, offline fallback/API exclusion, and
authenticated full flow run by default against a deterministic local mock
backend, including playlist creation, repeat-mode cycling, a 60-file upload
with a simulated `429 Retry-After`, playback, seeking, and byte-range streaming.
To run the full flow against FastAPI, set `PLAYWRIGHT_BACKEND_URL` to the
backend URL and `PLAYWRIGHT_USERNAME` / `PLAYWRIGHT_PASSWORD` to a disposable
account; the mock-only full flow is skipped. To test a deployed Next.js service,
set `PLAYWRIGHT_BASE_URL` to its URL; otherwise Playwright starts the local app
on port 3100.

The Next.js service sends a `Content-Security-Policy-Report-Only` policy that
includes Next.js scripts/styles, Google Fonts, same-origin API/audio requests,
and LRCLIB. The FastAPI security-header configuration has not been changed;
its existing report-only header remains in effect until separately approved
and reviewed for enforcement.

Run database migrations before starting the backend: `alembic upgrade head`
must finish successfully before `uvicorn` starts. When Render terminates TLS
in front of the application, start Uvicorn with
`--proxy-headers --forwarded-allow-ips='*'` so forwarded HTTPS headers are
trusted.

If the application database role does not own the tables, set
`MIGRATION_DATABASE_URL` to a PostgreSQL URL for a role that owns them. Alembic
uses that URL for schema changes, while the running app continues using
`DATABASE_URL`. In particular, PostgreSQL requires table ownership to add the
`playlists.position` column; granting ordinary table privileges is not enough.
If you use only `DATABASE_URL`, that role must own the existing tables.

Check both services' browser console reports for CSP violations after
deployment. The policy is report-only intentionally; enforcing CSP requires a
separate review of both the Next.js and FastAPI response paths.

### Manual release checks

- **Repeat:** play a queue, cycle repeat through all, one, and off, then confirm
  repeat-one restarts the current track, repeat-all advances from the last track
  to the first, and repeat-off stops at the end.
- **iOS lock screen:** start playback in Safari on an iPhone, lock the screen,
  and verify audio continues and lock-screen play/pause and track controls work.
- **Offline app shell:** load the Next.js app online, reload once so the
  service worker takes control, then disconnect and reload. The offline shell
  should open; account data, library API calls, audio/range requests, uploads,
  and online lyrics must not be served from the service-worker cache.
- **Rate-limited bulk upload:** upload a batch of at least 60 files and confirm
  rate-limited requests retry within their advertised delay, then either
  complete or report a visible failure without silently dropping files.

The mock-backed 60-file test verifies the frontend retry flow, not the live
backend's rate limits or persistence. Confirm upload behavior against FastAPI
with a prepared batch before release. The iOS lock-screen check still requires
a physical iPhone and Safari.

---

## Keyboard shortcuts

The shortcuts button is available on desktop and hidden on tablet and mobile layouts. A physical keyboard can still use these shortcuts on supported devices.

| Key | Does what |
|---|---|
| `Space` | Play / pause |
| `←` `→` | Seek back / forward |
| `Shift + ←` `→` | Previous / next track |
| `↑` `↓` | Volume up / down |
| `M` | Mute |
| `F` | Favorite the current track |
| `/` | Jump to search |
| `N` | Open mini player |
| `L` | Open lyrics |
| `V` | Open visualizer |
| `Esc` | Close whatever's open |
| `?` | Show this list in-app |

---

## What's next

Things I'd like to get to eventually:

- [x] Cloud deployment support (Supabase PostgreSQL + Render)
- [x] Multi-device sync
- [x] More metadata providers
- [x] Artist detail view and verified profile links
- [x] Responsive desktop, tablet, and mobile layouts
- [ ] Smarter playlists
- [ ] Better offline support
- [ ] Installable PWA
- [x] Wider format support
- [ ] Better library sorting/filtering
- [ ] Some way to share a library publicly

---

Vervfy's an ongoing side project, not a polished product. 
