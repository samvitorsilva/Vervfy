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
Drag-and-drop uploads (whole folders, where the browser allows it), metadata and embedded artwork read only from your audio files, user-uploaded cover replacements, and generated placeholders when a file has no art. Track details come from the file tags, with filename parsing as a fallback. Supported formats include MP3, M4A/MP4, AAC, FLAC, OGG/OGA, Opus, WAV, and WebM audio.

The interface supports English and Brazilian Portuguese. It follows the browser language by default, and users can choose a language on the sign-in screen or in account settings.

**Player**
The basics you'd expect — play/pause, next/previous, seeking, volume, mute — plus a queue system with an "up next" view, shuffle and repeat, a mini player for when you want it out of the way, system media controls where supported, and keyboard shortcuts for everything (see below). Playback supports authenticated byte-range seeking.

**Organization**
Favorite tracks, build playlists, and keep it all sorted per user. Libraries are kept fully separate between accounts.

**Lyrics**
Vervfy checks embedded ID3 lyrics first (plain and synced), then can look up lyrics through LRCLIB. Fetched lyrics are cached only in the browser for three days; they are not saved to the account. Set `LYRICS_PROVIDER_LRCLIB=0` to disable external lookups. Custom lyrics can be pasted or typed in and are saved to the account.

**Visualizer**
A Web Audio API–based visualizer that reacts to whatever's currently playing.

**Accounts**
Its own auth system — registration, username-and-password login, logout, optional account email, account password changes, bcrypt-hashed passwords, session-based auth, CSRF protection, and rate limiting. Email is account information only and is not used for sign-in or password recovery. Every user gets their own isolated library.

**Artist info**
Artist profiles use manually maintained entries or a matching Wikipedia summary. Wikipedia-derived text links to its article and the CC BY-SA 4.0 license, with shortened or adapted text identified. Artist avatars are generated locally from each name; no artist photos or follower counts are fetched.

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
├── library.py         # tracks, file-tag metadata, user artwork, lyrics storage
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

PostgreSQL stores accounts, bcrypt password hashes, profile photos, track
metadata, cover art, custom lyrics, favorites, and playlists. Legacy audio may
remain in `tracks.audio_data`; new uploads use the private Supabase Storage
bucket configured by `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and
`SUPABASE_BUCKET`. Production startup fails if Storage credentials are absent.
Use a dedicated PostgreSQL `app_runtime` role without `BYPASSRLS` for the
application's `DATABASE_URL`; run Alembic migrations separately before deploy.
Profile photos are limited to 5 MB and can be JPEG, PNG, WebP, or GIF.

Before applying an Alembic migration to a live database, create and verify a
`pg_dump` backup. The cover-source migration labels existing covers `unknown`;
after deploying it, `scripts/rebuild_covers.py` can recover embedded art from
stored audio and replace other old covers with placeholders. It is a dry run by
default; review its summary, then pass `--apply` to write changes. The script
processes one track at a time and never overwrites a user-uploaded cover.

The public `/credits` page lists external data sources and attribution.

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
- [x] User-owned artwork and file-tag metadata
- [x] Artist detail view and attributed profile links
- [x] Responsive desktop, tablet, and mobile layouts
- [ ] Smarter playlists
- [ ] Better offline support
- [ ] Installable PWA
- [x] Wider format support
- [ ] Better library sorting/filtering
- [ ] Some way to share a library publicly

---

Vervfy's an ongoing side project, not a polished product. 
