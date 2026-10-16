#!/usr/bin/env python3
"""Vervfy — music library and playback API."""

from __future__ import annotations

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
import tempfile
import unicodedata
import uuid
from typing import Annotated, Literal
from urllib.parse import quote, urlparse
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool

from database import Base, engine
import audio_store
import auth
from cover_art import schedule_cover_resolution
from artist_images import (
    TheAudioDBQueue,
    artists_from_credit,
    is_stale as artist_image_is_stale,
    normalize_artist_name,
)
from db import ArtistImage, ArtistPhoto, Favorite, Playlist, PlaylistTrack, SessionLocal, TrackRecord, UploadJob, User, tenant_session
from library import AudioUnavailableError, Library, UploadQuotaExceeded, track_id_for_file
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
            is_upload = path == "/api/library/upload" or (
                request.method == "PUT"
                and (path.endswith("/cover") or path == "/api/artists/photo")
            )
            limit, window = (UPLOADS_PER_10MIN, 10 * 60) if is_upload else (120, 60)
            identity = request.session.get("user_id") or auth.client_ip(request)
            throttle_path = (
                "/api/library/upload" if is_upload else "mutations"
            )
            key = f"api:{identity}:{throttle_path}"
            try:
                allowed = await run_in_threadpool(
                    request_throttle.allow, key, limit, window
                )
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
                allowed = await run_in_threadpool(
                    request_throttle.allow,
                    f"auth:{auth.client_ip(request)}:{path}",
                    30,
                    15 * 60,
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
audiodb_queue = TheAudioDBQueue(request_throttle.allow)
login_throttle = auth.LoginThrottle(limiter=request_throttle)
signup_throttle = auth.SignupThrottle(limiter=request_throttle)
session_store = auth.SessionStore(os.environ.get("REDIS_URL"))
log = logging.getLogger("vervfy")
MAX_UPLOAD_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
USER_QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS_PER_USER = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))
MULTIPART_UPLOAD_OVERHEAD_BYTES = 1024 * 1024
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024
MAX_TRACK_COVER_BYTES = 5 * 1024 * 1024
MAX_TRACK_COVER_DIMENSION = 8192
MAX_TRACK_COVER_PIXELS = 12_000_000
MAX_ARTIST_PHOTO_BYTES = 5 * 1024 * 1024
MAX_ARTIST_PHOTO_DIMENSION = 800
MAX_ARTIST_PROFILE_CACHE_ENTRIES = 1024
CSP_REPORT_ONLY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https://*.theaudiodb.com https://theaudiodb.com "
        "https://coverartarchive.org https://*.archive.org https://archive.org https://*.supabase.co; "
        "media-src 'self' blob:; "
        "connect-src 'self' https://lrclib.net; "
        "frame-ancestors 'none'"
)

_libraries: dict[str, Library] = {}
_artist_profile_cache: dict[str, tuple[float, dict[str, str] | None]] = {}


def _artist_search_key(name: str) -> str:
    """Normalize artist credits for manual profiles and Wikipedia matching."""
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    # Stylized credits: A$AP↔ASAP, Florence + The Machine↔Florence and the Machine.
    normalized = normalized.replace("$", "s")
    normalized = re.sub(r"(?<=[A-Za-z])!(?=[A-Za-z])", "i", normalized)
    normalized = re.sub(r"\s*[&+]\s*", " and ", normalized)
    return "".join(c.lower() for c in normalized if c.isalnum())


def _cache_artist_result(cache, key: str, value, expires_at: float) -> None:
    now = time.monotonic()
    for cached_key, (expiry, _) in list(cache.items()):
        if expiry <= now:
            del cache[cached_key]
    if len(cache) >= MAX_ARTIST_PROFILE_CACHE_ENTRIES and key not in cache:
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


# These entries are manually maintained profiles with artist-specific sources.
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
    "thekidlaroi": {
        "bio": (
            "The Kid LAROI (Charlton Howard) is an Australian singer, rapper, "
            "and songwriter whose single “Stay” became an international hit."
        ),
        "genre": "Pop, hip-hop",
        "highlights": "Australian singer, rapper, and songwriter; known internationally for “Stay.”",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/The_Kid_Laroi",
    },
    "shawnmendes": {
        "bio": (
            "Shawn Mendes is a Canadian singer and songwriter who first built "
            "an audience by sharing song covers online before releasing his "
            "debut EP in 2014."
        ),
        "genre": "Pop",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/Shawn_Mendes",
    },
    "maroon5": {
        "bio": (
            "Maroon 5 is an American pop-rock band formed in Los Angeles. "
            "The group began as Kara’s Flowers before adopting the Maroon 5 "
            "name and breaking through with Songs About Jane."
        ),
        "genre": "Pop rock",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/Maroon_5",
    },
    "theneighborhood": {
        "bio": (
            "The Neighbourhood is an American alternative-rock band formed "
            "in California in 2011. The group is known for songs including "
            "“Sweater Weather” and “Daddy Issues.”"
        ),
        "genre": "Alternative rock",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/The_Neighbourhood",
    },
    "theneighbourhood": {
        "bio": (
            "The Neighbourhood is an American alternative-rock band formed "
            "in California in 2011. The group is known for songs including "
            "“Sweater Weather” and “Daddy Issues.”"
        ),
        "genre": "Alternative rock",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/The_Neighbourhood",
    },
}


