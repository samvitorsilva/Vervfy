#!/usr/bin/env python3
"""Vervfy — local music player server."""

from __future__ import annotations

from email.message import EmailMessage
from database import Base, engine


from io import BytesIO
from html import escape as html_escape
import smtplib
import ssl
import json
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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool

import audio_store
import auth
from db import Favorite, Playlist, PlaylistTrack, SessionLocal, TrackRecord, UploadJob, User, tenant_session
from library import Library, UploadQuotaExceeded, track_id_for_bytes
import upload_queue

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
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
    # CORS only — never use this value as an auth redirect Location (open
    # redirect / broken static hosts caused post-login 404s).
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:8000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

UPLOADS_PER_10MIN = int(os.environ.get("VERVFY_UPLOADS_PER_10MIN", "60"))


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
        elif path in {"/login", "/register", "/forgot-password", "/reset-password", "/verify-email"}:
            try:
                allowed = request_throttle.allow(
                    f"auth:{auth.client_ip(request)}:{path}", 30, 15 * 60
                )
            except RuntimeError:
                return Response("Rate-limit service unavailable", status_code=503)
            if not allowed:
                return Response("Too many requests", status_code=429, headers={"Retry-After": "900"})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
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

templates = Jinja2Templates(directory=str(ROOT / "templates"))
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

_libraries: dict[str, Library] = {}
def _artist_search_key(name: str) -> str:
    """Normalize names before comparing a public catalog search result."""
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return "".join(c.lower() for c in normalized if c.isalnum())


# These entries are deliberately small.  General music catalogs are useful for
# discovery, but an exact name match is not enough to establish an artist's
# identity (especially for short, stylised, or shared names).  Each profile
# below was checked against an authoritative, artist-specific source and is
# used before a catalog lookup. Do not add an entry without a source that
# unambiguously identifies the performer.
_VERIFIED_ARTIST_PROFILES: dict[str, dict[str, str]] = {
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
    profile = _VERIFIED_ARTIST_PROFILES.get(_artist_search_key(name.strip()))
    return profile.copy() if profile else None


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


def _lookup_artist_photo(name: str) -> str | None:
    """Return a portrait only when the artist identity has been explicitly verified."""
    key = _artist_search_key(name)
    if not key:
        return None
    return _VERIFIED_ARTIST_PHOTOS.get(key)


def _lookup_artist_profile(name: str) -> dict[str, str] | None:
    """Return only manually identity-checked details; never guess from a name search."""
    return _verified_artist_profile(name)


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


class LoginRequired(Exception):
    """Raised by HTML page deps so we can return a real redirect, not JSON."""


@app.exception_handler(LoginRequired)
async def _login_required_handler(request: Request, exc: LoginRequired) -> RedirectResponse:
    del request, exc
    return RedirectResponse("/login", status_code=303)


def require_page_user(request: Request):
    """For HTML page routes: bounce to /login instead of a bare 401."""
    row = current_user_row(request)
    if row is None:
        raise LoginRequired()
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request, user=Depends(require_page_user)) -> HTMLResponse:
    del user
    page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    page = page.replace("__CSRF_TOKEN__", auth.get_or_create_csrf_token(request))
    page = page.replace("__API_BASE__", html_escape(str(request.base_url).rstrip("/"), quote=True))
    return HTMLResponse(
        page,
        headers={"Cache-Control": "no-store"},
    )


# ------------------------------------------------------------------ accounts

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    if current_user_row(request) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"csrf_token": auth.get_or_create_csrf_token(request)},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    auth.verify_csrf(request, csrf_token)
    ip = auth.client_ip(request)

    def fail(message: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "csrf_token": auth.get_or_create_csrf_token(request),
                "error": message,
                "username": username,
            },
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    if login_throttle.is_locked(ip, username):
        return fail("Too many attempts. Please wait a few minutes and try again.")

    row = user_store.get_by_username(username)
    password_matches = (
        auth.verify_password(password, row["password_hash"])
        if row is not None
        else auth.verify_password(password, auth._DUMMY_HASH)
    )
    if row is None or not password_matches:
        login_throttle.record_failure(ip, username)
        return fail("Incorrect username or password")

    login_throttle.clear(ip, username)
    request.session.clear()
    request.session["user_id"] = row["id"]
    request.session["sv"] = row["session_version"]
    return RedirectResponse("/", status_code=303)


