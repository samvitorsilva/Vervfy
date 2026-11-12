"""Actual route transactions under app_runtime in disposable PostgreSQL schemas."""

import concurrent.futures
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session
from test_passkey_enrollment_postgres import pg as _pg
from test_passkey_enrollment_postgres import postgres as _postgres
from test_passkeys import redis_client as _redis_client

import auth
import passkey_schema as s
import passkeys as p
import server
from db import User

pg = _pg
postgres = _postgres
redis_client = _redis_client


@pytest.fixture
def route_db(pg, monkeypatch):
    engine, name = pg

    def tenant_session(user_id):
        session = Session(engine, info={"tenant_id": user_id}, expire_on_commit=False)

        @sa.event.listens_for(session, "after_begin")
        def configure(session, transaction, connection):
            connection.exec_driver_sql(f"SET LOCAL search_path TO {name}")
            connection.exec_driver_sql("SET LOCAL ROLE app_runtime")
            connection.execute(
                sa.text("SELECT set_config('app.current_user_id',:uid,true)"),
                {"uid": user_id},
            )

        return session

    monkeypatch.setattr(server, "tenant_session", tenant_session)
    monkeypatch.setattr(server, "_passkey_services", lambda: (object(),) * 4)
    monkeypatch.setattr(server, "_check_passkey_rate", lambda *args: None)
    monkeypatch.setattr(server, "rotate_authenticated_session", Mock())
    monkeypatch.setattr(server.session_store, "revoke_user", Mock())
    return tenant_session


def seed(sessions, action):
    now = int(time.time())
    binding = p.Binding("a", "live", 1, action)
    payload = {
        "email_change": "new@example.com",
        "password_add": "Long-test-password-42!",
        "logout_all": "",
    }[action]
    with sessions("a") as session, session.begin():
        session.execute(s.handles.insert().values(user_id="a", handle=b"a" * 32))
        session.execute(
            s.credentials.insert().values(
                id="credential",
                user_id="a",
                credential_id=b"external",
                public_key=b"verified-in-service-tests",
                algorithm=-7,
                sign_count=0,
                backup_eligible=False,
                backed_up=False,
                created_at=now,
            )
        )
        intent = p.create_intent(
            session, binding, server._passkey_action_digest("a", action, payload)
        )
        proof = "p" * 43
        session.execute(
            s.proofs.insert().values(
                id=proof,
                user_id="a",
                intent_id=intent,
                credential_id="credential",
                verified_at=now,
                expires_at=now + 120,
            )
        )
    return intent, proof, payload


def invoke(sessions, action, intent, proof, payload, *, sid="live"):
    with sessions("a") as session:
        user = session.get(User, "a")
    # Use the original request version to exercise concurrent/replayed requests.
    user.session_version = 1
    request = SimpleNamespace(session={"user_id": "a", "sid": sid, "sv": 1})
    ids = {"passkey_intent_id": intent, "passkey_proof_id": proof}
    if action == "email_change":
        return server.change_account_email(
            server.EmailChangeRequest(email=payload, **ids), request, user, None
        )
    if action == "password_add":
        return server.change_password(
            server.PasswordChangeRequest(new_password=payload, **ids),
            request,
            user,
            None,
        )
    return server.logout_all(server.LogoutAllRequest(**ids), request, user, None)


@pytest.mark.parametrize("action", ["email_change", "password_add", "logout_all"])
@pytest.mark.parametrize("rollback", [False, True])
def test_route_proof_mutation_atomicity(route_db, monkeypatch, action, rollback):
    intent, proof, payload = seed(route_db, action)
    helper = {
        "email_change": "change_email",
        "password_add": "set_password",
        "logout_all": "bump_logout_version",
    }[action]
    if rollback:
        original = getattr(server.account_transactions, helper)

        def fail_after_mutation(*args, **kwargs):
            original(*args, **kwargs)
            raise sa.exc.SQLAlchemyError("injected failure after flush")

        monkeypatch.setattr(server.account_transactions, helper, fail_after_mutation)
        with pytest.raises(HTTPException) as caught:
            invoke(route_db, action, intent, proof, payload)
        assert caught.value.status_code == 503
    else:
        invoke(route_db, action, intent, proof, payload)
        with pytest.raises(HTTPException):
            invoke(route_db, action, intent, proof, payload)
    with route_db("a") as session:
        user = session.get(User, "a")
        assert user.session_version == (1 if rollback else 2)
        assert (session.scalar(sa.select(s.proofs.c.consumed_at)) is None) == rollback
        assert (session.scalar(sa.select(s.intents.c.consumed_at)) is None) == rollback
        if action == "email_change":
            assert user.email == (None if rollback else payload)
        if action == "password_add":
            assert (
                user.password_hash is None
                if rollback
                else auth.verify_password(payload, user.password_hash)
            )


@pytest.mark.parametrize("failure", ["session", "payload", "action"])
def test_route_rejects_mismatched_proofs(route_db, failure):
    intent, proof, payload = seed(route_db, "email_change")
    action = "logout_all" if failure == "action" else "email_change"
    with pytest.raises(HTTPException) as caught:
        invoke(
            route_db,
            action,
            intent,
            proof,
            "wrong@example.com" if failure == "payload" else payload,
            sid="different" if failure == "session" else "live",
        )
    assert caught.value.status_code == 403
    with route_db("a") as session:
        assert session.get(User, "a").session_version == 1
        assert session.scalar(sa.select(s.proofs.c.consumed_at)) is None


