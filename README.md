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
Its own auth system — registration, username-and-password login, logout, optional account email, account password changes, bcrypt-hashed passwords, session-based auth, CSRF protection, and rate limiting. Email is account information only and is not used for sign-in or password recovery. Every user gets their own isolated library.

**Artist info**
Artist profiles prefer manually checked entries, then use an exact Deezer artist match tied to a title in the user's library before fetching a matching Wikipedia summary. Portraits use the same catalog/title verification, with a manually verified portrait for the ambiguous artist Dave. The profile shows its source, and artist lookup failures leave the library usable.

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
photos are limited to 5 MB and can be JPEG, PNG, WebP, or GIF. 

### Deploying on Render

Set `VERVFY_PUBLIC_URL` to the public HTTPS URL of the service. Run database
migrations before starting the web process: `alembic upgrade head` must finish
successfully before `uvicorn` starts. When Render terminates TLS in front of
the application, start Uvicorn with `--proxy-headers --forwarded-allow-ips='*'`
so forwarded HTTPS headers are trusted.

Vervfy sends a `Content-Security-Policy-Report-Only` header. Check the browser
console for violations after deployment, then change it to an enforcing
`Content-Security-Policy` header when the policy is confirmed to be complete.

### Manual release checks

- **Repeat:** play a queue, cycle repeat through all, one, and off, then confirm
  repeat-one restarts the current track, repeat-all advances from the last track
  to the first, and repeat-off stops at the end.
- **iOS lock screen:** start playback in Safari on an iPhone, lock the screen,
  and verify audio continues and lock-screen play/pause and track controls work.
- **Offline app shell:** load the app once, disconnect the device, and verify
  the cached shell still opens. Confirm audio playback and online lyrics remain
  unavailable while offline.
- **Rate-limited bulk upload:** upload a batch of at least 60 files and confirm
  rate-limited requests retry within their advertised delay, then either
  complete or report a visible failure without silently dropping files.

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