_VERIFIED_ARTIST_PROFILES_PT: dict[str, dict[str, str]] = {
    "tatemcrae": {
        "bio": "A canadense Tate McRae é cantora, compositora e dançarina. Ela ficou conhecida primeiro pela dança e, depois, construiu carreira na música.",
        "genre": "Pop",
    },
    "morada": {
        "bio": "A banda MORADA, de Fernandópolis (SP), foi formada em 2009 e faz música cristã contemporânea.",
        "genre": "Música cristã contemporânea",
        "source": "Biografia do MORADA",
    },
    "tommybueno": {
        "bio": "Tommy Bueno é um artista de Buenos Aires. Entre seus lançamentos estão “Visionario” e “Atmósfera”.",
        "source": "Página oficial de Tommy Bueno",
    },
    "obros": {
        "bio": "A dupla alemã O'Bros é de Munique e mistura hip-hop com temas de fé cristã em suas músicas.",
        "genre": "Hip-hop cristão",
        "highlights": "Dupla de Munique que mistura hip-hop e fé cristã.",
    },
    "kallysmashupcast": {
        "bio": "KALLY'S Mashup Cast é o grupo responsável pelas músicas da série de TV “KALLY'S Mashup”, da Nickelodeon.",
    },
    "viclucas": {
        "bio": "Vic Lucas é um artista de afrobeat que mistura influências da Nigéria, da África do Sul e dos Estados Unidos. Fé e gratidão também estão no centro de sua música.",
    },
    "kaimalachi": {
        "bio": "Kai Malachi é um projeto de gospel com sonoridade cinematográfica, soul e R&B alternativo, criado, produzido e dirigido por Tim Vishnevskiy.",
        "genre": "Gospel cinematográfico, soul e R&B alternativo",
    },
    "ajvitanza": {
        "bio": "AJ Vitanza é um artista pop. Seu EP de estreia, “Plastic Heart”, tem nove faixas.",
    },
    "mielsanmarcos": {
        "bio": "Miel San Marcos é uma banda cristã guatemalteca, formada em 2000 pelos irmãos Josh, Luis e Samy Morales.",
        "genre": "Música cristã contemporânea",
    },
    "josephobrien": {
        "bio": "Joseph O'Brien é um cantor e compositor de Nashville e faz parte do selo Gotee Records. Sua música busca inspirar a fé de quem ouve.",
        "genre": "Música cristã",
        "highlights": "Cantor e compositor de Nashville, integrante do selo Gotee Records.",
    },
    "stringsheart": {
        "bio": "Strings & Heart é uma banda cristã independente formada por três irmãos: Angelo, Michael e Eric Espinosa.",
        "genre": "Indie cristão",
        "highlights": "Banda formada pelos irmãos Angelo, Michael e Eric Espinosa.",
    },
    "gio": {
        "bio": "gio. é um artista de pop cristão e hip-hop da região de Boston. Influenciado pelo gospel e pela poesia desde cedo, ele busca trazer uma abordagem moderna e criativa à música cristã.",
        "genre": "Pop cristão e hip-hop",
    },
    "thekidlaroi": {
        "bio": "The Kid LAROI (Charlton Howard) é um cantor, rapper e compositor australiano. Seu single “Stay” fez sucesso no mundo todo.",
        "genre": "Pop e hip-hop",
    },
    "shawnmendes": {
        "bio": "Shawn Mendes é um cantor e compositor canadense. Ele conquistou seu público compartilhando versões de músicas na internet, antes de lançar seu primeiro EP em 2014.",
        "genre": "Pop",
    },
    "maroon5": {
        "bio": "Maroon 5 é uma banda americana de pop rock formada em Los Angeles. Antes de adotar esse nome e fazer sucesso com “Songs About Jane”, o grupo se chamava Kara’s Flowers.",
        "genre": "Pop rock",
    },
    "theneighborhood": {
        "bio": "The Neighbourhood é uma banda americana de rock alternativo, formada na Califórnia em 2011. Entre suas músicas mais conhecidas estão “Sweater Weather” e “Daddy Issues”.",
        "genre": "Rock alternativo",
    },
    "theneighbourhood": {
        "bio": "The Neighbourhood é uma banda americana de rock alternativo, formada na Califórnia em 2011. Entre suas músicas mais conhecidas estão “Sweater Weather” e “Daddy Issues”.",
        "genre": "Rock alternativo",
    },
}


def _verified_artist_profile(
    name: str, language: Literal["en", "pt-BR"] = "en"
) -> dict[str, str] | None:
    """Return an identity-checked profile for an artist credit, if available."""
    for candidate in _artist_name_candidates(name):
        key = _artist_search_key(candidate)
        profile_key = key
        profile = _VERIFIED_ARTIST_PROFILES.get(key)
        if profile is None and key == "stringsandheart":
            profile_key = "stringsheart"
            profile = _VERIFIED_ARTIST_PROFILES[profile_key]
        if profile:
            result = profile.copy()
            if language == "pt-BR":
                result.update(_VERIFIED_ARTIST_PROFILES_PT.get(profile_key, {}))
                if result.get("source") == "Wikipedia":
                    result["source"] = "Wikipédia"
            if candidate != name.strip():
                result["lookup_name"] = candidate
            return result
    return None


