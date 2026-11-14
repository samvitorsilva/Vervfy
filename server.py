#!/usr/bin/env python3
"""Vervfy — music library and playback API."""

from __future__ import annotations

import asyncio
import functools
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
import time
import unicodedata
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
import redis
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

import audio_store
import auth
import email_smtp
import google_oauth
import password_reset
import staging_guard
import storage_lifecycle
import upload_queue

# Password/Google authentication must not require the optional WebAuthn stack.
# Keep its implementation and migrations intact, but load them only on opt-in.
_webauthn_enabled = os.environ.get("VERVFY_WEBAUTHN_ENABLED", "0")
if _webauthn_enabled not in {"0", "1"}:
    raise RuntimeError("Invalid WebAuthn enable flag")
account_transactions = passkey_enrollment = passkey_schema = passkeys = None
if _webauthn_enabled == "1":
    import account_transactions
    import passkey_enrollment
    import passkey_schema
    import passkeys
from artist_images import (
    TheAudioDBQueue,
    artists_from_credit,
    normalize_artist_name,
)
from artist_images import (
    is_stale as artist_image_is_stale,
)
from cover_art import schedule_cover_resolution
from database import engine
from db import (
    ArtistImage,
    ArtistPhoto,
    Favorite,
    Playlist,
    PlaylistTrack,
    ProviderIdentity,
    SessionLocal,
    TrackListen,
    TrackRecord,
    UploadJob,
    User,
    tenant_session,
)
from library import (
    AUDIO_EXTENSIONS,
    EXECUTABLE_UPLOAD_SUFFIXES,
    AudioUnavailableError,
    Library,
    UploadQuotaExceeded,
    track_id_for_file,
)
from request_limits import RequestSizeLimitMiddleware

ArtistProfileLanguage = Literal["en", "pt-BR", "fr", "es"]

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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await run_in_threadpool(startup)
    try:
        yield
    finally:
        close_audio_store()


_enable_docs = os.environ.get("VERVFY_ENABLE_DOCS") == "1"
app = FastAPI(
    title="Vervfy",
    version="1.0",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
    lifespan=lifespan,
)


def close_audio_store() -> None:
    audio_store.close_client()
    if google_oauth_service is not None:
        google_oauth_service.close()


# Provisional until startup reads the DB; must exist so /register never AttributeErrors
# if a request somehow arrives before the startup hook finishes.
app.state.is_first_account = True
environment = (
    os.environ.get("VERVFY_ENVIRONMENT")
    or os.environ.get("ENVIRONMENT", "development")
).lower()
staging_guard.validate_runtime_redis_url(
    os.environ.get("REDIS_URL"), environment, os.environ
)
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

MAX_UPLOAD_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
MAX_TRACK_COVER_BYTES = 5 * 1024 * 1024
MULTIPART_UPLOAD_OVERHEAD_BYTES = 1024 * 1024
# Keep the streaming guard inside the HTTP middleware so receive exceptions
# reach FastAPI directly, without an intervening task-group exception wrapper.
app.add_middleware(
    RequestSizeLimitMiddleware,
    audio_bytes=MAX_UPLOAD_BYTES,
    image_bytes=MAX_TRACK_COVER_BYTES,
    overhead=MULTIPART_UPLOAD_OVERHEAD_BYTES,
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
    path = request.url.path
    if passkey_config is None and (
        path.startswith("/api/account/passkeys/")
        or path == "/api/account/security-methods"
    ):
        return JSONResponse(
            {"detail": "Not found"}, status_code=404,
            headers={"Cache-Control": "private, no-store"},
        )
    if path in {
        "/api/auth/google/start",
        "/api/auth/google/callback",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify-reset-email",
    }:
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
    elif request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        if path.startswith("/api/"):
            is_upload = path in {"/api/library/upload", "/api/account/photo"} or (
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
        elif path in {
            "/login",
            "/register",
        }:
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
    if path.startswith("/api/account/passkeys/") or path in {
        "/api/account/email",
        "/api/account/password",
        "/api/account/logout-all",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify-reset-email",
    }:
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Pragma"] = "no-cache"
    if path in {
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify-reset-email",
    }:
        response.headers["Referrer-Policy"] = "no-referrer"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault("Content-Security-Policy-Report-Only", CSP_REPORT_ONLY)
    if request.method == "GET" and request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
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
password_reset_store = password_reset.PasswordResetStore(os.environ.get("REDIS_URL"))
email_verification_store = password_reset.EmailVerificationStore(
    os.environ.get("REDIS_URL")
)
email_sender = email_smtp.EmailSender()
password_reset_logger = logging.getLogger("vervfy.password_reset")
PASSWORD_RESET_GENERIC = (
    "If an account exists for that email, we sent password reset instructions."
)
PASSWORD_RESET_EMAIL_VERIFICATION_GENERIC = (
    "If you own this email address, reset instructions will arrive shortly."
)
PASSWORD_RESET_IP_LIMIT = 5
PASSWORD_RESET_EMAIL_LIMIT = 3
PASSWORD_RESET_WINDOW_SECONDS = 15 * 60


def _password_recovery_enabled() -> bool:
    return os.environ.get("VERVFY_PASSWORD_RECOVERY_ENABLED", "").strip() == "1"


def _require_password_recovery_enabled() -> None:
    if not _password_recovery_enabled():
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable, try again shortly",
        )


passkey_config = passkeys.Config.from_environment() if passkeys is not None else None
passkey_redis = None
passkey_assertions = None
passkey_registration = None
passkey_recovery = None
if passkey_config is not None:
    passkey_redis_url = os.environ.get("REDIS_URL", "").strip()
    if not passkey_redis_url:
        raise RuntimeError("REDIS_URL is required when WebAuthn is enabled")
    passkey_redis = redis.Redis.from_url(
        passkey_redis_url,
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )
    passkey_challenges = passkeys.ChallengeStore(passkey_redis)
    passkey_gate = passkey_enrollment.SecurityGate(passkey_redis, session_store)
    passkey_assertions = passkeys.AssertionService(passkey_config, passkey_challenges)
    passkey_registration = passkey_enrollment.RegistrationService(
        passkey_config, passkey_challenges, passkey_gate
    )
    passkey_recovery = passkey_enrollment.RecoveryCodes(passkey_config, passkey_gate)


class PasskeyRequestLimiter:
    SCRIPT = """
    local allowed=1
    for i=1,#KEYS do
        local count=redis.call('INCR',KEYS[i])
        if count==1 then redis.call('EXPIRE',KEYS[i],ARGV[1]) end
        if count>tonumber(ARGV[2]) then allowed=0 end
    end
    return allowed
    """

    def __init__(self, client):
        self.client = client

    def check(self, request: Request, binding: passkeys.Binding, scope: str) -> None:
        ip_digest = hashlib.sha256(auth.client_ip(request).encode()).hexdigest()
        session_digest = binding.session_digest
        account_digest = hashlib.sha256(binding.user_id.encode()).hexdigest()
        keys = [
            f"vervfy:passkey:api:{scope}:account:{account_digest}",
            f"vervfy:passkey:api:{scope}:session:{session_digest}",
            f"vervfy:passkey:api:{scope}:ip:{ip_digest}",
        ]
        try:
            allowed = self.client.eval(self.SCRIPT, len(keys), *keys, 900, 30)
        except redis.RedisError:
            raise HTTPException(
                status_code=503, detail="Passkey service temporarily unavailable"
            ) from None
        if int(allowed) != 1:
            raise HTTPException(
                status_code=429,
                detail="Too many passkey requests",
                headers={"Retry-After": "900"},
            )


passkey_request_limiter = (
    PasskeyRequestLimiter(passkey_redis) if passkey_redis is not None else None
)


def _passkey_services():
    if passkey_config is None:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        passkey_assertions is None
        or passkey_registration is None
        or passkey_recovery is None
        or passkey_request_limiter is None
    ):
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        )
    return (
        passkey_assertions,
        passkey_registration,
        passkey_recovery,
        passkey_request_limiter,
    )


def _passkey_binding(request: Request, user: User, action: str) -> passkeys.Binding:
    session_id = request.session.get("sid")
    session_version = request.session.get("sv")
    if (
        not isinstance(session_id, str)
        or not session_id
        or type(session_version) is not int
        or session_version != user["session_version"]
    ):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return passkeys.Binding(user["id"], session_id, session_version, action)
    except passkeys.PasskeyError:
        raise HTTPException(status_code=400, detail="Invalid passkey request") from None


def _check_passkey_rate(
    request: Request, binding: passkeys.Binding, scope: str
) -> None:
    _passkey_services()
    passkey_request_limiter.check(request, binding, scope)


def _passkey_error(exc: passkeys.PasskeyError) -> HTTPException:
    if isinstance(exc, passkeys.PasskeyUnavailable):
        return HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        )
    return HTTPException(status_code=400, detail="Passkey request could not be completed")


google_oauth_config = google_oauth.GoogleOAuthConfig.from_environment()
if google_oauth_config is not None and configured_same_site != "lax":
    raise RuntimeError("Google OAuth requires VERVFY_COOKIE_SAME_SITE=lax")
google_oauth_service = (
    google_oauth.GoogleOAuthService(google_oauth_config)
    if google_oauth_config is not None
    else None
)
log = logging.getLogger("vervfy")
logging.getLogger("uvicorn.access").addFilter(google_oauth.OAuthAccessLogFilter())
USER_QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS_PER_USER = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PROFILE_PHOTO_DIMENSION = 8192
MAX_PROFILE_PHOTO_PIXELS = 12_000_000
MAX_TRACK_COVER_DIMENSION = 8192
MAX_TRACK_COVER_PIXELS = 12_000_000
IMAGE_UPLOAD_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".gif": "GIF",
}
STATIC_IMAGE_UPLOAD_FORMATS = {
    extension: image_format
    for extension, image_format in IMAGE_UPLOAD_FORMATS.items()
    if image_format != "GIF"
}
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
        "media-src 'self' blob: https://*.supabase.co; "
        "connect-src 'self' https://*.supabase.co; "
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

