"""Local synthetic WebAuthn registration and recovery; no hosted services."""

import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import cbor2
import pytest
import redis
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session
from test_passkeys import assertion
from test_passkeys import redis_client as _redis_client

redis_client = _redis_client
from webauthn.helpers import bytes_to_base64url as b64

import account_transactions as mutations
import auth
import passkey_enrollment as e
import passkey_schema as s
import passkeys as p
from db import Base, User
from google_oauth import GoogleOAuthService, RedisOAuthTransactionStore


def migration28():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0028_webauthn_enrollment.py"
    )
    spec = importlib.util.spec_from_file_location("enrollment_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(redis_client):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(conn)
        s.metadata.create_all(conn)
    sessions = auth.SessionStore()
    with Session(engine) as session, session.begin():
        for user in ("a", "b"):
            session.add(
                User(
                    id=user,
                    username=user,
                    username_key=user,
                    email=None,
                    password_hash=auth.hash_password("test-password-strong"),
                    session_version=1,
                    created_at=1000,
                )
            )
    sid = sessions.create("a")
    binding = p.Binding("a", sid, 1, "passkey_add")
    config = p.Config("app.example.com", "Vervfy", ("https://app.example.com",))
    gate = e.SecurityGate(redis_client, sessions)
    service = e.RegistrationService(
        config, p.ChallengeStore(redis_client), gate, clock=lambda: 1000
    )
    # Isolate account rate-limit keys between tests without touching shared services.
    for key in redis_client.scan_iter("vervfy:passkey:limit:*"):
        redis_client.delete(key)
    redis_client.delete("vervfy:ratelimit:current-password:a")
    yield engine, service, binding, config, gate
    engine.dispose()


def authorize(env):
    engine, service, binding, _, _ = env
    with (
        Session(engine, info={"tenant_id": binding.user_id}) as session,
        session.begin(),
    ):
        return service.authorize_password(session, binding, "test-password-strong")


def begin(env, grant):
    with (
        Session(env[0], info={"tenant_id": env[2].user_id}) as session,
        session.begin(),
    ):
        return env[1].begin(session, env[2], grant)


def finish(env, grant, cid, response, binding=None):
    binding = binding or env[2]
    with (
        Session(env[0], info={"tenant_id": binding.user_id}) as session,
        session.begin(),
    ):
        return env[1].finish(session, binding, grant, cid, response)


def registration(
    challenge,
    *,
    credential=b"credential",
    origin="https://app.example.com",
    rp="app.example.com",
    flags=69,
    cross=False,
):
    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    cose = cbor2.dumps(
        {
            1: 2,
            3: -7,
            -1: 1,
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
    )
    data = (
        hashlib.sha256(rp.encode()).digest()
        + bytes([flags])
        + b"\0" * 4
        + b"\0" * 16
        + len(credential).to_bytes(2, "big")
        + credential
        + cose
    )
    client = json.dumps(
        {
            "type": "webauthn.create",
            "challenge": challenge,
            "origin": origin,
            "crossOrigin": cross,
        }
    ).encode()
    return key, {
        "id": b64(credential),
        "rawId": b64(credential),
        "type": "public-key",
        "response": {
            "clientDataJSON": b64(client),
            "attestationObject": b64(
                cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": data})
            ),
        },
    }


def enrolled(env):
    grant = authorize(env)
    cid, opts = begin(env, grant)
    key, response = registration(opts["challenge"])
    credential = finish(env, grant, cid, response)
    return key, credential


def test_registration_uv_multiple_and_authorization_replay(env):
    grant = authorize(env)
    cid, opts = begin(env, grant)
    assert opts["authenticatorSelection"]["userVerification"] == "required"
    _, response = registration(opts["challenge"])
    finish(env, grant, cid, response)
    with pytest.raises(p.PasskeyError):
        begin(env, grant)
    with pytest.raises(p.PasskeyError):
        finish(env, grant, cid, response)
    grant2 = authorize(env)
    cid, opts2 = begin(env, grant2)
    assert opts2["user"]["id"] == opts["user"]["id"]
    assert opts2["excludeCredentials"][0]["id"] == b64(b"credential")
    _, response = registration(opts2["challenge"], credential=b"second")
    finish(env, grant2, cid, response)
    with env[0].connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(s.credentials)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"origin": "https://evil.example.com"},
        {"rp": "evil.example.com"},
        {"flags": 65},
        {"flags": 68},
        {"cross": True},
    ],
)
def test_registration_rejects_invalid_and_burns_challenge(env, changes):
    grant = authorize(env)
    cid, opts = begin(env, grant)
    _, response = registration(opts["challenge"], **changes)
    with pytest.raises(p.PasskeyError):
        finish(env, grant, cid, response)
    with pytest.raises(p.PasskeyError):
        finish(env, grant, cid, response)