def _account_token_serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(app.state.session_secret, salt=salt)


def _send_account_email(recipient: str, subject: str, body: str) -> None:
    host = os.environ.get("VERVFY_SMTP_HOST", "").strip()
    sender = os.environ.get("VERVFY_EMAIL_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("Account email delivery is not configured")
    port = int(os.environ.get("VERVFY_SMTP_PORT", "587"))
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as smtp:
            username = os.environ.get("VERVFY_SMTP_USERNAME")
            password = os.environ.get("VERVFY_SMTP_PASSWORD")
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            username = os.environ.get("VERVFY_SMTP_USERNAME")
            password = os.environ.get("VERVFY_SMTP_PASSWORD")
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)


def _account_link(request: Request, path: str, token: str) -> str:
    public_url = os.environ.get("VERVFY_PUBLIC_URL", "").strip()
    if is_production and not public_url:
        raise RuntimeError("VERVFY_PUBLIC_URL is required for account email links")
    base_url = public_url or str(request.base_url)
    parsed = urlsplit(base_url)
    if (
        not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment
        or (is_production and parsed.scheme != "https")
    ):
        raise RuntimeError("VERVFY_PUBLIC_URL must be a valid HTTPS application origin")
    return f"{base_url.rstrip('/')}{path}?token={quote(token, safe='')}"


def _render_password_reset(request: Request, token: str, error: str | None = None, success: bool = False):
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "csrf_token": auth.get_or_create_csrf_token(request),
            "token": token,
            "error": error,
            "success": success,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return templates.TemplateResponse(
        request, "forgot_password.html",
        {"csrf_token": auth.get_or_create_csrf_token(request)},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    csrf_token: str = Form(...),
):
    auth.verify_csrf(request, csrf_token)
    try:
        allowed = request_throttle.allow(
            f"password-reset:{auth.client_ip(request)}", 5, 15 * 60
        )
    except RuntimeError:
        return Response("Password recovery is temporarily unavailable.", status_code=503)
    if allowed:
        normalized_email = email.strip().lower()
        email_limit_key = hashlib.sha256(
            f"{SESSION_SECRET}:{normalized_email}".encode("utf-8")
        ).hexdigest()
        try:
            email_allowed = request_throttle.allow(
                f"password-reset-email:{email_limit_key}", 3, 60 * 60
            )
        except RuntimeError:
            return Response("Password recovery is temporarily unavailable.", status_code=503)
        if email_allowed and not auth.validate_email(normalized_email):
            user = user_store.get_by_email(normalized_email)
            if user and user["email_verified"]:
                token = _account_token_serializer("password-reset").dumps({
                    "uid": user["id"], "sv": user["session_version"],
                    "email": user["email"].lower(),
                })
                link = _account_link(request, "/reset-password", token)
                try:
                    _send_account_email(
                        normalized_email,
                        "Reset your Vervfy password",
                        f"Use this link within 30 minutes to reset your Vervfy password:\n\n{link}\n\n"
                        "If you did not request this, you can ignore this email.",
                    )
                except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
                    log.exception("Password reset email delivery failed")
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "csrf_token": auth.get_or_create_csrf_token(request),
            "sent": True,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str = Query(default="")):
    try:
        _account_token_serializer("password-reset").loads(token, max_age=30 * 60)
    except (BadSignature, SignatureExpired):
        return _render_password_reset(request, "", error="This password reset link is invalid or expired.")
    return _render_password_reset(request, token)


@app.post("/reset-password", response_class=HTMLResponse)
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str = Form(...),
):
    auth.verify_csrf(request, csrf_token)
    try:
        payload = _account_token_serializer("password-reset").loads(token, max_age=30 * 60)
    except (BadSignature, SignatureExpired):
        return _render_password_reset(request, "", error="This password reset link is invalid or expired.")
    error = auth.validate_password(password)
    if error:
        return _render_password_reset(request, token, error=error)
    if password != password_confirm:
        return _render_password_reset(request, token, error="Passwords do not match.")
    user = user_store.get_by_id(payload.get("uid", ""))
    if (
        not user or not user["email_verified"] or not user["email"]
        or user["session_version"] != payload.get("sv")
        or user["email"].lower() != payload.get("email")
    ):
        return _render_password_reset(request, "", error="This password reset link is invalid or expired.")
    if user_store.reset_password(user["id"], auth.hash_password(password)) is None:
        return _render_password_reset(request, "", error="This password reset link is invalid or expired.")
    request.session.clear()
    return _render_password_reset(request, "", success=True)