_VERIFIED_ARTIST_PROFILE_TRANSLATIONS: dict[
    str, dict[str, dict[str, str]]
] = {
    "pt-BR": {
        "tatemcrae": {
            "highlights": "Cantora, compositora e dançarina canadense.",
        },
        "morada": {
            "highlights": "Formada em Fernandópolis (SP), em 2009.",
        },
        "tommybueno": {
            "highlights": "Entre seus lançamentos estão “Visionario” e “Atmósfera”.",
        },
        "kallysmashupcast": {
            "highlights": "Grupo responsável pelas músicas da série “KALLY'S Mashup”, da Nickelodeon.",
        },
        "viclucas": {
            "genre": "Afrobeat",
            "highlights": "Mistura influências da Nigéria, da África do Sul e dos Estados Unidos.",
        },
        "kaimalachi": {
            "highlights": "Projeto criado, produzido e dirigido por Tim Vishnevskiy.",
        },
        "ajvitanza": {
            "genre": "Pop",
            "highlights": "Lançou o EP de estreia “Plastic Heart”, com nove faixas.",
        },
        "mielsanmarcos": {
            "highlights": "Formada em 2000 pelos irmãos Josh, Luis e Samy Morales.",
        },
        "gio": {
            "highlights": "Traz influências do gospel e da poesia para um som moderno de pop cristão e hip-hop.",
        },
        "thekidlaroi": {
            "highlights": "Cantor, rapper e compositor australiano conhecido mundialmente por “Stay”.",
        },
        "shawnmendes": {
            "highlights": "Ganhou público compartilhando versões de músicas na internet antes de lançar seu primeiro EP em 2014.",
        },
        "maroon5": {
            "highlights": "A banda se chamava Kara’s Flowers antes de adotar o nome Maroon 5.",
        },
        "theneighborhood": {
            "highlights": "Banda conhecida por músicas como “Sweater Weather” e “Daddy Issues”.",
        },
        "theneighbourhood": {
            "highlights": "Banda conhecida por músicas como “Sweater Weather” e “Daddy Issues”.",
        },
    },
    "fr": {
        "tatemcrae": {
            "bio": "Tate McRae est une chanteuse, compositrice et danseuse canadienne. Elle s’est d’abord fait connaître comme danseuse avant de lancer sa carrière musicale.",
            "genre": "Pop",
            "highlights": "Chanteuse, compositrice et danseuse canadienne.",
        },
        "morada": {
            "bio": "MORADA est un groupe chrétien contemporain brésilien formé en 2009 à Fernandópolis, dans l’État de São Paulo.",
            "genre": "Musique chrétienne contemporaine",
            "highlights": "Formé à Fernandópolis, dans l’État de São Paulo, en 2009.",
        },
        "tommybueno": {
            "bio": "Tommy Bueno est un artiste basé à Buenos Aires, dont le catalogue comprend les sorties Visionario et Atmósfera.",
            "highlights": "Son catalogue comprend les sorties Visionario et Atmósfera.",
        },
        "obros": {
            "bio": "O'Bros est un duo allemand de hip-hop chrétien originaire de Munich. Leur musique associe le hip-hop à la foi chrétienne.",
            "genre": "Hip-hop chrétien",
            "highlights": "Duo munichois connu pour associer le hip-hop à la foi chrétienne.",
        },
        "kallysmashupcast": {
            "bio": "KALLY'S Mashup Cast est l’ensemble crédité pour la musique de la série télévisée KALLY'S Mashup de Nickelodeon.",
            "highlights": "Ensemble crédité pour la musique de la série télévisée KALLY'S Mashup de Nickelodeon.",
        },
        "viclucas": {
            "bio": "Vic Lucas est un artiste d’afrobeat dont la musique puise dans les influences nigérianes, sud-africaines et américaines, avec la foi et la gratitude au cœur de son œuvre.",
            "genre": "Afrobeat",
            "highlights": "Sa musique mêle des influences nigérianes, sud-africaines et américaines.",
        },
        "kaimalachi": {
            "bio": "Kai Malachi est un projet de gospel cinématographique, de soul et de R&B alternatif créé, produit et dirigé par Tim Vishnevskiy.",
            "genre": "Gospel cinématographique, soul et R&B alternatif",
            "highlights": "Projet créé, produit et dirigé par Tim Vishnevskiy.",
        },
        "ajvitanza": {
            "bio": "AJ Vitanza est un artiste pop. Son premier EP, Plastic Heart, comporte neuf titres.",
            "genre": "Pop",
            "highlights": "A sorti le premier EP de neuf titres Plastic Heart.",
        },
        "mielsanmarcos": {
            "bio": "Miel San Marcos est un groupe chrétien guatémaltèque fondé en 2000 par les frères Josh, Luis et Samy Morales.",
            "genre": "Musique chrétienne contemporaine",
            "highlights": "Fondé en 2000 par les frères Josh, Luis et Samy Morales.",
        },
        "josephobrien": {
            "bio": "Joseph O'Brien est un auteur-compositeur-interprète basé à Nashville et signé chez Gotee Records. Sa musique cherche à encourager la foi de son public.",
            "genre": "Musique chrétienne",
            "highlights": "Auteur-compositeur-interprète basé à Nashville et artiste de Gotee Records.",
        },
        "stringsheart": {
            "bio": "Strings & Heart est un groupe chrétien indépendant composé de trois frères : Angelo, Michael et Eric Espinosa.",
            "genre": "Indie chrétien",
            "highlights": "Groupe composé des frères Angelo, Michael et Eric Espinosa.",
        },
        "gio": {
            "bio": "gio. est un artiste de pop chrétienne et de hip-hop de la région de Boston. Marqué dès son plus jeune âge par le gospel et la poésie, il souhaite apporter une approche moderne et créative à la musique chrétienne.",
            "genre": "Pop chrétienne, hip-hop",
            "highlights": "Associe les influences du gospel et de la poésie à un son moderne de pop chrétienne et de hip-hop.",
        },
        "thekidlaroi": {
            "bio": "The Kid LAROI (Charlton Howard) est un chanteur, rappeur et auteur-compositeur australien. Son single Stay a connu un succès international.",
            "genre": "Pop, hip-hop",
            "highlights": "Chanteur, rappeur et auteur-compositeur australien connu dans le monde entier pour Stay.",
        },
        "shawnmendes": {
            "bio": "Shawn Mendes est un chanteur et auteur-compositeur canadien qui s’est d’abord fait connaître en partageant des reprises en ligne, avant de sortir son premier EP en 2014.",
            "genre": "Pop",
            "highlights": "S’est fait connaître en partageant des reprises en ligne avant de sortir son premier EP en 2014.",
        },
        "maroon5": {
            "bio": "Maroon 5 est un groupe de pop-rock américain formé à Los Angeles. Le groupe s’appelait Kara’s Flowers avant d’adopter le nom Maroon 5 et de connaître le succès avec Songs About Jane.",
            "genre": "Pop-rock",
            "highlights": "Le groupe s’appelait Kara’s Flowers avant d’adopter le nom Maroon 5.",
        },
        "theneighborhood": {
            "bio": "The Neighbourhood est un groupe de rock alternatif américain formé en Californie en 2011. Il est notamment connu pour les chansons Sweater Weather et Daddy Issues.",
            "genre": "Rock alternatif",
            "highlights": "Groupe connu notamment pour Sweater Weather et Daddy Issues.",
        },
        "theneighbourhood": {
            "bio": "The Neighbourhood est un groupe de rock alternatif américain formé en Californie en 2011. Il est notamment connu pour les chansons Sweater Weather et Daddy Issues.",
            "genre": "Rock alternatif",
            "highlights": "Groupe connu notamment pour Sweater Weather et Daddy Issues.",
        },
    },
    "es": {
        "tatemcrae": {
            "bio": "Tate McRae es una cantante, compositora y bailarina canadiense. Primero se dio a conocer como bailarina antes de iniciar su carrera musical.",
            "genre": "Pop",
            "highlights": "Cantante, compositora y bailarina canadiense.",
        },
        "morada": {
            "bio": "MORADA es una banda brasileña de música cristiana contemporánea, formada en 2009 en Fernandópolis, estado de São Paulo.",
            "genre": "Música cristiana contemporánea",
            "highlights": "Se formó en Fernandópolis, estado de São Paulo, en 2009.",
        },
        "tommybueno": {
            "bio": "Tommy Bueno es un artista radicado en Buenos Aires cuyo catálogo incluye los lanzamientos Visionario y Atmósfera.",
            "highlights": "Su catálogo incluye los lanzamientos Visionario y Atmósfera.",
        },
        "obros": {
            "bio": "O'Bros es un dúo alemán de hip-hop cristiano de Múnich. Su música combina el hip-hop con la fe cristiana.",
            "genre": "Hip-hop cristiano",
            "highlights": "Dúo de Múnich conocido por combinar el hip-hop con la fe cristiana.",
        },
        "kallysmashupcast": {
            "bio": "KALLY'S Mashup Cast es el conjunto acreditado por la música de la serie de televisión KALLY'S Mashup de Nickelodeon.",
            "highlights": "Conjunto acreditado por la música de la serie de televisión KALLY'S Mashup de Nickelodeon.",
        },
        "viclucas": {
            "bio": "Vic Lucas es un artista de afrobeat cuya música combina influencias de Nigeria, Sudáfrica y Estados Unidos, con la fe y la gratitud como pilares.",
            "genre": "Afrobeat",
            "highlights": "Su música combina influencias de Nigeria, Sudáfrica y Estados Unidos.",
        },
        "kaimalachi": {
            "bio": "Kai Malachi es un proyecto de gospel cinematográfico, soul y R&B alternativo creado, producido y dirigido por Tim Vishnevskiy.",
            "genre": "Gospel cinematográfico, soul y R&B alternativo",
            "highlights": "Proyecto creado, producido y dirigido por Tim Vishnevskiy.",
        },
        "ajvitanza": {
            "bio": "AJ Vitanza es un artista pop. Su EP debut, Plastic Heart, contiene nueve canciones.",
            "genre": "Pop",
            "highlights": "Publicó el EP debut de nueve canciones Plastic Heart.",
        },
        "mielsanmarcos": {
            "bio": "Miel San Marcos es una banda cristiana guatemalteca fundada en 2000 por los hermanos Josh, Luis y Samy Morales.",
            "genre": "Música cristiana contemporánea",
            "highlights": "Fundada en 2000 por los hermanos Josh, Luis y Samy Morales.",
        },
        "josephobrien": {
            "bio": "Joseph O'Brien es un cantante y compositor radicado en Nashville y artista de Gotee Records. Su música busca animar a quienes la escuchan en su fe.",
            "genre": "Música cristiana",
            "highlights": "Cantante y compositor radicado en Nashville y artista de Gotee Records.",
        },
        "stringsheart": {
            "bio": "Strings & Heart es una banda cristiana independiente formada por tres hermanos: Angelo, Michael y Eric Espinosa.",
            "genre": "Indie cristiano",
            "highlights": "Banda formada por los hermanos Angelo, Michael y Eric Espinosa.",
        },
        "gio": {
            "bio": "gio. es un artista de pop cristiano y hip-hop de las afueras de Boston. Influido desde pequeño por el gospel y la poesía, busca aportar un enfoque moderno y creativo a la música cristiana.",
            "genre": "Pop cristiano, hip-hop",
            "highlights": "Combina influencias del gospel y la poesía con un sonido moderno de pop cristiano y hip-hop.",
        },
        "thekidlaroi": {
            "bio": "The Kid LAROI (Charlton Howard) es un cantante, rapero y compositor australiano. Su sencillo Stay alcanzó el éxito internacional.",
            "genre": "Pop, hip-hop",
            "highlights": "Cantante, rapero y compositor australiano conocido internacionalmente por Stay.",
        },
        "shawnmendes": {
            "bio": "Shawn Mendes es un cantante y compositor canadiense que primero reunió seguidores al compartir versiones de canciones en internet, antes de publicar su EP debut en 2014.",
            "genre": "Pop",
            "highlights": "Se dio a conocer al compartir versiones en internet antes de publicar su primer EP en 2014.",
        },
        "maroon5": {
            "bio": "Maroon 5 es una banda estadounidense de pop rock formada en Los Ángeles. Antes de adoptar el nombre Maroon 5 y triunfar con Songs About Jane, el grupo se llamaba Kara’s Flowers.",
            "genre": "Pop rock",
            "highlights": "El grupo se llamaba Kara’s Flowers antes de adoptar el nombre Maroon 5.",
        },
        "theneighborhood": {
            "bio": "The Neighbourhood es una banda estadounidense de rock alternativo formada en California en 2011. Entre sus canciones más conocidas están Sweater Weather y Daddy Issues.",
            "genre": "Rock alternativo",
            "highlights": "Banda conocida por canciones como Sweater Weather y Daddy Issues.",
        },
        "theneighbourhood": {
            "bio": "The Neighbourhood es una banda estadounidense de rock alternativo formada en California en 2011. Entre sus canciones más conocidas están Sweater Weather y Daddy Issues.",
            "genre": "Rock alternativo",
            "highlights": "Banda conocida por canciones como Sweater Weather y Daddy Issues.",
        },
    },
}


