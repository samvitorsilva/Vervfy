"""Dormant registration/recovery services. No routes or account recovery grants.

Every SQL write belongs to the caller's transaction. Return values (especially
codes and session cookies) must not be published before commit. No function here
may be wired to a route without CSRF, request-size and network rate-limit review.
"""

import hashlib
import json
import re
import secrets
import time
import uuid

import redis
import sqlalchemy as sa
from webauthn import (
    generate_registration_options,
    options_to_json,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.decode_credential_public_key import decode_credential_public_key
from webauthn.helpers.parse_registration_credential_json import (
    parse_registration_credential_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    CredentialDeviceType,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

import auth
import passkey_schema as s
from db import ProviderIdentity, User
from google_oauth import GOOGLE_ISSUER
from passkeys import (
    Binding,
    Config,
    PasskeyError,
    PasskeyUnavailable,
    _tenant,
    consume_proof,
)

RECOVERY_DIGEST = hashlib.sha256(b"vervfy:initial-recovery-codes:v1").hexdigest()


class SecurityGate:
    """Mandatory live-session validation and shared Redis attempt budgets."""

    WINDOW = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"

    def __init__(self, client, sessions):
        if client is None or sessions is None:
            raise PasskeyUnavailable("Session and rate-limit backends required")
        self.client, self.sessions = client, sessions

    def check(self, binding, scope, limit=10):
        try:
            if not self.sessions.is_valid(binding.session_id, binding.user_id):
                raise PasskeyError("Live session required")
            key = (
                "vervfy:passkey:limit:"
                + scope
                + ":"
                + hashlib.sha256(binding.user_id.encode()).hexdigest()
            )
            if int(self.client.eval(self.WINDOW, 1, key, 900)) > limit:
                raise PasskeyError("Verification attempt limit exceeded")
        except PasskeyError:
            raise
        except (redis.RedisError, RuntimeError):
            raise PasskeyUnavailable("Security backend unavailable") from None


def _grant(session, binding, method, now, signup_transaction=None, *, expires_at=None):
    _tenant(session, binding)
    if binding.action != "passkey_add":
        raise PasskeyError("Enrollment action required")
    identifier = secrets.token_urlsafe(32)
    values = binding.record()
    values.pop("action")
    session.execute(
        s.enrollments.insert().values(
            id=identifier,
            **values,
            method=method,
            signup_transaction=signup_transaction,
            created_at=now,
            expires_at=min(now + 300, expires_at)
            if expires_at is not None
            else now + 300,
        )
    )
    return identifier


def _authorization(session, binding, identifier, now):
    _tenant(session, binding)
    if binding.action != "passkey_add":
        raise PasskeyError("Enrollment action required")
    row = (
        session.execute(
            sa.select(s.enrollments)
            .where(
                s.enrollments.c.id == identifier,
                s.enrollments.c.user_id == binding.user_id,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if (
        not row
        or row["session_binding"] != binding.session_digest
        or row["session_version"] != binding.session_version
        or row["consumed_at"] is not None
        or not row["created_at"] <= now < row["expires_at"]
    ):
        raise PasskeyError("Invalid enrollment authorization")
    return row


class RegistrationService:
    def __init__(self, config, challenges, gate, *, clock=time.time):
        if not isinstance(config, Config):
            raise PasskeyUnavailable("Registration disabled")
        self.config, self.challenges, self.gate, self.clock = (
            config,
            challenges,
            gate,
            clock,
        )

    def authorize_password(self, session, binding, password):
        self.gate.check(binding, "password-enrollment")
        _tenant(session, binding)
        row = session.get(User, binding.user_id)
        # Preserve the current-password limiter's key, limits and successful reset.
        throttle = auth.RequestThrottle()
        throttle._redis = self.gate.client
        key = "current-password:" + binding.user_id
        if throttle.peek(key, 900) >= 10:
            raise PasskeyError("Current-password attempt limit exceeded")
        if (
            not row
            or not row.password_hash
            or not auth.verify_password(password, row.password_hash)
        ):
            throttle.allow(key, 10, 900)
            raise PasskeyError("Current password verification failed")
        throttle.discard(key)
        return _grant(session, binding, "password", int(self.clock()))

    def create_google_signup(self, session, oauth, browser_binding, username):
        """Alternative onboarding transaction, deliberately NOT called by existing routes.

        Consumes the actual Google pending-signup store. Always INSERTs a new user
        and provider identity; cannot grant enrollment to an existing account.
        Caller opens a fresh transaction; this method chooses its tenant itself.
        """
        if not session.in_transaction() or session.info.get("tenant_id"):
            raise PasskeyError("Fresh signup transaction required")
        if auth.validate_username(username):
            raise PasskeyError("Invalid signup username")
        pending = oauth.consume_pending_signup(browser_binding)
        now = int(self.clock())
        if (
            not isinstance(pending, dict)
            or pending.get("issuer") != GOOGLE_ISSUER
            or not isinstance(pending.get("subject"), str)
            or not pending["subject"]
            or not re.fullmatch(r"[0-9a-f]{64}", pending.get("signup_transaction", ""))
            or type(pending.get("signup_verified_at")) is not int
            or not pending["signup_verified_at"]
            <= now
            < pending["signup_verified_at"] + 300
        ):
            raise PasskeyError("Valid original Google signup required")
        if (
            oauth.lookup_identity({"iss": GOOGLE_ISSUER, "sub": pending["subject"]})
            is not None
        ):
            raise PasskeyError("Existing accounts cannot receive signup enrollment")
        email = pending.get("email")
        if email is not None and (
            not isinstance(email, str) or auth.validate_email(email)
        ):
            raise PasskeyError("Invalid signup email")
        user_id = uuid.uuid4().hex
        session.info["tenant_id"] = user_id
        if session.get_bind().dialect.name == "postgresql":
            session.execute(
                sa.text("SELECT set_config('app.current_user_id',:tenant,true)"),
                {"tenant": user_id},
            )
        user = User(
            id=user_id,
            username=username,
            username_key=username.lower(),
            email=email.strip().lower() if email else None,
            email_verified=bool(email),
            password_hash=None,
            session_version=0,
            created_at=now,
        )
        session.add(user)
        session.flush()
        session.add(
            ProviderIdentity(
                issuer=GOOGLE_ISSUER,
                subject=pending["subject"],
                user_id=user_id,
                created_at=now,
            )
        )
        session.flush()  # Unique issuer+subject rejects an existing Google identity.
        sid = self.gate.sessions.create(user_id)
        binding = Binding(user_id, sid, 0, "passkey_add")
        try:
            grant = _grant(
                session,
                binding,
                "google_signup",
                now,
                pending["signup_transaction"],
                expires_at=pending["signup_verified_at"] + 300,
            )
        except Exception:
            self.gate.sessions.revoke(sid)
            raise
        # A rolled-back later transaction leaves at most an orphan sid: no user,
        # therefore existing current_user_row rejects it. Never return cookie early.
        return binding, grant

    def begin(self, session, binding, authorization_id):
        self.gate.check(binding, "registration-begin")
        now = int(self.clock())
        authorization = _authorization(session, binding, authorization_id, now)
        rows = (
            session.execute(
                sa.select(s.credentials).where(
                    s.credentials.c.user_id == binding.user_id
                )
            )
            .mappings()
            .all()
        )
        if len(rows) >= 10:
            raise PasskeyError("Credential limit reached")
        handle = session.execute(
            sa.select(s.handles.c.handle).where(s.handles.c.user_id == binding.user_id)
        ).scalar_one_or_none()
        if handle is None:
            handle = secrets.token_bytes(32)
            session.execute(
                s.handles.insert().values(user_id=binding.user_id, handle=handle)
            )
        challenge = secrets.token_bytes(32)
        record = dict(
            binding.record(),
            ceremony="registration",
            authorization_id=authorization_id,
            handle=bytes_to_base64url(handle),
            challenge=bytes_to_base64url(challenge),
            issued_at=now,
            expires_at=min(now + 120, authorization["expires_at"]),
        )
        identifier = self.challenges.create(record)
        options = generate_registration_options(
            rp_id=self.config.rp_id,
            rp_name=self.config.rp_name,
            user_name=binding.user_id,
            user_id=handle,
            challenge=challenge,
            timeout=120000,
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.REQUIRED,
                resident_key=ResidentKeyRequirement.REQUIRED,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=row["credential_id"]) for row in rows
            ],
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_SHA_256,
                COSEAlgorithmIdentifier.EDDSA,
                COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
            ],
        )
        return identifier, json.loads(options_to_json(options))

    def finish(self, session, binding, authorization_id, challenge_id, response):
        self.gate.check(binding, "registration-finish")
        record = self.challenges.consume(challenge_id)
        now = int(self.clock())
        if (
            record.get("ceremony") != "registration"
            or record.get("authorization_id") != authorization_id
            or any(record.get(k) != v for k, v in binding.record().items())
            or type(record.get("issued_at")) is not int
            or type(record.get("expires_at")) is not int
            or not record["issued_at"] <= now < record["expires_at"]
            or record["expires_at"] > record["issued_at"] + 120
        ):
            raise PasskeyError("Invalid registration binding")
        _authorization(session, binding, authorization_id, now)
        handle = session.execute(
            sa.select(s.handles.c.handle).where(s.handles.c.user_id == binding.user_id)
        ).scalar_one()
        if bytes_to_base64url(handle) != record.get("handle"):
            raise PasskeyError("Registration handle changed")
        if (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(s.credentials)
                .where(s.credentials.c.user_id == binding.user_id)
            )
            >= 10
        ):
            raise PasskeyError("Credential limit reached")
        try:
            if not isinstance(response, dict) or len(json.dumps(response)) > 32768:
                raise ValueError
            parsed = parse_registration_credential_json(response)
            client = json.loads(parsed.response.client_data_json)
            if client.get("crossOrigin", False) is not False or "topOrigin" in client:
                raise ValueError
            verified = verify_registration_response(
                credential=parsed,
                expected_challenge=base64url_to_bytes(record["challenge"]),
                expected_rp_id=self.config.rp_id,
                expected_origin=list(self.config.origins),
                require_user_presence=True,
                require_user_verification=True,
            )
        except Exception:  # noqa: BLE001 - never expose untrusted library error data
            raise PasskeyError("Registration verification failed") from None
        identifier = secrets.token_urlsafe(32)
        session.execute(
            s.credentials.insert().values(
                id=identifier,
                user_id=binding.user_id,
                credential_id=verified.credential_id,
                public_key=verified.credential_public_key,
                algorithm=int(
                    decode_credential_public_key(verified.credential_public_key).alg
                ),
                sign_count=verified.sign_count,
                backup_eligible=verified.credential_device_type
                == CredentialDeviceType.MULTI_DEVICE,
                backed_up=verified.credential_backed_up,
                created_at=now,
            )
        )
        result = session.execute(
            s.enrollments.update()
            .where(
                s.enrollments.c.id == authorization_id,
                s.enrollments.c.user_id == binding.user_id,
                s.enrollments.c.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        if result.rowcount != 1:
            raise PasskeyError("Enrollment already consumed")
        return identifier


class RecoveryCodes:
    """Codes can produce only pending restricted state, never a replacement grant."""

    def __init__(self, config, gate, *, clock=time.time):
        if not isinstance(config, Config):
            raise PasskeyUnavailable("Recovery disabled")
        self.gate, self.clock = gate, clock

    @staticmethod
    def digest(user_id, code):
        return hashlib.sha256(
            b"vervfy:recovery:v1\0" + user_id.encode() + b"\0" + code.encode()
        ).digest()

    def issue_initial(self, session, binding, intent_id, proof_id):
        self.gate.check(binding, "recovery-issue", 5)
        if binding.action != "recovery_rotate":
            raise PasskeyError("Recovery action required")
        now = int(self.clock())
        _tenant(session, binding)
        if session.scalar(
            sa.select(sa.func.count())
            .select_from(s.recovery_codes)
            .where(s.recovery_codes.c.user_id == binding.user_id)
        ):
            raise PasskeyError("Recovery codes already issued; rotation not enabled")
        consume_proof(session, binding, intent_id, proof_id, RECOVERY_DIGEST, now=now)
        codes = [secrets.token_hex(32) for _ in range(10)]
        session.execute(
            s.recovery_codes.insert(),
            [
                {
                    "id": secrets.token_urlsafe(32),
                    "user_id": binding.user_id,
                    "code_hash": self.digest(binding.user_id, code),
                    "created_at": now,
                }
                for code in codes
            ],
        )
        return codes

    def consume(self, session, binding, code):
        self.gate.check(binding, "recovery-consume", 5)
        _tenant(session, binding)
        if (
            binding.action != "recovery_rotate"
            or not isinstance(code, str)
            or not re.fullmatch(r"[0-9a-f]{64}", code)
        ):
            raise PasskeyError("Invalid recovery request")
        now = int(self.clock())
        result = session.execute(
            s.recovery_codes.update()
            .where(
                s.recovery_codes.c.user_id == binding.user_id,
                s.recovery_codes.c.code_hash == self.digest(binding.user_id, code),
                s.recovery_codes.c.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        if result.rowcount != 1:
            raise PasskeyError("Invalid or consumed recovery code")
        identifier = secrets.token_urlsafe(32)
        session.execute(
            s.recovery_states.insert().values(
                id=identifier,
                user_id=binding.user_id,
                session_binding=binding.session_digest,
                session_version=binding.session_version,
                status="pending",
                created_at=now,
                expires_at=now + 300,
            )
        )
        return identifier
