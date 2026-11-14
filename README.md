# Vervfy

A personal music library for the web, built with a modern design that feels unique and user-friendly.

Upload your music, organize playlists and favorites, and find lyrics and artist details alongside your collection.

---

## What it does

Vervfy is a personal music library with a Next.js App Router frontend in
`web/` and a FastAPI backend for authentication, library data, uploads, and
audio streaming. Next.js is the only user-facing frontend.

Here's roughly what's in there:

**Library**
Drag-and-drop uploads (whole folders, where the browser allows it), metadata and embedded artwork read only from your audio files, user-uploaded cover replacements, and generated placeholders when a file has no art. Uploads matching an existing track's normalized title and artist and within two seconds of its duration are skipped, even when album tags differ. Track details come from the file tags, with filename parsing as a fallback. Supported formats include MP3, M4A/MP4, AAC, FLAC, OGG/OGA, Opus, WAV, and WebM audio.

The interface supports English, Brazilian Portuguese, Spanish and French. It follows the browser language by default, and users can choose a language on the sign-in screen or in account settings.

**Playback**
The basics you'd expect — play/pause, next/previous, seeking, volume, mute — plus a queue system with an "up next" view, shuffle and repeat, a mini player for when you want it out of the way, system media controls where supported, and keyboard shortcuts for everything (see below). Playback supports authenticated byte-range seeking.

**Organization**
Favorite tracks, build playlists, and keep it all sorted per user. Libraries are kept fully separate between accounts.

**Lyrics**
Vervfy checks embedded ID3 lyrics first (plain and synced), then can look up lyrics through LRCLIB. Fetched lyrics are cached only in the browser for three days; they are not saved to the account. Custom lyrics can be pasted or typed in and are saved to the account.

**Visualizer**
A Web Audio API–based visualizer that reacts to whatever's currently playing.

**Accounts**
Its own auth system — registration, username-and-password login, logout, optional account email, account password changes, secure email-based password recovery, bcrypt-hashed passwords, session-based auth, CSRF protection, and rate limiting. Email is optional and is not used for sign-in. Recovery verifies an unverified password-account email before sending a separate one-time reset link; Google-only accounts cannot use password recovery. A reset updates the password and invalidates existing sessions without automatically signing in. Every user gets their own isolated library.

Password recovery uses Redis for expiring single-use tokens and the existing SMTP environment settings for email. SMTP and a public `FRONTEND_URL` are required to send recovery messages in production; without SMTP, the endpoint still returns a generic response but sends no email. See [docs/password-reset.md](docs/password-reset.md) for configuration and a staging checklist.

**Artist info**
Artist profiles use manually maintained entries or a matching Wikipedia summary. Wikipedia-derived text links to its article and the CC BY-SA 4.0 license, with shortened or adapted text identified. Artist cards and profiles prefer a photo you upload, then an eligible Wikimedia Commons image with on-screen attribution, then a locally generated avatar. Commons images are copied to Vervfy storage only after license and metadata checks; Vervfy does not hotlink them. 

**As a web app**
It's built to feel like an app, not a website: responsive on desktop, tablet, and mobile, a mini player, account-backed sync, and full keyboard navigation. The keyboard-shortcuts button is hidden on touch-sized layouts, while physical keyboards still work. The service worker caches the app shell and offline fallback, not streamed audio or library data. Tracks explicitly downloaded in a browser can be played offline from that browser's local storage; unsaved tracks, library/account requests, and online lyrics require a connection.

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
├── render.yaml        # Render services for Redis, FastAPI, and Next.js
├── data/
│
└── README.md
```

---

## Hosted app

The FastAPI backend is deployed at
https://vervfy.onrender.com. The Next.js frontend is a separate Render web
service (defined in `render.yaml`) and proxies browser API requests to that
backend.

---

## Persistent data and deployment

PostgreSQL stores accounts, bcrypt password hashes, profile photos, artist
photos, track metadata, cover art, custom lyrics, favorites, and playlists.
New uploads use the private Supabase Storage bucket; audio is redirected to a
one-hour signed URL, so the FastAPI service never relays the audio bytes.

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
- [ ] Broader offline application support
- [x] Offline app shell (service worker and manifest)
- [x] Wider format support
- [ ] Better library sorting/filtering
- [ ] Some way to share a library publicly

---

Vervfy's an ongoing side project, not a polished product. 
