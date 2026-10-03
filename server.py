#!/usr/bin/env python3
"""Vervfy — music library and playback API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import asyncio
import functools
import hashlib
import logging
import mimetypes
import os
import re
import secrets
import time
import unicodedata
import uuid
from typing import Annotated
from urllib.parse import quote, urlsplit
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
import httpx
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool

from database import Base, engine
import audio_store
import auth
from db import Artist, Favorite, Playlist, PlaylistTrack, SessionLocal, TrackRecord, UploadJob, User, tenant_session
from library import Library, UploadQuotaExceeded, track_id_for_bytes
import upload_queue

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SECRET_KEY_PATH = DATA_DIR / ".secret_key"


def _load_or_create_secret_key() -> str:
    """Persist a random session-signing key across restarts.

    Prefers the VERVFY_SECRET_KEY env var (set this in production so the
    key isn't just a file sitting next to the app). Falls back to a
    generated key stored under data/ for local/dev use.
    """
    # Keep the old Auralis name as a migration path for existing deployments.
    # Render instances have ephemeral disks, so a stable environment key is
    # required or every redeploy invalidates all signed session cookies.
    env_key = os.environ.get("VERVFY_SECRET_KEY") or os.environ.get("AURALIS_SECRET_KEY")
    if env_key:
        return env_key
    if is_production:
        raise RuntimeError("VERVFY_SECRET_KEY is required in production")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_KEY_PATH.is_file():
        return SECRET_KEY_PATH.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    SECRET_KEY_PATH.write_text(key, encoding="utf-8")
    try:
        os.chmod(SECRET_KEY_PATH, 0o600)
    except OSError:
        pass
    return key


_enable_docs = os.environ.get("VERVFY_ENABLE_DOCS") == "1"
app = FastAPI(
    title="Vervfy",
    version="1.0",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
)


@app.on_event("shutdown")
def close_audio_store() -> None:
    audio_store.close_client()


# Provisional until startup reads the DB; must exist so /register never AttributeErrors
# if a request somehow arrives before the startup hook finishes.
app.state.is_first_account = True
environment = (
    os.environ.get("VERVFY_ENVIRONMENT")
    or os.environ.get("ENVIRONMENT", "development")
).lower()
is_production = environment in {"production", "prod"}
async_uploads = os.environ.get("VERVFY_ASYNC_UPLOADS") == "1"
https_only = (
    os.environ.get("VERVFY_HTTPS_ONLY")
    or os.environ.get("AURALIS_HTTPS_ONLY", "0")
) == "1"
if is_production and not https_only:
    raise RuntimeError("VERVFY_HTTPS_ONLY=1 is required in production")
if is_production and not os.environ.get("REDIS_URL"):
    raise RuntimeError("REDIS_URL is required in production for distributed rate limiting")
# For same-origin app hosting, lax is sufficient; only use the stricter None
# setting when explicitly needed.
configured_same_site = (
    os.environ.get("VERVFY_COOKIE_SAME_SITE")
    or os.environ.get("AURALIS_COOKIE_SAME_SITE", "lax")
).lower()
if configured_same_site not in {"lax", "strict", "none"}:
    configured_same_site = "lax"
if is_production and configured_same_site == "none" and not https_only:
    raise RuntimeError("SameSite=None requires HTTPS in production")
app.add_middleware(
    CORSMiddleware,
    # CORS only — never use this value as an auth redirect Location.
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:8000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

UPLOADS_PER_10MIN = int(os.environ.get("VERVFY_UPLOADS_PER_10MIN", "60"))
UPLOAD_CONCURRENCY = max(1, int(os.environ.get("VERVFY_UPLOAD_CONCURRENCY", "2")))
upload_processing_semaphore = asyncio.Semaphore(UPLOAD_CONCURRENCY)


def limit_upload_processing(handler):
    @functools.wraps(handler)
    async def limited(*args, **kwargs):
        async with upload_processing_semaphore:
            return await handler(*args, **kwargs)
    return limited


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        path = request.url.path
        if path.startswith("/api/"):
            is_upload = path == "/api/library/upload"
            limit, window = (UPLOADS_PER_10MIN, 10 * 60) if is_upload else (120, 60)
            identity = request.session.get("user_id") or auth.client_ip(request)
            key = f"api:{identity}:{path if is_upload else 'mutations'}"
            try:
                allowed = request_throttle.allow(key, limit, window)
            except RuntimeError:
                return JSONResponse({"detail": "Rate-limit service unavailable"}, status_code=503)
            if not allowed:
                return JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={"Retry-After": str(window)},
                )
        elif path in {"/login", "/register"}:
            try:
                allowed = request_throttle.allow(
                    f"auth:{auth.client_ip(request)}:{path}", 30, 15 * 60
                )
            except RuntimeError:
                return JSONResponse(
                    {"detail": "Rate-limit service unavailable"},
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            if not allowed:
                return JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={"Retry-After": "900", "Cache-Control": "no-store"},
                )
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault("Content-Security-Policy-Report-Only", CSP_REPORT_ONLY)
    if https_only:
        response.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
    return response


SESSION_SECRET = _load_or_create_secret_key()
app.state.session_secret = SESSION_SECRET
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="auralis_session",
    same_site=configured_same_site,
    https_only=https_only,
    max_age=60 * 60 * 24 * 30,  # 30 days
)

user_store = auth.UserStore()
request_throttle = auth.RequestThrottle(os.environ.get("REDIS_URL"))
login_throttle = auth.LoginThrottle(limiter=request_throttle)
signup_throttle = auth.SignupThrottle(limiter=request_throttle)
log = logging.getLogger("vervfy")
MAX_UPLOAD_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
USER_QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS_PER_USER = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))
MULTIPART_UPLOAD_OVERHEAD_BYTES = 1024 * 1024
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024
CSP_REPORT_ONLY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https://*.dzcdn.net; "
    "media-src 'self' blob:; "
    "connect-src 'self' https://lrclib.net; "
    "frame-ancestors 'none'"
)

_libraries: dict[str, Library] = {}
_artist_photo_cache: dict[str, tuple[float, dict | None]] = {}
_artist_photo_result_cache: dict[str, tuple[float, tuple[str | None, int | None]]] = {}
_artist_profile_cache: dict[str, tuple[float, dict[str, str] | None]] = {}
MAX_ARTIST_CACHE_ENTRIES = 1024


def _artist_search_key(name: str) -> str:
    """Normalize names before comparing a public catalog search result."""
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return "".join(c.lower() for c in normalized if c.isalnum())


def _cache_artist_result(cache, key: str, value, expires_at: float) -> None:
    now = time.monotonic()
    for cached_key, (expiry, _) in list(cache.items()):
        if expiry <= now:
            del cache[cached_key]
    if len(cache) >= MAX_ARTIST_CACHE_ENTRIES and key not in cache:
        del cache[min(cache, key=lambda item: cache[item][0])]
    cache[key] = (expires_at, value)


def _artist_name_candidates(name: str) -> list[str]:
    full_name = name.strip()
    if not full_name:
        return []
    has_list_sep = re.search(
        r"[,;/]|\bfeat(?:uring)?\.?\b|\bft\.?\b|\bwith\b",
        full_name,
        flags=re.IGNORECASE,
    )
    if has_list_sep:
        parts = re.split(
            r"\s*(?:,|;|/|\bfeat(?:uring)?\.?\b|\bft\.?\b|\bwith\b)\s*",
            full_name,
            flags=re.IGNORECASE,
        )
        parts = [
            piece
            for part in parts
            for piece in re.split(r"\s+(?:&|and)\s+", part, flags=re.IGNORECASE)
        ]
    else:
        parts = [full_name]

    candidates: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part.strip(" \t-–—·•")).strip()
        key = _artist_search_key(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            candidates.append(cleaned)
    return candidates


# These entries are deliberately small.  General music catalogs are useful for
# discovery, but an exact name match is not enough to establish an artist's
# identity (especially for short, stylised, or shared names).  Each profile
# below was checked against an authoritative, artist-specific source and is
# used before a catalog lookup. Do not add an entry without a source that
# unambiguously identifies the performer.
_VERIFIED_ARTIST_PROFILES: dict[str, dict[str, str]] = {
    "tatemcrae": {
        "bio": (
            "Tate McRae is a Canadian singer, songwriter, and dancer who first "
            "rose to prominence as a dancer before launching her music career."
        ),
        "genre": "Pop",
        "highlights": "Canadian singer, songwriter, and dancer.",
        "website": "https://www.tatemcrae.com/",
        "website_label": "Official artist website",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/Tate_McRae",
    },
    "morada": {
        "bio": (
            "MORADA is a Brazilian contemporary Christian band formed in 2009 "
            "in Fernandópolis, São Paulo."
        ),
        "genre": "Contemporary Christian music",
        "formed_year": "2009",
        "highlights": "Formed in Fernandópolis, São Paulo, in 2009.",
        "website": "https://www.youtube.com/watch?v=ePdRgBWhvog",
        "website_label": "Official music video",
        "source": "MORADA artist biography",
        "source_url": "https://jairproducoes.com.br/morada",
    },
    "marcosnui": {
        "bio": (
            "Marcos Nui is the artist behind the 2024 single Mi Tiempo and "
            "other Spanish-language releases."
        ),
        "highlights": "Released the single Mi Tiempo in 2024.",
        "website": "https://music.apple.com/us/artist/marcos-nui/1686270730",
        "website_label": "Artist profile",
        "source": "Marcos Nui artist profile",
        "source_url": "https://music.apple.com/us/artist/marcos-nui/1686270730",
    },
    "tommybueno": {
        "bio": (
            "Tommy Bueno is a Buenos Aires–based artist whose catalog includes "
            "the releases Visionario and Atmósfera."
        ),
        "highlights": "Catalog includes the releases Visionario and Atmósfera.",
        "website": "https://linktr.ee/tommybueno",
        "website_label": "Official artist page",
        "source": "Tommy Bueno official artist page",
        "source_url": "https://linktr.ee/tommybueno",
    },
    "visionofleo": {
        "bio": (
            "Vision of Leo is a Pop artist whose 2023 album Legacy of Faith "
            "was released through Vision of Leo Records."
        ),
        "genre": "Pop",
        "label": "Vision of Leo Records",
        "highlights": "Released the album Legacy of Faith in 2023 through Vision of Leo Records.",
        "website": "https://music.apple.com/us/artist/vision-of-leo/1461686609",
        "website_label": "Artist profile",
        "source": "Vision of Leo release page",
        "source_url": "https://music.apple.com/us/album/legacy-of-faith/1688293569",
    },
    "obros": {
        "bio": (
            "O'Bros are a German Christian hip-hop duo from Munich. Their "
            "music brings hip-hop together with Christian faith."
        ),
        "genre": "Christian hip-hop",
        "highlights": "Munich duo known for bringing hip-hop together with Christian faith.",
        "website": "https://obros.eu/presse/",
        "website_label": "Official artist site",
        "source": "O'Bros official artist site",
        "source_url": "https://obros.eu/presse/",
    },
    "kallysmashupcast": {
        "bio": (
            "KALLY'S Mashup Cast is the credited ensemble for music from "
            "Nickelodeon's KALLY'S Mashup television series."
        ),
        "highlights": "Credited ensemble for music from Nickelodeon's KALLY'S Mashup television series.",
        "website": "https://www.youtube.com/watch?v=SRQdCfYQJAU",
        "website_label": "Official music video",
        "source": "KALLY'S Mashup official artist channel",
        "source_url": "https://www.youtube.com/watch?v=SRQdCfYQJAU",
    },
    "viclucas": {
        "bio": (
            "Vic Lucas is an Afrobeat artist whose music draws on Nigerian, "
            "South African, and U.S. influences, with faith and gratitude at "
            "its core."
        ),
        "genre": "Afrobeat",
        "highlights": "Music blends Nigerian, South African, and U.S. influences.",
        "website": "https://www.viclucas.com/",
        "website_label": "Official artist site",
        "source": "Vic Lucas official artist site and artist profile",
        "source_url": "https://www.viclucas.com/",
    },
    "kaimalachi": {
        "bio": (
            "Kai Malachi is a cinematic gospel, soul, and alternative R&B "
            "project created, produced, and directed by Tim Vishnevskiy."
        ),
        "genre": "Cinematic gospel, soul, alternative R&B",
        "highlights": "A project created, produced, and directed by Tim Vishnevskiy.",
        "website": "https://kaimalachi.com/",
        "website_label": "Official artist site",
        "source": "Kai Malachi official artist site and artist profile",
        "source_url": "https://kaimalachi.com/",
    },
    "ajvitanza": {
        "bio": (
            "AJ Vitanza is a pop artist whose official site presents the "
            "nine-track debut EP Plastic Heart."
        ),
        "genre": "Pop",
        "highlights": "Released the nine-track debut EP Plastic Heart.",
        "website": "https://ajvitanza.com/",
        "website_label": "Official artist site",
        "source": "AJ Vitanza official artist site",
        "source_url": "https://ajvitanza.com/",
    },
    "mielsanmarcos": {
        "bio": (
            "Miel San Marcos is a Guatemalan Christian band founded in 2000 "
            "by brothers Josh, Luis, and Samy Morales."
        ),
        "genre": "Contemporary Christian music",
        "formed_year": "2000",
        "highlights": "Founded in 2000 by brothers Josh, Luis, and Samy Morales.",
        "website": "https://www.mielsanmarcos.org/artist",
        "website_label": "Official artist site",
        "source": "Miel San Marcos official artist site",
        "source_url": "https://www.mielsanmarcos.org/artist",
    },
    "braydentabakian": {
        "bio": (
            "Brayden Tabakian is a singer and drummer based in Missouri whose "
            "work includes Christian music."
        ),
        "genre": "Pop, Christian music",
        "highlights": "Performs as both a singer and drummer from Missouri.",
        "website": "https://open.spotify.com/artist/0wbQ4YBld5MzVAh9lTZlYy",
        "website_label": "Artist profile",
        "source": "Brayden Tabakian artist profile",
        "source_url": "https://open.spotify.com/artist/0wbQ4YBld5MzVAh9lTZlYy",
    },
    "josephobrien": {
        "bio": (
            "Joseph O'Brien is a Nashville-based singer-songwriter. He is a "
            "Gotee Records artist whose music aims to encourage listeners in "
            "their faith."
        ),
        "genre": "Christian music",
        "label": "Gotee Records",
        "highlights": "Nashville-based singer-songwriter and a Gotee Records artist.",
        "website": "https://www.josephobrienmusic.com/",
        "website_label": "Official artist site",
        "source": "Joseph O'Brien official artist site",
        "source_url": "https://www.josephobrienmusic.com/",
    },
    "stringsheart": {
        "bio": (
            "Strings & Heart is an indie Christian band of three brothers: "
            "Angelo, Michael, and Eric Espinosa."
        ),
        "genre": "Indie Christian",
        "highlights": "Three-brother band: Angelo, Michael, and Eric Espinosa.",
        "website": "https://www.stringsandheart.com/",
        "website_label": "Official artist site",
        "source": "Strings & Heart official artist site",
        "source_url": "https://www.stringsandheart.com/",
    },
    "gio": {
        "bio": (
            "gio. is a Christian pop and hip-hop artist from the outskirts of "
            "Boston. His music is shaped by early exposure to gospel and poetry, "
            "and he aims to bring a modern, creative approach to Christian music."
        ),
        "genre": "Christian pop, hip-hop",
        "highlights": "Brings gospel and poetry influences to a modern Christian pop and hip-hop sound.",
        "website": "https://www.wassupgio.com/about/",
        "website_label": "Official artist site",
        "source": "gio. official artist site",
        "source_url": "https://www.wassupgio.com/about/",
    },
    "kodoku": {
        "bio": (
            "Kodoku is the recording artist behind releases including “Rose Bath,” "
            '“DEVOTED” with Sam Rivera, and “WATERWALKIN” featuring Hulvey.'
        ),
        "highlights": "Notable releases include Rose Bath, DEVOTED with Sam Rivera, and WATERWALKIN featuring Hulvey.",
        "website": "https://open.spotify.com/artist/2mDygmvuNzsZhLvMfEUfmu",
        "website_label": "Spotify artist profile",
        "source": "Kodoku Spotify artist profile",
        "source_url": "https://open.spotify.com/artist/2mDygmvuNzsZhLvMfEUfmu",
    },
    "ruayoung": {
        "bio": (
            "RUA YOUNG is a Christian recording artist whose catalog includes "
            "God Did, Say The Word, I’M GOD’S, and ADONAI."
        ),
        "genre": "Christian",
        "highlights": (
            "Recent releases include God Did (Remix Pack), Say The Word, "
            "I’M GOD’S, Designer, and ADONAI."
        ),
        "website": "https://music.apple.com/us/artist/rua-young/1782603897",
        "website_label": "Apple Music artist profile",
        "source": "RUA YOUNG Apple Music artist profile",
        "source_url": "https://music.apple.com/us/artist/rua-young/1782603897",
    },
}


def _verified_artist_profile(name: str) -> dict[str, str] | None:
    """Return an identity-checked profile for an artist credit, if available."""
    for candidate in _artist_name_candidates(name):
        profile = _VERIFIED_ARTIST_PROFILES.get(_artist_search_key(candidate))
        if profile:
            result = profile.copy()
            if candidate != name.strip():
                result["lookup_name"] = candidate
            return result
    return None


# The British rapper Dave (Santan Dave) shares his stage name with unrelated
# artists. This Deezer portrait is tied to artist ID 11256100, whose catalog
# includes Psychodrama, Split Decision, and The Boy Who Played the Harp.
_DAVE_DEEZER_PHOTO = (
    "https://cdn-images.dzcdn.net/images/artist/"
    "eb2c8952b7328fdf32b3546d5ffab8c2/500x500-000000-80-0-0.jpg"
)
_VERIFIED_ARTIST_PHOTOS = {
    "dave": _DAVE_DEEZER_PHOTO,
    "davesantan": _DAVE_DEEZER_PHOTO,
    "santandave": _DAVE_DEEZER_PHOTO,
}


def _matching_catalog_artist(
    results: list[dict], candidates: list[str], name_field: str
) -> tuple[dict | None, str | None]:
    for candidate in candidates:
        key = _artist_search_key(candidate)
        for result in results:
            if _artist_search_key(str(result.get(name_field, ""))) == key:
                return result, candidate
    return None, None


def _deezer_artist_for_name(name: str) -> dict | None:
    key = _artist_search_key(name)
    if not key:
        return None
    now = time.monotonic()
    cached = _artist_photo_cache.get(key)
    if cached and cached[0] > now:
        return cached[1]

    artist: dict | None = None
    candidates = _artist_name_candidates(name) or [name.strip()]
    try:
        with httpx.Client(timeout=4.0) as client:
            for candidate in candidates:
                response = client.get(
                    "https://api.deezer.com/search/artist",
                    params={"q": candidate, "limit": 10},
                    headers={"User-Agent": "Vervfy/1.0"},
                )
                response.raise_for_status()
                results = response.json().get("data", [])
                artist, _ = _matching_catalog_artist(results, [candidate], "name")
                if artist:
                    break
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        log.warning("Deezer artist lookup failed for %r: %s", name, exc)
    _cache_artist_result(
        _artist_photo_cache, key, artist, now + (60 * 60 * 24 if artist else 10 * 60)
    )
    return artist


def _deezer_artist_has_library_title(artist: dict, titles: list[str]) -> bool:
    title_keys = {_artist_track_title_key(title) for title in titles if title.strip()}
    artist_id = artist.get("id")
    if not artist_id or not title_keys:
        return False
    try:
        with httpx.Client(timeout=3.0, headers={"User-Agent": "Vervfy/1.0"}) as client:
            try:
                top = client.get(
                    f"https://api.deezer.com/artist/{artist_id}/top",
                    params={"limit": 100},
                )
                top.raise_for_status()
                tracks = top.json().get("data", [])
                if any(_artist_track_title_key(str(track.get("title", ""))) in title_keys for track in tracks):
                    return True
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                log.warning("Deezer top-track check failed for artist %r: %s", artist.get("name"), exc)

            albums_response = client.get(
                f"https://api.deezer.com/artist/{artist_id}/albums",
                params={"limit": 50},
            )
            albums_response.raise_for_status()
            albums = albums_response.json().get("data", [])
            for album in albums:
                if _artist_track_title_key(str(album.get("title", ""))) in title_keys:
                    return True
            # Cap album crawls — top + album titles cover most library matches.
            for album in albums[:5]:
                album_id = album.get("id")
                if not album_id:
                    continue
                try:
                    response = client.get(
                        f"https://api.deezer.com/album/{album_id}/tracks",
                        params={"limit": 100},
                    )
                    response.raise_for_status()
                    tracks = response.json().get("data", [])
                    if any(_artist_track_title_key(str(track.get("title", ""))) in title_keys for track in tracks):
                        return True
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    log.warning("Deezer album-track check failed for artist %r: %s", artist.get("name"), exc)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        log.warning("Deezer catalog verification failed for artist %r: %s", artist.get("name"), exc)
    return False


def _artist_track_title_key(title: str) -> str:
    cleaned = re.sub(
        r"\s*[\[(]\s*(?:feat(?:uring)?\.?|ft\.?)\s+[^\])]*[\])]", "", title, flags=re.I
    )
    cleaned = re.sub(r"\s+(?:feat(?:uring)?\.?|ft\.?)\s+.+$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*[\[(]\s*explicit\s*[\])]", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\s*[-–—]\s*(?:\d{4}\s+)?remaster(?:ed)?(?:\s+\d{4})?\s*$",
        "", cleaned, flags=re.I,
    )
    return _artist_search_key(cleaned)


def _verified_deezer_artist(name: str, titles: list[str]) -> dict | None:
    """Exact Deezer name match for any credit variant, proven by library titles."""
    candidate_keys = {
        _artist_search_key(candidate) for candidate in _artist_name_candidates(name)
    }
    artist = _deezer_artist_for_name(name)
    if not artist:
        return None
    if _artist_search_key(str(artist.get("name", ""))) not in candidate_keys:
        return None
    return artist if _deezer_artist_has_library_title(artist, titles) else None


def _deezer_portrait_url(artist: dict) -> str | None:
    # Prefer mid-size portraits: artist cards/detail avatars are ~112–256px.
    photo = (
        artist.get("picture_medium")
        or artist.get("picture_big")
        or artist.get("picture_xl")
        or artist.get("picture")
    )
    try:
        host = urlsplit(photo).hostname if isinstance(photo, str) else None
    except ValueError:
        host = None
    if (
        not isinstance(photo, str)
        or not photo.startswith("https://")
        or not host
        or not (host == "dzcdn.net" or host.endswith(".dzcdn.net"))
        or "/images/artist//" in photo
    ):
        return None
    return photo


def _artist_photo_result_key(name: str, titles: list[str]) -> str:
    key = _artist_search_key(name)
    title_keys = sorted(
        {_artist_track_title_key(title) for title in titles if title.strip()}
    )[:40]
    return f"{key}|{'|'.join(title_keys)}"


def _lookup_artist_photo(name: str, titles: list[str]) -> tuple[str | None, int | None]:
    """Return a Deezer portrait only after matching this user's catalog titles."""
    for candidate_name in _artist_name_candidates(name):
        verified_photo = _VERIFIED_ARTIST_PHOTOS.get(_artist_search_key(candidate_name))
        if verified_photo:
            # Hardcoded portraits are already trusted — skip live Deezer verification.
            return verified_photo, None

    cache_key = _artist_photo_result_key(name, titles)
    now = time.monotonic()
    cached = _artist_photo_result_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    artist = _verified_deezer_artist(name, titles)
    if not artist:
        result: tuple[str | None, int | None] = (None, None)
        _cache_artist_result(_artist_photo_result_cache, cache_key, result, now + 10 * 60)
        return result
    photo = _deezer_portrait_url(artist)
    fans = artist.get("nb_fan")
    result = (photo, fans if isinstance(fans, int) else None)
    _cache_artist_result(
        _artist_photo_result_cache,
        cache_key,
        result,
        now + (60 * 60 * 24 if photo else 10 * 60),
    )
    return result


_WIKI_TITLE_QUALIFIER = re.compile(
    r"\s*\((?:singer(?:-songwriter)?|rapper|band|musician|group|dj|composer|"
    r"vocalist|music(?:al)?\s+group|recording\s+artist)\)\s*$",
    re.I,
)
_MUSIC_PERSON_HINT = re.compile(
    r"\b(?:music(?:al|ian|ians)?|singer(?:-songwriter)?s?|songwriters?|"
    r"rappers?|bands?|groups?|vocalists?|composers?|djs?|producers?|"
    r"orchestras?|ensembles?|recording\s+artists?|hip[\s-]?hop|"
    r"r&b|rhythm\s+and\s+blues|pop\s+stars?|rock\s+bands?)\b",
    re.I,
)


def _wiki_title_matches(title: str, name: str) -> bool:
    strip = lambda value: _WIKI_TITLE_QUALIFIER.sub("", value).strip()
    return _artist_search_key(strip(title)) == _artist_search_key(strip(name))


def _first_sentences(value: object, limit: int = 3) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return " ".join(re.split(r"(?<=[.!?])\s+", text)[:limit])


def _wikipedia_summary_to_profile(summary: dict, name: str) -> dict[str, str] | None:
    if summary.get("type") != "standard":
        return None
    if not _wiki_title_matches(str(summary.get("title", "")), name):
        return None
    description = str(summary.get("description", ""))
    extract = str(summary.get("extract", ""))
    if not _MUSIC_PERSON_HINT.search(f"{description} {extract}"):
        return None
    bio = _first_sentences(extract)
    if not bio:
        return None
    return {
        "bio": bio,
        "source": "Wikipedia",
        "source_url": (
            summary.get("content_urls", {})
            .get("desktop", {})
            .get("page", "")
        ),
    }


def _fetch_wikipedia_artist_profile(client: httpx.Client, name: str) -> dict[str, str] | None:
    """Direct summary first, then a title-constrained Wikipedia search."""
    try:
        response = client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(name, safe='')}"
        )
        if response.status_code == 200:
            profile = _wikipedia_summary_to_profile(response.json(), name)
            if profile:
                return profile
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        log.warning("Wikipedia summary lookup failed for %r: %s", name, exc)

    try:
        search = client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": name,
                "srlimit": 5,
                "format": "json",
            },
        )
        search.raise_for_status()
        hits = search.json().get("query", {}).get("search", [])
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        log.warning("Wikipedia search failed for %r: %s", name, exc)
        return None

    for hit in hits:
        title = str(hit.get("title", "")).strip()
        if not title or not _wiki_title_matches(title, name):
            continue
        try:
            response = client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}"
            )
            response.raise_for_status()
            profile = _wikipedia_summary_to_profile(response.json(), name)
            if profile:
                return profile
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("Wikipedia search-hit summary failed for %r: %s", title, exc)
    return None