def test_concurrent_route_has_one_winner(route_db):
    intent, proof, payload = seed(route_db, "logout_all")

    def attempt(_):
        try:
            invoke(route_db, "logout_all", intent, proof, payload)
            return True
        except HTTPException as exc:
            assert exc.status_code == 403
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]


# Capture these before route_db replaces them for focused transaction tests.
_real_rotation = server.rotate_authenticated_session
_real_rate_check = server._check_passkey_rate
_real_services = server._passkey_services


def test_http_registration_assertion_recovery_and_email(
    route_db, redis_client, monkeypatch
):
    import base64
    import json

    from fastapi.testclient import TestClient
    from itsdangerous import TimestampSigner
    from test_passkey_enrollment import registration
    from test_passkeys import assertion
    from webauthn.helpers import base64url_to_bytes

    import passkey_enrollment as enrollment

    sessions = auth.SessionStore()
    config = p.Config("app.example.com", "Vervfy", ("https://app.example.com",))
    gate = enrollment.SecurityGate(redis_client, sessions)
    challenges = p.ChallengeStore(redis_client)
    monkeypatch.setattr(server, "session_store", sessions)
    monkeypatch.setattr(server, "passkey_config", config)
    monkeypatch.setattr(
        server, "passkey_assertions", p.AssertionService(config, challenges)
    )
    monkeypatch.setattr(
        server,
        "passkey_registration",
        enrollment.RegistrationService(config, challenges, gate),
    )
    monkeypatch.setattr(
        server, "passkey_recovery", enrollment.RecoveryCodes(config, gate)
    )
    monkeypatch.setattr(
        server, "passkey_request_limiter", server.PasskeyRequestLimiter(redis_client)
    )
    monkeypatch.setattr(server, "_check_passkey_rate", _real_rate_check)
    monkeypatch.setattr(server, "_passkey_services", _real_services)
    monkeypatch.setattr(server, "rotate_authenticated_session", _real_rotation)
    monkeypatch.setattr(server.request_throttle, "allow", lambda *args: True)

    def get_user(uid):
        with route_db(uid) as session:
            return session.get(User, uid)

    monkeypatch.setattr(server.user_store, "get_by_id", get_user)
    monkeypatch.setattr(
        server.user_store,
        "account_security",
        lambda uid: {
            "has_password": get_user(uid).password_hash is not None,
            "google_linked": False,
        },
    )
    with route_db("a") as session, session.begin():
        session.get(User, "a").password_hash = auth.hash_password(
            "strong-test-password"
        )
    client = TestClient(server.app, base_url="https://app.example.com")

    def login(uid):
        client.cookies.clear()
        data = base64.b64encode(
            json.dumps(
                {
                    "user_id": uid,
                    "sid": sessions.create(uid),
                    "sv": 1,
                    "csrf_token": "csrf",
                }
            ).encode()
        )
        client.cookies.set(
            "auralis_session",
            TimestampSigner(server.SESSION_SECRET).sign(data).decode(),
        )
        client.headers["x-csrf-token"] = "csrf"

    def post(path, data):
        response = client.post("/api/account/passkeys/" + path, json=data)
        assert response.status_code == 200, response.text
        return response.json()

    # A passwordless account's ordinary session cannot authorize enrollment.
    login("b")
    response = client.post(
        "/api/account/passkeys/registration/authorize",
        json={"current_password": "invented"},
    )
    assert response.status_code == 400
    with route_db("b") as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(s.enrollments)) == 0
        )
    login("a")
    assert client.get("/api/account/passkeys/enrollment-eligibility").json()["eligible"]
    grant = post("registration/authorize", {"current_password": "strong-test-password"})
    options = post("registration/options", grant)
    key, response = registration(options["options"]["challenge"])
    assert post(
        "registration/complete",
        {**grant, "challenge_id": options["challenge_id"], "response": response},
    ) == {"registered": True}
    client.headers["x-csrf-token"] = client.get("/api/csrf").json()["csrf_token"]
    assert client.get("/api/account/security-methods").json()["passkey_count"] == 1
    handle = base64url_to_bytes(options["options"]["user"]["id"])

    def prove(action, counter, **payload):
        intent = post("action-intents", {"action": action, **payload})
        options = post(f"actions/{action}/options", intent)
        body = {
            **intent,
            "challenge_id": options["challenge_id"],
            "response": assertion(
                key, options["options"]["challenge"], handle=handle, counter=counter
            ),
        }
        proof = post(f"actions/{action}/complete", body)
        assert (
            client.post(
                f"/api/account/passkeys/actions/{action}/complete", json=body
            ).status_code
            == 400
        )
        return {**intent, **proof}

    recovery_proof = prove("recovery_rotate", 1)
    codes = post("recovery/codes", recovery_proof)["recovery_codes"]
    assert len(codes) == 10
    assert post("recovery/consume", {"code": codes[0]}) == {
        "status": "pending",
        "capabilities": [],
    }
    assert (
        client.post(
            "/api/account/passkeys/recovery/consume", json={"code": codes[0]}
        ).status_code
        == 400
    )
    proof = prove("email_change", 2, email="New@Example.com")
    response = client.put(
        "/api/account/email",
        json={
            "email": "new@example.com",
            "passkey_intent_id": proof["intent_id"],
            "passkey_proof_id": proof["proof_id"],
        },
    )
    assert response.status_code == 200, response.text
    assert get_user("a").email == "new@example.com"
    assert get_user("a").session_version == 3
    client.close()
