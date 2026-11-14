"""Single-use password-reset and email-verification tokens in Redis."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass

try:
    import redis
except ImportError:  # pragma: no cover - dependency is required in production
    redis = None

_CREATE_TOKEN_SCRIPT = """
local token_key = KEYS[1]
local user_key = KEYS[2]
local lock_key = KEYS[3]
local user_id = ARGV[1]
local token_hash = ARGV[2]
local ttl = tonumber(ARGV[3])
if redis.call('GET', lock_key) then
  return 0
end
local prior = redis.call('GET', user_key)
if prior and prior ~= token_hash then
  redis.call('DEL', ARGV[4] .. prior)
end
redis.call('SET', token_key, ARGV[5], 'EX', ttl)
redis.call('SET', user_key, token_hash, 'EX', ttl)
return 1
"""

_CLAIM_TOKEN_SCRIPT = """
local subject = redis.call('GET', KEYS[1])
if not subject or string.sub(subject, 1, string.len(ARGV[1])) == ARGV[1] then
  return nil
end
local ttl = redis.call('PTTL', KEYS[1])
if ttl <= 0 then
  redis.call('DEL', KEYS[1])
  return nil
end
local user_id = cjson.decode(subject).user_id
local lock_key = ARGV[3] .. user_id
if not redis.call('SET', lock_key, ARGV[4], 'NX', 'PX', ttl) then
  return nil
end
redis.call('SET', KEYS[1], ARGV[2] .. subject, 'PX', ttl)
return subject
"""

_COMMIT_TOKEN_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call('DEL', KEYS[1])
if redis.call('GET', KEYS[2]) == ARGV[2] then
  redis.call('DEL', KEYS[2])
end
if redis.call('GET', KEYS[3]) == ARGV[3] then
  redis.call('DEL', KEYS[3])
end
return 1
"""

_RELEASE_TOKEN_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
local ttl = redis.call('PTTL', KEYS[1])
if ttl <= 0 then
  redis.call('DEL', KEYS[1])
  if redis.call('GET', KEYS[2]) == ARGV[2] then
    redis.call('DEL', KEYS[2])
  end
  return 0
end
redis.call('SET', KEYS[1], ARGV[3], 'PX', ttl)
if redis.call('GET', KEYS[3]) == ARGV[4] then
  redis.call('DEL', KEYS[3])
end
return 1
"""

_DELETE_TOKEN_SCRIPT = """
local token_key = KEYS[1]
local subject = redis.call('GET', token_key)
redis.call('DEL', token_key)
if subject and string.sub(subject, 1, string.len(ARGV[1])) ~= ARGV[1] then
  local user_id = cjson.decode(subject).user_id
  local user_key = ARGV[2] .. user_id
  if redis.call('GET', user_key) == ARGV[3] then
    redis.call('DEL', user_key)
  end