def _verified_artist_profile(
    name: str, language: ArtistProfileLanguage = "en"
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
            result.update(
                _VERIFIED_ARTIST_PROFILE_TRANSLATIONS.get(language, {}).get(
                    profile_key, {}
                )
            )
            if candidate != name.strip():
                result["lookup_name"] = candidate
            return result
    return None


_WIKI_TITLE_QUALIFIER = re.compile(
    r"\s*\((?:singer(?:-songwriter)?|rapper|band|musician|group|dj|composer|"
    r"vocalist|music(?:al)?\s+group|recording\s+artist|actor|actress|actriz|"
    r"ator|atriz|acteur|actrice)\)\s*$",
    re.IGNORECASE,
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
    re.IGNORECASE,
)
_MUSIC_PERSON_HINT_PT = re.compile(
    r"\b(?:m[uú]sic[oa]s?|cantor(?:a|as|es)?|compositor(?:a|as|es)?|"
    r"rapper(?:s)?|banda(?:s)?|grupo(?:s)?|vocalista(?:s)?|"
    r"produtor(?:a|es)?|artista(?:s)?|pop|rock|hip[\s-]?hop|"
    r"gospel|afrobeat|cantautores?)\b",
    re.IGNORECASE,
)
_MUSIC_PERSON_HINT_FR = re.compile(
    r"\b(?:musicien(?:ne|s)?|chanteu(?:r|se|rs|ses)|compositeur(?:ice|s)?|"
    r"rappeur(?:se|s|ses)?|groupe(?:s)?|guitariste(?:s)?|artiste(?:s)?|"
    r"producteur(?:rice|s|rices)?|orchestre(?:s)?|ensemble(?:s)?|"
    r"hip[\s-]?hop|r&b|rock|pop)\b",
    re.IGNORECASE,
)
_MUSIC_PERSON_HINT_ES = re.compile(
    r"\b(?:m[uú]sico(?:s)?|cantant(?:e|es)|compositor(?:a|es)?|"
    r"rapero(?:a|s|as)?|banda(?:s)?|grupo(?:s)?|vocalista(?:s)?|"
    r"productor(?:a|es)?|artista(?:s)?|orquesta(?:s)?|"
    r"hip[\s-]?hop|r&b|rock|pop)\b",
    re.IGNORECASE,
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
    summary: dict, name: str, language: ArtistProfileLanguage = "en"
) -> dict[str, str] | None:
    if summary.get("type") != "standard":
        return None
    if not _wiki_title_matches(str(summary.get("title", "")), name):
        return None
    description = str(summary.get("description", ""))
    extract = str(summary.get("extract", ""))
    music_hint = {
        "en": _MUSIC_PERSON_HINT,
        "pt-BR": _MUSIC_PERSON_HINT_PT,
        "fr": _MUSIC_PERSON_HINT_FR,
        "es": _MUSIC_PERSON_HINT_ES,
    }[language]
    if not music_hint.search(f"{description} {extract}"):
        return None
    bio = _first_sentences(extract)
    if not bio:
        return None
    source_label = {
        "en": "Wikipedia",
        "pt-BR": "Wikipédia",
        "fr": "Wikipédia",
        "es": "Wikipedia",
    }[language]
    profile = {
        "bio": bio,
        "source": source_label,
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
    language: ArtistProfileLanguage = "en",
) -> dict[str, str] | None:
    """Prefer the requested Wikipedia, then fall back to English."""
    languages: tuple[ArtistProfileLanguage, ...] = (
        (language, "en") if language != "en" else ("en",)
    )
    for profile_language in languages:
        wiki_language = {
            "en": "en",
            "pt-BR": "pt",
            "fr": "fr",
            "es": "es",
        }[profile_language]
        wiki_root = f"https://{wiki_language}.wikipedia.org"
        try:
            response = client.get(
                f"{wiki_root}/api/rest_v1/page/summary/{quote(name, safe='')}"
            )
            if response.status_code == 200:
                profile = _wikipedia_summary_to_profile(
                    response.json(), name, profile_language
                )
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
            continue

        for hit in hits:
            title = str(hit.get("title", "")).strip()
            if not title or not _wiki_title_matches(title, name):
                continue
            try:
                response = client.get(
                    f"{wiki_root}/api/rest_v1/page/summary/{quote(title, safe='')}"
                )
                response.raise_for_status()
                profile = _wikipedia_summary_to_profile(
                    response.json(), name, profile_language
                )
                if profile:
                    return profile
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                log.warning("Wikipedia search-hit summary failed for %r: %s", title, exc)
    return None


def _lookup_artist_profile(
    name: str, language: ArtistProfileLanguage = "en"
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
        storage_lifecycle.bound_transaction(session)
        if session.get(User, user_id, with_for_update=True) is None:
            raise RuntimeError("Account no longer exists")
        row = session.get(
            ArtistPhoto,
            {
                "user_id": user_id,
                "normalized_artist_name": normalized_name,
            },
        )
        if row is not None and row.source == "user" and source != "user":
            return
        if row is None:
            row = ArtistPhoto(
                user_id=user_id,
                normalized_artist_name=normalized_name,
                jpeg_data=jpeg_data,
                storage_path=storage_path,
                source=source,
            )
            session.add(row)
        row.media_version = uuid.uuid4()
        row.jpeg_data = jpeg_data
        row.storage_path = storage_path
        row.source = source
        row.resized_for_display = resized_for_display
        session.commit()


def _delete_artist_photo(user_id: str, normalized_name: str) -> str | None:
    with tenant_session(user_id) as session:
        storage_lifecycle.bound_transaction(session)
        row = session.get(
            ArtistPhoto,
            {
                "user_id": user_id,
                "normalized_artist_name": normalized_name,
            },
        )
        if row is not None:
            session.delete(row)
            session.commit()
    return None


def _has_executable_upload_suffix(filename: str) -> bool:
    return any(
        suffix.lower() in EXECUTABLE_UPLOAD_SUFFIXES
        for suffix in Path(filename.replace("\\", "/")).suffixes
    )


def _image_upload_format(
    filename: str,
    allowed_formats: dict[str, str],
) -> str:
    safe_name = os.path.basename(filename.replace("\\", "/"))
    suffixes = Path(safe_name).suffixes
    if (
        not safe_name
        or len(safe_name) > 255
        or _has_executable_upload_suffix(safe_name)
        or not suffixes
        or suffixes[-1].lower() not in allowed_formats
    ):
        raise HTTPException(status_code=400, detail="Unsupported image filename or format")
    return allowed_formats[suffixes[-1].lower()]


def _normalize_artist_photo(
    data: bytes, expected_format: str | None = None
) -> tuple[bytes, bool]:
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(
                    status_code=400,
                    detail="Artist photo must be a JPEG, PNG, or WebP image",
                )
            if expected_format is not None and image.format != expected_format:
                raise HTTPException(status_code=400, detail="Image extension does not match its content")
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


def _require_migrated_schema() -> None:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    missing_schema = {}
    required_columns = {
        "users": set(),
        "tracks": {"cover_url", "media_version"},
        "artist_photos": {"media_version"},
        "upload_jobs": {"cover_data", "processing_token"},
    }
    for table, expected_columns in required_columns.items():
        if not inspector.has_table(table):
            missing_schema[table] = sorted(expected_columns) or ["<table>"]
            continue
        existing_columns = (
            {column["name"] for column in inspector.get_columns(table)}
        )
        missing = expected_columns - existing_columns
        if missing:
            missing_schema[table] = sorted(missing)
    if missing_schema:
        raise RuntimeError(
            "Database schema is incomplete for this application "
            f"(missing_tables_or_columns={missing_schema}); inspect and migrate "
            "it to the explicitly reviewed migration revision using the authorized migration "
            "connection before starting Vervfy."
        )
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.connect() as connection:
            guarded = connection.execute(
                text("""
                SELECT count(*) FROM pg_catalog.pg_trigger
                WHERE tgrelid IN (
                    'public.tracks'::regclass,
                    'public.artist_photos'::regclass,
                    'public.upload_jobs'::regclass
                )
                  AND tgname='storage_reference_guard'
                  AND tgenabled='O'
                  AND tgtype=31
                  AND tgfoid=to_regprocedure('vervfy_storage.guard_references()')
                """)
            ).scalar_one()
            replication_role = connection.execute(
                text("SELECT current_setting('session_replication_role')")
            ).scalar_one()
        if guarded != 3 or replication_role != "origin":
            raise RuntimeError(
                "Storage lifecycle reference guards are missing or disabled; "
                "apply the reviewed storage lifecycle migrations before startup"
            )


def _require_private_upload_storage() -> None:
    if audio_store.enabled() and not audio_store.bucket_is_private():
        raise RuntimeError(
            "Configured Supabase Storage bucket must be explicitly private"
        )


def startup() -> None:
    _require_migrated_schema()
    if is_production:
        if not audio_store.enabled():
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY are required in production"
            )
        _require_private_upload_storage()
        if "VERVFY_TRUSTED_PROXY_HOPS" not in os.environ:
            log.warning(
                "VERVFY_TRUSTED_PROXY_HOPS is unset in production; rate limits may use the proxy IP"
            )
        app.state.is_first_account = user_store.count() == 0
        return
    _require_private_upload_storage()
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


def _google_oauth_unavailable() -> JSONResponse:
    return JSONResponse(
        {"detail": "Google sign-in is temporarily unavailable"},
        status_code=503,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def _google_oauth_failed(
    config: google_oauth.GoogleOAuthConfig,
    purpose: str = "login",
    *,
    clear_browser_binding: bool = True,
) -> Response:
    if purpose == "signup":
        destination = "/register?google=failed"
    elif purpose == "link":
        destination = "/?view=account&google_link=failed"
    elif purpose not in {"login", "signup"}:
        destination = f"/?view=account&google_reauth=failed&google_action={purpose}"
    else:
        destination = "/login?google=failed"
    response = RedirectResponse(destination, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    if clear_browser_binding:
        response.delete_cookie(
            config.browser_cookie_name,
            path="/",
            secure=config.cookie_secure,
            httponly=True,
            samesite="lax",
        )
    return response


def _google_browser_binding(request: Request, config) -> str:
    value = request.cookies.get(config.browser_cookie_name, "")
    if len(value) < 32 or len(value) > 256:
        return secrets.token_urlsafe(32)
    return value


def _set_google_browser_cookie(response: Response, config, binding: str) -> None:
    response.set_cookie(
        config.browser_cookie_name,
        binding,
        max_age=google_oauth.TRANSACTION_TTL_SECONDS,
        path="/",
        secure=config.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_google_browser_cookie(response: Response, config) -> None:
    response.delete_cookie(
        config.browser_cookie_name,
        path="/",
        secure=config.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@app.get("/api/auth/google/start", include_in_schema=False)
async def google_oauth_start(
    request: Request, purpose: str = Query("login")
) -> Response:
    service = google_oauth_service
    config = google_oauth_config
    if service is None or config is None:
        raise HTTPException(status_code=404, detail="Not found")
    if purpose not in {"login", "signup"}:
        raise HTTPException(status_code=400, detail="Invalid Google sign-in flow")
    browser_binding = _google_browser_binding(request, config)
    try:
        authorization_url = await service.create_authorization_url(
            browser_binding, purpose=purpose
        )
    except (
        google_oauth.OAuthBackendUnavailable,
        google_oauth.GoogleProviderError,
        google_oauth.OAuthTransactionError,
    ):
        return _google_oauth_unavailable()
    response = RedirectResponse(authorization_url, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    _set_google_browser_cookie(response, config, browser_binding)
    return response


class GoogleLinkStartRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class GoogleReauthStartRequest(BaseModel):
    purpose: Literal[
        "password_add", "email_change", "account_delete", "logout_all"
    ]


def _check_google_password_setup_rate(
    request: Request, user_id: str, stage: Literal["start", "submit"]
) -> None:
    window_seconds = 15 * 60
    user_key = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    ip_key = hashlib.sha256(
        auth.client_ip(request).encode("utf-8")
    ).hexdigest()
    try:
        user_allowed = request_throttle.allow(
            f"google-password-setup:{stage}:user:{user_key}",
            5,
            window_seconds,
        )
        ip_allowed = request_throttle.allow(
            f"google-password-setup:{stage}:ip:{ip_key}",
            20,
            window_seconds,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Rate-limit service unavailable"
        ) from exc
    if not user_allowed or not ip_allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many password setup attempts. Try again later.",
            headers={"Retry-After": str(window_seconds)},
        )


class GoogleOnboardingRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)


class GoogleUnlinkRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


async def _start_account_google_flow(
    request: Request,
    config,
    service,
    *,
    purpose: str,
    user: User,
    issued_password_at: int | None = None,
) -> JSONResponse:
    session_id = request.session.get("sid")
    session_version = request.session.get("sv")
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(session_version, int)
        or isinstance(session_version, bool)
        or session_version != user.session_version
    ):
        raise HTTPException(status_code=401, detail="Not authenticated")
    context: dict[str, object] = {
        "user_id": user.id,
        "session_id": session_id,
        "session_version": session_version,
    }
    if issued_password_at is not None:
        context["password_verified_at"] = issued_password_at
    binding = _google_browser_binding(request, config)
    try:
        authorization_url = await service.create_authorization_url(
            binding, purpose=purpose, context=context
        )
    except (
        google_oauth.OAuthBackendUnavailable,
        google_oauth.GoogleProviderError,
        google_oauth.OAuthTransactionError,
    ):
        return _google_oauth_unavailable()
    response = JSONResponse(
        {"authorization_url": authorization_url},
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    _set_google_browser_cookie(response, config, binding)
    return response


@app.post("/api/account/google/link/start")
async def google_account_link_start(
    payload: GoogleLinkStartRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> Response:
    service = google_oauth_service
    config = google_oauth_config
    if service is None or config is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        security = await run_in_threadpool(
            user_store.account_security, user["id"]
        )
    except (SQLAlchemyError, ValueError):
        return _google_oauth_unavailable()
    if not security["has_password"]:
        raise HTTPException(
            status_code=400, detail="A password is required before linking Google"
        )
    if security["google_linked"]:
        raise HTTPException(status_code=409, detail="A Google account is already linked")
    verify_current_password(user, payload.current_password)
    return await _start_account_google_flow(
        request,
        config,
        service,
        purpose="link",
        user=user,
        issued_password_at=int(time.time()),
    )


@app.post("/api/account/google/reauth/start")
async def google_account_reauth_start(
    payload: GoogleReauthStartRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> Response:
    service = google_oauth_service
    config = google_oauth_config
    if service is None or config is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        security = await run_in_threadpool(
            user_store.account_security, user["id"]
        )
    except (SQLAlchemyError, ValueError):
        return _google_oauth_unavailable()
    if security["has_password"] or not security["google_linked"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google account confirmation is not available for this account"
                if payload.purpose == "password_add"
                else "Google reauthentication is not available for this account"
            ),
        )
    if payload.purpose == "password_add":
        await run_in_threadpool(
            _check_google_password_setup_rate, request, user["id"], "start"
        )
    return await _start_account_google_flow(
        request, config, service, purpose=payload.purpose, user=user
    )


@app.post("/api/auth/google/onboarding")
def google_account_onboarding(
    payload: GoogleOnboardingRequest,
    request: Request,
    _csrf=Depends(auth.verify_api_csrf),
) -> Response:
    service = google_oauth_service
    config = google_oauth_config
    if service is None or config is None:
        raise HTTPException(status_code=404, detail="Not found")
    username_error = auth.validate_username(payload.username)
    if username_error:
        raise HTTPException(status_code=400, detail=username_error)
    ip = auth.client_ip(request)
    try:
        if signup_throttle.is_limited(ip):
            raise HTTPException(
                status_code=429,
                detail="Too many sign-ups from this network. Try again later.",
            )
        binding = request.cookies.get(config.browser_cookie_name, "")
        pending = service.consume_pending_signup(binding)
        if (
            not isinstance(pending, dict)
            or pending.get("issuer") != google_oauth.GOOGLE_ISSUER
            or not isinstance(pending.get("subject"), str)
        ):
            raise HTTPException(
                status_code=400, detail="Google sign-up expired; start again"
            )
        email = pending.get("email")
        # Pending email is stored only from a verified Google token. Recheck the
        # current restriction before creation, including after configuration changes.
        try:
            config.require_test_user(email, email_verified=True)
        except google_oauth.GoogleTokenError:
            raise HTTPException(
                status_code=400, detail="Google sign-up could not be completed"
            ) from None
        if email is not None and (
            not isinstance(email, str) or auth.validate_email(email)
        ):
            raise HTTPException(
                status_code=400, detail="Google sign-up could not be completed"
            )
        new_user = user_store.create_google_user(
            payload.username, email, pending["subject"]
        )
        signup_throttle.record_success(ip)
        request.app.state.is_first_account = False
        user = user_store.get_by_id(new_user["id"])
        if user is None:
            return _google_oauth_unavailable()
        session_id = session_store.create(user["id"])
    except HTTPException:
        raise
    except ValueError as exc:
        if not service.store_pending_signup(
            binding,
            {"sub": pending["subject"], "email": pending.get("email"),
             "email_verified": pending.get("email") is not None},
            original_signup=pending,
        ):
            return _google_oauth_unavailable()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (SQLAlchemyError, RuntimeError):
        return _google_oauth_unavailable()
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["sv"] = user["session_version"]
    request.session["sid"] = session_id
    response = RedirectResponse("/", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    _clear_google_browser_cookie(response, config)
    return response


@app.get("/api/auth/google/callback", include_in_schema=False)
async def google_oauth_callback(request: Request) -> Response:
    service = google_oauth_service
    config = google_oauth_config
    if service is None or config is None:
        raise HTTPException(status_code=404, detail="Not found")

    stage = "transaction"
    purpose = "login"

    def failed(*args, **kwargs):
        if purpose in google_oauth.GOOGLE_IDENTITY_CONFIRMATION_PURPOSES:
            google_oauth.log_google_identity_confirmation_failure(stage)
        elif purpose in google_oauth.GOOGLE_REAUTHENTICATION_PURPOSES:
            google_oauth.log_google_reauthentication_failure(stage)
        else:
            google_oauth.local_diagnostic(stage)
        return _google_oauth_failed(*args, **kwargs)

    state = request.query_params.get("state", "")
    browser_binding = request.cookies.get(config.browser_cookie_name, "")
    if not state or not browser_binding:
        google_oauth.log_google_reauthentication_failure("transaction")
        return JSONResponse(
            {"detail": "Google sign-in could not be completed"},
            status_code=400,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )
    try:
        transaction = await service.consume_transaction(state, browser_binding)
    except google_oauth.OAuthBackendUnavailable:
        google_oauth.local_diagnostic(stage + "_unavailable")
        return _google_oauth_unavailable()
    except google_oauth.OAuthTransactionError:
        google_oauth.log_google_reauthentication_failure("transaction")
        return failed(config, clear_browser_binding=False)
    purpose = transaction.get("purpose", "login")

    stage = "authorization_response"
    if request.query_params.get("error") or not request.query_params.get("code"):
        return failed(config, purpose)
    stage = "token_validation"
    try:
        claims = await service.exchange_and_validate(
            request.query_params["code"], transaction
        )
        config.require_test_user(
            claims.get("email"), email_verified=claims.get("email_verified")
        )
    except google_oauth.GoogleTokenError as exc:
        if isinstance(exc, google_oauth.GoogleFreshnessError):
            stage = exc.failure_stage
        return failed(config, purpose)
    except (
        google_oauth.GoogleProviderError,
        google_oauth.OAuthBackendUnavailable,
    ):
        google_oauth.local_diagnostic(stage + "_unavailable")
        return _google_oauth_unavailable()

    stage = "identity_lookup"
    try:
        user_id = await run_in_threadpool(service.lookup_identity, claims)
        if purpose == "signup" and user_id is None:
            if not service.store_pending_signup(browser_binding, claims):
                return failed(config, purpose)
            response = RedirectResponse("/register?google=complete", status_code=303)
            _set_google_browser_cookie(response, config, browser_binding)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        if purpose in {"login", "signup"}:
            if not user_id:
                return failed(config, purpose)
            user = await run_in_threadpool(user_store.get_by_id, user_id)
            if user is None:
                return failed(config, purpose)
            old_session_id = request.session.get("sid")
            if isinstance(old_session_id, str) and old_session_id:
                await run_in_threadpool(session_store.revoke, old_session_id)
            session_id = await run_in_threadpool(session_store.create, user["id"])
            request.session.clear()
            request.session["user_id"] = user["id"]
            request.session["sv"] = user["session_version"]
            request.session["sid"] = session_id
            response = RedirectResponse("/", status_code=303)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            _clear_google_browser_cookie(response, config)
            return response

        stage = "account_session_binding"
        user = current_user_row(request)
        expected_user_id = transaction.get("user_id")
        expected_session_id = transaction.get("session_id")
        expected_version = transaction.get("session_version")
        if (
            user is None
            or user["id"] != expected_user_id
            or request.session.get("sid") != expected_session_id
            or request.session.get("sv") != expected_version
            or (
                purpose == "link"
                and user_id is not None
            )
            or (
                purpose != "link"
                and (not isinstance(user_id, str) or user_id != user["id"])
            )
        ):
            return failed(config, purpose)
        auth_time = None
        identity_verified_at = None
        if purpose not in google_oauth.GOOGLE_IDENTITY_CONFIRMATION_PURPOSES:
            stage = "freshness"
            auth_time = service.require_fresh_authentication(claims)
        if purpose == "link":
            password_verified_at = transaction.get("password_verified_at")
            if (
                not isinstance(password_verified_at, int)
                or isinstance(password_verified_at, bool)
                or time.time() - password_verified_at
                > google_oauth.FRESH_AUTH_MAX_AGE_SECONDS
                or password_verified_at > time.time() + google_oauth.CLOCK_SKEW_SECONDS
            ):
                return failed(config, purpose)
            session_version = await run_in_threadpool(
                user_store.link_google_identity, user["id"], claims["sub"]
            )
            await run_in_threadpool(session_store.revoke_user, user["id"])
            session_id = await run_in_threadpool(session_store.create, user["id"])
            request.session.clear()
            request.session["user_id"] = user["id"]
            request.session["sv"] = session_version
            request.session["sid"] = session_id
            response = RedirectResponse(
                "/?view=account&google_link=success", status_code=303
            )
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            _clear_google_browser_cookie(response, config)
            return response

        if purpose not in {
            "password_add",
            "email_change",
            "account_delete",
            "logout_all",
        }:
            return failed(config, purpose)
        stage = "account_eligibility"
        security = await run_in_threadpool(
            user_store.account_security, user["id"]
        )
        if security["has_password"] or not security["google_linked"]:
            return failed(config, purpose)
        if purpose in google_oauth.GOOGLE_IDENTITY_CONFIRMATION_PURPOSES:
            identity_verified_at = int(time.time())
            proof = {
                "proof_type": "google_identity_assertion",
                "purpose": purpose,
                "user_id": user["id"],
                "session_id": expected_session_id,
                "session_version": expected_version,
                "identity_verified_at": identity_verified_at,
            }
            store_proof = service.store_password_add_identity_proof
            store_args = (expected_session_id, proof)
        else:
            proof = {
                "purpose": purpose,
                "user_id": user["id"],
                "session_id": expected_session_id,
                "session_version": expected_version,
                "auth_time": auth_time,
                "verified_at": int(time.time()),
            }
            store_proof = service.store_reauthentication_proof
            store_args = (expected_session_id, purpose, proof)
        stage = "proof_storage"
        if not await run_in_threadpool(
            store_proof,
            *store_args,
        ):
            return failed(config, purpose)
        response = RedirectResponse(
            f"/?view=account&google_reauth=success&google_action={purpose}",
            status_code=303,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        _clear_google_browser_cookie(response, config)
        return response
    except google_oauth.GoogleTokenError as exc:
        if isinstance(exc, google_oauth.GoogleFreshnessError):
            stage = exc.failure_stage
        return failed(config, purpose)
    except ValueError:
        return failed(config, purpose)
    except (SQLAlchemyError, RuntimeError, google_oauth.OAuthBackendUnavailable):
        google_oauth.local_diagnostic(stage + "_unavailable")
        return _google_oauth_unavailable()
    return failed(config, purpose)


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
    # Allow idempotent logout after the session is already gone, but require
    # CSRF protection before revoking any active session.
    if request.session.get("sid"):
        auth.verify_csrf(request, submitted_token)
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


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class VerifyResetEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


def _password_reset_generic_response() -> dict:
    return {"ok": True, "message": PASSWORD_RESET_GENERIC}


def _email_verification_generic_response() -> dict:
    return {
        "ok": True,
        "message": PASSWORD_RESET_EMAIL_VERIFICATION_GENERIC,
    }


def _check_password_reset_rate_limits(request: Request, email: str) -> None:
    ip = auth.client_ip(request)
    email_key = password_reset.email_rate_key(email)
    try:
        ip_allowed = request_throttle.allow(
            f"password-reset:ip:{ip}",
            PASSWORD_RESET_IP_LIMIT,
            PASSWORD_RESET_WINDOW_SECONDS,
        )
        email_allowed = request_throttle.allow(
            email_key,
            PASSWORD_RESET_EMAIL_LIMIT,
            PASSWORD_RESET_WINDOW_SECONDS,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc
    if not ip_allowed or not email_allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": str(PASSWORD_RESET_WINDOW_SECONDS)},
        )


def _release_token_claim(
    store: password_reset.PasswordResetStore,
    token: str,
    claim: password_reset.TokenClaim,
) -> bool:
    try:
        released = store.release(token, claim)
    except RuntimeError:
        password_reset_logger.warning("password-reset token claim release failed")
        return False
    if not released:
        password_reset_logger.warning("password-reset token claim could not be released")
    return released


def _discard_unsent_token(
    store: password_reset.PasswordResetStore,
    token: str,
) -> None:
    try:
        store.discard(token)
    except RuntimeError:
        password_reset_logger.warning("unsent password-reset token cleanup failed")


@app.post("/api/auth/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    _require_password_recovery_enabled()

    email = (payload.email or "").strip().lower()
    _check_password_reset_rate_limits(request, email)
    validation_error = auth.validate_email(email) if email else "Enter a valid email address"
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    try:
        account = user_store.get_password_reset_account(email)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc
    if account is None:
        auth.verify_password("password-reset-timing-pad", auth._DUMMY_HASH)
        return _password_reset_generic_response()

    user_id, email_verified = account
    try:
        if email_verified:
            token = password_reset_store.issue(user_id)
        else:
            email_digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
            token = email_verification_store.issue(
                user_id,
                binding=email_digest,
            )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc
    if token is None:
        return _password_reset_generic_response()

    try:
        if email_verified:
            email_sender.send_password_reset(to_email=email, token=token)
        else:
            email_sender.send_email_verification(to_email=email, token=token)
    except (email_smtp.SmtpConfigError, email_smtp.SmtpSendError):
        store = password_reset_store if email_verified else email_verification_store
        _discard_unsent_token(store, token)
        return _password_reset_generic_response()

    return _password_reset_generic_response()


@app.post("/api/auth/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    _require_password_recovery_enabled()

    ip = auth.client_ip(request)
    try:
        if not request_throttle.allow(
            f"password-reset:ip:{ip}",
            PASSWORD_RESET_IP_LIMIT,
            PASSWORD_RESET_WINDOW_SECONDS,
        ):
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(PASSWORD_RESET_WINDOW_SECONDS)},
            )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc

    password_error = auth.validate_password(payload.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    try:
        claim = password_reset_store.claim(payload.token)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc
    if claim is None:
        raise HTTPException(
            status_code=400, detail="This reset link is invalid or has expired"
        )

    try:
        user_store.reset_password_and_invalidate_sessions(
            claim.user_id,
            payload.password,
        )
    except ValueError as exc:
        if not _release_token_claim(password_reset_store, payload.token, claim):
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable, try again shortly",
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except auth.PasswordResetCommitUncertain as exc:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable, request a new reset link if needed",
        ) from exc
    except SQLAlchemyError as exc:
        if not _release_token_claim(password_reset_store, payload.token, claim):
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable, request a new reset link if needed",
            ) from exc
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc

    try:
        password_reset_store.commit(payload.token, claim)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable; the reset may have completed",
        ) from exc

    try:
        session_store.revoke_user(claim.user_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc

    # Do not create a new session; user must sign in with the new password.
    if request.session.get("user_id") == claim.user_id:
        request.session.clear()
        auth.get_or_create_csrf_token(request)

    return {
        "ok": True,
        "message": "Your password has been updated. You can log in with your new password.",
    }


@app.post("/api/auth/verify-reset-email")
def verify_reset_email(
    payload: VerifyResetEmailRequest,
    request: Request,
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    _require_password_recovery_enabled()

    ip = auth.client_ip(request)
    try:
        if not request_throttle.allow(
            f"password-reset:ip:{ip}",
            PASSWORD_RESET_IP_LIMIT,
            PASSWORD_RESET_WINDOW_SECONDS,
        ):
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(PASSWORD_RESET_WINDOW_SECONDS)},
            )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc

    try:
        claim = email_verification_store.claim(payload.token)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc
    if claim is None:
        raise HTTPException(
            status_code=400, detail="This verification link is invalid or has expired"
        )
    if (
        claim.binding is None
        or len(claim.binding) != 64
        or any(character not in "0123456789abcdef" for character in claim.binding)
    ):
        if not _release_token_claim(email_verification_store, payload.token, claim):
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable, try again shortly"
            )
        raise HTTPException(
            status_code=400, detail="This verification link is invalid or has expired"
        )

    try:
        user_store.verify_password_reset_email(claim.user_id, claim.binding)
    except ValueError as exc:
        if not _release_token_claim(email_verification_store, payload.token, claim):
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable, try again shortly",
            ) from exc
        raise HTTPException(
            status_code=400, detail="This verification link is invalid or has expired"
        ) from exc
    except auth.PasswordResetCommitUncertain as exc:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable; verification may have completed",
        ) from exc
    except SQLAlchemyError as exc:
        if not _release_token_claim(email_verification_store, payload.token, claim):
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable, try again shortly"
            ) from exc
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc

    try:
        email_verification_store.commit(payload.token, claim)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable; verification may have completed",
        ) from exc

    try:
        token = password_reset_store.issue(claim.user_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc
    if token is None:
        return _email_verification_generic_response()
    try:
        user = user_store.get_by_id(claim.user_id)
        email = user.email if user is not None else None
        if email:
            email_sender.send_password_reset(to_email=email, token=token)
        else:
            _discard_unsent_token(password_reset_store, token)
    except (email_smtp.SmtpConfigError, email_smtp.SmtpSendError):
        _discard_unsent_token(password_reset_store, token)
    except SQLAlchemyError as exc:
        _discard_unsent_token(password_reset_store, token)
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable, try again shortly"
        ) from exc

    return _email_verification_generic_response()


