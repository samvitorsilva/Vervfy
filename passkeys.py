"""Dormant WebAuthn assertion foundation. No enrollment or HTTP endpoints.

Callers must supply a validated live session and a tenant-scoped SQLAlchemy
transaction. No method commits, rotates sessions, or performs account mutations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import redis
import sqlalchemy as sa
from webauthn import (
    generate_authentication_options,
    options_to_json,
    verify_authentication_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.decode_credential_public_key import decode_credential_public_key
from webauthn.helpers.parse_authentication_credential_json import (
    parse_authentication_credential_json,
)
from webauthn.helpers.structs import (
    CredentialDeviceType,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

import passkey_schema as schema

ACTIONS = frozenset(
    {
        "password_add",
        "email_change",
        "logout_all",
        "account_delete",
        "passkey_add",
        "passkey_remove",
        "recovery_rotate",
    }
)
CHALLENGE_TTL = 120
PROOF_TTL = 300


class PasskeyError(RuntimeError):
    """Safe public error; never include assertion contents or library exceptions."""


class PasskeyUnavailable(PasskeyError):
    pass


@dataclass(frozen=True)
class Config:
    rp_id: str
    rp_name: str
    origins: tuple[str, ...]

    def __post_init__(self):
        # Deliberately require exact RP hostname origins, not arbitrary subdomains.
        if (
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", self.rp_id)
            or ".." in self.rp_id
            or "." not in self.rp_id
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                for label in self.rp_id.split(".")
            )
            or len(self.rp_id) > 253
            or self.rp_id.replace(".", "").isdigit()
            or any(
                self.rp_id == domain or self.rp_id.endswith("." + domain)
                for domain in (
                    "trycloudflare.com",
                    "ngrok.io",
                    "ngrok-free.app",
                    "localhost",
                )
            )
            or not self.rp_name.strip()
            or len(self.rp_name) > 64
            or not self.origins
        ):
            raise PasskeyError("Invalid WebAuthn configuration")
        for origin in self.origins:
            try:
                parsed = urlsplit(origin)
                valid = (
                    parsed.scheme == "https"
                    and parsed.hostname == self.rp_id
                    and not parsed.username
                    and not parsed.password
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and parsed.port in (None, 443)
                    and origin == "https://" + self.rp_id
                )
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise PasskeyError("Invalid WebAuthn origin")

    @classmethod
    def from_environment(cls):
        enabled = os.environ.get("VERVFY_WEBAUTHN_ENABLED", "0")
        if enabled == "0":
            return None
        if enabled != "1":
            raise PasskeyError("Invalid WebAuthn enable flag")
        try:
            origins = json.loads(os.environ["VERVFY_WEBAUTHN_ORIGINS"])
            if not isinstance(origins, list) or not all(
                isinstance(x, str) for x in origins
            ):
                raise ValueError
            return cls(
                os.environ["VERVFY_WEBAUTHN_RP_ID"],
                os.environ["VERVFY_WEBAUTHN_RP_NAME"],
                tuple(origins),
            )
        except (KeyError, ValueError, TypeError):
            raise PasskeyError("Missing or invalid WebAuthn configuration") from None


@dataclass(frozen=True)
class Binding:
    user_id: str
    session_id: str
    session_version: int
    action: str

    def __post_init__(self):
        if (
            not self.user_id
            or not self.session_id
            or self.action not in ACTIONS
            or type(self.session_version) is not int
            or self.session_version < 0
        ):
            raise PasskeyError("Invalid verification binding")

    @property
    def session_digest(self):
        return hashlib.sha256(self.session_id.encode()).hexdigest()

    def record(self):
        return {
            "user_id": self.user_id,
            "session_binding": self.session_digest,
            "session_version": self.session_version,
            "action": self.action,
        }


class ChallengeStore:
    """Mandatory Redis/Valkey. No process-local or outage fallback."""

    PREFIX = "vervfy:webauthn:challenge:"
    CONSUME = "local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]) end; return v"

    def __init__(self, client):
        if client is None:
            raise PasskeyUnavailable("WebAuthn challenge backend required")
        self.client = client

    def create(self, record):
        identifier = secrets.token_urlsafe(32)
        try:
            if not self.client.set(
                self.PREFIX + identifier, json.dumps(record), ex=CHALLENGE_TTL, nx=True
            ):
                raise PasskeyUnavailable("Challenge creation failed")
        except redis.RedisError:
            raise PasskeyUnavailable("Challenge backend unavailable") from None
        return identifier

    def consume(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{43}", identifier
        ):
            raise PasskeyError("Invalid challenge")
        try:
            raw = self.client.eval(self.CONSUME, 1, self.PREFIX + identifier)
        except redis.RedisError:
            raise PasskeyUnavailable("Challenge backend unavailable") from None
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise TypeError
            return record
        except (TypeError, ValueError):
            raise PasskeyError("Expired or consumed challenge") from None


def _tenant(session, binding):
    if not session.in_transaction() or session.info.get("tenant_id") != binding.user_id:
        raise PasskeyError("Explicit tenant transaction required")
    # Lock the account before intent/credential/proof rows, including at mutation.
    version = session.execute(
        sa.select(schema.users.c.session_version)
        .where(schema.users.c.id == binding.user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if version != binding.session_version:
        raise PasskeyError("Session version changed")


def _intent(session, binding, intent_id, now):
    row = (
        session.execute(
            sa.select(schema.intents)
            .where(
                schema.intents.c.id == intent_id,
                schema.intents.c.user_id == binding.user_id,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if (
        not row
        or any(row[k] != v for k, v in binding.record().items())
        or row["consumed_at"] is not None
        or not row["created_at"] <= now < row["expires_at"]
    ):
        raise PasskeyError("Invalid action intent")
    return row


def create_intent(session, binding, payload_digest, *, now=None):
    """Digest must describe a server-validated exact mutation; never raw passwords."""
    now = int(time.time()) if now is None else now
    _tenant(session, binding)
    if not re.fullmatch(r"[0-9a-f]{64}", payload_digest):
        raise PasskeyError("Invalid action digest")
    identifier = secrets.token_urlsafe(32)
    session.execute(
        schema.intents.insert().values(
            id=identifier,
            **binding.record(),
            payload_digest=payload_digest,
            created_at=now,
            expires_at=now + PROOF_TTL,
        )
    )
    return identifier


class AssertionService:
    def __init__(self, config: Config, challenges: ChallengeStore, *, clock=time.time):
        if not isinstance(config, Config):
            raise PasskeyUnavailable("WebAuthn is disabled")
        self.config, self.challenges, self.clock = config, challenges, clock

    def begin(self, session, binding, intent_id):
        _tenant(session, binding)
        now = int(self.clock())
        intent = _intent(session, binding, intent_id, now)
        rows = (
            session.execute(
                sa.select(schema.credentials).where(
                    schema.credentials.c.user_id == binding.user_id,
                    schema.credentials.c.revoked_at.is_(None),
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            raise PasskeyError("No active verification credential")
        challenge = secrets.token_bytes(32)
        record = dict(
            **binding.record(),
            intent_id=intent_id,
            credential_ids=[bytes_to_base64url(r["credential_id"]) for r in rows],
            challenge=bytes_to_base64url(challenge),
            issued_at=now,
            expires_at=min(now + CHALLENGE_TTL, intent["expires_at"]),
        )
        identifier = self.challenges.create(record)
        options = generate_authentication_options(
            rp_id=self.config.rp_id,
            challenge=challenge,
            timeout=CHALLENGE_TTL * 1000,
            user_verification=UserVerificationRequirement.REQUIRED,
            allow_credentials=[
                PublicKeyCredentialDescriptor(id=r["credential_id"]) for r in rows
            ],
        )
        return identifier, json.loads(options_to_json(options))

    def finish(self, session, binding, intent_id, challenge_id, response):
        # Burn before verification: malformed, mismatched and failed responses cannot replay.
        record = self.challenges.consume(challenge_id)
        now = int(self.clock())
        if (
            any(record.get(k) != v for k, v in binding.record().items())
            or record.get("intent_id") != intent_id
            or type(record.get("issued_at")) is not int
            or type(record.get("expires_at")) is not int
            or not record["issued_at"] <= now < record["expires_at"]
            or record["expires_at"] > record["issued_at"] + CHALLENGE_TTL
        ):
            raise PasskeyError("Invalid challenge binding or expiry")
        _tenant(session, binding)
        intent = _intent(session, binding, intent_id, now)
        try:
            if not isinstance(response, dict) or len(json.dumps(response)) > 32768:
                raise ValueError
            parsed = parse_authentication_credential_json(response)
            # Library checks the signed challenge/origin; reject embedding explicitly.
            client = json.loads(parsed.response.client_data_json)
            if client.get("crossOrigin", False) is not False or "topOrigin" in client:
                raise ValueError
        except Exception:  # noqa: BLE001 - sanitize all untrusted parser/library errors
            raise PasskeyError("Invalid WebAuthn response") from None
        credential = (
            session.execute(
                sa.select(schema.credentials)
                .where(
                    schema.credentials.c.user_id == binding.user_id,
                    schema.credentials.c.credential_id == parsed.raw_id,
                    schema.credentials.c.revoked_at.is_(None),
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not credential or parsed.id not in record.get("credential_ids", []):
            raise PasskeyError("Invalid verification credential")
        handle = session.execute(
            sa.select(schema.handles.c.handle).where(
                schema.handles.c.user_id == binding.user_id
            )
        ).scalar_one()
        if (
            parsed.response.user_handle is not None
            and parsed.response.user_handle != handle
        ):
            raise PasskeyError("Invalid user handle")
        try:
            key = decode_credential_public_key(credential["public_key"])
            if int(key.alg) != credential["algorithm"] or credential[
                "algorithm"
            ] not in (-7, -257, -8):
                raise ValueError
            # Synced authenticators may use zero or non-monotonic counters.
            # Replay protection comes from the atomic challenge, not these counters.
            verified = verify_authentication_response(
                credential=parsed,
                expected_challenge=base64url_to_bytes(record["challenge"]),
                expected_rp_id=self.config.rp_id,
                expected_origin=list(self.config.origins),
                credential_public_key=credential["public_key"],
                credential_current_sign_count=0
                if credential["backup_eligible"]
                else credential["sign_count"],
                require_user_verification=True,
            )
            backup_eligible = (
                verified.credential_device_type == CredentialDeviceType.MULTI_DEVICE
            )
            if backup_eligible != credential["backup_eligible"]:
                raise ValueError
        except Exception:  # noqa: BLE001 - sanitize all untrusted parser/library errors
            raise PasskeyError("WebAuthn verification failed") from None
        session.execute(
            schema.credentials.update()
            .where(
                schema.credentials.c.id == credential["id"],
                schema.credentials.c.user_id == binding.user_id,
            )
            .values(
                sign_count=max(credential["sign_count"], verified.new_sign_count),
                backed_up=verified.credential_backed_up,
                last_used_at=now,
            )
        )
        proof_id = secrets.token_urlsafe(32)
        session.execute(
            schema.proofs.insert().values(
                id=proof_id,
                user_id=binding.user_id,
                intent_id=intent_id,
                credential_id=credential["id"],
                verified_at=now,
                expires_at=min(now + PROOF_TTL, intent["expires_at"]),
            )
        )
        return proof_id


def consume_proof(session, binding, intent_id, proof_id, payload_digest, *, now=None):
    """Must run INSIDE the same transaction as the mutation. Never commits.

    Caller must not catch a mutation error and commit this transaction. Session
    allowlist validation and CSRF/rate limiting belong to future route integration.
    """
    now = int(time.time()) if now is None else now
    _tenant(session, binding)
    intent = _intent(session, binding, intent_id, now)
    if intent["payload_digest"] != payload_digest:
        raise PasskeyError("Action payload changed")
    proof = (
        session.execute(
            sa.select(schema.proofs)
            .where(
                schema.proofs.c.id == proof_id,
                schema.proofs.c.user_id == binding.user_id,
                schema.proofs.c.intent_id == intent_id,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if (
        not proof
        or proof["consumed_at"] is not None
        or not proof["verified_at"] <= now < proof["expires_at"]
    ):
        raise PasskeyError("Expired or consumed verification proof")
    active = session.execute(
        sa.select(schema.credentials.c.id)
        .where(
            schema.credentials.c.id == proof["credential_id"],
            schema.credentials.c.user_id == binding.user_id,
            schema.credentials.c.revoked_at.is_(None),
        )
        .with_for_update()
    ).first()
    if not active:
        raise PasskeyError("Verification credential revoked")
    for table, identifier in ((schema.proofs, proof_id), (schema.intents, intent_id)):
        result = session.execute(
            table.update()
            .where(
                table.c.id == identifier,
                table.c.user_id == binding.user_id,
                table.c.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        if result.rowcount != 1:
            raise PasskeyError("Verification already consumed")
