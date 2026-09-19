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
Its own auth system — registration, login/logout, bcrypt-hashed passwords, session-based auth, CSRF protection, and basic login throttling so it's not trivial to brute-force. Every user gets their own isolated library.

**Artist info**
When available, Vervfy pulls in extra context about the artist you're listening to — bio, genre, mood, formation year, followers, label, that sort of thing — from public catalogs, and caches it so it's not hitting external APIs on every page load. Artists have a dedicated detail view with photos and profile links when verified data is available.

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
├── start.sh
├── stop.sh
├── open_app.sh
├── install_launcher.sh
└── README.md
```

---

## Getting it open

For local use, run `./start.sh`; it creates the virtual environment, installs dependencies, starts the server, and opens `http://127.0.0.1:8765`. Set `DATABASE_URL` before starting, using a PostgreSQL connection string for deployment. The hosted app is https://vervfy-app.onrender.com; the free Render service may show a starting page while it wakes.

---

## Persistent data and deployment

Vervfy stores accounts, bcrypt password hashes, tracks/audio, cover art,
custom lyrics, favorites, and playlists in PostgreSQL. Session cookies are signed with `VERVFY_SECRET_KEY` in production, `VERVFY_HTTPS_ONLY=1` enables secure-only cookies behind HTTPS, and `VERVFY_COOKIE_SAME_SITE` controls the cookie SameSite policy (`lax` by default).

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