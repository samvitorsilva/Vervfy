"""Accounts: PostgreSQL-backed user store, password hashing, sessions, CSRF."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
import time
import uuid
from hmac import compare_digest

import bcrypt
from fastapi import HTTPException, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db import (
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

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DUMMY_HASH = "$2b$12$16SzrlA/CFIYsvKCPGxg4e/G5yv59dknprQQazXEHPgIyzm3pjpgm"

try:
    import redis
except ImportError:  # pragma: no cover - dependency is required in production
    redis = None


_INCREMENT_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""

_CREATE_SESSION_SCRIPT = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
redis.call('SADD', KEYS[2], ARGV[3])
redis.call('EXPIRE', KEYS[2], ARGV[2])
return 1
"""

_REVOKE_SESSION_SCRIPT = """
local user_id = redis.call('GET', KEYS[1])
if user_id then
    redis.call('SREM', ARGV[1] .. user_id, ARGV[2])
end
return redis.call('DEL', KEYS[1])
"""

_REVOKE_USER_SESSIONS_SCRIPT = """
local session_ids = redis.call('SMEMBERS', KEYS[1])
for _, session_id in ipairs(session_ids) do
    redis.call('DEL', ARGV[1] .. session_id)
end
redis.call('DEL', KEYS[1])
return #session_ids
"""