@app.get("/api/me")
def api_me(user=Depends(require_api_user)) -> dict:
    security = user_store.account_security(user["id"])
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        **security,
        "google_oauth_enabled": google_oauth_service is not None,
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
        headers={"Cache-Control": "private, max-age=86400"},
    )


@app.post("/api/account/photo")
@limit_upload_processing
async def upload_account_photo(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(require_api_user),
) -> dict:
    auth.verify_api_csrf(request)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Choose an image file")
    expected_format = _image_upload_format(file.filename or "", IMAGE_UPLOAD_FORMATS)
    photo_data = await file.read(MAX_PROFILE_PHOTO_BYTES + 1)
    if len(photo_data) > MAX_PROFILE_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Profile photo must be 5 MB or smaller")
    photo_mime = await run_in_threadpool(
        _validate_profile_photo, photo_data, expected_format
    )
    await run_in_threadpool(user_store.update_profile_photo, user["id"], photo_data, photo_mime)
    return {"photo_url": "/api/account/photo"}


def _validate_profile_photo(
    photo_data: bytes, expected_format: str | None = None
) -> str:
    try:
        with Image.open(BytesIO(photo_data)) as image:
            width, height = image.size
            if (
                width <= 0
                or height <= 0
                or width > MAX_PROFILE_PHOTO_DIMENSION
                or height > MAX_PROFILE_PHOTO_DIMENSION
                or width * height > MAX_PROFILE_PHOTO_PIXELS
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Profile photo dimensions exceed the configured limit",
                )
            image.verify()
            image_format = (image.format or "").upper()
        # JPEG verify() checks headers, not the compressed pixel stream.
        # Decode it before accepting bytes that browsers may fail to display.
        with Image.open(BytesIO(photo_data)) as image:
            image.load()
            if expected_format is not None and image.format != expected_format:
                raise HTTPException(status_code=400, detail="Image extension does not match its content")
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


class PasskeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PasskeyAuthorizationRequest(PasskeyRequest):
    current_password: str = Field(min_length=1, max_length=128)


class PasskeyRegistrationOptionsRequest(PasskeyRequest):
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class PasskeyRegistrationCompleteRequest(PasskeyRequest):
    authorization_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    challenge_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    response: dict[str, object]


class PasskeyActionIntentRequest(PasskeyRequest):
    action: Literal["password_add", "email_change", "logout_all", "recovery_rotate"]
    new_password: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=320)


class PasskeyAssertionOptionsRequest(PasskeyRequest):
    intent_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class PasskeyAssertionCompleteRequest(PasskeyRequest):
    intent_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    challenge_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    response: dict[str, object]


class PasskeyRecoverySetupRequest(PasskeyRequest):
    intent_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    proof_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class PasskeyRecoveryConsumeRequest(PasskeyRequest):
    code: str = Field(pattern=r"^[0-9a-f]{64}$")


def _passkey_security_status(user: User) -> dict[str, object]:
    try:
        security = user_store.account_security(user["id"])
        with tenant_session(user["id"]) as session:
            active_credentials = session.scalar(
                select(func.count())
                .select_from(passkey_schema.credentials)
                .where(
                    passkey_schema.credentials.c.user_id == user["id"],
                    passkey_schema.credentials.c.revoked_at.is_(None),
                )
            ) or 0
            recovery_codes = session.scalar(
                select(func.count())
                .select_from(passkey_schema.recovery_codes)
                .where(
                    passkey_schema.recovery_codes.c.user_id == user["id"],
                    passkey_schema.recovery_codes.c.consumed_at.is_(None),
                )
            ) or 0
    except (SQLAlchemyError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="Security status temporarily unavailable"
        ) from exc
    return {
        "has_password": security["has_password"],
        "google_linked": security["google_linked"],
        "passkey_count": active_credentials,
        "recovery_codes_remaining": recovery_codes,
    }