_WIKI_TITLE_QUALIFIER = re.compile(
    r"\s*\((?:singer(?:-songwriter)?|rapper|band|musician|group|dj|composer|"
    r"vocalist|music(?:al)?\s+group|recording\s+artist)\)\s*$",
    re.I,
)
_WIKIPEDIA_ARTIST_TITLE_ALIASES = {
    "theneighborhood": {"theneighbourhood"},
    "theneighbourhood": {"theneighborhood"},
}
_MUSIC_PERSON_HINT = re.compile(
    r"\b(?:music(?:al|ian|ians)?|singer(?:-songwriter)?s?|songwriters?|"
    r"rappers?|bands?|groups?|vocalists?|composers?|djs?|producers?|"
    r"orchestras?|ensembles?|recording\s+artists?|hip[\s-]?hop|"
    r"r&b|rhythm\s+and\s+blues|pop\s+stars?|rock\s+bands?)\b",
    re.I,
)
_MUSIC_PERSON_HINT_PT = re.compile(
    r"\b(?:m[uú]sic[oa]s?|cantor(?:a|as|es)?|compositor(?:a|as|es)?|"
    r"rapper(?:s)?|banda(?:s)?|grupo(?:s)?|vocalista(?:s)?|"
    r"produtor(?:a|es)?|artista(?:s)?|pop|rock|hip[\s-]?hop|"
    r"gospel|afrobeat|cantautores?)\b",
    re.I,
)


def _wiki_title_matches(title: str, name: str) -> bool:
    strip = lambda value: _WIKI_TITLE_QUALIFIER.sub("", value).strip()
    title_key = _artist_search_key(strip(title))
    name_key = _artist_search_key(strip(name))
    return title_key == name_key or title_key in _WIKIPEDIA_ARTIST_TITLE_ALIASES.get(name_key, set())


def _first_sentences(value: object, limit: int = 3) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return " ".join(re.split(r"(?<=[.!?])\s+", text)[:limit])


def _wikipedia_summary_to_profile(
    summary: dict, name: str, language: Literal["en", "pt-BR"] = "en"
) -> dict[str, str] | None:
    if summary.get("type") != "standard":
        return None
    if not _wiki_title_matches(str(summary.get("title", "")), name):
        return None
    description = str(summary.get("description", ""))
    extract = str(summary.get("extract", ""))
    music_hint = _MUSIC_PERSON_HINT_PT if language == "pt-BR" else _MUSIC_PERSON_HINT
    if not music_hint.search(f"{description} {extract}"):
        return None
    bio = _first_sentences(extract)
    if not bio:
        return None
    profile = {
        "bio": bio,
        "source": "Wikipédia" if language == "pt-BR" else "Wikipedia",
        "source_modified": "true",
        "source_url": (
            summary.get("content_urls", {})
            .get("desktop", {})
            .get("page", "")
        ),
    }
    return profile


def _fetch_wikipedia_artist_profile(
    client: httpx.Client,
    name: str,
    language: Literal["en", "pt-BR"] = "en",
) -> dict[str, str] | None:
    """Direct summary first, then a title-constrained Wikipedia search."""
    wiki_language = "pt" if language == "pt-BR" else "en"
    wiki_root = f"https://{wiki_language}.wikipedia.org"
    try:
        response = client.get(
            f"{wiki_root}/api/rest_v1/page/summary/{quote(name, safe='')}"
        )
        if response.status_code == 200:
            profile = _wikipedia_summary_to_profile(response.json(), name, language)
            if profile:
                return profile
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        log.warning("Wikipedia summary lookup failed for %r: %s", name, exc)

    try:
        search = client.get(
            f"{wiki_root}/w/api.php",
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
                f"{wiki_root}/api/rest_v1/page/summary/{quote(title, safe='')}"
            )
            response.raise_for_status()
            profile = _wikipedia_summary_to_profile(response.json(), name, language)
            if profile:
                return profile
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("Wikipedia search-hit summary failed for %r: %s", title, exc)
    return None


def _lookup_artist_profile(
    name: str, language: Literal["en", "pt-BR"] = "en"
) -> dict[str, str] | None:
    """Return a manually maintained profile or an attributed Wikipedia summary."""
    manual = _verified_artist_profile(name, language)
    if manual:
        if manual.get("source") in {"Wikipedia", "Wikipédia"}:
            manual["source_modified"] = "true"
        return manual
    artist_key = _artist_search_key(name)
    if not artist_key:
        return None
    key = f"{language}:{artist_key}"
    now = time.monotonic()
    cached = _artist_profile_cache.get(key)
    if cached and cached[0] > now:
        profile = cached[1].copy() if cached[1] else {}
    else:
        profile = {}
        try:
            with httpx.Client(
                timeout=6.0,
                headers={
                    "User-Agent": (
                        "Vervfy/1.0 "
                        "(https://github.com/samvitorsilva/Vervfy; "
                        "contact: https://github.com/samvitorsilva)"
                    )
                },
                follow_redirects=True,
            ) as client:
                profile = _fetch_wikipedia_artist_profile(client, name, language) or {}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("Wikipedia artist lookup failed for %r: %s", name, exc)
        _cache_artist_result(
            _artist_profile_cache, key, profile or None,
            now + (60 * 60 * 24 if profile else 10 * 60),
        )
    return profile or None