def _lookup_artist_profile(name: str, titles: list[str]) -> dict[str, str] | None:
    """Return an exact-name Wikipedia biography and verified Deezer audience information."""
    manual = _verified_artist_profile(name)
    if manual:
        return manual
    key = _artist_search_key(name)
    if not key:
        return None
    artist = _verified_deezer_artist(name, titles) if titles else None
    now = time.monotonic()
    cached = _artist_profile_cache.get(key)
    if cached and cached[0] > now:
        profile = cached[1].copy() if cached[1] else {}
    else:
        profile = {}
        try:
            with httpx.Client(
                timeout=6.0,
                headers={"User-Agent": "Vervfy/1.0 (artist profile lookup)"},
                follow_redirects=True,
            ) as client:
                profile = _fetch_wikipedia_artist_profile(client, name) or {}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("Wikipedia artist lookup failed for %r: %s", name, exc)
        _cache_artist_result(
            _artist_profile_cache, key, profile or None,
            now + (60 * 60 * 24 if profile else 10 * 60),
        )
    fans = artist.get("nb_fan") if artist else None
    if isinstance(fans, int):
        profile["followers"] = str(fans)
    return profile or None


def get_library(user_id: str) -> Library:
    """One lightweight, PostgreSQL-backed library facade per account."""
    lib = _libraries.get(user_id)
    if lib is None:
        lib = Library(user_id)
        _libraries[user_id] = lib
    return lib


