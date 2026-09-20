"""Accounts: PostgreSQL-backed user store, password hashing, sessions, CSRF."""

from __future__ import annotations

import os
import re
import secrets
import time
import uuid

import bcrypt
from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from db import Favorite, Playlist, PlaylistTrack, SessionLocal, TrackRecord, User

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


# ---------------------------------------------------------------- user store

class UserStore:
    """Small SQLAlchemy store.  Rows remain mapping-compatible with routes."""

    def create_user(self, username: str, email: str | None, password: str) -> dict:
        user_id = uuid.uuid4().hex
        password_hash = hash_password(password)
        # SQLite UNIQUE treats NULL as distinct but "" as a real value — blank
        # emails would otherwise collide on the second account that skips email.
        if email is not None:
            email = email.strip() or None
        with SessionLocal() as session:
            try:
                session.add(User(id=user_id, username=username, username_key=username.lower(), email=email,
                                 password_hash=password_hash, created_at=time.time()))
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("That username or email is already taken") from exc
        return {"id": user_id, "username": username, "email": email}

    def get_by_username(self, username: str):
        with SessionLocal() as session:
            return session.scalar(select(User).where(User.username_key == username.lower()))

    def get_by_id(self, user_id: str):
        with SessionLocal() as session:
            return session.get(User, user_id)

    def update_password(self, user_id: str, new_password_hash: str) -> None:
        with SessionLocal() as session:
            row = session.get(User, user_id)
            if row:
                row.password_hash = new_password_hash
                session.commit()

    def update_profile_photo(self, user_id: str, photo_data: bytes | None, photo_mime: str | None) -> None:
        with SessionLocal() as session:
            row = session.get(User, user_id)
            if row:
                row.photo_data = photo_data
                row.photo_mime = photo_mime
                session.commit()

    def delete_user(self, user_id: str) -> None:
        """Permanently remove an account and every piece of account-owned data.

        The explicit child deletes keep this reliable for local SQLite databases
        too, where foreign-key cascade support may not be enabled by the host.
        """
        with SessionLocal() as session:
            playlist_ids = select(Playlist.id).where(Playlist.user_id == user_id)
            session.query(PlaylistTrack).filter(PlaylistTrack.playlist_id.in_(playlist_ids)).delete(
                synchronize_session=False
            )
            session.query(Favorite).filter(Favorite.user_id == user_id).delete(synchronize_session=False)
            session.query(TrackRecord).filter(TrackRecord.user_id == user_id).delete(synchronize_session=False)
            session.query(Playlist).filter(Playlist.user_id == user_id).delete(synchronize_session=False)
            session.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            session.commit()

    def count(self) -> int:
        with SessionLocal() as session:
            return session.scalar(select(func.count()).select_from(User)) or 0


# ---------------------------------------------------------- password hashing

def hash_password(password: str) -> str:
    # bcrypt truncates >72 bytes silently; reject early instead of surprising
    # a user whose password 73+ bytes in effectively collapses to fewer chars.
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password is too long (max 72 bytes)")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_username(username: str) -> str | None:
    if not USERNAME_RE.match(username or ""):
        return "Username must be 3-32 characters: letters, numbers, _ . -"
    return None


def validate_password(password: str) -> str | None:
    if not password or len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password.encode("utf-8")) > 72:
        return "Password must be under 72 bytes"
    return None


# ------------------------------------------------------------- login throttle

class LoginThrottle:
    """Basic in-memory brute-force guard: N failures -> temporary lockout per key.

    Keyed by (client IP, username) so one abusive IP can't lock out everyone,
    and one targeted username can't be hammered from many IPs unnoticed.
    In-memory is fine for a single-process deploy; swap for Redis if you
    ever run multiple workers.
    """

    MAX_ATTEMPTS = 5
    WINDOW_SECONDS = 15 * 60

    def __init__(self):
        self._failures: dict[str, list[float]] = {}

    def _key(self, ip: str, username: str) -> str:
        return f"{ip}:{username.lower()}"

    def is_locked(self, ip: str, username: str) -> bool:
        key = self._key(ip, username)
        now = time.time()
        attempts = [t for t in self._failures.get(key, []) if now - t < self.WINDOW_SECONDS]
        self._failures[key] = attempts
        return len(attempts) >= self.MAX_ATTEMPTS

    def record_failure(self, ip: str, username: str) -> None:
        key = self._key(ip, username)
        self._failures.setdefault(key, []).append(time.time())

    def clear(self, ip: str, username: str) -> None:
        self._failures.pop(self._key(ip, username), None)


class SignupThrottle:
    """Limit successful registrations from one client IP within an hour."""

    WINDOW_SECONDS = 60 * 60

    def __init__(self, max_signups: int | None = None):
        self.max_signups = max_signups if max_signups is not None else int(
            os.environ.get("VERVFY_SIGNUPS_PER_HOUR", "5")
        )
        self._successes: dict[str, list[float]] = {}

    def _recent(self, ip: str) -> list[float]:
        now = time.time()
        recent = [timestamp for timestamp in self._successes.get(ip, []) if now - timestamp < self.WINDOW_SECONDS]
        self._successes[ip] = recent
        return recent

    def is_limited(self, ip: str) -> bool:
        return len(self._recent(ip)) >= self.max_signups

    def record_success(self, ip: str) -> None:
        self._recent(ip).append(time.time())


# ------------------------------------------------------------------------ CSRF

def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, submitted_token: str) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=403, detail="Invalid or expired form submission, please retry")


def verify_api_csrf(request: Request) -> None:
    """Same check as verify_csrf, but reads the token from a header
    (X-CSRF-Token) instead of a form field — for JSON fetch() calls from
    the SPA rather than <form> submissions."""
    verify_csrf(request, request.headers.get("x-csrf-token", ""))


# --------------------------------------------------------------------- misc

def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