@app.get("/api/account/security-methods")
def account_security_methods(
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, object]:
    _passkey_services()
    binding = _passkey_binding(request, user, "passkey_add")
    _check_passkey_rate(request, binding, "security-methods")
    return _passkey_security_status(user)


@app.get("/api/account/passkeys/enrollment-eligibility")
def passkey_enrollment_eligibility(
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, object]:
    _passkey_services()
    binding = _passkey_binding(request, user, "passkey_add")
    _check_passkey_rate(request, binding, "enrollment-eligibility")
    status = _passkey_security_status(user)
    if not status["has_password"]:
        return {
            "eligible": False,
            "reason": "password_verification_required",
            "passkey_count": status["passkey_count"],
        }
    if status["passkey_count"] >= 10:
        return {
            "eligible": False,
            "reason": "credential_limit_reached",
            "passkey_count": status["passkey_count"],
        }
    return {
        "eligible": True,
        "reason": None,
        "passkey_count": status["passkey_count"],
    }


@app.post("/api/account/passkeys/registration/authorize")
def authorize_passkey_registration(
    payload: PasskeyAuthorizationRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, str]:
    _assertions, registration, _recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, "passkey_add")
    _check_passkey_rate(request, binding, "registration-authorize")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            authorization_id = registration.authorize_password(
                session, binding, payload.current_password
            )
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except RuntimeError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"authorization_id": authorization_id}


@app.post("/api/account/passkeys/registration/options")
def passkey_registration_options(
    payload: PasskeyRegistrationOptionsRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, object]:
    _assertions, registration, _recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, "passkey_add")
    _check_passkey_rate(request, binding, "registration-options")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            challenge_id, options = registration.begin(
                session, binding, payload.authorization_id
            )
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except RuntimeError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"challenge_id": challenge_id, "options": options}


@app.post("/api/account/passkeys/registration/complete")
def complete_passkey_registration(
    payload: PasskeyRegistrationCompleteRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, bool]:
    _assertions, registration, _recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, "passkey_add")
    _check_passkey_rate(request, binding, "registration-complete")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            registration.finish(
                session,
                binding,
                payload.authorization_id,
                payload.challenge_id,
                payload.response,
            )
            account = session.scalar(
                select(User).where(User.id == user["id"]).with_for_update()
            )
            if account is None:
                raise passkeys.PasskeyError("Account is unavailable")
            account.session_version += 1
            session_version = account.session_version
            session.flush()
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except RuntimeError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    rotate_authenticated_session(request, user["id"], session_version)
    log.info("WebAuthn credential enrolled", extra={"user_id": user["id"]})
    return {"registered": True}


def _passkey_action_digest(user_id: str, action: str, payload: str = "") -> str:
    message = (
        "vervfy:passkey-action:v1\0"
        + user_id
        + "\0"
        + action
        + "\0"
        + payload
    ).encode()
    return hmac.new(SESSION_SECRET.encode(), message, hashlib.sha256).hexdigest()


@app.post("/api/account/passkeys/action-intents")
def prepare_passkey_action_intent(
    payload: PasskeyActionIntentRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, str]:
    _assertions, _registration, _recovery, _limiter = _passkey_services()
    action = payload.action
    normalized_email = None
    if action == "password_add":
        if payload.new_password is None or payload.email is not None:
            raise HTTPException(status_code=400, detail="Invalid action payload")
        if user["password_hash"] is not None:
            raise HTTPException(status_code=409, detail="Password is already set")
        error = auth.validate_password(payload.new_password)
        if error:
            raise HTTPException(status_code=400, detail=error)
        canonical_payload = payload.new_password
    elif action == "email_change":
        if payload.email is None or payload.new_password is not None:
            raise HTTPException(status_code=400, detail="Invalid action payload")
        normalized_email = payload.email.strip().lower() or None
        if normalized_email is not None and auth.validate_email(normalized_email):
            raise HTTPException(status_code=400, detail="Invalid email")
        canonical_payload = normalized_email or ""
    else:
        if payload.email is not None or payload.new_password is not None:
            raise HTTPException(status_code=400, detail="Invalid action payload")
        canonical_payload = ""

    binding = _passkey_binding(request, user, action)
    _check_passkey_rate(request, binding, "action-intent")
    digest = (
        passkey_enrollment.RECOVERY_DIGEST
        if action == "recovery_rotate"
        else _passkey_action_digest(user["id"], action, canonical_payload)
    )
    try:
        with tenant_session(user["id"]) as session, session.begin():
            active_count = session.scalar(
                select(func.count())
                .select_from(passkey_schema.credentials)
                .where(
                    passkey_schema.credentials.c.user_id == user["id"],
                    passkey_schema.credentials.c.revoked_at.is_(None),
                )
            ) or 0
            if not active_count:
                raise HTTPException(
                    status_code=403, detail="An enrolled passkey is required"
                )
            if action == "recovery_rotate":
                existing_codes = session.scalar(
                    select(func.count())
                    .select_from(passkey_schema.recovery_codes)
                    .where(passkey_schema.recovery_codes.c.user_id == user["id"])
                ) or 0
                if existing_codes:
                    raise HTTPException(
                        status_code=409, detail="Recovery-code rotation is unavailable"
                    )
            intent_id = passkeys.create_intent(session, binding, digest)
    except HTTPException:
        raise
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"intent_id": intent_id}


@app.post("/api/account/passkeys/actions/{action}/options")
def passkey_assertion_options(
    action: Literal["password_add", "email_change", "logout_all", "recovery_rotate"],
    payload: PasskeyAssertionOptionsRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, object]:
    assertions, _registration, _recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, action)
    _check_passkey_rate(request, binding, "assertion-options")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            challenge_id, options = assertions.begin(
                session, binding, payload.intent_id
            )
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"challenge_id": challenge_id, "options": options}


@app.post("/api/account/passkeys/actions/{action}/complete")
def complete_passkey_assertion(
    action: Literal["password_add", "email_change", "logout_all", "recovery_rotate"],
    payload: PasskeyAssertionCompleteRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, str]:
    assertions, _registration, _recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, action)
    _check_passkey_rate(request, binding, "assertion-complete")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            proof_id = assertions.finish(
                session,
                binding,
                payload.intent_id,
                payload.challenge_id,
                payload.response,
            )
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"proof_id": proof_id}


@app.post("/api/account/passkeys/recovery/codes")
def setup_passkey_recovery_codes(
    payload: PasskeyRecoverySetupRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, list[str]]:
    _assertions, _registration, recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, "recovery_rotate")
    _check_passkey_rate(request, binding, "recovery-setup")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            codes = recovery.issue_initial(
                session, binding, payload.intent_id, payload.proof_id
            )
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"recovery_codes": codes}


@app.post("/api/account/passkeys/recovery/consume")
def consume_passkey_recovery_code(
    payload: PasskeyRecoveryConsumeRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict[str, object]:
    _assertions, _registration, recovery, _limiter = _passkey_services()
    binding = _passkey_binding(request, user, "recovery_rotate")
    _check_passkey_rate(request, binding, "recovery-consume")
    try:
        with tenant_session(user["id"]) as session, session.begin():
            recovery.consume(session, binding, payload.code)
    except passkeys.PasskeyError as exc:
        raise _passkey_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Passkey service temporarily unavailable"
        ) from None
    return {"status": "pending", "capabilities": []}


class PasswordChangeRequest(BaseModel):
    current_password: str | None = None
    new_password: str
    passkey_intent_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    passkey_proof_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")


class EmailChangeRequest(BaseModel):
    email: str = Field(max_length=320)
    current_password: str | None = None
    passkey_intent_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    passkey_proof_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")


class AccountDeletionRequest(BaseModel):
    current_password: str | None = None
    confirmation: str


class LogoutAllRequest(BaseModel):
    current_password: str | None = None
    passkey_intent_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    passkey_proof_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")


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