def current_user_row(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    row = user_store.get_by_id(user_id)
    if row is None:
        return None
    if request.session.get("sv", 0) != row["session_version"]:
        request.session.clear()
        return None
    return row


def require_api_user(request: Request):
    """For JSON API routes: a clean 401 the frontend can react to."""
    row = current_user_row(request)
    if row is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return row


def _track_payload(track) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration": track.duration,
        "custom_lyrics": track.custom_lyrics,
        "has_cover": track.has_cover,
        "cover_url": f"/api/tracks/{track.id}/cover",
        "stream_url": f"/api/tracks/{track.id}/stream",
    }


@app.on_event("startup")
def startup() -> None:
    if is_production:
        if "VERVFY_TRUSTED_PROXY_HOPS" not in os.environ:
            log.warning(
                "VERVFY_TRUSTED_PROXY_HOPS is unset in production; rate limits may use the proxy IP"
            )
        app.state.is_first_account = user_store.count() == 0
        return
    # create_all does not add columns to an existing deployment. Keep older
    # databases usable while Alembic catches up on the next deployment.
    from sqlalchemy import inspect, text

    Base.metadata.create_all(engine)
    existing_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "photo_data" not in existing_columns:
            photo_type = "BYTEA" if engine.dialect.name == "postgresql" else "BLOB"
            connection.execute(text(f"ALTER TABLE users ADD COLUMN photo_data {photo_type}"))
        if "photo_mime" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN photo_mime VARCHAR(64)"))
        if "session_version" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0"))
        if "email_verified" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        if "pending_email" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN pending_email VARCHAR(320)"))
        existing_track_columns = {column["name"] for column in inspect(engine).get_columns("tracks")}
        if "size_bytes" not in existing_track_columns:
            connection.execute(text("ALTER TABLE tracks ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0"))
        if "storage_path" not in existing_track_columns:
            connection.execute(text("ALTER TABLE tracks ADD COLUMN storage_path VARCHAR(600)"))
        existing_playlist_columns = {column["name"] for column in inspect(engine).get_columns("playlists")}
        if "position" not in existing_playlist_columns:
            connection.execute(text("ALTER TABLE playlists ADD COLUMN position INTEGER NOT NULL DEFAULT 0"))
        if engine.dialect.name == "postgresql":
            audio_data_col = next(
                (c for c in inspect(engine).get_columns("tracks") if c["name"] == "audio_data"),
                None,
            )
            if audio_data_col is not None and not audio_data_col.get("nullable", True):
                # Audio moved to Supabase Storage, so the blob column may now be empty.
                connection.execute(text("ALTER TABLE tracks ALTER COLUMN audio_data DROP NOT NULL"))
            connection.execute(text(
                "UPDATE tracks SET size_bytes = length(audio_data) WHERE size_bytes = 0 AND audio_data IS NOT NULL"
            ))
    app.state.is_first_account = user_store.count() == 0