def _artist_photo_record(user_id: str, normalized_name: str) -> dict[str, object] | None:
    with tenant_session(user_id) as session:
        row = session.execute(
            select(
                ArtistPhoto.jpeg_data,
                ArtistPhoto.storage_path,
                ArtistPhoto.source,
            ).where(
                ArtistPhoto.user_id == user_id,
                ArtistPhoto.normalized_artist_name == normalized_name,
            )
        ).one_or_none()
    if row is None:
        return None
    return {
        "jpeg_data": bytes(row.jpeg_data) if row.jpeg_data is not None else None,
        "storage_path": row.storage_path,
        "source": row.source,
    }


def _save_artist_photo(
    user_id: str,
    normalized_name: str,
    jpeg_data: bytes | None,
    *,
    source: str,
    storage_path: str | None = None,
    resized_for_display: bool = False,
) -> None:
    with tenant_session(user_id) as session:
        row = session.get(
            ArtistPhoto,
            {
                "user_id": user_id,
                "normalized_artist_name": normalized_name,
            },
        )
        if row is None:
            row = ArtistPhoto(
                user_id=user_id,
                normalized_artist_name=normalized_name,
                jpeg_data=jpeg_data,
                storage_path=storage_path,
                source=source,
            )
            session.add(row)
        row.jpeg_data = jpeg_data
        row.storage_path = storage_path
        row.source = source
        row.resized_for_display = resized_for_display
        session.commit()


def _delete_artist_photo(user_id: str, normalized_name: str) -> str | None:
    storage_path = None
    with tenant_session(user_id) as session:
        row = session.get(
            ArtistPhoto,
            {
                "user_id": user_id,
                "normalized_artist_name": normalized_name,
            },
        )
        if row is not None:
            storage_path = row.storage_path
            session.delete(row)
            session.commit()
    return storage_path


def _normalize_artist_photo(data: bytes) -> tuple[bytes, bool]:
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(
                    status_code=400,
                    detail="Artist photo must be a JPEG, PNG, or WebP image",
                )
            width, height = image.size
            if (
                width <= 0
                or height <= 0
                or width > MAX_TRACK_COVER_DIMENSION
                or height > MAX_TRACK_COVER_DIMENSION
                or width * height > MAX_TRACK_COVER_PIXELS
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Artist photo dimensions exceed the configured limit",
                )
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            resized = image.width > MAX_ARTIST_PHOTO_DIMENSION or image.height > MAX_ARTIST_PHOTO_DIMENSION
            image.thumbnail(
                (MAX_ARTIST_PHOTO_DIMENSION, MAX_ARTIST_PHOTO_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            output = BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            return output.getvalue(), resized
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=400, detail="Invalid artist photo") from exc


def _artist_photo_for_user(
    user_id: str, name: str, *, lookup_throttled: bool = False
) -> dict[str, object] | None:
    del lookup_throttled
    normalized_name = _artist_search_key(name)
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Invalid artist name")
    stored = _artist_photo_record(user_id, normalized_name)
    return stored if stored and stored["source"] == "user" else None


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
    session_id = request.session.get("sid")
    session_version = request.session.get("sv")
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(session_version, int)
        or isinstance(session_version, bool)
    ):
        request.session.clear()
        return None
    row = user_store.get_by_id(user_id)
    if row is None:
        return None
    if session_version != row["session_version"]:
        request.session.clear()
        return None
    try:
        if not session_store.is_valid(session_id, user_id):
            request.session.clear()
            return None
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable",
        ) from exc
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
        "cover_source": track.cover_source,
        "cover_url": track.cover_url or f"/api/tracks/{track.id}/cover",
        "stream_url": f"/api/tracks/{track.id}/stream",
    }