@app.get("/verify-email", response_class=HTMLResponse)
def verify_email_form(request: Request, token: str = Query(default="")):
    try:
        _account_token_serializer("verify-email").loads(token, max_age=24 * 60 * 60)
        error = None
    except (BadSignature, SignatureExpired):
        token, error = "", "This email confirmation link is invalid or expired."
    return templates.TemplateResponse(
        request,
        "verify_email.html",
        {
            "csrf_token": auth.get_or_create_csrf_token(request),
            "token": token,
            "error": error,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.post("/verify-email", response_class=HTMLResponse)
def verify_email_submit(
    request: Request,
    token: str = Form(...),
    csrf_token: str = Form(...),
):
    auth.verify_csrf(request, csrf_token)
    try:
        payload = _account_token_serializer("verify-email").loads(token, max_age=24 * 60 * 60)
    except (BadSignature, SignatureExpired):
        return templates.TemplateResponse(
            request, "verify_email.html",
            {"csrf_token": auth.get_or_create_csrf_token(request), "token": "", "error": "This email confirmation link is invalid or expired."},
            headers={"Cache-Control": "no-store"},
        )
    try:
        confirmed = user_store.confirm_pending_email(payload.get("uid", ""), payload.get("email", ""))
    except ValueError as exc:
        confirmed = False
        error = str(exc)
    else:
        error = "This email confirmation link is no longer valid." if not confirmed else None
    return templates.TemplateResponse(
        request,
        "verify_email.html",
        {
            "csrf_token": auth.get_or_create_csrf_token(request),
            "token": "",
            "error": error,
            "success": confirmed,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request) -> HTMLResponse:
    if current_user_row(request) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "register.html", {"csrf_token": auth.get_or_create_csrf_token(request)}
    )


@app.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(""),
    csrf_token: str = Form(...),
) -> Response:
    auth.verify_csrf(request, csrf_token)

    def fail(message: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "csrf_token": auth.get_or_create_csrf_token(request),
                "error": message,
                "username": username,
                "email": email,
            },
            status_code=status_code,
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
    # after another login/logout cycle; do not expose a JSON CSRF error page
    # when the desired outcome is simply to end the current session.
    try:
        auth.verify_csrf(request, submitted_token)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
    # A copied cookie stays valid after a plain logout until the password
    # changes or logout-all is used.
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/logout")
def logout_get(request: Request) -> Response:
    # A GET must not change authentication state. Keep this route as a
    # compatibility redirect for old bookmarks and links.
    del request
    return RedirectResponse("/login", status_code=303)


@app.get("/api/me")
def api_me(user=Depends(require_api_user)) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "email_verified": user["email_verified"],
        "pending_email": user["pending_email"],
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
def api_csrf(request: Request, user=Depends(require_api_user)) -> dict:
    """SPA fetches this once and sends the token back as X-CSRF-Token on
    any state-changing call (upload, delete, password change)."""
    return {"csrf_token": auth.get_or_create_csrf_token(request)}


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
        "playlists": sorted(
            state["playlists"],
            key=lambda item: item["id"],
        ),
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f'"{digest}"'


def _parse_range_header(range_header: str, size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[6:].strip()
    if not spec or "," in spec:
        return None
    if spec.startswith("-"):
        try:
            suffix = int(spec[1:])
        except ValueError:
            return None
        if suffix <= 0 or suffix > size:
            return None
        return max(0, size - suffix), size - 1
    start_str, _, end_str = spec.partition("-")
    try:
        start = int(start_str)
        end = int(end_str) if end_str else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size:
        return None
    end = min(end, size - 1)
    if end < start:
        return None
    return start, end


def _content_disposition_filename(filename: str) -> str:
    """Keep uploaded names safe when placed in a response header."""
    ascii_name = os.path.basename(filename).encode("ascii", "ignore").decode("ascii")
    return re.sub(r'[\r\n"\\]', "_", ascii_name) or "audio"


@app.put("/api/account/email")
def change_account_email(
    payload: EmailChangeRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    if not auth.verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    email = payload.email.strip().lower()
    if email:
        error = auth.validate_email(email)
        if error:
            raise HTTPException(status_code=400, detail=error)
        if email == user["email"] and user["email_verified"]:
            return {"email": user["email"], "email_verified": True, "pending_email": None}
        token = _account_token_serializer("verify-email").dumps({
            "uid": user["id"], "email": email,
        })
        link = _account_link(request, "/verify-email", token)
        try:
            _send_account_email(
                email,
                "Verify your Vervfy email address",
                f"Confirm this address for your Vervfy account within 24 hours:\n\n{link}\n\n"
                "If you did not request this, you can ignore this email.",
            )
        except (OSError, smtplib.SMTPException, RuntimeError, ValueError) as exc:
            log.exception("Account email verification delivery failed")
            raise HTTPException(
                status_code=503,
                detail="Could not send the verification email. Check the email service configuration and try again.",
            ) from exc
        user_store.set_pending_email(user["id"], email)
        return {
            "email": user["email"],
            "email_verified": user["email_verified"],
            "pending_email": email,
        }
    user_store.set_pending_email(user["id"], None)
    return {"email": None, "email_verified": False, "pending_email": None}


@app.post("/api/account/password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user=Depends(require_api_user),
    _csrf=Depends(auth.verify_api_csrf),
) -> dict:
    if not auth.verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
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
    if not auth.verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    storage_paths = get_library(user["id"]).storage_paths()
    user_store.delete_user(user["id"])
    audio_store.delete_many_quietly(storage_paths)
    _libraries.pop(user["id"], None)
    request.session.clear()
    request.app.state.is_first_account = user_store.count() == 0
    return {"ok": True}


@app.get("/sw.js")
def service_worker() -> FileResponse:
    """Serve the worker that keeps the app shell available offline."""
    path = STATIC_DIR / "sw.js"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        path,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store", "Service-Worker-Allowed": "/"},
    )


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
        for item in payload.playlists:
            if item.id in requested:
                continue
            requested.add(item.id)
            name = item.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="Playlist name cannot be empty")
            playlist = existing.pop(item.id, None)
            if playlist is None:
                playlist = Playlist(id=item.id, user_id=user["id"], name=name)
                session.add(playlist)
            else:
                playlist.name = name
                playlist.tracks.clear()
            ids = list(dict.fromkeys(track_id for track_id in item.trackIds if track_id in valid_ids))
            playlist.tracks = [PlaylistTrack(track_id=track_id, position=index) for index, track_id in enumerate(ids)]
        for playlist in existing.values():
            session.delete(playlist)
        session.commit()
        state = _library_state_from_session(user["id"], session)
    response.headers["ETag"] = _library_state_etag(state)
    return state


@app.get("/api/artists/photo")
def artist_photo(
    name: str = Query(min_length=1, max_length=200), user=Depends(require_api_user)
) -> dict:
    """Find an artist portrait for the Artists view, if the public catalog has one."""
    del user  # The dependency keeps this account-scoped endpoint private.
    return {"url": _lookup_artist_photo(name.strip())}


@app.get("/api/artists/profile")
def artist_profile(
    name: str = Query(min_length=1, max_length=200), user=Depends(require_api_user)
) -> dict:
    """Return public artist metadata for the detail page, when available."""
    del user  # The dependency keeps this account-scoped endpoint private.
    return {"profile": _lookup_artist_profile(name.strip())}


@app.get("/api/tracks")
def list_tracks(user=Depends(require_api_user)) -> dict:
    library = get_library(user["id"])
    return {"tracks": [_track_payload(t) for t in library.list_tracks()]}


@app.post("/api/library/upload")
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

    media_type = mimetypes.guess_type(filename)[0] or "audio/mpeg"
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
        range_match = _parse_range_header(range_header, size)
        if range_match is None:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"})
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


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