# ------------------------------------------------------------------ accounts

@app.post("/login")
def login_submit(
    request: Request,
    identifier: str = Form(..., alias="username"),
    password: str = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    auth.verify_csrf(request, csrf_token)
    ip = auth.client_ip(request)
    identifier = identifier.strip()

    def fail(message: str, status_code: int = 400) -> JSONResponse:
        return JSONResponse(
            {"detail": message},
            status_code=status_code,
            headers={"Cache-Control": "no-store"},
        )

    try:
        if login_throttle.is_locked(ip, identifier):
            return fail("Too many attempts. Please wait a few minutes and try again.")
    except RuntimeError:
        return fail("Service temporarily unavailable, try again shortly", status_code=503)

    row = user_store.get_by_username(identifier)
    password_matches = (
        auth.verify_password(password, row["password_hash"])
        if row is not None
        else auth.verify_password(password, auth._DUMMY_HASH)
    )
    if row is None or not password_matches:
        try:
            login_throttle.record_failure(ip, identifier)
        except RuntimeError:
            return fail("Service temporarily unavailable, try again shortly", status_code=503)
        return fail("Incorrect username or password")

    try:
        login_throttle.clear(ip, identifier)
    except RuntimeError:
        return fail("Service temporarily unavailable, try again shortly", status_code=503)
    request.session.clear()
    request.session["user_id"] = row["id"]
    request.session["sv"] = row["session_version"]
    return RedirectResponse("/", status_code=303)


@app.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(""),
    csrf_token: str = Form(...),
) -> Response:
    auth.verify_csrf(request, csrf_token)

    def fail(message: str, status_code: int = 400) -> JSONResponse:
        return JSONResponse(
            {"detail": message},
            status_code=status_code,
            headers={"Cache-Control": "no-store"},
        )

    username_error = auth.validate_username(username)
    if username_error:
        return fail(username_error)
    if email.strip():
        email_error = auth.validate_email(email.strip())
        if email_error:
            return fail(email_error)
    password_error = auth.validate_password(password)
    if password_error:
        return fail(password_error)
    ip = auth.client_ip(request)
    if signup_throttle.is_limited(ip):
        return fail("Too many sign-ups from this network. Try again later.", status_code=429)

    try:
        new_user = user_store.create_user(username, email or None, password)
    except ValueError as exc:
        return fail(str(exc))

    signup_throttle.record_success(ip)
    request.app.state.is_first_account = False

    request.session.clear()
    request.session["user_id"] = new_user["id"]
    request.session["sv"] = 0
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request, csrf_token: str | None = Form(None)) -> Response:
    submitted_token = csrf_token or request.headers.get("x-csrf-token", "")
    # Logging out is safe to repeat.  A stale page may submit an old token
    # after another login/logout cycle; avoid surfacing a CSRF error when the
    # desired outcome is simply to end the current session.
    try:
        auth.verify_csrf(request, submitted_token)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
    # A copied cookie stays valid after a plain logout until the password
    # changes or logout-all is used.
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/api/me")
def api_me(user=Depends(require_api_user)) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "created_at": user["created_at"],
        "photo_url": (
            f"/api/account/photo?v={int(user['created_at'])}"
            if user_store.has_profile_photo(user["id"])
            else None
        ),
        "track_count": get_library(user["id"]).count_tracks(),
    }