end
return subject
"""


def default_ttl_seconds() -> int:
    raw = os.environ.get("VERVFY_PASSWORD_RESET_TTL_SECONDS", "1800").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1800
    return max(60, min(value, 24 * 60 * 60))


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def email_rate_key(email: str) -> str:
    normalized = email.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"password-reset:email:{digest}"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class TokenClaim:
    user_id: str
    binding: str | None
    claim_id: str


class PasswordResetStore:
    """Keep token digests in Redis and claim tokens before touching PostgreSQL."""

    TOKEN_PREFIX = "vervfy:password-reset:token:"
    USER_PREFIX = "vervfy:password-reset:user:"
    LOCK_PREFIX = "vervfy:password-reset:lock:"
    CLAIM_PREFIX = "__claim__:"

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        ttl_seconds: int | None = None,
        token_prefix: str | None = None,
        user_prefix: str | None = None,
        lock_prefix: str | None = None,
    ):
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else default_ttl_seconds()
        self.token_prefix = token_prefix or self.TOKEN_PREFIX
        self.user_prefix = user_prefix or self.USER_PREFIX
        self.lock_prefix = lock_prefix or self.LOCK_PREFIX
        self._redis = None
        self._tokens: dict[str, tuple[str, float, str | None]] = {}
        self._user_tokens: dict[str, str] = {}
        self._user_locks: dict[str, tuple[str, float]] = {}
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

    def issue(self, user_id: str, *, binding: str | None = None) -> str | None:
        token = generate_token()
        digest = token_digest(token)
        subject = json.dumps(
            {"user_id": user_id, "binding": binding},
            separators=(",", ":"),
        )
        if self._redis is not None:
            try:
                result = self._redis.eval(
                    _CREATE_TOKEN_SCRIPT,
                    3,
                    f"{self.token_prefix}{digest}",
                    f"{self.user_prefix}{user_id}",
                    f"{self.lock_prefix}{user_id}",
                    user_id,
                    digest,
                    self.ttl_seconds,
                    self.token_prefix,
                    subject,
                )
            except redis.RedisError as exc:
                raise RuntimeError("password-reset backend unavailable") from exc
            if not result:
                return None
            return token

        expires_at = time.time() + self.ttl_seconds
        with self._lock:
            active_lock = self._user_locks.get(user_id)
            if active_lock and active_lock[1] > time.time():
                return None
            if active_lock:
                self._user_locks.pop(user_id, None)
            prior = self._user_tokens.get(user_id)
            if prior and prior != digest:
                self._tokens.pop(prior, None)
            self._tokens[digest] = (subject, expires_at, None)
            self._user_tokens[user_id] = digest
            self._prune_locked(time.time())
        return token

    def claim(self, token: str) -> TokenClaim | None:
        if not token or len(token) > 256:
            return None
        digest = token_digest(token)
        claim_id = secrets.token_urlsafe(18)
        marker = f"{self.CLAIM_PREFIX}{claim_id}:"

        if self._redis is not None:
            try:
                subject = self._redis.eval(
                    _CLAIM_TOKEN_SCRIPT,
                    1,
                    f"{self.token_prefix}{digest}",
                    self.CLAIM_PREFIX,
                    marker,
                    self.lock_prefix,
                    claim_id,
                )
            except redis.RedisError as exc:
                raise RuntimeError("password-reset backend unavailable") from exc
            if isinstance(subject, bytes):
                subject = subject.decode("utf-8")
            if not subject:
                return None
        else:
            now = time.time()
            with self._lock:
                stored = self._tokens.get(digest)
                if stored is None or stored[1] <= now or stored[2] is not None:
                    if stored is not None and stored[1] <= now:
                        self._tokens.pop(digest, None)
                        self._clear_user_pointer(stored[0], digest)
                    return None
                subject, expires_at, _ = stored
                try:
                    user_id = json.loads(subject)["user_id"]
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise RuntimeError(
                        "password-reset token store is inconsistent"
                    ) from exc
                active_lock = self._user_locks.get(user_id)
                if active_lock and active_lock[1] > now:
                    return None
                if active_lock:
                    self._user_locks.pop(user_id, None)
                self._tokens[digest] = (subject, expires_at, claim_id)
                self._user_locks[user_id] = (claim_id, expires_at)

        try:
            value = json.loads(subject)
            user_id = value["user_id"]
            binding = value["binding"]
            if not isinstance(user_id, str) or (
                binding is not None and not isinstance(binding, str)
            ):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("password-reset token store is inconsistent") from exc
        return TokenClaim(user_id=user_id, binding=binding, claim_id=claim_id)

    def commit(self, token: str, claim: TokenClaim) -> bool:
        digest = token_digest(token)
        marker = f"{self.CLAIM_PREFIX}{claim.claim_id}:"
        if self._redis is not None:
            try:
                result = self._redis.eval(
                    _COMMIT_TOKEN_SCRIPT,
                    3,
                    f"{self.token_prefix}{digest}",
                    f"{self.user_prefix}{claim.user_id}",
                    f"{self.lock_prefix}{claim.user_id}",
                    f"{marker}{self._subject(claim)}",
                    digest,
                    claim.claim_id,
                )
            except redis.RedisError as exc:
                raise RuntimeError("password-reset backend unavailable") from exc
            return bool(result)

        with self._lock:
            stored = self._tokens.get(digest)
            if (
                stored is None
                or stored[1] <= time.time()
                or stored[2] != claim.claim_id
                or stored[0] != self._subject(claim)
                or self._user_locks.get(claim.user_id, (None, 0))[0]
                != claim.claim_id
            ):
                return False
            self._tokens.pop(digest, None)
            self._clear_user_pointer(stored[0], digest)
            self._user_locks.pop(claim.user_id, None)
            return True

    def release(self, token: str, claim: TokenClaim) -> bool:
        digest = token_digest(token)
        marker = f"{self.CLAIM_PREFIX}{claim.claim_id}:"
        if self._redis is not None:
            try:
                result = self._redis.eval(
                    _RELEASE_TOKEN_SCRIPT,
                    3,
                    f"{self.token_prefix}{digest}",
                    f"{self.user_prefix}{claim.user_id}",
                    f"{self.lock_prefix}{claim.user_id}",
                    f"{marker}{self._subject(claim)}",
                    digest,
                    self._subject(claim),
                    claim.claim_id,
                )
            except redis.RedisError as exc:
                raise RuntimeError("password-reset backend unavailable") from exc
            return bool(result)

        with self._lock:
            stored = self._tokens.get(digest)
            if (
                stored is None
                or stored[1] <= time.time()
                or stored[2] != claim.claim_id
                or stored[0] != self._subject(claim)
                or self._user_locks.get(claim.user_id, (None, 0))[0]
                != claim.claim_id
            ):
                return False
            self._tokens[digest] = (stored[0], stored[1], None)
            self._user_locks.pop(claim.user_id, None)
            return True

    def consume(self, token: str) -> str | None:
        """Compatibility helper for callers that do not need a DB transaction."""
        claim = self.claim(token)
        if claim is None:
            return None
        return claim.user_id if self.commit(token, claim) else None

    def discard(self, token: str) -> None:
        if not token:
            return
        digest = token_digest(token)
        if self._redis is not None:
            try:
                self._redis.eval(
                    _DELETE_TOKEN_SCRIPT,
                    1,
                    f"{self.token_prefix}{digest}",
                    self.CLAIM_PREFIX,
                    self.user_prefix,
                    digest,
                )
            except redis.RedisError as exc:
                raise RuntimeError("password-reset backend unavailable") from exc
            return

        with self._lock:
            stored = self._tokens.pop(digest, None)
            if stored:
                self._clear_user_pointer(stored[0], digest)

    def peek_user_id(self, token: str) -> str | None:
        """Test helper: non-consuming lookup. Never used by request handlers."""
        if not token:
            return None
        digest = token_digest(token)
        if self._redis is not None:
            try:
                subject = self._redis.get(f"{self.token_prefix}{digest}")
            except redis.RedisError as exc:
                raise RuntimeError("password-reset backend unavailable") from exc
            if isinstance(subject, bytes):
                subject = subject.decode("utf-8")
            if not subject or subject.startswith(self.CLAIM_PREFIX):
                return None
        else:
            with self._lock:
                stored = self._tokens.get(digest)
                if stored is None or stored[1] <= time.time() or stored[2] is not None:
                    return None
                subject = stored[0]
        try:
            value = json.loads(subject)
            return value["user_id"] if isinstance(value["user_id"], str) else None
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    @staticmethod
    def _subject(claim: TokenClaim) -> str:
        return json.dumps(
            {"user_id": claim.user_id, "binding": claim.binding},
            separators=(",", ":"),
        )

    def _clear_user_pointer(self, subject: str, digest: str) -> None:
        try:
            user_id = json.loads(subject)["user_id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return
        if self._user_tokens.get(user_id) == digest:
            self._user_tokens.pop(user_id, None)

    def _prune_locked(self, now: float) -> None:
        if len(self._tokens) <= 10_000:
            return
        for digest, (subject, expires_at, _) in list(self._tokens.items()):
            if expires_at <= now:
                self._tokens.pop(digest, None)
                self._clear_user_pointer(subject, digest)


class EmailVerificationStore(PasswordResetStore):
    TOKEN_PREFIX = "vervfy:password-reset-email:token:"
    USER_PREFIX = "vervfy:password-reset-email:user:"
    LOCK_PREFIX = "vervfy:password-reset-email:lock:"

    def __init__(self, redis_url: str | None = None, *, ttl_seconds: int | None = None):
        super().__init__(
            redis_url,
            ttl_seconds=ttl_seconds,
            token_prefix=self.TOKEN_PREFIX,
            user_prefix=self.USER_PREFIX,
            lock_prefix=self.LOCK_PREFIX,
        )
