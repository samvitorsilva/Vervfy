# Vervfy

A self-hosted music player for the web, built with a modern design that feels unique and user-friendly. 

Upload your own files, organize them into playlists, look up lyrics and artist bio, and listen through a player that doesn't feel like an afterthought.

---

## What it does

Vervfy is a small FastAPI backend paired with a vanilla JS frontend — no framework, no build step, just HTML, CSS, and JavaScript doing the work. The idea is simple: you own the files, you own the library, and the whole thing runs on your own machine (or server) if you want it to.

Here's roughly what's in there right now:

**Library**
Drag-and-drop uploads (whole folders, where the browser allows it), automatic metadata reading, album art extraction — and if a track has no cover, one gets generated so your library doesn't look empty. You can search, remove tracks, and stream everything straight from the backend.

**Player**
The basics you'd expect — play/pause, next/previous, seeking, volume, mute — plus a queue system with an "up next" view, shuffle and repeat, a mini player for when you want it out of the way, and keyboard shortcuts for everything (see below).

**Organization**
Favorite tracks, build playlists, and keep it all sorted per user. Libraries are kept fully separate between accounts.

**Lyrics**
This ended up being one of the more involved parts. Vervfy checks embedded ID3 lyrics first (plain and synced), then LRC files, then falls back to an online lookup through LRCLIB if nothing's found locally. Lyrics scroll in sync with playback and highlight the current line. If none of that turns anything up, you can just paste or type lyrics in yourself.

**Visualizer**
A Web Audio API–based visualizer that reacts to whatever's currently playing.

**Accounts**
Its own auth system — registration, login/logout, bcrypt-hashed passwords, session-based auth, CSRF protection, and basic login throttling so it's not trivial to brute-force. Every user gets their own isolated library.

**Artist info**
When available, Vervfy pulls in extra context about the artist you're listening to — bio, genre, mood, formation year, followers, label, that sort of thing — from public catalogs, and caches it so it's not hitting external APIs on every page load.

**As a web app**
It's built to feel like an app, not a website: responsive on both desktop and mobile, a mini player, offline-friendly bits via a service worker and IndexedDB, and full keyboard navigation.

---

## Stack

**Backend** — Python, FastAPI, Uvicorn, SQLAlchemy, PostgreSQL (Supabase), Alembic, bcrypt, Starlette sessions, Jinja2, python-multipart

**Audio/media** — Mutagen for metadata and ID3 handling, Pillow for artwork

**Frontend** — HTML5, CSS3, vanilla JS, Web Audio API, IndexedDB, Service Worker — no framework required

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
│   └── logo.jpeg
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

The website is https://vervfy-app.onrender.com.
Using the free Render service, so you might come across a 'starting application' page. 

```

---

## Persistent data and deployment

Vervfy stores accounts, bcrypt password hashes, tracks/audio, cover art,
custom lyrics, favorites, and playlists in PostgreSQL. `

---

## Keyboard shortcuts

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
- [ ] Smarter playlists
- [ ] Album/artist detail pages
- [ ] Better offline support
- [ ] Installable PWA
- [ ] Wider format support
- [ ] Better library sorting/filtering
- [ ] Some way to share a library publicly

---

Vervfy's an ongoing side project, not a polished product. 