@app.get("/api/account/photo")
def account_photo(user=Depends(require_api_user)) -> Response:
    photo_data, photo_mime = user_store.get_profile_photo(user["id"])
    if not photo_data or not photo_mime:
        raise HTTPException(status_code=404, detail="No profile photo")
    return Response(
        content=photo_data,
        media_type=photo_mime,
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/account/photo")
async def upload_account_photo(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(require_api_user),
) -> dict:
    auth.verify_api_csrf(request)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Choose an image file")
    photo_data = await file.read(MAX_PROFILE_PHOTO_BYTES + 1)
    if len(photo_data) > MAX_PROFILE_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Profile photo must be 5 MB or smaller")
    photo_mime = await run_in_threadpool(_validate_profile_photo, photo_data)
    await run_in_threadpool(user_store.update_profile_photo, user["id"], photo_data, photo_mime)
    return {"photo_url": "/api/account/photo"}


def _validate_profile_photo(photo_data: bytes) -> str:
    try:
        with Image.open(BytesIO(photo_data)) as image:
            image.verify()
            image_format = (image.format or "").upper()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="That file is not a valid image") from None
    allowed_formats = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
    }
    photo_mime = allowed_formats.get(image_format)
    if not photo_mime:
        raise HTTPException(status_code=400, detail="Use a JPEG, PNG, WebP, or GIF image")
    return photo_mime


@app.delete("/api/account/photo")
def delete_account_photo(request: Request, user=Depends(require_api_user)) -> dict:
    auth.verify_api_csrf(request)
    user_store.update_profile_photo(user["id"], None, None)
    return {"photo_url": None}


@app.get("/api/csrf")
def api_csrf(request: Request) -> Response:
    """Issue the session-bound token used by login and authenticated API calls."""
    return JSONResponse(
        {"csrf_token": auth.get_or_create_csrf_token(request)},
        headers={"Cache-Control": "no-store"},
    )


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class EmailChangeRequest(BaseModel):
    email: str = Field(max_length=320)
    current_password: str


class AccountDeletionRequest(BaseModel):
    current_password: str
    confirmation: str


class TrackLyricsRequest(BaseModel):
    lyrics: str = Field(..., min_length=1, max_length=200_000)


SafeId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class PlaylistState(BaseModel):
    id: SafeId
    name: str = Field(min_length=1, max_length=200)
    trackIds: list[SafeId] = Field(default_factory=list, max_length=10_000)


