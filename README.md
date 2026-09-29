# Vervfy

A self-hosted music player for the web, built with a modern design that feels unique and user-friendly. 

Upload your own files, organize them into playlists, look up lyrics and artist bio, and listen through a player that doesn't feel like an afterthought.

---

## What it does

Vervfy is a small FastAPI backend paired with a vanilla JS frontend — no framework, no build step, just HTML, CSS, and JavaScript doing the work. 

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
Its own auth system — registration, login/logout, verified-email password recovery, account email management, bcrypt-hashed passwords, session-based auth, CSRF protection, and rate limiting. Every user gets their own isolated library.

**Artist info**
Artist biographies and portraits are shown only for names with manually verified artist-specific sources. Vervfy does not guess from name-only catalog searches; when an identity cannot be verified, it keeps the library artwork and shows no artist claims. Artist details never block music playback or library browsing.

**As a web app**
It's built to feel like an app, not a website: responsive on desktop, tablet, and mobile, a mini player, account-backed sync, and full keyboard navigation. The keyboard-shortcuts button is hidden on touch-sized layouts, while physical keyboards still work. Audio and online lyrics require an active connection.

---

## Stack

**Backend** — Python, FastAPI, Uvicorn, SQLAlchemy, PostgreSQL (Supabase), Alembic, bcrypt, Starlette sessions, Jinja2, python-multipart

**Audio/media** — Mutagen for metadata and ID3 handling, Pillow for artwork

**Frontend** — HTML5, CSS3, vanilla JS, Web Audio API, IndexedDB — no framework required

---

## Project layout

```text
vervfy/
├── auth.py            # accounts, sessions, CSRF, throttling
├── library.py         # tracks, metadata, artwork, lyrics storage
├── server.py           # the FastAPI app itself — routes, streaming, uploads
├── requirements.txt
│
├── static/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── auth.css
│   ├── sw.js
│   └── gemini-svg.svg
│
├── templates/
│   ├── login.html
│   └── register.html
│
├── data/
│
└── README.md
```

---

## Hosted app

Vervfy is deployed globally at https://vervfy-app.onrender.com. The free Render
service may show a starting page while it wakes.

---

## Persistent data and deployment

Vervfy stores accounts, bcrypt password hashes, profile photos, tracks/audio,
cover art, custom lyrics, favorites, and playlists in PostgreSQL. Profile
photos are limited to 5 MB and can be JPEG, PNG, WebP, or GIF. Session cookies
are signed with `VERVFY_SECRET_KEY` in production, `VERVFY_HTTPS_ONLY=1`
enables secure-only cookies behind HTTPS, and `VERVFY_COOKIE_SAME_SITE`
controls the cookie SameSite policy (`lax` by default).
Password recovery and email verification require SMTP settings:
`VERVFY_PUBLIC_URL` (the canonical HTTPS app origin),
`VERVFY_SMTP_HOST`, `VERVFY_SMTP_PORT` (587 with STARTTLS, or 465 with
implicit TLS), `VERVFY_EMAIL_FROM`, and, when required by your provider,
`VERVFY_SMTP_USERNAME` and `VERVFY_SMTP_PASSWORD`. Password reset is available
only after the account email has been verified. Existing and registration-time
email addresses must be verified from the account profile before they can be
used for recovery.
Apply database changes before deploying with `alembic upgrade head`.
Set `VERVFY_TRUSTED_PROXY_HOPS=1` on Render so rate limits use each visitor's
forwarded IP instead of the shared proxy address. Uploads are limited to 60
per user per 10-minute window by default; adjust this with
`VERVFY_UPLOADS_PER_10MIN`.
For Supabase, use the PostgreSQL transaction-pooler connection URL when
connecting through PgBouncer; Vervfy disables psycopg prepared statements for
PostgreSQL URLs to remain compatible with transaction pooling.

Tenant-scoped database work uses an explicit SQLAlchemy session carrying the
authenticated user ID; PostgreSQL applies it transaction-locally for row-level
security. It does not depend on request context being copied across threadpool
calls.

To run the PostgreSQL RLS integration test, set `VERVFY_TEST_POSTGRES_URL` to
a dedicated PostgreSQL test database URL using a role that is neither a
superuser nor `BYPASSRLS`, then run:

```sh
pytest -q tests/test_tenant_isolation_postgres.py
```

The test creates and drops a uniquely named schema in that database. The rest
of the suite does not require PostgreSQL.

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