@pytest.mark.parametrize(
    "case",
    [
        "account",
        "session",
        "action",
        "expired",
        "grant",
        "challenge",
        "revoked-session",
    ],
)
def test_registration_bindings(env, case):
    grant = authorize(env)
    cid, opts = begin(env, grant)
    _, response = registration("wrong" if case == "challenge" else opts["challenge"])
    binding = env[2]
    if case == "account":
        binding = replace(binding, user_id="b", session_id=env[4].sessions.create("b"))
    if case == "session":
        binding = replace(binding, session_id=env[4].sessions.create("a"))
    if case == "action":
        binding = replace(binding, action="email_change")
    if case == "expired":
        env[1].clock = lambda: 1300
    if case == "revoked-session":
        env[4].sessions.revoke(binding.session_id)
    with pytest.raises(p.PasskeyError):
        finish(env, "bad" if case == "grant" else grant, cid, response, binding)


def test_duplicate_credential_rolls_back_authorization(env):
    enrolled(env)
    grant = authorize(env)
    cid, opts = begin(env, grant)
    _, response = registration(opts["challenge"])
    with pytest.raises(sa.exc.IntegrityError):
        finish(env, grant, cid, response)
    with env[0].connect() as conn:
        assert (
            conn.scalar(
                sa.select(s.enrollments.c.consumed_at).where(
                    s.enrollments.c.id == grant
                )
            )
            is None
        )
    with pytest.raises(p.PasskeyError):
        finish(env, grant, cid, response)


def test_passwordless_existing_account_and_throttling(env):
    with Session(env[0]) as session, session.begin():
        session.get(User, "a").password_hash = None
    with pytest.raises(p.PasskeyError):
        authorize(env)
    with Session(env[0]) as session, session.begin():
        session.get(User, "a").password_hash = auth.hash_password(
            "test-password-strong"
        )
    for _ in range(10):
        with (
            Session(env[0], info={"tenant_id": "a"}) as session,
            session.begin(),
            pytest.raises(p.PasskeyError),
        ):
            env[1].authorize_password(session, env[2], "wrong")
    with pytest.raises(p.PasskeyError):
        authorize(env)


def oauth_pending(env):
    oauth = object.__new__(GoogleOAuthService)
    oauth.transactions = RedisOAuthTransactionStore("", client=env[4].client)
    oauth._clock = lambda: 1000
    oauth.lookup_identity = Mock(return_value=None)
    browser = "new-signup-browser-" + env[2].session_id
    assert oauth.store_pending_signup(
        browser, {"sub": browser, "email_verified": False}
    )
    return oauth, browser