class LibraryStateRequest(BaseModel):
    favorites: list[SafeId] = Field(default_factory=list, max_length=10_000)
    playlists: list[PlaylistState] = Field(default_factory=list, max_length=1_000)


def _queue_staged_upload(job_id: str, user_id: str, filename: str, data: bytearray) -> None:
    suffix = os.path.splitext(os.path.basename(filename))[1].lower()
    staging_path = f"{user_id}/.staging/{job_id}{suffix}"
    try:
        audio_store.upload(staging_path, data, audio_store.guess_content_type(filename))
        with tenant_session(user_id) as session:
            session.add(UploadJob(
                id=job_id,
                user_id=user_id,
                filename=filename,
                storage_path=staging_path,
                created_at=time.time(),
            ))
            session.commit()
        upload_queue.enqueue(job_id, user_id)
    except Exception as exc:
        try:
            with tenant_session(user_id) as session:
                job = session.get(UploadJob, job_id)
                if job:
                    job.status = "failed"
                    job.error = "Upload could not be added to the processing queue."
                    session.commit()
        except Exception:
            log.exception("could not mark staged upload as failed")
        audio_store.delete_quietly(staging_path)
        log.exception("could not queue upload")
        raise HTTPException(status_code=503, detail="Upload queue is unavailable") from exc


def _upload_preflight(library: Library, data: bytearray) -> tuple[str, int, int, bool]:
    track_id = track_id_for_bytes(data)
    if library.get(track_id) is not None:
        return track_id, 0, 0, True
    return track_id, library.total_bytes(), library.count_tracks(), False


def _library_state_from_session(user_id: str, session) -> dict:
    favorites = session.scalars(select(Favorite.track_id).where(Favorite.user_id == user_id)).all()
    playlists = session.scalars(
        select(Playlist)
        .options(selectinload(Playlist.tracks))
        .where(Playlist.user_id == user_id)
        .order_by(Playlist.position, Playlist.id)
    ).all()
    return {"favorites": favorites, "playlists": [
        {"id": playlist.id, "name": playlist.name,
         "trackIds": [item.track_id for item in playlist.tracks]}
        for playlist in playlists
    ]}


def _library_state(user_id: str) -> dict:
    with tenant_session(user_id) as session:
        return _library_state_from_session(user_id, session)


def _library_state_etag(state: dict) -> str:
    canonical = {
        "favorites": sorted(state["favorites"]),
        "playlists": state["playlists"],
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f'"{digest}"'


class RangeNotSatisfiable(ValueError):
    """A syntactically valid byte range that has no bytes in the resource."""


def _parse_range_header(range_header: str, size: int) -> tuple[int, int] | None:
    """Return one requested byte range, or None when the header is malformed."""
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[6:].strip()
    if not spec or "," in spec:
        return None
    match = re.fullmatch(r"(\d*)-(\d*)", spec)
    if match is None:
        return None
    start_str, end_str = match.groups()
    if not start_str and not end_str:
        return None
    if not start_str:
        suffix = int(end_str)
        if suffix <= 0 or size <= 0:
            raise RangeNotSatisfiable
        return max(0, size - suffix), size - 1
    start = int(start_str)
    if start >= size:
        raise RangeNotSatisfiable
    end = int(end_str) if end_str else size - 1
    end = min(end, size - 1)
    if end < start:
        raise RangeNotSatisfiable
    return start, end


def _content_disposition_filename(filename: str) -> str:
    """Keep uploaded names safe when placed in a response header."""
    ascii_name = os.path.basename(filename).encode("ascii", "ignore").decode("ascii")
    return re.sub(r'[\r\n"\\]', "_", ascii_name) or "audio"


def verify_current_password(user: User, password: str) -> None:
    """Verify a sensitive account action without allowing password guessing."""
    matches = auth.verify_password(password, user.password_hash)
    key = f"current-password:{user.id}"
    try:
        if matches:
            request_throttle.discard(key)
        elif not request_throttle.allow(key, 10, 15 * 60):
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect current-password attempts. Try again later.",
                headers={"Retry-After": "900"},
            )
    except RuntimeError:
        raise HTTPException(
            status_code=503, detail="Rate-limit service unavailable"
        ) from None
    if not matches:
        raise HTTPException(status_code=400, detail="Current password is incorrect")