class TrackListenRequest(BaseModel):
    track_id: SafeId = Field(alias="trackId")


def _queue_staged_upload(
    job_id: str,
    user_id: str,
    filename: str,
    audio_path: str,
) -> None:
    try:
        staging_path = storage_lifecycle.upload_file(
            user_id,
            "staged-audio",
            audio_path,
            audio_store.guess_content_type(filename),
            os.path.splitext(filename)[1].lower().lstrip("."),
        )
        with tenant_session(user_id) as session:
            storage_lifecycle.bound_transaction(session)
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
                storage_lifecycle.bound_transaction(session)
                job = session.get(UploadJob, job_id)
                if job:
                    job.status = "failed"
                    job.error = "Upload could not be added to the processing queue."
                    job.storage_path = None
                    session.commit()
        except Exception:
            log.exception("could not mark staged upload as failed")
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
         "trackIds": [item.track_id for item in playlist.tracks],
         "lastPlayedAt": playlist.last_played_at}
        for playlist in playlists
    ]}


def _library_state(user_id: str) -> dict:
    with tenant_session(user_id) as session:
        return _library_state_from_session(user_id, session)


def _listening_period_summary(
    session,
    user_id: str,
    start: float,
    end: float | None = None,
    end_inclusive: bool = False,
) -> dict:
    listen_period = [
        TrackListen.user_id == user_id,
        TrackListen.played_at >= start,
    ]
    if end is not None:
        listen_period.append(
            TrackListen.played_at <= end
            if end_inclusive
            else TrackListen.played_at < end
        )
    rows = session.execute(
        select(
            TrackListen.track_id,
            TrackRecord.artist,
            func.count(TrackListen.id),
        )
        .join(
            TrackRecord,
            (TrackRecord.id == TrackListen.track_id)
            & (TrackRecord.user_id == TrackListen.user_id),
        )
        .where(*listen_period)
        .group_by(TrackListen.track_id, TrackRecord.artist)
        .order_by(func.count(TrackListen.id).desc())
    ).all()
    artist_counts: dict[str, dict[str, object]] = {}
    for _, artist, count in rows:
        key = artist.strip().casefold()
        entry = artist_counts.setdefault(key, {"artist": artist.strip(), "playCount": 0})
        entry["playCount"] = int(entry["playCount"]) + count
    return {
        "playCount": sum(count for _, _, count in rows),
        "topTracks": [
            {"trackId": track_id, "playCount": count}
            for track_id, _, count in rows[:5]
        ],
        "topArtists": sorted(
            artist_counts.values(),
            key=lambda item: int(item["playCount"]),
            reverse=True,
        )[:5],
    }


def _listening_summary(user_id: str) -> dict:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (
        month_start.replace(year=month_start.year - 1, month=12)
        if month_start.month == 1
        else month_start.replace(month=month_start.month - 1)
    )
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    as_of = now.timestamp()
    with tenant_session(user_id) as session:
        last_played = session.execute(
            select(TrackListen.track_id, func.max(TrackListen.played_at))
            .where(TrackListen.user_id == user_id)
            .group_by(TrackListen.track_id)
        ).all()
        return {
            "lastPlayedAt": {track_id: played_at for track_id, played_at in last_played},
            "month": _listening_period_summary(
                session, user_id, month_start.timestamp(), as_of, end_inclusive=True
            ),
            "previousMonth": _listening_period_summary(
                session,
                user_id,
                previous_month_start.timestamp(),
                month_start.timestamp(),
            ),
            "year": _listening_period_summary(
                session, user_id, year_start.timestamp(), as_of, end_inclusive=True
            ),
            "monthStart": month_start.timestamp(),
            "previousMonthStart": previous_month_start.timestamp(),
            "yearLabel": str(now.year),
            "asOf": as_of,
        }


def _library_state_etag(state: dict) -> str:
    canonical = {
        "favorites": sorted(state["favorites"]),
        "playlists": [
            {
                "id": playlist["id"],
                "name": playlist["name"],
                "trackIds": playlist["trackIds"],
            }
            for playlist in state["playlists"]
        ],
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f'"{digest}"'


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


def verify_google_action_proof(
    request: Request, user: User, purpose: str
) -> None:
    identity_confirmation = (
        purpose in google_oauth.GOOGLE_IDENTITY_CONFIRMATION_PURPOSES
    )
    failure_detail = (
        "Google account confirmation expired. Verify again."
        if identity_confirmation
        else "Recent Google verification required"
    )
    service = google_oauth_service
    session_id = request.session.get("sid")
    session_version = request.session.get("sv")
    if (
        service is None
        or not isinstance(session_id, str)
        or not session_id
        or not isinstance(session_version, int)
        or isinstance(session_version, bool)
        or session_version != user["session_version"]
    ):
        raise HTTPException(status_code=403, detail=failure_detail)
    try:
        if identity_confirmation:
            proof = service.consume_password_add_identity_proof(session_id)
        else:
            proof = service.consume_reauthentication_proof(session_id, purpose)
    except google_oauth.OAuthBackendUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Authentication service temporarily unavailable"
        ) from exc
    if not isinstance(proof, dict):
        raise HTTPException(status_code=403, detail=failure_detail)
    now = int(time.time())
    verified_at = (
        proof.get("identity_verified_at")
        if identity_confirmation
        else proof.get("verified_at")
    )
    if (
        proof.get("purpose") != purpose
        or proof.get("user_id") != user["id"]
        or proof.get("session_id") != session_id
        or proof.get("session_version") != session_version
        or isinstance(verified_at, bool)
        or not isinstance(verified_at, int)
        or now - verified_at > google_oauth.CREDENTIAL_PROOF_TTL_SECONDS
        or verified_at > now + google_oauth.CLOCK_SKEW_SECONDS
        or (
            identity_confirmation
            and proof.get("proof_type") != "google_identity_assertion"
        )
        or (
            not identity_confirmation
            and (
                isinstance(proof.get("auth_time"), bool)
                or not isinstance(proof.get("auth_time"), int)
                or now - proof["auth_time"]
                > google_oauth.FRESH_AUTH_MAX_AGE_SECONDS
                or proof["auth_time"]
                > now + google_oauth.CLOCK_SKEW_SECONDS
            )
        )
    ):
        raise HTTPException(status_code=403, detail=failure_detail)


def verify_account_action(
    request: Request,
    user: User,
    purpose: str,
    current_password: str | None,
) -> None:
    if user["password_hash"] is not None:
        if not current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        verify_current_password(user, current_password)
        return
    try:
        security = user_store.account_security(user["id"])
    except (SQLAlchemyError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="Authentication service temporarily unavailable"
        ) from exc
    if not security["google_linked"]:
        raise HTTPException(status_code=403, detail="A usable sign-in method is required")
    verify_google_action_proof(request, user, purpose)


def _require_passkey_proof_pair(intent_id: str | None, proof_id: str | None) -> bool:
    if bool(intent_id) != bool(proof_id):
        raise HTTPException(status_code=400, detail="Both passkey proof identifiers are required")
    return bool(intent_id and proof_id)


def _consume_passkey_proof(
    session,
    binding: passkeys.Binding,
    intent_id: str,
    proof_id: str,
    digest: str,
) -> None:
    passkeys.consume_proof(session, binding, intent_id, proof_id, digest)


def rotate_authenticated_session(
    request: Request, user_id: str, session_version: int
) -> None:
    # The committed version invalidates old cookies even if Redis is unavailable.
    request.session.clear()
    try:
        session_store.revoke_user(user_id)
        session_id = session_store.create(user_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Account updated, but session rotation failed; sign in again",
        ) from exc
    request.session.clear()
    request.session["user_id"] = user_id
    request.session["sv"] = session_version
    request.session["sid"] = session_id
    auth.get_or_create_csrf_token(request)