class RequestThrottle:
    """Fixed-window limiter with Redis sharing across workers and instances."""

    def __init__(self, redis_url: str | None = None):
        self._redis = None
        self._local: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        if redis_url:
            if redis is None:
                raise RuntimeError("redis is required when REDIS_URL is configured")
            self._redis = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )

    def peek(self, key: str, window_seconds: int) -> int:
        now = time.time()
        if self._redis is not None:
            try:
                return int(self._redis.get(f"vervfy:ratelimit:{key}") or 0)
            except redis.RedisError as exc:
                raise RuntimeError("rate-limit backend unavailable") from exc

        with self._lock:
            count, expires_at = self._local.get(key, (0, now))
            if now >= expires_at:
                self._local.pop(key, None)
                return 0
            return count

    def increment(self, key: str, window_seconds: int) -> int:
        now = time.time()
        if self._redis is not None:
            redis_key = f"vervfy:ratelimit:{key}"
            try:
                return int(self._redis.eval(
                    _INCREMENT_WINDOW_SCRIPT, 1, redis_key, window_seconds
                ))
            except redis.RedisError as exc:
                raise RuntimeError("rate-limit backend unavailable") from exc

        with self._lock:
            count, expires_at = self._local.get(key, (0, now))
            if now >= expires_at:
                count, expires_at = 0, now + window_seconds
            count += 1
            self._local[key] = (count, expires_at)
            if len(self._local) > 10_000:
                self._local = {
                    item_key: item
                    for item_key, item in self._local.items()
                    if item[1] > now
                }
            return count

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        return self.increment(key, window_seconds) <= limit

    def discard(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(f"vervfy:ratelimit:{key}")
            except redis.RedisError as exc:
                raise RuntimeError("rate-limit backend unavailable") from exc
            return
        with self._lock:
            self._local.pop(key, None)


# ---------------------------------------------------------------- user store

class PasswordResetCommitUncertain(RuntimeError):
    """The database may have committed; never release the reset-token claim."""


class UserStore:
    """Small SQLAlchemy store.  Rows remain mapping-compatible with routes."""

    def create_user(self, username: str, email: str | None, password: str) -> dict:
        user_id = uuid.uuid4().hex
        password_hash = hash_password(password)
        # SQLite UNIQUE treats NULL as distinct but "" as a real value — blank
        # emails would otherwise collide on the second account that skips email.
        if email is not None:
            email = email.strip().lower() or None
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

    def get_password_reset_account(self, email: str) -> tuple[str, bool] | None:
        """Find a password account by its stored email, without OAuth linking."""
        normalized = (email or "").strip().lower()
        if not normalized:
            return None
        with SessionLocal() as session:
            row = session.scalar(
                select(User).where(func.lower(User.email) == normalized)
            )
            if row is None or row.password_hash is None or not row.email:
                return None
            return row.id, bool(row.email_verified)

    def get_password_reset_target(self, email: str) -> str | None:
        """Return only password accounts whose email has already been verified."""
        target = self.get_password_reset_account(email)
        if target is None or not target[1]:
            return None
        return target[0]

    def verify_password_reset_email(self, user_id: str, email_digest: str) -> None:
        """Verify the same email address that received the reset-verification link."""
        with SessionLocal() as session:
            row = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if (
                row is None
                or row.password_hash is None
                or not row.email
                or row.email_verified
                or not compare_digest(
                    hashlib.sha256(
                        row.email.strip().lower().encode("utf-8")
                    ).hexdigest(),
                    email_digest,
                )
            ):
                raise ValueError("This verification link is invalid or has expired")
            row.email_verified = True
            try:
                session.commit()
            except SQLAlchemyError as exc:
                raise PasswordResetCommitUncertain(
                    "Email verification may have committed"
                ) from exc

    def reset_password_and_invalidate_sessions(
        self, user_id: str, new_password: str
    ) -> int:
        """Set a new password hash and bump session_version (caller revokes Redis)."""
        error = validate_password(new_password)
        if error:
            raise ValueError(error)
        new_password_hash = hash_password(new_password)
        with SessionLocal() as session:
            row = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if row is None:
                raise ValueError("Account not found")
            if row.password_hash is None or not row.email or not row.email_verified:
                raise ValueError("Password reset is not available for this account")
            row.password_hash = new_password_hash
            row.session_version += 1
            try:
                session.commit()
            except SQLAlchemyError as exc:
                raise PasswordResetCommitUncertain(
                    "Password reset may have committed"
                ) from exc
            return row.session_version

    def update_password(self, user_id: str, new_password_hash: str) -> None:
        with SessionLocal() as session:
            row = session.get(User, user_id)
            if row:
                row.password_hash = new_password_hash
                row.session_version += 1
                session.commit()

    def update_email(self, user_id: str, email: str | None) -> int:
        with SessionLocal() as session:
            row = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if not row:
                raise ValueError("Account not found")
            if email:
                existing_user_id = session.scalar(
                    select(User.id).where(
                        func.lower(User.email) == email.lower(),
                        User.id != user_id,
                    )
                )
                if existing_user_id:
                    raise ValueError("That email is already in use")
            try:
                row.email = email
                row.email_verified = False
                row.pending_email = None
                row.session_version += 1
                session.commit()
                return row.session_version
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("That email is already in use") from exc

    def account_security(self, user_id: str) -> dict[str, bool]:
        with tenant_session(user_id) as session:
            row = session.get(User, user_id)
            if row is None:
                raise ValueError("Account not found")
            google_linked = session.scalar(
                select(ProviderIdentity.subject)
                .where(
                    ProviderIdentity.user_id == user_id,
                    ProviderIdentity.issuer.in_(
                        ("https://accounts.google.com", "accounts.google.com")
                    ),
                )
                .limit(1)
            ) is not None
            return {
                "has_password": row.password_hash is not None,
                "google_linked": google_linked,
            }

    def create_google_user(
        self, username: str, email: str | None, subject: str
    ) -> dict:
        user_id = uuid.uuid4().hex
        if email is not None:
            email = email.strip().lower() or None
        with SessionLocal(info={"tenant_id": user_id}) as session:
            try:
                if email and session.scalar(
                    select(User.id).where(func.lower(User.email) == email)
                ):
                    raise ValueError("Could not create an account with this Google account")
                session.add(
                    User(
                        id=user_id,
                        username=username,
                        username_key=username.lower(),
                        email=email,
                        email_verified=email is not None,
                        password_hash=None,
                        created_at=time.time(),
                    )
                )
                session.flush()
                session.add(
                    ProviderIdentity(
                        issuer="https://accounts.google.com",
                        subject=subject,
                        user_id=user_id,
                        created_at=time.time(),
                    )
                )
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(
                    "Could not create an account with this username or Google account"
                ) from exc
        return {"id": user_id, "username": username, "email": email}

    def link_google_identity(self, user_id: str, subject: str) -> int:
        with tenant_session(user_id) as session:
            row = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if row is None:
                raise ValueError("Account not found")
            if row.password_hash is None:
                raise ValueError("A password is required before linking Google")
            if session.scalar(
                select(ProviderIdentity.subject).where(
                    ProviderIdentity.user_id == user_id,
                    ProviderIdentity.issuer.in_(
                        ("https://accounts.google.com", "accounts.google.com")
                    ),
                ).limit(1)
            ) is not None:
                raise ValueError("A Google account is already linked")
            session.add(
                ProviderIdentity(
                    issuer="https://accounts.google.com",
                    subject=subject,
                    user_id=user_id,
                    created_at=time.time(),
                )
            )
            row.session_version += 1
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("This Google account is already linked") from exc
            return row.session_version

    def unlink_google_identity(self, user_id: str) -> int:
        with tenant_session(user_id) as session:
            row = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if row is None:
                raise ValueError("Account not found")
            identities = list(
                session.scalars(
                    select(ProviderIdentity).where(
                        ProviderIdentity.user_id == user_id,
                        ProviderIdentity.issuer.in_(
                            ("https://accounts.google.com", "accounts.google.com")
                        ),
                    )
                )
            )
            if not identities:
                raise ValueError("No Google account is linked")
            all_identity_count = session.scalar(
                select(func.count()).select_from(ProviderIdentity).where(
                    ProviderIdentity.user_id == user_id
                )
            ) or 0
            if row.password_hash is None and all_identity_count <= len(identities):
                raise ValueError("Add another sign-in method before unlinking Google")
            for identity in identities:
                session.delete(identity)
            row.session_version += 1
            session.commit()
            return row.session_version

    def set_password_and_bump_version(
        self,
        user_id: str,
        new_password_hash: str,
        *,
        expected_password_hash: str | None,
    ) -> int:
        with tenant_session(user_id) as session:
            row = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if row is None:
                raise ValueError("Account not found")
            if expected_password_hash is None:
                if row.password_hash is not None:
                    raise ValueError("A password is already set")
            elif row.password_hash is None or not compare_digest(
                row.password_hash, expected_password_hash
            ):
                raise ValueError("Account credentials changed; sign in again")
            row.password_hash = new_password_hash
            row.session_version += 1
            session.commit()
            return row.session_version

    def bump_session_version(self, user_id: str) -> int:
        with SessionLocal() as session:
            session.execute(
                text("UPDATE users SET session_version = session_version + 1 WHERE id = :id"),
                {"id": user_id},
            )
            value = session.scalar(select(User.session_version).where(User.id == user_id))
            session.commit()
            return value if value is not None else 0

    def update_profile_photo(self, user_id: str, photo_data: bytes | None, photo_mime: str | None) -> None:
        with SessionLocal() as session:
            row = session.get(User, user_id)
            if row:
                row.photo_data = photo_data
                row.photo_mime = photo_mime
                session.commit()

    def has_profile_photo(self, user_id: str) -> bool:
        with SessionLocal() as session:
            return session.scalar(select(User.photo_mime).where(User.id == user_id)) is not None

    def get_profile_photo(self, user_id: str) -> tuple[bytes | None, str | None]:
        with SessionLocal() as session:
            row = session.execute(
                select(User.photo_data, User.photo_mime).where(User.id == user_id)
            ).one_or_none()
            return (row.photo_data, row.photo_mime) if row else (None, None)

    def delete_user(self, user_id: str) -> None:
        """Remove account-owned database rows; object storage is handled separately."""
        with tenant_session(user_id) as session:
            playlist_ids = select(Playlist.id).where(Playlist.user_id == user_id)
            session.query(PlaylistTrack).filter(PlaylistTrack.playlist_id.in_(playlist_ids)).delete(
                synchronize_session=False
            )
            session.query(Favorite).filter(Favorite.user_id == user_id).delete(synchronize_session=False)
            session.query(TrackListen).filter(TrackListen.user_id == user_id).delete(
                synchronize_session=False
            )
            session.query(ArtistPhoto).filter(ArtistPhoto.user_id == user_id).delete(
                synchronize_session=False
            )
            session.query(UploadJob).filter(UploadJob.user_id == user_id).delete(
                synchronize_session=False
            )
            session.query(TrackRecord).filter(TrackRecord.user_id == user_id).delete(synchronize_session=False)
            session.query(Playlist).filter(Playlist.user_id == user_id).delete(synchronize_session=False)
            session.query(ProviderIdentity).filter_by(user_id=user_id).delete(synchronize_session=False)
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


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        # Missing credentials still incur bcrypt work, but can never authenticate.
        matches = bcrypt.checkpw(password.encode("utf-8"), (password_hash or _DUMMY_HASH).encode("utf-8"))
        return bool(password_hash) and matches
    except (ValueError, TypeError):
        return False


def validate_username(username: str) -> str | None:
    if not USERNAME_RE.match(username or ""):
        return "Username must be 3-32 characters: letters, numbers, _ . -"
    return None


def validate_email(email: str) -> str | None:
    if len(email) > 320 or not EMAIL_RE.fullmatch(email):
        return "Enter a valid email address"
    return None


def validate_password(password: str) -> str | None:
    if not password or len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password.encode("utf-8")) > 72:
        return "Password must be 72 bytes or fewer"
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

    def __init__(self, limiter: RequestThrottle | None = None):
        self._failures: dict[str, list[float]] = {}
        self._limiter = limiter

    def _key(self, ip: str, username: str) -> str:
        return f"{ip}:{username.lower()}"

    def is_locked(self, ip: str, username: str) -> bool:
        if self._limiter is not None:
            return self._limiter.peek(
                f"login:{ip}:{username.lower()}", self.WINDOW_SECONDS
            ) >= self.MAX_ATTEMPTS
        key = self._key(ip, username)
        now = time.time()
        attempts = [t for t in self._failures.get(key, []) if now - t < self.WINDOW_SECONDS]
        self._failures[key] = attempts
        return len(attempts) >= self.MAX_ATTEMPTS

    def record_failure(self, ip: str, username: str) -> None:
        if self._limiter is not None:
            self._limiter.increment(
                f"login:{ip}:{username.lower()}", self.WINDOW_SECONDS
            )
            return
        key = self._key(ip, username)
        self._failures.setdefault(key, []).append(time.time())

    def clear(self, ip: str, username: str) -> None:
        if self._limiter is not None:
            self._limiter.discard(f"login:{ip}:{username.lower()}")
            return
        self._failures.pop(self._key(ip, username), None)