@app.on_event("startup")
def startup() -> None:
    if is_production:
        if not audio_store.enabled():
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY are required in production"
            )
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
        if "cover_path" not in existing_track_columns:
            connection.execute(text("ALTER TABLE tracks ADD COLUMN cover_path VARCHAR(600)"))
        if "cover_source" not in existing_track_columns:
            connection.execute(
                text(
                    "ALTER TABLE tracks ADD COLUMN cover_source "
                    "VARCHAR(20) NOT NULL DEFAULT 'unknown'"
                )
            )
            connection.execute(text("UPDATE tracks SET cover_source = 'unknown'"))
        connection.execute(text(
            "UPDATE tracks SET cover_source = 'embedded' "
            "WHERE cover_source = 'unknown' AND has_cover IS TRUE"
        ))
        existing_playlist_columns = {column["name"] for column in inspect(engine).get_columns("playlists")}
        if "position" not in existing_playlist_columns:
            connection.execute(text("ALTER TABLE playlists ADD COLUMN position INTEGER NOT NULL DEFAULT 0"))
        existing_artist_photo_columns = {
            column["name"] for column in inspect(engine).get_columns("artist_photos")
        }
        if "storage_path" not in existing_artist_photo_columns:
            connection.execute(
                text("ALTER TABLE artist_photos ADD COLUMN storage_path VARCHAR(600)")
            )
        if engine.dialect.name == "postgresql":
            audio_data_col = next(
                (c for c in inspect(engine).get_columns("tracks") if c["name"] == "audio_data"),
                None,
            )
            if audio_data_col is not None and not audio_data_col.get("nullable", True):
                # Audio moved to Supabase Storage, so the blob column may now be empty.
                connection.execute(text("ALTER TABLE tracks ALTER COLUMN audio_data DROP NOT NULL"))
            cover_data_col = next(
                (c for c in inspect(engine).get_columns("tracks") if c["name"] == "cover_data"),
                None,
            )
            if cover_data_col is not None and not cover_data_col.get("nullable", True):
                connection.execute(text("ALTER TABLE tracks ALTER COLUMN cover_data DROP NOT NULL"))
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
    try:
        previous_session_id = request.session.get("sid")
        if isinstance(previous_session_id, str) and previous_session_id:
            session_store.revoke(previous_session_id)
        session_id = session_store.create(row["id"])
    except RuntimeError:
        return fail("Service temporarily unavailable, try again shortly", status_code=503)
    request.session.clear()
    request.session["user_id"] = row["id"]
    request.session["sv"] = row["session_version"]
    request.session["sid"] = session_id
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

    try:
        session_id = session_store.create(new_user["id"])
    except RuntimeError:
        return fail("Service temporarily unavailable, try again shortly", status_code=503)
    request.session.clear()
    request.session["user_id"] = new_user["id"]
    request.session["sv"] = 0
    request.session["sid"] = session_id
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
    session_id = request.session.get("sid")
    if isinstance(session_id, str) and session_id:
        try:
            session_store.revoke(session_id)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail="Logout could not be completed; please retry",
            ) from exc
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


class TrackMetadataUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    artist: str = Field(..., min_length=1, max_length=512)
    album: str = Field(..., min_length=1, max_length=512)


SafeId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class PlaylistState(BaseModel):
    id: SafeId
    name: str = Field(min_length=1, max_length=200)
    trackIds: list[SafeId] = Field(default_factory=list, max_length=10_000)


class LibraryStateRequest(BaseModel):
    favorites: list[SafeId] = Field(default_factory=list, max_length=10_000)
    playlists: list[PlaylistState] = Field(default_factory=list, max_length=1_000)


def _queue_staged_upload(
    job_id: str,
    user_id: str,
    filename: str,
    audio_path: str,
) -> None:
    suffix = os.path.splitext(os.path.basename(filename))[1].lower()
    staging_path = f"{user_id}/.staging/{job_id}{suffix}"
    try:
        audio_store.upload_file(
            staging_path, audio_path, audio_store.guess_content_type(filename)
        )
        with tenant_session(user_id) as session:
            owner_id = session.scalar(
                select(User.id).where(User.id == user_id).with_for_update()
            )
            if owner_id is None:
                raise RuntimeError("account no longer exists")
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


def _upload_preflight(library: Library, path: str) -> tuple[str, int, int, bool]:
    track_id = track_id_for_file(path)
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
    with tenant_session(user["id"]) as session:
        owner_id = session.scalar(
            select(User.id).where(User.id == user["id"]).with_for_update()
        )
        if owner_id is None:
            raise HTTPException(status_code=404, detail="Account not found")
        storage_paths = list(session.scalars(
            select(TrackRecord.storage_path).where(
                TrackRecord.user_id == user["id"],
                TrackRecord.storage_path.is_not(None),
            )
        ).all())
        storage_paths.extend(session.scalars(
            select(UploadJob.storage_path).where(UploadJob.user_id == user["id"])
        ).all())
        try:
            audio_store.delete_many(storage_paths)
        except audio_store.StorageError as exc:
            log.exception("could not delete account Storage objects")
            raise HTTPException(
                status_code=502,
                detail="Account audio could not be deleted; please retry",
            ) from exc

        playlist_ids = select(Playlist.id).where(Playlist.user_id == user["id"])
        session.query(PlaylistTrack).filter(
            PlaylistTrack.playlist_id.in_(playlist_ids)
        ).delete(synchronize_session=False)
        session.query(Favorite).filter_by(user_id=user["id"]).delete(
            synchronize_session=False
        )
        session.query(TrackRecord).filter_by(user_id=user["id"]).delete(
            synchronize_session=False
        )
        session.query(UploadJob).filter_by(user_id=user["id"]).delete(
            synchronize_session=False
        )
        session.query(Playlist).filter_by(user_id=user["id"]).delete(
            synchronize_session=False
        )
        session.query(User).filter_by(id=user["id"]).delete(
            synchronize_session=False
        )
        session.commit()
    _libraries.pop(user["id"], None)
    request.session.clear()
    request.app.state.is_first_account = user_store.count() == 0
    return {"ok": True}


@app.get("/api/health")
def health(user=Depends(require_api_user)) -> dict:
    return {"ok": True, "tracks": get_library(user["id"]).count_tracks()}


@app.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
def healthz() -> Response:
    # Public, no auth, no database: only keeps the service awake.
    return Response(content="ok", media_type="text/plain", headers={"Cache-Control": "no-store"})


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