@app.put("/api/account/email")
def change_account_email(
    payload: EmailChangeRequest,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    verify_current_password(user, payload.current_password)
    email = payload.email.strip().lower()
    if email:
        error = auth.validate_email(email)
        if error:
            raise HTTPException(status_code=400, detail=error)
    try:
        user_store.update_email(user["id"], email or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"email": email or None}


@app.post("/api/account/password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    verify_current_password(user, payload.current_password)
    error = auth.validate_password(payload.new_password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    user_store.update_password(user["id"], auth.hash_password(payload.new_password))
    request.session["sv"] = user_store.bump_session_version(user["id"])
    return {"ok": True}


@app.post("/api/account/logout-all")
def logout_all(
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    user_store.bump_session_version(user["id"])
    request.session.clear()
    return {"ok": True}


@app.delete("/api/account")
def delete_account(
    payload: AccountDeletionRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    """Permanently delete the signed-in account after explicit confirmation."""
    if payload.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail='Type DELETE to confirm account deletion')
    verify_current_password(user, payload.current_password)
    storage_paths = get_library(user["id"]).storage_paths()
    user_store.delete_user(user["id"])
    audio_store.delete_many_quietly(storage_paths)
    _libraries.pop(user["id"], None)
    request.session.clear()
    request.app.state.is_first_account = user_store.count() == 0
    return {"ok": True}


@app.get("/api/health")
def health(user=Depends(require_api_user)) -> dict:
    return {"ok": True, "tracks": get_library(user["id"]).count_tracks()}


@app.get("/api/library/state")
def get_library_state(response: Response, user=Depends(require_api_user)) -> dict:
    """Server-backed favorites and playlists, shared across browsers/redeploys."""
    state = _library_state(user["id"])
    response.headers["ETag"] = _library_state_etag(state)
    return state


@app.get("/api/library/usage")
def get_library_usage(user=Depends(require_api_user)) -> dict:
    library = get_library(user["id"])
    return {
        "used_bytes": library.total_bytes(),
        "quota_bytes": USER_QUOTA_BYTES,
        "track_count": library.count_tracks(),
        "max_tracks": MAX_TRACKS_PER_USER,
    }


@app.put("/api/library/state")
def save_library_state(
    payload: LibraryStateRequest,
    request: Request,
    response: Response,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    if_match = request.headers.get("if-match")
    if not if_match:
        raise HTTPException(status_code=428, detail="If-Match is required")
    # Accept only tracks belonging to this account; this prevents cross-account
    # playlist references and cleans stale browser IndexedDB entries safely.
    with tenant_session(user["id"]) as session:
        session.scalar(
            select(User.id).where(User.id == user["id"]).with_for_update()
        )
        current_etag = _library_state_etag(_library_state_from_session(user["id"], session))
        if if_match != current_etag:
            raise HTTPException(
                status_code=409,
                detail="Library state changed; reload before saving",
                headers={"ETag": current_etag},
            )
        valid_ids = set(session.scalars(select(TrackRecord.id).where(TrackRecord.user_id == user["id"])).all())
        favorite_ids = list(dict.fromkeys(track_id for track_id in payload.favorites if track_id in valid_ids))
        session.query(Favorite).filter_by(user_id=user["id"]).delete()
        session.add_all(Favorite(user_id=user["id"], track_id=track_id) for track_id in favorite_ids)
        existing = {playlist.id: playlist for playlist in session.scalars(select(Playlist).where(Playlist.user_id == user["id"])).all()}
        requested = set()
        for position, item in enumerate(payload.playlists):
            if item.id in requested:
                continue
            requested.add(item.id)
            name = item.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="Playlist name cannot be empty")
            playlist = existing.pop(item.id, None)
            if playlist is None:
                playlist = Playlist(id=item.id, user_id=user["id"], name=name, position=position)
                session.add(playlist)
            else:
                playlist.name = name
                playlist.position = position
                playlist.tracks.clear()
            ids = list(dict.fromkeys(track_id for track_id in item.trackIds if track_id in valid_ids))
            playlist.tracks = [PlaylistTrack(track_id=track_id, position=index) for index, track_id in enumerate(ids)]
        for playlist in existing.values():
            session.delete(playlist)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Playlist id is already in use; please try again") from exc
        state = _library_state_from_session(user["id"], session)
    response.headers["ETag"] = _library_state_etag(state)
    return state


def _library_titles_for_artist(user_id: str, name: str) -> list[str]:
    """Titles in this user's own library credited to `name` (used to prove identity).

    Derived server-side so identity checks never depend on what the browser sends,
    which also keeps older cached clients working.
    """
    key = _artist_search_key(name)
    if not key:
        return []
    titles: list[str] = []
    for track in get_library(user_id).list_tracks():
        credit = getattr(track, "artist", "") or ""
        names = _artist_name_candidates(credit)
        title = getattr(track, "title", "") or ""
        featured = re.search(r"\b(?:feat(?:uring)?\.?|ft\.?|with)\s+(.+)$", title, re.I)
        if featured:
            featured_names = re.sub(r"[\])].*$", "", featured.group(1)).strip()
            names.extend(_artist_name_candidates(featured_names))
        if key in {_artist_search_key(artist) for artist in names}:
            if title:
                titles.append(title)
        if len(titles) >= 40:
            break
    return titles


def _throttle_artist_lookup(user_id: str) -> None:
    try:
        allowed = request_throttle.allow(f"artist-lookup:{user_id}", 240, 60)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Rate-limit service unavailable") from exc
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many artist lookups", headers={"Retry-After": "60"})


def _deezer_error_is_quota(error: object) -> bool:
    if not isinstance(error, dict):
        return False
    code = str(error.get("code", "")).lower()
    error_type = str(error.get("type", "")).lower()
    message = str(error.get("message", "")).lower()
    return code in {"4", "quota"} or "quota" in error_type or "quota" in message


def _fetch_deezer_artist(name: str) -> dict:
    try:
        with httpx.Client(timeout=6.0, headers={"User-Agent": "Vervfy/1.0"}) as client:
            for attempt in range(2):
                response = client.get(
                    "https://api.deezer.com/search/artist",
                    params={"q": name, "limit": 10},
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise HTTPException(status_code=502, detail="Invalid artist provider response")
                error = payload.get("error")
                if error is not None:
                    if attempt == 0 and _deezer_error_is_quota(error):
                        time.sleep(1)
                        continue
                    raise HTTPException(status_code=502, detail="Artist provider lookup failed")
                results = payload.get("data")
                if not isinstance(results, list):
                    raise HTTPException(status_code=502, detail="Invalid artist provider response")
                artist = next(
                    (
                        result
                        for result in results
                        if isinstance(result, dict)
                        and _artist_search_key(str(result.get("name", "")))
                        == _artist_search_key(name)
                    ),
                    results[0] if results else None,
                )
                if not isinstance(artist, dict) or not isinstance(artist.get("id"), int):
                    raise HTTPException(status_code=404, detail="Artist not found")
                return artist
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        log.warning("Deezer artist lookup failed for %r: %s", name, exc)
        raise HTTPException(status_code=502, detail="Artist provider lookup failed") from exc
    raise HTTPException(status_code=502, detail="Artist provider lookup failed")


@app.get("/artists/{name}")
def get_artist(name: str, user=Depends(require_api_user)) -> dict:
    """Return cached artist data, refreshing it from Deezer every 30 days."""
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 200:
        raise HTTPException(status_code=422, detail="Artist name must be 1 to 200 characters")
    _throttle_artist_lookup(user["id"])
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        artist = next(
            (
                cached
                for cached in session.scalars(select(Artist)).all()
                if _artist_search_key(cached.name) == _artist_search_key(normalized_name)
            ),
            None,
        )
        if artist and artist.fetched_at:
            fetched_at = artist.fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if now - fetched_at < timedelta(days=30):
                return {
                    "deezer_id": artist.deezer_id,
                    "name": artist.name,
                    "picture": artist.picture,
                    "fans": artist.fans,
                    "url": f"https://www.deezer.com/artist/{artist.deezer_id}",
                    "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(),
                }

        result = _fetch_deezer_artist(normalized_name)
        deezer_id = result["id"]
        if artist and artist.deezer_id != deezer_id:
            session.delete(artist)
            session.flush()
        artist = session.get(Artist, deezer_id)
        if artist is None:
            artist = Artist(deezer_id=deezer_id, name=str(result.get("name") or normalized_name))
            session.add(artist)
        artist.name = str(result.get("name") or normalized_name)
        artist.picture = _deezer_portrait_url(result)
        artist.fans = result.get("nb_fan") if isinstance(result.get("nb_fan"), int) else None
        artist.fetched_at = now
        session.commit()
        return {
            "deezer_id": artist.deezer_id,
            "name": artist.name,
            "picture": artist.picture,
            "fans": artist.fans,
            "url": f"https://www.deezer.com/artist/{artist.deezer_id}",
            "fetched_at": artist.fetched_at.astimezone(timezone.utc).isoformat(),
        }


@app.get("/api/artists/photo")
def artist_photo(
    name: str = Query(min_length=1, max_length=200),
    user=Depends(require_api_user),
) -> dict:
    """Find a verified portrait from this user's own artist catalog."""
    _throttle_artist_lookup(user["id"])
    own = _library_titles_for_artist(user["id"], name.strip())
    picture, fans = _lookup_artist_photo(name.strip(), own)
    return {"picture": picture, "nb_fan": fans}


@app.get("/api/artists/profile")
def artist_profile(
    name: str = Query(min_length=1, max_length=200),
    user=Depends(require_api_user),
) -> dict:
    """Return public artist metadata for the detail page, when available."""
    _throttle_artist_lookup(user["id"])
    own = _library_titles_for_artist(user["id"], name.strip())
    return {"profile": _lookup_artist_profile(name.strip(), own)}


@app.get("/api/tracks")
def list_tracks(user=Depends(require_api_user)) -> dict:
    library = get_library(user["id"])
    return {"tracks": [_track_payload(t) for t in library.list_tracks()]}


@app.post("/api/library/upload")
@limit_upload_processing
async def upload_track(
    request: Request, file: UploadFile = File(...), user=Depends(require_api_user), _csrf=Depends(auth.verify_api_csrf)
) -> dict:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES + MULTIPART_UPLOAD_OVERHEAD_BYTES:
                raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid upload size") from None
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    buffer = bytearray()
    total_bytes = 0
    while part := await file.read(1024 * 1024):
        total_bytes += len(part)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
        buffer.extend(part)
    if not buffer:
        raise HTTPException(status_code=400, detail="Empty upload")
    library = get_library(user["id"])
    if async_uploads:
        job_id = uuid.uuid4().hex
        await run_in_threadpool(_queue_staged_upload, job_id, user["id"], file.filename, buffer)
        return {"id": job_id, "status": "processing"}
    track_id, used_bytes, track_count, existing = await run_in_threadpool(
        _upload_preflight, library, buffer
    )
    if not existing:
        if used_bytes + len(buffer) > USER_QUOTA_BYTES or track_count >= MAX_TRACKS_PER_USER:
            used_mb = used_bytes / (1024 * 1024)
            quota_mb = USER_QUOTA_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"Storage quota reached ({used_mb:.1f} MB of {quota_mb:.1f} MB used)",
            )
    try:
        track = await run_in_threadpool(
            library.add_upload,
            file.filename,
            buffer,
            quota_bytes=USER_QUOTA_BYTES,
            max_tracks=MAX_TRACKS_PER_USER,
        )
    except UploadQuotaExceeded:
        used_bytes = await run_in_threadpool(library.total_bytes)
        used_mb = used_bytes / (1024 * 1024)
        quota_mb = USER_QUOTA_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Storage quota reached ({used_mb:.1f} MB of {quota_mb:.1f} MB used)",
        ) from None
    except audio_store.StorageError as exc:
        log.exception("audio storage failed during upload")
        raise HTTPException(status_code=502, detail=f"Audio storage error: {str(exc)[:200]}") from None
    if track is None:
        raise HTTPException(status_code=400, detail="Could not read uploaded audio file")
    return _track_payload(track)


@app.get("/api/library/upload/{job_id}")
def upload_status(job_id: str, user=Depends(require_api_user)) -> dict:
    with tenant_session(user["id"]) as session:
        job = session.scalar(select(UploadJob).where(
            UploadJob.id == job_id,
            UploadJob.user_id == user["id"],
        ))
        if not job:
            raise HTTPException(status_code=404, detail="Upload job not found")
        payload = {
            "id": job.id,
            "status": job.status,
            "error": job.error,
            "attempts": job.attempts,
        }
        if job.track_id:
            payload["track_id"] = job.track_id
            track = get_library(user["id"]).get(job.track_id)
            if track:
                payload["track"] = _track_payload(track)
        return payload


@app.delete("/api/tracks/{track_id}")
def delete_track(
    track_id: str, user=Depends(require_api_user), _csrf=Depends(auth.verify_api_csrf)
) -> dict:
    library = get_library(user["id"])
    if not library.remove(track_id):
        raise HTTPException(status_code=404, detail="Track not found")
    return {"removed": track_id}


@app.put("/api/tracks/{track_id}/lyrics")
def save_track_lyrics(
    track_id: str,
    payload: TrackLyricsRequest,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    lyrics = payload.lyrics.strip()
    if not lyrics:
        raise HTTPException(status_code=400, detail="Lyrics cannot be empty")
    track = get_library(user["id"]).set_custom_lyrics(track_id, lyrics)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return {"custom_lyrics": track.custom_lyrics}


@app.get("/api/tracks/{track_id}/cover")
def track_cover(
    track_id: str, size: int = Query(default=512, ge=64, le=1024), user=Depends(require_api_user)
) -> Response:
    library = get_library(user["id"])
    if library.get(track_id) is None:
        raise HTTPException(status_code=404, detail="Track not found")
    payload = library.cover_jpeg(track_id, size)
    return Response(
        content=payload,
        media_type="image/jpeg",
        headers={
            # Covers are user-uploaded private media, so shared caches must not
            # store or replay them across accounts. The browser may keep the
            # account-scoped URL warm because track covers are immutable until
            # the track is replaced.
            "Cache-Control": "private, max-age=86400, immutable",
            "Content-Length": str(len(payload)),
        },
    )


@app.get("/api/tracks/{track_id}/stream")
def track_stream(request: Request, track_id: str, user=Depends(require_api_user)) -> Response:
    library = get_library(user["id"])
    info = library.audio_info(track_id)
    if info is None or not info.size_bytes:
        raise HTTPException(status_code=404, detail="Track not found")
    filename, size, storage_path = info.filename, info.size_bytes, info.storage_path

    media_type = "audio/webm" if filename.lower().endswith(".weba") else mimetypes.guess_type(filename)[0] or "audio/mpeg"
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": (
            f'inline; filename="{_content_disposition_filename(filename)}"; '
            f"filename*=UTF-8''{quote(os.path.basename(filename), safe='')}"
        ),
        "Cache-Control": "private, max-age=3600",
    }
    range_header = request.headers.get("range")
    if range_header:
        try:
            range_match = _parse_range_header(range_header, size)
        except RangeNotSatisfiable:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"})
        if range_match is None:
            start, end, status_code = 0, size - 1, 200
        else:
            start, end = range_match
            status_code = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    else:
        start, end, status_code = 0, size - 1, 200
    headers["Content-Length"] = str(end - start + 1)

    if storage_path:
        # Relay only the requested byte range from Supabase Storage.
        try:
            _, upstream = audio_store.open_range(storage_path, start, end)
        except audio_store.StorageError:
            log.exception("audio storage read failed for %s", track_id)
            raise HTTPException(status_code=502, detail="Audio storage is unavailable") from None

        def body():
            try:
                remaining = end - start + 1
                skip = start if upstream.status_code == 200 else 0
                for chunk in upstream.iter_bytes(64 * 1024):
                    if skip:
                        skipped = min(skip, len(chunk))
                        chunk = chunk[skipped:]
                        skip -= skipped
                    if not chunk:
                        continue
                    chunk = chunk[:remaining]
                    if chunk:
                        yield chunk
                        remaining -= len(chunk)
                    if remaining == 0:
                        break
            finally:
                upstream.close()

        return StreamingResponse(body(), status_code=status_code, media_type=media_type, headers=headers)

    # Legacy track whose audio is still in Postgres: fetch just the slice.
    payload = library.read_range(track_id, start, end) or b""
    headers["Content-Length"] = str(len(payload))
    return Response(content=payload, status_code=status_code, media_type=media_type, headers=headers)


@app.get("/api/tracks/{track_id}/tag-head")
def track_tag_head(track_id: str, user=Depends(require_api_user)) -> Response:
    """Return the start of the audio file so the client can parse embedded ID3.

    Lyrics (SYLT/USLT) and the MPEG frame header used for frame-count timestamps
    both live near the start of the file. Serving just that prefix lets the UI
    reuse its existing ID3 parser without downloading the whole track.
    """
    library = get_library(user["id"])
    info = library.audio_info(track_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Track not found")
    initial_bytes = min(info.size_bytes, 256 * 1024) if info.storage_path else 256 * 1024
    try:
        data = library.read_range(track_id, 0, initial_bytes - 1, info=info) if initial_bytes else b""
        if data and len(data) >= 10 and data[:3] == b"ID3":
            tag_size = sum(
                (data[index] & 0x7F) << shift
                for index, shift in zip(range(6, 10), (21, 14, 7, 0))
            )
            tag_bytes = 10 + tag_size
            if tag_bytes > 32 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Embedded metadata tag is too large")
            if tag_bytes > len(data):
                end = min(tag_bytes, info.size_bytes) - 1 if info.storage_path else tag_bytes - 1
                remainder = library.read_range(track_id, len(data), end, info=info)
                data += remainder or b""
            else:
                data = data[:tag_bytes]
        elif data:
            data = data[:10]
    except audio_store.StorageError:
        log.exception("audio storage read failed for %s", track_id)
        raise HTTPException(status_code=502, detail="Audio storage is unavailable") from None
    return Response(
        content=data or b"",
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Length": str(len(data or b"")),
        },
    )