class SignupThrottle:
    """Limit successful registrations from one client IP within an hour."""

    WINDOW_SECONDS = 60 * 60

    def __init__(self, max_signups: int | None = None, limiter: RequestThrottle | None = None):
        self.max_signups = max_signups if max_signups is not None else int(
            os.environ.get("VERVFY_SIGNUPS_PER_HOUR", "5")
        )
        self._successes: dict[str, list[float]] = {}
        self._limiter = limiter

    def _recent(self, ip: str) -> list[float]:
        now = time.time()
        recent = [timestamp for timestamp in self._successes.get(ip, []) if now - timestamp < self.WINDOW_SECONDS]
        self._successes[ip] = recent
        return recent

    def is_limited(self, ip: str) -> bool:
        if self._limiter is not None:
            return self._limiter.peek(f"signup:{ip}", self.WINDOW_SECONDS) >= self.max_signups
        return len(self._recent(ip)) >= self.max_signups

    def record_success(self, ip: str) -> None:
        if self._limiter is not None:
            self._limiter.increment(f"signup:{ip}", self.WINDOW_SECONDS)
            return
        self._recent(ip).append(time.time())


class SessionStore:
    """Allowlist signed-cookie session IDs so logout revokes copied cookies."""

    TTL_SECONDS = 60 * 60 * 24 * 30
    KEY_PREFIX = "vervfy:session:"
    USER_SESSIONS_PREFIX = "vervfy:user-sessions:"

    def __init__(self, redis_url: str | None = None):
        self._redis = None
        self._sessions: dict[str, tuple[str, float]] = {}
        self._user_sessions: dict[str, set[str]] = {}
        self._lock = threading.Lock()
        if redis_url:
            if redis is None:
                raise RuntimeError("redis is required when REDIS_URL is configured")
            self._redis = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )

    def create(self, user_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        if self._redis is not None:
            try:
                self._redis.eval(
                    _CREATE_SESSION_SCRIPT,
                    2,
                    f"{self.KEY_PREFIX}{session_id}",
                    f"{self.USER_SESSIONS_PREFIX}{user_id}",
                    user_id,
                    self.TTL_SECONDS,
                    session_id,
                )
            except redis.RedisError as exc:
                raise RuntimeError("session backend unavailable") from exc
            return session_id

        now = time.time()
        with self._lock:
            if len(self._sessions) > 10_000:
                for expired_id, (_, expires_at) in list(self._sessions.items()):
                    if expires_at <= now:
                        self._remove_memory_session(expired_id)
            self._sessions[session_id] = (user_id, now + self.TTL_SECONDS)
            self._user_sessions.setdefault(user_id, set()).add(session_id)
        return session_id

    def is_valid(self, session_id: str, user_id: str) -> bool:
        if self._redis is not None:
            try:
                stored_user_id = self._redis.get(f"{self.KEY_PREFIX}{session_id}")
            except redis.RedisError as exc:
                raise RuntimeError("session backend unavailable") from exc
            return stored_user_id == user_id

        now = time.time()
        with self._lock:
            stored = self._sessions.get(session_id)
            if stored is None:
                return False
            if stored[1] <= now:
                self._remove_memory_session(session_id)
                return False
            return stored[0] == user_id

    def revoke(self, session_id: str) -> None:
        if self._redis is not None:
            try:
                self._redis.eval(
                    _REVOKE_SESSION_SCRIPT,
                    1,
                    f"{self.KEY_PREFIX}{session_id}",
                    self.USER_SESSIONS_PREFIX,
                    session_id,
                )
            except redis.RedisError as exc:
                raise RuntimeError("session backend unavailable") from exc
            return

        with self._lock:
            self._remove_memory_session(session_id)

    def revoke_user(self, user_id: str) -> None:
        if self._redis is not None:
            try:
                # Remove pre-index sessions too, including sessions created before
                # the reverse user-to-session index was introduced.
                for key in self._redis.scan_iter(match=f"{self.KEY_PREFIX}*"):
                    if isinstance(key, bytes):
                        key = key.decode("utf-8")
                    session_id = key.removeprefix(self.KEY_PREFIX)
                    stored_user_id = self._redis.get(key)
                    if isinstance(stored_user_id, bytes):
                        stored_user_id = stored_user_id.decode("utf-8")
                    if stored_user_id == user_id:
                        self._redis.eval(
                            _REVOKE_SESSION_SCRIPT,
                            1,
                            key,
                            self.USER_SESSIONS_PREFIX,
                            session_id,
                        )
                self._redis.eval(
                    _REVOKE_USER_SESSIONS_SCRIPT,
                    1,
                    f"{self.USER_SESSIONS_PREFIX}{user_id}",
                    self.KEY_PREFIX,
                )
            except redis.RedisError as exc:
                raise RuntimeError("session backend unavailable") from exc
            return

        with self._lock:
            for session_id in list(self._user_sessions.get(user_id, ())):
                self._remove_memory_session(session_id)

    def _remove_memory_session(self, session_id: str) -> None:
        stored = self._sessions.pop(session_id, None)
        if stored is None:
            return
        user_id, _ = stored
        user_sessions = self._user_sessions.get(user_id)
        if user_sessions is None:
            return
        user_sessions.discard(session_id)
        if not user_sessions:
            self._user_sessions.pop(user_id, None)


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
    peer = request.client.host if request.client else "unknown"
    trusted_hops = int(os.environ.get("VERVFY_TRUSTED_PROXY_HOPS", "0"))
    if trusted_hops <= 0:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    addresses = [item.strip() for item in forwarded.split(",") if item.strip()]
    if len(addresses) >= trusted_hops:
        return addresses[-trusted_hops]
    return peer