def _throttle_artist_lookup(user_id: str) -> None:
    try:
        allowed = request_throttle.allow(f"artist-lookup:{user_id}", 240, 60)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Rate-limit service unavailable") from exc
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many artist lookups", headers={"Retry-After": "60"})


@app.get("/api/artists/profile")
def artist_profile(
    name: str = Query(min_length=1, max_length=200),
    language: Literal["en", "pt-BR"] = "en",
    user=Depends(require_api_user),
) -> dict:
    """Return public artist metadata for the detail page, when available."""
    _throttle_artist_lookup(user["id"])
    return {"profile": _lookup_artist_profile(name.strip(), language)}


@app.get("/api/artists/images")
def artist_images(
    user=Depends(require_api_user),
) -> dict:
    """Return cached global artist images for this user's library and queue misses."""
    _throttle_artist_lookup(user["id"])
    artist_names = sorted(
        {
            name
            for track in get_library(user["id"]).list_tracks()
            for name in artists_from_credit(track.artist)
        },
        key=str.casefold,
    )
    normalized_names = {
        normalize_artist_name(name): name for name in artist_names
    }
    if not normalized_names:
        return {"artists": {}}

    keys = set(normalized_names)
    with SessionLocal() as session:
        image_rows = session.scalars(
            select(ArtistImage).where(
                ArtistImage.normalized_artist_name.in_(keys)
            )
        ).all()
    cached_by_key = {row.normalized_artist_name: row for row in image_rows}

    user_photo_names = {
        _artist_search_key(name): name for name in artist_names
    }
    with tenant_session(user["id"]) as session:
        photo_rows = session.execute(
            select(ArtistPhoto.normalized_artist_name).where(
                ArtistPhoto.user_id == user["id"],
                ArtistPhoto.normalized_artist_name.in_(set(user_photo_names)),
                ArtistPhoto.source == "user",
            )
        ).scalars().all()
    user_photos = set(photo_rows)

    result: dict[str, dict[str, object]] = {}
    for key, name in normalized_names.items():
        cached = cached_by_key.get(key)
        cached_value = (
            {
                "audiodb_id": cached.audiodb_id,
                "image_url": cached.image_url,
                "banner_url": cached.banner_url,
                "status": cached.status,
                "fetched_at": cached.fetched_at.isoformat(),
            }
            if cached is not None
            else {
                "audiodb_id": None,
                "image_url": None,
                "banner_url": None,
                "status": "pending",
                "fetched_at": None,
            }
        )
        pending = artist_image_is_stale(
            {
                "status": cached.status,
                "fetched_at": cached.fetched_at,
            }
            if cached is not None
            else None
        )
        if pending:
            audiodb_queue.enqueue(name)
        photo_key = _artist_search_key(name)
        cached_value["user_photo_url"] = (
            "/api/artists/photo?name=" + quote(name, safe="")
            if photo_key in user_photos
            else None
        )
        cached_value["pending"] = pending
        result[key] = cached_value
    return {"artists": result}


@app.get("/api/artists/photo")
def artist_photo(
    name: str = Query(min_length=1, max_length=200),
    user=Depends(require_api_user),
) -> Response:
    photo = _artist_photo_for_user(user["id"], name.strip())
    if not photo:
        raise HTTPException(status_code=404, detail="No artist photo")
    storage_path = photo.get("storage_path")
    if isinstance(storage_path, str) and storage_path:
        try:
            signed_url = audio_store.create_signed_url(storage_path)
        except audio_store.StorageError as exc:
            log.error("Could not create artist image URL: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Artist image storage is temporarily unavailable",
            ) from exc
        return RedirectResponse(
            signed_url,
            status_code=307,
            headers={"Cache-Control": "private, no-store"},
        )
    data = photo.get("jpeg_data")
    if not isinstance(data, bytes):
        raise HTTPException(status_code=404, detail="No artist photo")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Length": str(len(data)),
            "X-Artist-Photo-Source": str(photo["source"]),
        },
    )


@app.put("/api/artists/photo")
@limit_upload_processing
async def upload_artist_photo(
    request: Request,
    name: str = Form(..., min_length=1, max_length=200),
    file: UploadFile = File(...),
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    normalized_name = _artist_search_key(name.strip())
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Invalid artist name")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_ARTIST_PHOTO_BYTES + MULTIPART_UPLOAD_OVERHEAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Artist photo upload exceeds the 5 MB size limit",
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid upload size") from None
    data = bytearray()
    try:
        while part := await file.read(64 * 1024):
            data.extend(part)
            if len(data) > MAX_ARTIST_PHOTO_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Artist photo upload exceeds the 5 MB size limit",
                )
        jpeg_data, resized = await run_in_threadpool(
            _normalize_artist_photo, bytes(data)
        )
    finally:
        await file.close()
    existing_photo = await run_in_threadpool(
        _artist_photo_record,
        user["id"],
        normalized_name,
    )
    storage_path = None
    if audio_store.enabled():
        storage_path = (
            f"artist-photos/{user['id']}/{normalized_name}/{uuid.uuid4().hex}.jpg"
        )
        try:
            await run_in_threadpool(
                audio_store.upload,
                storage_path,
                jpeg_data,
                "image/jpeg",
            )
        except audio_store.StorageError as exc:
            log.error("Could not store artist image: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Artist image storage is temporarily unavailable",
            ) from exc
    try:
        await run_in_threadpool(
            _save_artist_photo,
            user["id"],
            normalized_name,
            None if storage_path else jpeg_data,
            source="user",
            storage_path=storage_path,
            resized_for_display=resized,
        )
    except Exception:
        if storage_path:
            audio_store.delete_quietly(storage_path)
        raise
    old_storage_path = existing_photo.get("storage_path") if existing_photo else None
    if (
        storage_path
        and isinstance(old_storage_path, str)
        and old_storage_path != storage_path
    ):
        audio_store.delete_quietly(old_storage_path)
    return {"photo_url": "/api/artists/photo?name=" + quote(name.strip(), safe="")}