def test_signup_authorization_original_transaction_only(env):
    oauth, browser = oauth_pending(env)
    with Session(env[0]) as session, session.begin():
        binding, grant = env[1].create_google_signup(session, oauth, browser, "newuser")
    other = (env[0], env[1], binding, env[3], env[4])
    cid, opts = begin(other, grant)
    _, response = registration(opts["challenge"])
    finish(other, grant, cid, response)
    with Session(env[0]) as session, session.begin(), pytest.raises(p.PasskeyError):
        env[1].create_google_signup(session, oauth, browser, "otheruser")
    # A normal new session cannot use the signup-bound grant or mint a new one.
    relogin = replace(binding, session_id=env[4].sessions.create(binding.user_id))
    with (
        Session(env[0], info={"tenant_id": binding.user_id}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        env[1].begin(session, relogin, grant)
    with (
        Session(env[0], info={"tenant_id": binding.user_id}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        env[1].authorize_password(session, relogin, "test-password-strong")


def test_signup_existing_identity_and_expired_pending_denied(env):
    oauth, browser = oauth_pending(env)
    oauth.lookup_identity.return_value = "a"
    with Session(env[0]) as session, session.begin(), pytest.raises(p.PasskeyError):
        env[1].create_google_signup(session, oauth, browser, "existing")
    oauth, browser = oauth_pending(env)
    env[1].clock = lambda: 1300
    with Session(env[0]) as session, session.begin(), pytest.raises(p.PasskeyError):
        env[1].create_google_signup(session, oauth, browser, "expired")


def recovery_proof(env):
    key, _ = enrolled(env)
    binding = replace(env[2], action="recovery_rotate")
    service = p.AssertionService(
        env[3], p.ChallengeStore(env[4].client), clock=lambda: 1000
    )
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        intent = p.create_intent(session, binding, e.RECOVERY_DIGEST, now=1000)
        cid, opts = service.begin(session, binding, intent)
        handle = session.scalar(
            sa.select(s.handles.c.handle).where(s.handles.c.user_id == "a")
        )
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        proof = service.finish(
            session,
            binding,
            intent,
            cid,
            assertion(key, opts["challenge"], handle=handle),
        )
    return binding, intent, proof


def test_recovery_requires_assertion_and_only_creates_pending_state(env):
    binding, intent, proof = recovery_proof(env)
    recovery = e.RecoveryCodes(env[3], env[4], clock=lambda: 1000)
    with (
        Session(env[0], info={"tenant_id": "a"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        recovery.issue_initial(session, binding, intent, "fake")
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        codes = recovery.issue_initial(session, binding, intent, proof)
    assert len(set(codes)) == 10
    with env[0].connect() as conn:
        stored = conn.execute(sa.select(s.recovery_codes.c.code_hash)).scalars().all()
        assert all(code.encode() not in stored for code in codes)
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        state = recovery.consume(session, binding, codes[0])
    with (
        Session(env[0], info={"tenant_id": "a"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        recovery.consume(session, binding, codes[0])
    with env[0].connect() as conn:
        assert (
            conn.scalar(
                sa.select(s.recovery_states.c.status).where(
                    s.recovery_states.c.id == state
                )
            )
            == "pending"
        )
    for _ in range(5):
        with (
            Session(env[0], info={"tenant_id": "a"}) as session,
            session.begin(),
            pytest.raises(p.PasskeyError),
        ):
            recovery.consume(session, binding, "0" * 64)
    with (
        Session(env[0], info={"tenant_id": "a"}) as session,
        session.begin(),
        pytest.raises(p.PasskeyError),
    ):
        recovery.consume(session, binding, codes[1])


def test_database_failure_no_signup_grant_and_retry_requires_new_google_flow(env):
    with Session(env[0]) as session, session.begin():
        row = session.get(User, "a")
        row.username = "existinguser"
        row.username_key = "existinguser"
    oauth, browser = oauth_pending(env)
    with (
        Session(env[0]) as session,
        session.begin(),
        pytest.raises(sa.exc.IntegrityError),
    ):
        env[1].create_google_signup(session, oauth, browser, "existinguser")
    with env[0].connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(s.enrollments)) == 0
    with Session(env[0]) as session, session.begin(), pytest.raises(p.PasskeyError):
        env[1].create_google_signup(session, oauth, browser, "different")


def test_security_backend_outage_and_disabled(env):
    with pytest.raises(p.PasskeyUnavailable):
        e.RegistrationService(None, p.ChallengeStore(env[4].client), env[4])
    client = Mock()
    client.eval.side_effect = redis.ConnectionError()
    gate = e.SecurityGate(client, env[4].sessions)
    with pytest.raises(p.PasskeyUnavailable):
        gate.check(env[2], "test")


def test_mutations_leave_commit_to_caller(env):
    binding = replace(env[2], action="email_change")
    with (
        pytest.raises(RuntimeError),
        Session(env[0], info={"tenant_id": "a"}) as session,
        session.begin(),
    ):
        assert mutations.change_email(session, binding, "fresh@example.com") == 2
        raise RuntimeError("rollback")
    with Session(env[0]) as session:
        assert session.get(User, "a").email is None
        assert session.get(User, "a").session_version == 1


def test_cross_account_credential_collision_is_not_reassigned(env):
    enrolled(env)
    other_binding = p.Binding("b", env[4].sessions.create("b"), 1, "passkey_add")
    other = (env[0], env[1], other_binding, env[3], env[4])
    grant = authorize(other)
    cid, opts = begin(other, grant)
    _, response = registration(opts["challenge"])
    with pytest.raises(sa.exc.IntegrityError):
        finish(other, grant, cid, response)
    with env[0].connect() as conn:
        assert (
            conn.scalar(
                sa.select(s.credentials.c.user_id).where(
                    s.credentials.c.credential_id == b"credential"
                )
            )
            == "a"
        )


def test_recovery_failed_state_write_rolls_back_code(env):
    binding, intent, proof = recovery_proof(env)
    recovery = e.RecoveryCodes(env[3], env[4], clock=lambda: 1000)
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        codes = recovery.issue_initial(session, binding, intent, proof)
    with (
        pytest.raises(RuntimeError),
        Session(env[0], info={"tenant_id": "a"}) as session,
        session.begin(),
    ):
        recovery.consume(session, binding, codes[0])
        raise RuntimeError("transaction failed")
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        recovery.consume(session, binding, codes[0])


def test_atomic_password_creation_with_proof_and_rollback(env):
    key, _ = enrolled(env)
    with Session(env[0]) as session, session.begin():
        session.get(User, "a").password_hash = None
    binding = replace(env[2], action="password_add")
    verifier = p.AssertionService(
        env[3], p.ChallengeStore(env[4].client), clock=lambda: 1000
    )
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        intent = p.create_intent(session, binding, "a" * 64, now=1000)
        cid, opts = verifier.begin(session, binding, intent)
        handle = session.scalar(
            sa.select(s.handles.c.handle).where(s.handles.c.user_id == "a")
        )
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        proof = verifier.finish(
            session,
            binding,
            intent,
            cid,
            assertion(key, opts["challenge"], handle=handle),
        )
    with (
        pytest.raises(RuntimeError),
        Session(env[0], info={"tenant_id": "a"}) as session,
        session.begin(),
    ):
        p.consume_proof(session, binding, intent, proof, "a" * 64, now=1000)
        mutations.set_password(
            session, binding, "new-test-password", expected_password_hash=None
        )
        raise RuntimeError("mutation rollback")
    with Session(env[0], info={"tenant_id": "a"}) as session, session.begin():
        assert session.get(User, "a").password_hash is None
        p.consume_proof(session, binding, intent, proof, "a" * 64, now=1000)
        assert (
            mutations.set_password(
                session, binding, "new-test-password", expected_password_hash=None
            )
            == 2
        )
    with Session(env[0]) as session:
        assert auth.verify_password(
            "new-test-password", session.get(User, "a").password_hash
        )


def test_signup_database_rollback_leaves_no_authorization(env):
    oauth, browser = oauth_pending(env)
    with pytest.raises(RuntimeError), Session(env[0]) as session, session.begin():
        binding, _ = env[1].create_google_signup(
            session, oauth, browser, "rollbackuser"
        )
        raise RuntimeError("commit failed")
    with Session(env[0]) as session:
        assert session.get(User, binding.user_id) is None
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(s.enrollments)) == 0
        )
    with Session(env[0]) as session, session.begin(), pytest.raises(p.PasskeyError):
        env[1].create_google_signup(session, oauth, browser, "retryuser")


def test_signup_retry_does_not_refresh_enrollment_receipt(env):
    oauth, browser = oauth_pending(env)
    pending = oauth.consume_pending_signup(browser)
    oauth._clock = lambda: 1250
    assert oauth.store_pending_signup(
        browser, {"sub": pending["subject"]}, original_signup=pending
    )
    restored = oauth.consume_pending_signup(browser)
    assert restored["signup_transaction"] == pending["signup_transaction"]
    assert restored["signup_verified_at"] == 1000
