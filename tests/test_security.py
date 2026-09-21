import base64
import importlib
import json
import re
import sys

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("VERVFY_ENABLE_DOCS", raising=False)
    monkeypatch.delenv("VERVFY_HTTPS_ONLY", raising=False)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    module = importlib.import_module("server")
    with TestClient(module.app) as client:
        yield module, client


def _csrf(client):
    response = client.get("/login")
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def _register(client, username="alice", passphrase="old-password"):
    response = client.post(
        "/register",
        data={
            "username": username,
            "password": passphrase,
            "email": "",
            "csrf_token": _csrf(client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _login(client, username="alice", passphrase="old-password"):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": passphrase,
            "csrf_token": _csrf(client),
        },
        follow_redirects=False,
    )


def _reload_server(tmp_path, monkeypatch, env_name, env_value):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / (env_name + '.db')}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", env_name + "-secret")
    monkeypatch.setenv(env_name, env_value)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    return importlib.import_module("server")


def test_api_docs_disabled_by_default_and_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'docs.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "docs-secret")
    monkeypatch.delenv("VERVFY_ENABLE_DOCS", raising=False)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    server = importlib.import_module("server")
    with TestClient(server.app) as client:
        assert [client.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")] == [404] * 3

    monkeypatch.setenv("VERVFY_ENABLE_DOCS", "1")
    server = importlib.reload(server)
    with TestClient(server.app) as client:
        assert [client.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")] == [200] * 3


def test_hsts_only_when_https_only(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, "VERVFY_HTTPS_ONLY", "1")
    with TestClient(server.app) as client:
        assert client.get("/login").headers["strict-transport-security"] == "max-age=15552000"

    monkeypatch.setenv("VERVFY_HTTPS_ONLY", "0")
    server = importlib.reload(server)
    with TestClient(server.app) as client:
        assert "strict-transport-security" not in client.get("/login").headers


def test_unknown_username_verifies_dummy_hash_once(app_module, monkeypatch):
    server, client = app_module
    _register(client)
    login_client = TestClient(server.app)
    real = _login(login_client, passphrase="wrong-password")
    calls = []
    original = server.auth.verify_password

    def spy(passphrase, password_hash):
        calls.append(password_hash)
        return original(passphrase, password_hash)

    monkeypatch.setattr(server.auth, "verify_password", spy)
    unknown = _login(login_client, username="nobody")
    assert unknown.status_code == real.status_code == 400
    assert "Incorrect username or password" in unknown.text
    assert "Incorrect username or password" in real.text
    assert len(calls) == 1


def test_library_ids_are_validated(app_module):
    _, client = app_module
    _register(client)
    headers = {"X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"]}
    bad = '\"><img src=x onerror=alert(1)>'
    assert client.put(
        "/api/library/state",
        headers=headers,
        json={"favorites": [bad], "playlists": [{"id": "ok", "name": "x", "trackIds": []}]},
    ).status_code == 422
    assert client.put(
        "/api/library/state",
        headers=headers,
        json={"favorites": [], "playlists": [{"id": "abc_01-Z", "name": "x", "trackIds": ["abc_01-Z"]}]},
    ).status_code == 200
    assert client.put(
        "/api/library/state",
        headers=headers,
        json={"favorites": [], "playlists": [{"id": bad, "name": "x", "trackIds": []}]},
    ).status_code == 422


def test_session_revocation_and_logout_all(app_module):
    server, client_a = app_module
    _register(client_a)
    client_b = TestClient(server.app)
    _login(client_b)
    copied_cookie = client_a.cookies.get("auralis_session")
    client_c = TestClient(server.app)
    client_c.cookies.set("auralis_session", copied_cookie)

    csrf = client_a.get("/api/csrf").json()["csrf_token"]
    response = client_a.post(
        "/api/account/password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": "old-password", "new_password": "new-password"},
    )
    assert response.status_code == 200
    assert client_a.get("/api/me").status_code == 200
    assert client_b.get("/api/me").status_code == 401

    csrf = client_a.get("/api/csrf").json()["csrf_token"]
    assert client_a.post("/api/account/logout-all", headers={"X-CSRF-Token": csrf}).json() == {"ok": True}
    assert client_c.get("/api/me").status_code == 401


def test_logout_redirects_even_with_stale_csrf_token(app_module):
    server, client = app_module
    _register(client)

    response = client.post(
        "/logout",
        headers={"X-CSRF-Token": "stale-token"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert client.get("/api/me").status_code == 401


def test_login_form_is_not_cached(app_module):
    _, client = app_module
    response = client.get("/login")

    assert response.headers["cache-control"] == "no-store"


def test_cookie_without_session_version_is_valid_at_zero(app_module):
    server, client = app_module
    _register(client)
    cookie = client.cookies.get("auralis_session")
    signed = cookie.split(".", 1)[0]
    payload = json.loads(base64.b64decode(signed + "=" * (-len(signed) % 4)))
    payload.pop("sv", None)
    unsigned = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode())
    old_cookie = TimestampSigner("test-secret-key").sign(unsigned).decode()
    old_client = TestClient(server.app)
    old_client.cookies.set("auralis_session", old_cookie)
    assert old_client.get("/api/me").status_code == 200