@app.delete("/api/artists/photo")
def remove_artist_photo(
    name: str = Query(min_length=1, max_length=200),
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    normalized_name = _artist_search_key(name.strip())
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Invalid artist name")
    photo = _artist_photo_record(user["id"], normalized_name)
    if photo and isinstance(photo.get("storage_path"), str):
        try:
            audio_store.delete(str(photo["storage_path"]))
        except audio_store.StorageError as exc:
            log.error("Could not remove artist image from Storage: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Artist image storage is temporarily unavailable",
            ) from exc
    _delete_artist_photo(user["id"], normalized_name)
    return {"photo_url": None}


@app.get("/api/config")
def public_config() -> dict:
    """Expose only frontend-safe feature flags."""
    enabled = os.environ.get("LYRICS_PROVIDER_LRCLIB", "1").strip().lower()
    return {"lyrics_provider_lrclib": enabled not in {"0", "false", "off", "no"}}


@app.get("/api/tracks")
def list_tracks(user=Depends(require_api_user)) -> dict:
    library = get_library(user["id"])
    tracks = library.list_tracks()
    return {"tracks": [_track_payload(track) for track in tracks]}


@app.get("/api/tracks/covers")
def track_covers(
    background_tasks: BackgroundTasks,
    user=Depends(require_api_user),
) -> dict:
    """Return saved covers and queue missing/generated covers through the full chain."""
    try:
        allowed = request_throttle.allow(
            f"track-cover-lookup:{user['id']}", 120, 60
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Rate-limit service unavailable"
        ) from exc
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many cover lookups",
            headers={"Retry-After": "60"},
        )

    results: dict[str, dict[str, object]] = {}
    pending = False
    tracks = get_library(user["id"]).list_tracks()
    for track in tracks:
        missing = (
            track.cover_source in {None, "generated", "placeholder", "unknown"}
            and not track.cover_url
        )
        if missing:
            schedule_cover_resolution(background_tasks, user["id"], track.id)
        pending = pending or missing
        results[track.id] = {
            "cover_url": track.cover_url or f"/api/tracks/{track.id}/cover",
            "cover_source": track.cover_source,
            "status": "pending" if missing else "found",
            "pending": missing,
        }
    return {"covers": results, "pending": pending}


@app.post("/api/library/upload")
@limit_upload_processing
async def upload_track(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
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
    total_bytes = 0
    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(file.filename)[1], delete=False
        ) as audio_file:
            audio_path = audio_file.name
            while part := await file.read(1024 * 1024):
                total_bytes += len(part)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Upload exceeds the configured size limit",
                    )
                audio_file.write(part)
        if not total_bytes:
            raise HTTPException(status_code=400, detail="Empty upload")
        library = get_library(user["id"])
        if async_uploads:
            job_id = uuid.uuid4().hex
            await run_in_threadpool(
                _queue_staged_upload,
                job_id,
                user["id"],
                file.filename,
                audio_path,
            )
            return {"id": job_id, "status": "processing"}
        track_id, used_bytes, track_count, existing = await run_in_threadpool(
            _upload_preflight, library, audio_path
        )
        if not existing and (
            used_bytes + total_bytes > USER_QUOTA_BYTES
            or track_count >= MAX_TRACKS_PER_USER
        ):
            used_mb = used_bytes / (1024 * 1024)
            quota_mb = USER_QUOTA_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"Storage quota reached ({used_mb:.1f} MB of {quota_mb:.1f} MB used)",
            )
        try:
            track = await run_in_threadpool(
                library.add_upload_file,
                file.filename,
                audio_path,
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
            raise HTTPException(
                status_code=502, detail=f"Audio storage error: {str(exc)[:200]}"
            ) from None
        if track is None:
            raise HTTPException(
                status_code=400, detail="Could not read uploaded audio file"
            )
        schedule_cover_resolution(
            background_tasks,
            user["id"],
            track.id,
        )
        return _track_payload(track)
    finally:
        if audio_path:
            try:
                os.unlink(audio_path)
            except OSError:
                log.warning("Could not remove temporary audio file %s", audio_path)


@app.get("/api/library/upload/{job_id}")
def upload_status(
    job_id: str,
    user=Depends(require_api_user),
) -> dict:
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


def _normalize_track_cover(data: bytes) -> bytes:
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(
                    status_code=400,
                    detail="Cover must be a JPEG, PNG, or WebP image",
                )
            width, height = image.size
            if (
                width <= 0
                or height <= 0
                or width > MAX_TRACK_COVER_DIMENSION
                or height > MAX_TRACK_COVER_DIMENSION
                or width * height > MAX_TRACK_COVER_PIXELS
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Cover dimensions exceed the configured limit",
                )
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((600, 600), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
            return output.getvalue()
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=400, detail="Invalid cover image") from exc


@app.get("/api/tracks/{track_id}/cover")
def track_cover(
    track_id: str, size: int = Query(default=512, ge=64, le=1024), user=Depends(require_api_user)
) -> Response:
    library = get_library(user["id"])
    if library.get(track_id) is None:
        raise HTTPException(status_code=404, detail="Track not found")
    storage_path = library.cover_storage_path(track_id)
    if storage_path:
        try:
            signed_url = audio_store.create_signed_url(storage_path)
        except audio_store.StorageError as exc:
            log.exception("track cover storage URL creation failed")
            raise HTTPException(
                status_code=502, detail="Cover storage is unavailable"
            ) from exc
        return RedirectResponse(
            signed_url,
            status_code=307,
            headers={"Cache-Control": "private, no-store"},
        )
    payload = library.cover_jpeg(track_id, size)
    return Response(
        content=payload,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Length": str(len(payload)),
        },
    )


