"""Google OIDC login primitives with Redis-owned one-time transactions."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx2
import redis
from authlib.integrations.base_client.errors import AuthlibBaseError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.integrations.starlette_client import OAuth
from joserfc.errors import JoseError
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from starlette.concurrency import run_in_threadpool

from provider_identity_lookup import lookup_verified_google_identity

GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_ISSUERS = (GOOGLE_ISSUER, "accounts.google.com")
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
CALLBACK_PATH = "/api/auth/google/callback"
TRANSACTION_TTL_SECONDS = 600
CREDENTIAL_PROOF_TTL_SECONDS = 300
CLOCK_SKEW_SECONDS = 60
FRESH_AUTH_MAX_AGE_SECONDS = 300
GOOGLE_FLOW_PURPOSES = {
    "login",
    "signup",
    "link",
    "password_add",
    "email_change",
    "account_delete",
    "logout_all",
}
GOOGLE_REAUTHENTICATION_PURPOSES = frozenset(
    {"email_change", "account_delete", "logout_all"}
)
GOOGLE_IDENTITY_CONFIRMATION_PURPOSES = frozenset({"password_add"})
GOOGLE_REAUTHENTICATION_FAILURE_STAGES = frozenset(
    {
        "freshness_missing_auth_time",
        "freshness_stale_auth_time",
        "account_session_binding",
        "transaction",
        "other_validation",
    }
)
GOOGLE_IDENTITY_CONFIRMATION_FAILURE_STAGES = frozenset(
    {
        "account_session_binding",
        "account_eligibility",
        "authorization_response",
        "identity_lookup",
        "proof_storage",
        "token_validation",
        "transaction",
        "other_validation",
    }
)

_CONSUME_TRANSACTION_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return false end
local transaction = cjson.decode(raw)
if transaction['browser_binding'] ~= ARGV[1] then return false end
redis.call('DEL', KEYS[1])
return raw
"""


class OAuthConfigurationError(RuntimeError):
    pass


class OAuthTransactionError(RuntimeError):
    pass


class OAuthBackendUnavailable(RuntimeError):
    pass


class GoogleProviderError(RuntimeError):
    pass


class GoogleTokenError(RuntimeError):
    pass


class GoogleFreshnessError(GoogleTokenError):
    def __init__(self, failure_stage: str):
        if failure_stage not in {
            "freshness_missing_auth_time",
            "freshness_stale_auth_time",
            "other_validation",
        }:
            failure_stage = "other_validation"
        self.failure_stage = failure_stage
        super().__init__("Google authentication is not recent")


def local_diagnostic(stage: str) -> None:
    """Temporary opt-in local diagnostics: never log request or claim values."""
    if (
        os.environ.get("VERVFY_ENVIRONMENT", "").lower() in {"local", "development", "test"}
        and os.environ.get("VERVFY_GOOGLE_OAUTH_DIAGNOSTICS") == "1"
    ):
        logging.getLogger("vervfy.oauth").warning("Google OAuth stage: %s", stage)


def log_google_reauthentication_failure(stage: str) -> None:
    environment = (
        os.environ.get("VERVFY_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT", "")
    ).strip().lower()
    if environment not in {
        "production",
        "prod",
    }:
        return
    safe_stage = (
        stage
        if stage in GOOGLE_REAUTHENTICATION_FAILURE_STAGES
        else "other_validation"
    )
    message = (
        "Google OAuth callback failure stage=%s"
        if safe_stage == "transaction"
        else "Google reauthentication failure stage=%s"
    )
    logging.getLogger("vervfy.oauth").warning(
        message, safe_stage
    )


def log_google_identity_confirmation_failure(stage: str) -> None:
    environment = (
        os.environ.get("VERVFY_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT", "")
    ).strip().lower()
    if environment not in {"production", "prod"}:
        return
    safe_stage = (
        stage
        if stage in GOOGLE_IDENTITY_CONFIRMATION_FAILURE_STAGES
        else "other_validation"
    )
    logging.getLogger("vervfy.oauth").warning(
        "Google password setup identity confirmation failure stage=%s",
        safe_stage,
    )


