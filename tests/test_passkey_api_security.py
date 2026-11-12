"""HTTP boundary tests: signed sessions, CSRF, gates and bounded JSON bodies."""

import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import redis
from fastapi import HTTPException
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

import server

TOKEN = "x" * 43
ENDPOINTS = [
    ("GET", "/api/account/security-methods", None),
    ("GET", "/api/account/passkeys/enrollment-eligibility", None),
    (
        "POST",
        "/api/account/passkeys/registration/authorize",
        {"current_password": "secret"},
    ),
    ("POST", "/api/account/passkeys/registration/options", {"authorization_id": TOKEN}),
    (
        "POST",
        "/api/account/passkeys/registration/complete",
        {"authorization_id": TOKEN, "challenge_id": TOKEN, "response": {}},
    ),
    ("POST", "/api/account/passkeys/action-intents", {"action": "logout_all"}),
    ("POST", "/api/account/passkeys/actions/logout_all/options", {"intent_id": TOKEN}),
    (
        "POST",
        "/api/account/passkeys/actions/logout_all/complete",
        {"intent_id": TOKEN, "challenge_id": TOKEN, "response": {}},
    ),
    (
        "POST",
        "/api/account/passkeys/recovery/codes",
        {"intent_id": TOKEN, "proof_id": TOKEN},
    ),
    ("POST", "/api/account/passkeys/recovery/consume", {"code": "a" * 64}),
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server.request_throttle, "allow", lambda *args: True)
    monkeypatch.setattr(
        server.user_store, "get_by_id", lambda uid: {"id": uid, "session_version": 1}
    )
    monkeypatch.setattr(
        server.session_store, "is_valid", lambda sid, uid: sid == "live-session"
    )
    client = TestClient(server.app, base_url="https://testserver")
    data = base64.b64encode(
        json.dumps(
            {"user_id": "a", "sid": "live-session", "sv": 1, "csrf_token": "csrf"}
        ).encode()
    )
    client.cookies.set(
        "auralis_session", TimestampSigner(server.SESSION_SECRET).sign(data).decode()
    )
    yield client
    client.close()


@pytest.mark.parametrize("method,path,payload", ENDPOINTS)
def test_disabled_endpoints_reject_before_services(
    client, monkeypatch, method, path, payload
):
    monkeypatch.setattr(server, "passkey_config", None)
    response = client.request(
        method, path, json=payload, headers={"x-csrf-token": "csrf"}
    )
    assert response.status_code == 404
    assert "no-store" in response.headers["cache-control"]


@pytest.mark.parametrize("method,path,payload", ENDPOINTS)
@pytest.mark.parametrize(
    "failure,status",
    [("csrf", 403), ("revoked", 401), ("outage", 503), ("version", 401)],
)
def test_http_authentication_boundaries(
    client, monkeypatch, method, path, payload, failure, status
):
    monkeypatch.setattr(server, "passkey_config", object())
    if failure == "revoked":
        monkeypatch.setattr(server.session_store, "is_valid", lambda *args: False)
    elif failure == "outage":
        monkeypatch.setattr(
            server.session_store,
            "is_valid",
            Mock(side_effect=RuntimeError("unavailable")),
        )
    elif failure == "version":
        monkeypatch.setattr(
            server.user_store,
            "get_by_id",
            lambda uid: {"id": uid, "session_version": 2},
        )
    headers = {} if failure == "csrf" else {"x-csrf-token": "csrf"}
    assert (
        client.request(method, path, json=payload, headers=headers).status_code
        == status
    )


@pytest.mark.parametrize(
    "path,size", [("registration/complete", 65537), ("action-intents", 16385)]
)
def test_oversized_json_is_rejected(client, monkeypatch, path, size):
    monkeypatch.setattr(server, "passkey_config", object())
    response = client.post(
        "/api/account/passkeys/" + path,
        content=b" " * size,
        headers={"x-csrf-token": "csrf", "content-type": "application/json"},
    )
    assert response.status_code == 413


@pytest.mark.parametrize("result,status", [(0, 429), (redis.ConnectionError(), 503)])
def test_distributed_limiter_fails_closed(result, status):
    backend = Mock()
    if isinstance(result, Exception):
        backend.eval.side_effect = result
    else:
        backend.eval.return_value = result
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    with pytest.raises(HTTPException) as caught:
        server.PasskeyRequestLimiter(backend).check(
            request, server.passkeys.Binding("a", "sid", 1, "logout_all"), "test"
        )
    assert caught.value.status_code == status
    args = backend.eval.call_args.args
    assert args[1] == 3
    assert all(
        part in args[i] for i, part in [(2, ":account:"), (3, ":session:"), (4, ":ip:")]
    )


def test_rotation_failure_clears_cookie(monkeypatch):
    monkeypatch.setattr(
        server.session_store, "revoke_user", Mock(side_effect=RuntimeError())
    )
    request = SimpleNamespace(session={"sid": "old", "csrf_token": "old"})
    with pytest.raises(HTTPException) as caught:
        server.rotate_authenticated_session(request, "a", 2)
    assert caught.value.status_code == 503
    assert request.session == {}


def test_rotation_refreshes_csrf(monkeypatch):
    monkeypatch.setattr(server.session_store, "revoke_user", Mock())
    monkeypatch.setattr(server.session_store, "create", lambda uid: "new-session")
    request = SimpleNamespace(session={"sid": "old", "csrf_token": "old"})
    server.rotate_authenticated_session(request, "a", 2)
    assert request.session["csrf_token"] != "old"
    assert request.session["sid"] == "new-session"
    assert request.session["sv"] == 2