@app.put("/api/tracks/{track_id}/cover")
@limit_upload_processing
async def upload_track_cover(
    track_id: str,
    request: Request,
    file: UploadFile = File(...),
    apply_to_album: bool = Form(False),
    replace_user_covers: bool = Form(False),
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    if replace_user_covers and not apply_to_album:
        raise HTTPException(
            status_code=400,
            detail="Confirm replacing user covers only when applying to the album",
        )
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_TRACK_COVER_BYTES + MULTIPART_UPLOAD_OVERHEAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Cover upload exceeds the 5 MB size limit",
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid upload size") from None

    data = bytearray()
    while part := await file.read(64 * 1024):
        data.extend(part)
        if len(data) > MAX_TRACK_COVER_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Cover upload exceeds the 5 MB size limit",
            )
    try:
        cover = await run_in_threadpool(_normalize_track_cover, bytes(data))
    finally:
        await file.close()
    library = get_library(user["id"])
    if apply_to_album:
        try:
            updated_count = await run_in_threadpool(
                library.set_album_user_cover,
                track_id,
                cover,
                replace_user_covers=replace_user_covers,
            )
        except audio_store.StorageError as exc:
            log.exception("track cover storage failed")
            raise HTTPException(
                status_code=502, detail="Cover storage is unavailable"
            ) from exc
        if updated_count is None:
            raise HTTPException(status_code=404, detail="Track not found")
        if updated_count == 0:
            raise HTTPException(
                status_code=400,
                detail="This track does not have an album name",
            )
        return {"cover_source": "user", "updated_count": updated_count}
    try:
        track = await run_in_threadpool(library.set_user_cover, track_id, cover)
    except audio_store.StorageError as exc:
        log.exception("track cover storage failed")
        raise HTTPException(
            status_code=502, detail="Cover storage is unavailable"
        ) from exc
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return {"cover_source": track.cover_source, "updated_count": 1}


@app.delete("/api/tracks/{track_id}/cover")
async def remove_track_cover(
    track_id: str,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    try:
        track = await run_in_threadpool(
            get_library(user["id"]).remove_user_cover, track_id
        )
    except audio_store.StorageError as exc:
        log.exception("audio storage read failed while resetting a cover")
        raise HTTPException(
            status_code=502, detail="Audio storage is unavailable"
        ) from exc
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return {"cover_source": track.cover_source}


@app.post("/api/tracks/{track_id}/cover/retry")
async def retry_track_cover(
    track_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    library = get_library(user["id"])
    track = await run_in_threadpool(library.get, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    if track.cover_source in {"upload", "user"}:
        return {
            "status": "skipped",
            "cover_source": track.cover_source,
            "detail": "Owned covers are not replaced by automatic lookup",
        }
    schedule_cover_resolution(
        background_tasks, user["id"], track_id, force=True
    )
    return {"status": "queued", "cover_source": track.cover_source}


@app.patch("/api/tracks/{track_id}")
def update_track_metadata(
    track_id: str,
    payload: TrackMetadataUpdate,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    values = {
        "title": payload.title.strip(),
        "artist": payload.artist.strip(),
        "album": payload.album.strip(),
    }
    if not all(values.values()):
        raise HTTPException(status_code=422, detail="Track details cannot be empty")
    track = get_library(user["id"]).update_metadata(track_id, **values)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return _track_payload(track)


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
    try:
        payload = library.read_range(track_id, start, end) or b""
    except AudioUnavailableError:
        log.error("track %s has no audio in Storage or the database", track_id)
        raise HTTPException(status_code=502, detail="Track audio is unavailable") from None
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
    except AudioUnavailableError:
        log.error("track %s has no audio in Storage or the database", track_id)
        raise HTTPException(status_code=502, detail="Track audio is unavailable") from None
    return Response(
        content=data or b"",
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Length": str(len(data or b"")),
        },
    )