class OAuthAccessLogFilter(logging.Filter):
    """Remove OAuth callback parameters before Uvicorn formats access records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, target, version, status = record.args
            if isinstance(target, str) and target.split("?", 1)[0] == CALLBACK_PATH:
                record.args = (client, method, CALLBACK_PATH, version, status)
        return True


def _origin_parts(value: str):
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        raise OAuthConfigurationError(
            "Invalid Google OAuth origin configuration"
        ) from None
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OAuthConfigurationError("Invalid Google OAuth origin configuration")
    return parsed


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_origin: str
    redis_url: str
    identity_lookup_database_url: str
    test_user_email: str = ""

    def require_test_user(self, email: Any, *, email_verified: Any) -> None:
        """Accept only the configured email from verified server-owned claims."""
        if (
            not self.test_user_email
            or email_verified is not True
            or not isinstance(email, str)
            or email.casefold() != self.test_user_email.casefold()
        ):
            raise GoogleTokenError("Google authentication is restricted")

    @classmethod
    def from_environment(cls) -> GoogleOAuthConfig | None:
        enabled = os.environ.get("GOOGLE_OAUTH_ENABLED", "0").strip().lower()
        if enabled in {"0", "false", "off", "no", ""}:
            return None
        if enabled not in {"1", "true", "on", "yes"}:
            raise OAuthConfigurationError("GOOGLE_OAUTH_ENABLED must be boolean")

        test_user_email = os.environ.get("GOOGLE_OAUTH_TEST_USER_EMAIL", "").strip()
        if (
            len(test_user_email) > 254
            or not re.fullmatch(
                r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
                r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
                r"[A-Za-z]{2,63}",
                test_user_email,
            )
            or len(test_user_email.split("@", 1)[0]) > 64
        ):
            raise OAuthConfigurationError(
                "GOOGLE_OAUTH_TEST_USER_EMAIL must contain one valid email address"
            )

        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
        frontend_origin = os.environ.get("GOOGLE_FRONTEND_ORIGIN", "").strip()
        redis_url = os.environ.get("REDIS_URL", "").strip()
        lookup_url = os.environ.get(
            "GOOGLE_IDENTITY_LOOKUP_DATABASE_URL", ""
        ).strip()
        if not all(
            (
                client_id,
                client_secret,
                redirect_uri,
                frontend_origin,
                redis_url,
                lookup_url,
            )
        ):
            raise OAuthConfigurationError(
                "Google OAuth requires client credentials, callback/origin, Redis, "
                "and the restricted identity-lookup database URL"
            )
        if any(character.isspace() for character in client_id):
            raise OAuthConfigurationError("Invalid Google OAuth client ID")

        frontend = _origin_parts(frontend_origin)
        callback = _origin_parts(redirect_uri)
        if (
            callback.path != CALLBACK_PATH
            or callback.scheme != frontend.scheme
            or callback.netloc.lower() != frontend.netloc.lower()
        ):
            raise OAuthConfigurationError(
                "Google redirect URI must be the configured frontend callback"
            )
        if frontend.path not in {"", "/"}:
            raise OAuthConfigurationError(
                "Google frontend origin must not include a path"
            )
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if callback.scheme != "https" and callback.hostname not in local_hosts:
            raise OAuthConfigurationError(
                "Google OAuth requires HTTPS except on localhost"
            )
        if (
            os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower()
            in {"production", "prod"}
            and callback.scheme != "https"
        ):
            raise OAuthConfigurationError(
                "Production Google OAuth requires HTTPS"
            )
        try:
            lookup_url = lookup_url.replace(
                "postgres://", "postgresql+psycopg://", 1
            )
            if lookup_url.startswith("postgresql://"):
                lookup_url = lookup_url.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                )
            lookup_parsed = make_url(lookup_url)
            if (
                lookup_parsed.get_backend_name() != "postgresql"
                or lookup_parsed.drivername != "postgresql+psycopg"
            ):
                raise ValueError
            application_url = os.environ.get("DATABASE_URL", "").strip()
            if application_url:
                application_url = application_url.replace(
                    "postgres://", "postgresql+psycopg://", 1
                )
                if application_url.startswith("postgresql://"):
                    application_url = application_url.replace(
                        "postgresql://", "postgresql+psycopg://", 1
                    )
                application_parsed = make_url(application_url)
                same_principal = (
                    lookup_parsed.host,
                    lookup_parsed.port,
                    lookup_parsed.username,
                    lookup_parsed.database,
                ) == (
                    application_parsed.host,
                    application_parsed.port,
                    application_parsed.username,
                    application_parsed.database,
                )
                if same_principal:
                    raise ValueError
            if (
                os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower()
                in {"production", "prod"}
                and lookup_parsed.query.get("sslmode")
                not in {"require", "verify-ca", "verify-full"}
            ):
                lookup_parsed = lookup_parsed.set(
                    query={**lookup_parsed.query, "sslmode": "require"}
                )
            lookup_url = lookup_parsed.render_as_string(hide_password=False)
        except (ArgumentError, ValueError, TypeError):
            raise OAuthConfigurationError(
                "Google identity lookup must use a dedicated PostgreSQL URL"
            ) from None

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            frontend_origin=frontend_origin.rstrip("/"),
            redis_url=redis_url,
            identity_lookup_database_url=lookup_url,
            test_user_email=test_user_email.casefold(),
        )

    @property
    def browser_cookie_name(self) -> str:
        return (
            "__Host-vervfy_google_oauth"
            if urlsplit(self.redirect_uri).scheme == "https"
            else "vervfy_google_oauth"
        )

    @property
    def cookie_secure(self) -> bool:
        return urlsplit(self.redirect_uri).scheme == "https"


class RedisOAuthTransactionStore:
    """Atomic one-time transactions; intentionally has no local fallback."""

    KEY_PREFIX = "vervfy:oauth:google:transaction:"
    TTL_SECONDS = TRANSACTION_TTL_SECONDS

    def __init__(
        self,
        redis_url: str,
        *,
        client: Any | None = None,
    ):
        if not redis_url and client is None:
            raise OAuthConfigurationError("Redis is required for Google OAuth")
        try:
            self._redis = client or redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        except (redis.RedisError, ValueError) as exc:
            raise OAuthConfigurationError(
                "Could not configure Google OAuth Redis transactions"
            ) from exc

    @staticmethod
    def state_digest(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    @staticmethod
    def binding_digest(browser_binding: str) -> str:
        return hashlib.sha256(browser_binding.encode("utf-8")).hexdigest()

    def create(self, state: str, transaction: dict[str, Any]) -> None:
        key = f"{self.KEY_PREFIX}{self.state_digest(state)}"
        try:
            stored = self._redis.set(
                key,
                json.dumps(transaction, separators=(",", ":"), sort_keys=True),
                ex=self.TTL_SECONDS,
                nx=True,
            )
        except redis.RedisError as exc:
            raise OAuthBackendUnavailable(
                "Google OAuth transaction service unavailable"
            ) from exc
        if not stored:
            raise OAuthTransactionError("Could not create OAuth transaction")

    def consume(
        self, state: str, browser_binding: str
    ) -> dict[str, Any] | None:
        key = f"{self.KEY_PREFIX}{self.state_digest(state)}"
        binding_digest = self.binding_digest(browser_binding)
        try:
            raw = self._redis.eval(
                _CONSUME_TRANSACTION_SCRIPT, 1, key, binding_digest
            )
        except redis.RedisError as exc:
            raise OAuthBackendUnavailable(
                "Google OAuth transaction service unavailable"
            ) from exc
        if not raw:
            return None
        try:
            transaction = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise OAuthBackendUnavailable(
                "Google OAuth transaction data is invalid"
            ) from exc
        if not isinstance(transaction, dict):
            raise OAuthBackendUnavailable(
                "Google OAuth transaction data is invalid"
            )
        return transaction

    def put_once(
        self, namespace: str, binding: str, value: dict[str, Any], ttl: int
    ) -> bool:
        key = self._ephemeral_key(namespace, binding)
        try:
            return bool(
                self._redis.set(
                    key,
                    json.dumps(value, separators=(",", ":"), sort_keys=True),
                    ex=ttl,
                    nx=True,
                )
            )
        except redis.RedisError as exc:
            raise OAuthBackendUnavailable(
                "Google OAuth transaction service unavailable"
            ) from exc

    def consume_once(self, namespace: str, binding: str) -> dict[str, Any] | None:
        key = self._ephemeral_key(namespace, binding)
        try:
            raw = self._redis.eval(
                "local value = redis.call('GET', KEYS[1]); "
                "if value then redis.call('DEL', KEYS[1]) end; "
                "return value",
                1,
                key,
            )
        except redis.RedisError as exc:
            raise OAuthBackendUnavailable(
                "Google OAuth transaction service unavailable"
            ) from exc
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise OAuthBackendUnavailable(
                "Google OAuth transaction data is invalid"
            ) from exc
        if not isinstance(value, dict):
            raise OAuthBackendUnavailable(
                "Google OAuth transaction data is invalid"
            )
        return value

    def _ephemeral_key(self, namespace: str, binding: str) -> str:
        digest = hashlib.sha256(binding.encode("utf-8")).hexdigest()
        return f"{self.KEY_PREFIX}ephemeral:{namespace}:{digest}"

    def close(self) -> None:
        self._redis.close()


class GoogleOAuthService:
    def __init__(
        self,
        config: GoogleOAuthConfig,
        *,
        transaction_store: RedisOAuthTransactionStore | None = None,
        identity_engine: Engine | None = None,
        oidc_app: Any | None = None,
        oauth_client_factory: Any = AsyncOAuth2Client,
        clock=time.time,
    ):
        self.config = config
        self._owns_transaction_store = transaction_store is None
        self.transactions = transaction_store or RedisOAuthTransactionStore(
            config.redis_url
        )
        self._clock = clock
        self._owns_identity_engine = identity_engine is None
        self.identity_engine = identity_engine or create_engine(
            config.identity_lookup_database_url,
            pool_pre_ping=True,
            connect_args={"prepare_threshold": None},
        )
        self._oauth_client_factory = oauth_client_factory
        if oidc_app is None:
            oauth = OAuth()
            oidc_app = oauth.register(
                name="google",
                client_id=config.client_id,
                client_secret=config.client_secret,
                server_metadata_url=GOOGLE_DISCOVERY_URL,
                authorize_url=GOOGLE_AUTHORIZATION_ENDPOINT,
                access_token_url=GOOGLE_TOKEN_ENDPOINT,
                client_kwargs={
                    "scope": "openid email profile",
                    "code_challenge_method": "S256",
                },
            )
        self._oidc_app = oidc_app

    async def _trusted_metadata(self) -> dict[str, Any]:
        try:
            metadata = await self._oidc_app.load_server_metadata()
        except (httpx2.HTTPError, AuthlibBaseError, ValueError) as exc:
            raise GoogleProviderError("Google OIDC metadata is unavailable") from exc
        algorithms = (
            metadata.get("id_token_signing_alg_values_supported")
            if isinstance(metadata, dict)
            else None
        )
        if (
            not isinstance(metadata, dict)
            or not isinstance(algorithms, (list, tuple))
            or metadata.get("issuer") != GOOGLE_ISSUER
            or metadata.get("authorization_endpoint")
            != GOOGLE_AUTHORIZATION_ENDPOINT
            or metadata.get("token_endpoint") != GOOGLE_TOKEN_ENDPOINT
            or metadata.get("jwks_uri") != GOOGLE_JWKS_URI
            or "RS256" not in algorithms
        ):
            raise GoogleProviderError("Google OIDC metadata is not trusted")
        metadata["id_token_signing_alg_values_supported"] = ["RS256"]
        return metadata

    async def create_authorization_url(
        self,
        browser_binding: str,
        *,
        purpose: str = "login",
        context: dict[str, Any] | None = None,
    ) -> str:
        if not browser_binding or len(browser_binding) < 32:
            raise OAuthTransactionError("Invalid browser binding")
        if purpose not in GOOGLE_FLOW_PURPOSES:
            raise OAuthTransactionError("Invalid Google OAuth purpose")
        if purpose not in {"login", "signup"} and not context:
            raise OAuthTransactionError("Account-bound OAuth context is required")
        await self._trusted_metadata()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        issued_at = int(self._clock())
        authorization_params: dict[str, Any] = {
            "state": state,
            "nonce": nonce,
            "code_verifier": verifier,
            "redirect_uri": self.config.redirect_uri,
        }
        if purpose in GOOGLE_IDENTITY_CONFIRMATION_PURPOSES:
            # Account selection is a documented identity confirmation prompt;
            # it is not treated as proof of recent Google credential entry.
            authorization_params["prompt"] = "select_account"
        elif purpose not in {"login", "signup"}:
            # Google returns auth_time only when this claim is requested and
            # the project's Session age claims setting is enabled.
            authorization_params.update(
                {
                    "max_age": FRESH_AUTH_MAX_AGE_SECONDS,
                    "claims": json.dumps(
                        {"id_token": {"auth_time": {"essential": True}}},
                        separators=(",", ":"),
                    ),
                }
            )
        try:
            async with self._oauth_client_factory(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scope="openid email profile",
                redirect_uri=self.config.redirect_uri,
                code_challenge_method="S256",
            ) as client:
                authorization_url, returned_state = client.create_authorization_url(
                    GOOGLE_AUTHORIZATION_ENDPOINT,
                    **authorization_params,
                )
        except (httpx2.HTTPError, AuthlibBaseError, ValueError, TypeError) as exc:
            raise GoogleProviderError(
                "Could not create Google authorization request"
            ) from exc
        if returned_state != state:
            raise GoogleProviderError("Google authorization state mismatch")

        transaction = {
            "purpose": purpose,
            "nonce": nonce,
            "code_verifier": verifier,
            "browser_binding": self.transactions.binding_digest(browser_binding),
            "issued_at": issued_at,
        }
        if context:
            transaction.update(context)
        await run_in_threadpool(self.transactions.create, state, transaction)
        return str(authorization_url)

    async def consume_transaction(
        self, state: str, browser_binding: str
    ) -> dict[str, Any]:
        if not state or len(state) > 512 or not browser_binding:
            raise OAuthTransactionError("Invalid OAuth transaction")
        transaction = await run_in_threadpool(
            self.transactions.consume, state, browser_binding
        )
        if (
            transaction is None
            or transaction.get("purpose") not in GOOGLE_FLOW_PURPOSES
        ):
            raise OAuthTransactionError("Invalid or replayed OAuth transaction")
        issued_at = transaction.get("issued_at")
        if (
            not isinstance(issued_at, int)
            or isinstance(issued_at, bool)
            or issued_at > self._clock() + CLOCK_SKEW_SECONDS
            or self._clock() - issued_at > TRANSACTION_TTL_SECONDS
        ):
            raise OAuthTransactionError("Expired OAuth transaction")
        if not all(
            isinstance(transaction.get(name), str) and transaction[name]
            for name in ("nonce", "code_verifier")
        ):
            raise OAuthTransactionError("Invalid OAuth transaction")
        return transaction

    async def exchange_and_validate(
        self, code: str, transaction: dict[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(code, str) or not code or len(code) > 4096:
            raise GoogleTokenError("Invalid Google authorization response")
        try:
            async with self._oauth_client_factory(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scope="openid email profile",
                redirect_uri=self.config.redirect_uri,
                code_challenge_method="S256",
            ) as client:
                token = await client.fetch_token(
                    GOOGLE_TOKEN_ENDPOINT,
                    grant_type="authorization_code",
                    code=code,
                    redirect_uri=self.config.redirect_uri,
                    code_verifier=transaction["code_verifier"],
                )
        except httpx2.HTTPError as exc:
            raise GoogleProviderError("Google token endpoint is unavailable") from exc
        except (AuthlibBaseError, ValueError, TypeError, KeyError) as exc:
            raise GoogleTokenError("Google authorization code was rejected") from exc
        try:
            await self._trusted_metadata()
            userinfo = await self._oidc_app.parse_id_token(
                token,
                nonce=transaction["nonce"],
                claims_options={
                    "iss": {"values": list(GOOGLE_ISSUERS)},
                    "aud": {"values": [self.config.client_id]},
                },
                leeway=CLOCK_SKEW_SECONDS,
            )
            if userinfo is None:
                raise GoogleTokenError("Google response did not contain an ID token")
            # Authlib UserInfo preserves the verified JWT claims; do not use
            # UserInfo.filter(), which would discard non-profile claims.
            claims = dict(userinfo)
            self._validate_required_claims(claims, transaction["nonce"])
            return claims
        except GoogleTokenError:
            raise
        except httpx2.HTTPError as exc:
            raise GoogleProviderError("Google signing keys are unavailable") from exc
        except (AuthlibBaseError, JoseError, ValueError, TypeError, KeyError) as exc:
            raise GoogleTokenError("Google ID token validation failed") from exc

    def _validate_required_claims(
        self, claims: dict[str, Any], expected_nonce: str
    ) -> None:
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise GoogleTokenError("Unexpected Google issuer")
        audience = claims.get("aud")
        audience_matches = (
            audience == self.config.client_id
            if isinstance(audience, str)
            else isinstance(audience, list)
            and self.config.client_id in audience
            and all(isinstance(item, str) for item in audience)
        )
        if not audience_matches:
            raise GoogleTokenError("Google token audience mismatch")
        if claims.get("azp") not in (None, self.config.client_id):
            raise GoogleTokenError("Google authorized party mismatch")
        nonce = claims.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(
            nonce, expected_nonce
        ):
            raise GoogleTokenError("Google token nonce mismatch")
        subject = claims.get("sub")
        if (
            not isinstance(subject, str)
            or not subject
            or len(subject) > 255
            or "\x00" in subject
        ):
            raise GoogleTokenError("Google token subject is invalid")
        now = self._clock()
        for name in ("exp", "iat", "nbf", "auth_time"):
            timestamp = claims.get(name)
            if name in {"exp", "iat"} and timestamp is None:
                raise GoogleTokenError(f"Google token is missing {name}")
            if timestamp is None:
                continue
            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, (int, float))
                or not math.isfinite(timestamp)
            ):
                raise GoogleTokenError(f"Google token has invalid {name}")
            if name == "exp" and timestamp + CLOCK_SKEW_SECONDS < now:
                raise GoogleTokenError("Google token has expired")
            if name in {"iat", "nbf", "auth_time"} and timestamp > (
                now + CLOCK_SKEW_SECONDS
            ):
                raise GoogleTokenError(f"Google token has future {name}")

    def lookup_identity(self, claims: dict[str, Any]) -> str | None:
        issuer = claims.get("iss")
        subject = claims.get("sub")
        if issuer not in GOOGLE_ISSUERS or not isinstance(subject, str):
            raise GoogleTokenError("Google identity claims are invalid")
        with self.identity_engine.connect() as connection:
            for trusted_issuer in (GOOGLE_ISSUER, "accounts.google.com"):
                user_id = lookup_verified_google_identity(
                    connection, issuer=trusted_issuer, subject=subject
                )
                if user_id:
                    return user_id
        return None

    def require_fresh_authentication(self, claims: dict[str, Any]) -> int:
        # Google may omit this opt-in claim and does not guarantee forced
        # reauthentication. A new token (iat) cannot prove a new authentication.
        auth_time = claims.get("auth_time")
        now = self._clock()
        failure_stage = "other_validation"
        if auth_time is None:
            local_diagnostic("freshness_missing_auth_time")
            failure_stage = "freshness_missing_auth_time"
        elif isinstance(auth_time, bool) or not isinstance(auth_time, int):
            local_diagnostic("freshness_invalid_auth_time")
        elif auth_time > now + CLOCK_SKEW_SECONDS:
            local_diagnostic("freshness_future_auth_time")
        elif now - auth_time > FRESH_AUTH_MAX_AGE_SECONDS:
            local_diagnostic("freshness_stale_auth_time")
            failure_stage = "freshness_stale_auth_time"
        if (
            isinstance(auth_time, bool)
            or not isinstance(auth_time, int)
            or auth_time > now + CLOCK_SKEW_SECONDS
            or now - auth_time > FRESH_AUTH_MAX_AGE_SECONDS
        ):
            raise GoogleFreshnessError(failure_stage)
        return auth_time

    def store_pending_signup(
        self, browser_binding: str, claims: dict[str, Any],
        *, original_signup: dict[str, Any] | None = None,
    ) -> bool:
        # Preserve the original signup receipt through username-conflict retries.
        # This context is server-owned pending data, never ID-token/client claims.
        receipt = (
            {key: original_signup[key] for key in ("signup_transaction", "signup_verified_at")
             if key in original_signup}
            if original_signup is not None
            else {"signup_transaction": secrets.token_hex(32),
                  "signup_verified_at": int(self._clock())}
        )
        return self.transactions.put_once(
            "signup",
            self.transactions.binding_digest(browser_binding),
            {
                **receipt,
                "issuer": GOOGLE_ISSUER,
                "subject": claims["sub"],
                "email": claims.get("email")
                if claims.get("email_verified") is True
                else None,
            },
            TRANSACTION_TTL_SECONDS,
        )

    def consume_pending_signup(self, browser_binding: str) -> dict[str, Any] | None:
        return self.transactions.consume_once(
            "signup", self.transactions.binding_digest(browser_binding)
        )

    def store_reauthentication_proof(
        self, session_id: str, purpose: str, proof: dict[str, Any]
    ) -> bool:
        return self.transactions.put_once(
            f"proof:{purpose}",
            session_id,
            proof,
            CREDENTIAL_PROOF_TTL_SECONDS,
        )

    def consume_reauthentication_proof(
        self, session_id: str, purpose: str
    ) -> dict[str, Any] | None:
        return self.transactions.consume_once(
            f"proof:{purpose}", session_id
        )

    def store_password_add_identity_proof(
        self, session_id: str, proof: dict[str, Any]
    ) -> bool:
        return self.transactions.put_once(
            "proof:password_add:identity",
            session_id,
            proof,
            CREDENTIAL_PROOF_TTL_SECONDS,
        )

    def consume_password_add_identity_proof(
        self, session_id: str
    ) -> dict[str, Any] | None:
        return self.transactions.consume_once(
            "proof:password_add:identity", session_id
        )

    def close(self) -> None:
        if self._owns_identity_engine:
            self.identity_engine.dispose()
        if self._owns_transaction_store:
            self.transactions.close()