@app.put("/api/account/email")
def change_account_email(
    payload: EmailChangeRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    passkey_proof = _require_passkey_proof_pair(
        payload.passkey_intent_id, payload.passkey_proof_id
    )
    if not passkey_proof:
        verify_account_action(
            request, user, "email_change", payload.current_password
        )
    email = payload.email.strip().lower()
    if email:
        error = auth.validate_email(email)
        if error:
            raise HTTPException(status_code=400, detail=error)
    if passkey_proof:
        _passkey_services()
        binding = _passkey_binding(request, user, "email_change")
        _check_passkey_rate(request, binding, "email-change")
        digest = _passkey_action_digest(user["id"], "email_change", email or "")
        try:
            with tenant_session(user["id"]) as session, session.begin():
                _consume_passkey_proof(
                    session,
                    binding,
                    payload.passkey_intent_id,
                    payload.passkey_proof_id,
                    digest,
                )
                session_version = account_transactions.change_email(
                    session, binding, email
                )
        except passkeys.PasskeyError as exc:
            raise HTTPException(
                status_code=403, detail="Passkey proof is invalid or expired"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="That email is already in use") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="Account update temporarily unavailable"
            ) from exc
    else:
        try:
            session_version = user_store.update_email(user["id"], email or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    rotate_authenticated_session(request, user["id"], session_version)
    return {"email": email or None}


@app.post("/api/account/password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    purpose = (
        "password_add"
        if user["password_hash"] is None
        else "password_change"
    )
    passkey_proof = _require_passkey_proof_pair(
        payload.passkey_intent_id, payload.passkey_proof_id
    )
    if passkey_proof and purpose != "password_add":
        raise HTTPException(
            status_code=400, detail="Passkey proof does not authorize this action"
        )
    if purpose == "password_add" and not passkey_proof:
        _check_google_password_setup_rate(request, user["id"], "submit")
    if not passkey_proof:
        verify_account_action(
            request, user, purpose, payload.current_password
        )
    error = auth.validate_password(payload.new_password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if passkey_proof:
        _passkey_services()
        binding = _passkey_binding(request, user, "password_add")
        _check_passkey_rate(request, binding, "password-add")
        digest = _passkey_action_digest(
            user["id"], "password_add", payload.new_password
        )
        try:
            with tenant_session(user["id"]) as session, session.begin():
                _consume_passkey_proof(
                    session,
                    binding,
                    payload.passkey_intent_id,
                    payload.passkey_proof_id,
                    digest,
                )
                session_version = account_transactions.set_password(
                    session,
                    binding,
                    payload.new_password,
                    expected_password_hash=None,
                )
        except passkeys.PasskeyError as exc:
            raise HTTPException(
                status_code=403, detail="Passkey proof is invalid or expired"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="Account update temporarily unavailable"
            ) from exc
    else:
        try:
            session_version = user_store.set_password_and_bump_version(
                user["id"],
                auth.hash_password(payload.new_password),
                expected_password_hash=user["password_hash"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    rotate_authenticated_session(request, user["id"], session_version)
    return {"ok": True}


@app.post("/api/account/logout-all")
def logout_all(
    payload: LogoutAllRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    passkey_proof = _require_passkey_proof_pair(
        payload.passkey_intent_id, payload.passkey_proof_id
    )
    if passkey_proof:
        _passkey_services()
        binding = _passkey_binding(request, user, "logout_all")
        _check_passkey_rate(request, binding, "logout-all")
        digest = _passkey_action_digest(user["id"], "logout_all")
        try:
            with tenant_session(user["id"]) as session, session.begin():
                _consume_passkey_proof(
                    session,
                    binding,
                    payload.passkey_intent_id,
                    payload.passkey_proof_id,
                    digest,
                )
                account_transactions.bump_logout_version(session, binding)
        except passkeys.PasskeyError as exc:
            raise HTTPException(
                status_code=403, detail="Passkey proof is invalid or expired"
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="Account update temporarily unavailable"
            ) from exc
    else:
        verify_account_action(
            request, user, "logout_all", payload.current_password
        )
        user_store.bump_session_version(user["id"])
    request.session.clear()
    try:
        session_store.revoke_user(user["id"])
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Could not revoke all account sessions"
        ) from exc
    request.session.clear()
    return {"ok": True}


@app.delete("/api/account/google")
def unlink_google_account(
    payload: GoogleUnlinkRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    verify_current_password(user, payload.current_password)
    try:
        session_version = user_store.unlink_google_identity(user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    rotate_authenticated_session(request, user["id"], session_version)
    return {"google_linked": False}


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
    verify_account_action(
        request, user, "account_delete", payload.current_password
    )
    try:
        user_store.bump_session_version(user["id"])
        session_store.revoke_user(user["id"])
    except (RuntimeError, SQLAlchemyError) as exc:
        log.exception("could not revoke account sessions before deletion")
        raise HTTPException(
            status_code=503,
            detail=(
                "Account sessions could not be revoked; deletion was not completed. "
                "Sign in again and retry"
            ),
        ) from exc
    try:
        with tenant_session(user["id"]) as session:
            storage_lifecycle.bound_transaction(session)
            owner_id = session.scalar(
                select(User.id).where(User.id == user["id"]).with_for_update()
            )
            if owner_id is None:
                raise HTTPException(status_code=404, detail="Account not found")
            playlist_ids = select(Playlist.id).where(Playlist.user_id == user["id"])
            session.query(PlaylistTrack).filter(
                PlaylistTrack.playlist_id.in_(playlist_ids)
            ).delete(synchronize_session=False)
            session.query(Favorite).filter_by(user_id=user["id"]).delete(
                synchronize_session=False
            )
            session.query(TrackListen).filter_by(user_id=user["id"]).delete(
                synchronize_session=False
            )
            session.query(ArtistPhoto).filter_by(user_id=user["id"]).delete(
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
            session.query(ProviderIdentity).filter_by(user_id=user["id"]).delete(
                synchronize_session=False
            )
            session.query(User).filter_by(id=user["id"]).delete(
                synchronize_session=False
            )
            session.commit()
    except SQLAlchemyError as exc:
        log.exception("could not delete account database records")
        raise HTTPException(
            status_code=503,
            detail=(
                "Account records could not be confirmed deleted; sign in again "
                "and retry deletion"
            ),
        ) from exc
    _libraries.pop(user["id"], None)
    request.session.clear()
    try:
        request.app.state.is_first_account = user_store.count() == 0
    except SQLAlchemyError:
        request.app.state.is_first_account = False
        log.exception("could not refresh first-account state after account deletion")
    return {"ok": True, "storage_cleanup": "pending"}


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


@app.get("/api/library/listening")
def get_listening_summary(user=Depends(require_api_user)) -> dict:
    return _listening_summary(user["id"])


@app.post("/api/library/listening")
def record_track_listen(
    payload: TrackListenRequest,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    with tenant_session(user["id"]) as session:
        track_exists = session.scalar(
            select(TrackRecord.id).where(
                TrackRecord.user_id == user["id"],
                TrackRecord.id == payload.track_id,
            )
        )
        if track_exists is None:
            raise HTTPException(status_code=404, detail="Track not found")
        played_at = time.time()
        session.add(
            TrackListen(
                id=uuid.uuid4().hex,
                user_id=user["id"],
                track_id=payload.track_id,
                played_at=played_at,
            )
        )
        session.commit()
    return {"trackId": payload.track_id, "playedAt": played_at}


@app.post("/api/library/playlists/{playlist_id}/listening")
def record_playlist_listen(
    playlist_id: SafeId,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    with tenant_session(user["id"]) as session:
        playlist = session.scalar(
            select(Playlist).where(
                Playlist.user_id == user["id"],
                Playlist.id == playlist_id,
            )
        )
        if playlist is None:
            raise HTTPException(status_code=404, detail="Playlist not found")
        played_at = max(time.time(), playlist.last_played_at or 0.0)
        playlist.last_played_at = played_at
        session.commit()
    return {"playlistId": playlist_id, "lastPlayedAt": played_at}


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
    language: ArtistProfileLanguage = "en",
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
            signed_url = audio_store.create_signed_url(
                storage_path, expires_in=7 * 24 * 60 * 60
            )
        except audio_store.StorageError as exc:
            log.error("Could not create artist image URL: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Artist image storage is temporarily unavailable",
            ) from exc
        return RedirectResponse(
            signed_url,
            status_code=307,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    data = photo.get("jpeg_data")
    if not isinstance(data, bytes):
        raise HTTPException(status_code=404, detail="No artist photo")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=86400",
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
    expected_format = _image_upload_format(
        file.filename or "", STATIC_IMAGE_UPLOAD_FORMATS
    )
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
            _normalize_artist_photo, bytes(data), expected_format
        )
    finally:
        await file.close()
    storage_path = None
    if audio_store.enabled():
        try:
            storage_path = await run_in_threadpool(
                storage_lifecycle.upload_bytes,
                user["id"],
                "artist-photo",
                jpeg_data,
            )
        except (audio_store.StorageError, SQLAlchemyError) as exc:
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
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="Artist image storage is temporarily unavailable"
        ) from exc
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
    _delete_artist_photo(user["id"], normalized_name)
    return {"photo_url": None}


@app.get("/api/config")
def public_config() -> dict:
    """Expose only frontend-safe feature flags."""
    enabled = os.environ.get("LYRICS_PROVIDER_LRCLIB", "1").strip().lower()
    return {
        "lyrics_provider_lrclib": enabled not in {"0", "false", "off", "no"},
        "google_oauth_enabled": google_oauth_service is not None,
    }


@app.get("/api/lyrics/authorize")
def authorize_lyrics_lookup(user: Annotated[User, Depends(require_api_user)]) -> Response:
    """Reuse the session and distributed limiter for the Next.js lyrics proxy."""
    if not public_config()["lyrics_provider_lrclib"]:
        raise HTTPException(status_code=403, detail="Lyrics lookup is disabled")
    try:
        allowed = request_throttle.allow(f"lyrics:{user['id']}", 60, 60)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Rate-limit service unavailable") from None
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many lyrics lookups", headers={"Retry-After": "60"})
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


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
        is_pending = False
        if missing:
            is_pending = bool(
                schedule_cover_resolution(
                    background_tasks,
                    user["id"],
                    track.id,
                    lookup_audiodb=audiodb_queue.lookup_track_cover,
                    prefer_audiodb=True,
                )
            )
        pending = pending or is_pending
        results[track.id] = {
            "cover_url": track.cover_url or f"/api/tracks/{track.id}/cover",
            "cover_source": track.cover_source,
            "status": "pending" if is_pending else "found",
            "pending": is_pending,
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
    filename = os.path.basename(file.filename.replace("\\", "/"))
    filename = "".join(char for char in filename if ord(char) >= 32 and ord(char) != 127)
    suffix = os.path.splitext(filename)[1].lower()
    if (
        not filename
        or len(filename) > 512
        or suffix not in AUDIO_EXTENSIONS
        or _has_executable_upload_suffix(filename)
    ):
        raise HTTPException(status_code=400, detail="Unsupported audio filename or format")
    total_bytes = 0
    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False
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
            # Use the same content parser as synchronous uploads before any
            # untrusted bytes enter durable staging storage.
            metadata = await run_in_threadpool(library._read_metadata_path, filename, audio_path)
            if metadata is None:
                raise HTTPException(status_code=400, detail="Could not read uploaded audio file")
        _, used_bytes, track_count, existing = await run_in_threadpool(
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
        if async_uploads:
            job_id = uuid.uuid4().hex
            await run_in_threadpool(_queue_staged_upload, job_id, user["id"], filename, audio_path)
            return {"id": job_id, "status": "processing"}
        try:
            track = await run_in_threadpool(
                library.add_upload_file,
                filename,
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
        except audio_store.StorageError:
            log.exception("audio storage failed during upload")
            raise HTTPException(
                status_code=502, detail="Audio storage is temporarily unavailable"
            ) from None
        if track is None:
            raise HTTPException(
                status_code=400, detail="Could not read uploaded audio file"
            )
        schedule_cover_resolution(
            background_tasks,
            user["id"],
            track.id,
            lookup_audiodb=audiodb_queue.lookup_track_cover,
            prefer_audiodb=True,
        )
        return _track_payload(track)
    finally:
        await file.close()
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


def _normalize_track_cover(
    data: bytes, expected_format: str | None = None
) -> bytes:
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(
                    status_code=400,
                    detail="Cover must be a JPEG, PNG, or WebP image",
                )
            if expected_format is not None and image.format != expected_format:
                raise HTTPException(status_code=400, detail="Image extension does not match its content")
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
            signed_url = audio_store.create_signed_url(
                storage_path, expires_in=7 * 24 * 60 * 60
            )
        except audio_store.StorageError as exc:
            log.exception("track cover storage URL creation failed")
            raise HTTPException(
                status_code=502, detail="Cover storage is unavailable"
            ) from exc
        return RedirectResponse(
            signed_url,
            status_code=307,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    payload = library.cover_jpeg(track_id, size)
    return Response(
        content=payload,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=86400",
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
    expected_format = _image_upload_format(
        file.filename or "", STATIC_IMAGE_UPLOAD_FORMATS
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
        cover = await run_in_threadpool(
            _normalize_track_cover, bytes(data), expected_format
        )
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
        background_tasks,
        user["id"],
        track_id,
        force=True,
        lookup_audiodb=audiodb_queue.lookup_track_cover,
        prefer_audiodb=True,
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
def track_stream(track_id: str, user=Depends(require_api_user)) -> Response:
    library = get_library(user["id"])
    info = library.audio_info(track_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Track not found")
    try:
        storage_path = info.storage_path or library.ensure_audio_storage(track_id)
        if not storage_path:
            raise HTTPException(status_code=404, detail="Track not found")
        signed_url = audio_store.create_signed_url(storage_path)
    except AudioUnavailableError:
        raise HTTPException(status_code=404, detail="Track audio not found") from None
    except audio_store.StorageError as exc:
        log.exception("audio storage migration or URL creation failed for %s", track_id)
        raise HTTPException(
            status_code=502, detail="Audio storage is unavailable"
        ) from exc
    return RedirectResponse(
        signed_url,
        status_code=302,
        headers={"Cache-Control": "private, no-store"},
    )
