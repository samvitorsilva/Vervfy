import base64
from contextvars import ContextVar
import importlib
import json
import sys

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker


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
    return client.get("/api/csrf").json()["csrf_token"]


def _register(client, username="alice", passphrase="old-password", email=""):
    response = client.post(
        "/register",
        data={
            "username": username,
            "password": passphrase,
            "email": email,
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


def _library_state_headers(client):
    return {
        "X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"],
        "If-Match": client.get("/api/library/state").headers["etag"],
    }


def test_redis_throttle_keeps_first_hit_window(app_module):
    server, _ = app_module
    auth = server.auth

    class FakeRedisCounter:
        def __init__(self):
            self.counts = {}
            self.expirations = []

        def eval(self, script, key_count, key, window):
            assert script == auth._INCREMENT_WINDOW_SCRIPT
            assert key_count == 1
            count = self.counts.get(key, 0) + 1
            self.counts[key] = count
            if count == 1:
                self.expirations.append((key, window))
            return count

        def get(self, key):
            return self.counts.get(key)

        def delete(self, key):
            self.counts.pop(key, None)

    limiter = auth.RequestThrottle()
    fake = FakeRedisCounter()
    limiter._redis = fake

    key = "login:ip:user"
    assert limiter.peek(key, 60) == 0
    assert limiter.increment(key, 60) == 1
    assert limiter.peek(key, 60) == 1
    assert limiter.allow(key, 2, 60)
    assert not limiter.allow(key, 2, 60)
    assert fake.expirations == [("vervfy:ratelimit:login:ip:user", 60)]


def test_parse_range_header_handles_valid_malformed_and_unsatisfiable_ranges(app_module):
    server, _ = app_module
    assert server._parse_range_header("bytes=2-5", 10) == (2, 5)
    assert server._parse_range_header("bytes=2-", 10) == (2, 9)
    assert server._parse_range_header("bytes=-3", 10) == (7, 9)
    assert server._parse_range_header("bytes=wat", 10) is None
    assert server._parse_range_header("bytes=0-1,3-4", 10) is None
    with pytest.raises(server.RangeNotSatisfiable):
        server._parse_range_header("bytes=10-", 10)


@pytest.mark.parametrize("backend", ["memory", "redis"])
def test_auth_throttles_count_only_successes_and_failures(app_module, backend):
    server, client = app_module
    limiter = server.auth.RequestThrottle()
    if backend == "redis":
        class FakeRedisCounter:
            def __init__(self):
                self.counts = {}

            def eval(self, _script, _key_count, key, _window):
                self.counts[key] = self.counts.get(key, 0) + 1
                return self.counts[key]

            def get(self, key):
                return self.counts.get(key)

            def delete(self, key):
                self.counts.pop(key, None)

        limiter._redis = FakeRedisCounter()
    server.request_throttle._redis = limiter._redis

    signup = server.auth.SignupThrottle(max_signups=5, limiter=limiter)
    for _ in range(5):
        assert not signup.is_limited("signup-ip")
    assert not signup.is_limited("signup-ip")
    for _ in range(5):
        signup.record_success("signup-ip")
    assert signup.is_limited("signup-ip")

    login = server.auth.LoginThrottle(limiter=limiter)
    for _ in range(5):
        assert not login.is_locked("login-ip", "alice")
    for _ in range(4):
        login.record_failure("login-ip", "alice")
        assert not login.is_locked("login-ip", "alice")
    login.record_failure("login-ip", "alice")
    assert login.is_locked("login-ip", "alice")

    _register(client)
    signup_client = TestClient(server.app)
    for _ in range(5):
        response = signup_client.post(
            "/register",
            data={
                "username": "alice",
                "password": "old-password",
                "email": "",
                "csrf_token": _csrf(signup_client),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert response.headers["cache-control"] == "no-store"
        assert isinstance(response.json()["detail"], str)
    response = signup_client.post(
        "/register",
        data={
            "username": "bob",
            "password": "old-password",
            "email": "",
            "csrf_token": _csrf(signup_client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_production_requires_stable_session_secret(app_module, monkeypatch):
    server, _ = app_module
    monkeypatch.setattr(server, "is_production", True)
    monkeypatch.delenv("VERVFY_SECRET_KEY", raising=False)
    monkeypatch.delenv("AURALIS_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="VERVFY_SECRET_KEY is required"):
        server._load_or_create_secret_key()


def _reload_server(tmp_path, monkeypatch, env_name, env_value):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / (env_name + '.db')}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", env_name + "-secret")
    monkeypatch.setenv(env_name, env_value)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    return importlib.import_module("server")


def test_sync_dependency_contextvar_is_not_visible_to_endpoint_or_sqlalchemy(tmp_path):
    tenant_context = ContextVar("reproduction_tenant", default=None)
    observed = {}
    sessions = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'context.db'}"))

    def dependency():
        tenant_context.set("tenant-a")
        observed["dependency"] = tenant_context.get()
        yield

    @event.listens_for(sessions, "after_begin")
    def capture_sqlalchemy_context(session, transaction, connection):
        del session, transaction, connection
        observed["listener"] = tenant_context.get()

    app = FastAPI()

    @app.get("/", dependencies=[Depends(dependency)])
    def endpoint():
        observed["endpoint"] = tenant_context.get()
        with sessions() as session:
            session.execute(text("SELECT 1"))
        return {"tenant": observed["endpoint"]}

    with TestClient(app) as client:
        assert client.get("/").json() == {"tenant": None}

    assert observed == {
        "dependency": "tenant-a",
        "endpoint": None,
        "listener": None,
    }


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


def test_production_can_use_synchronous_uploads_without_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'production.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "production-test-secret")
    monkeypatch.setenv("VERVFY_ENVIRONMENT", "production")
    monkeypatch.setenv("VERVFY_HTTPS_ONLY", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("VERVFY_ASYNC_UPLOADS", raising=False)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)

    server = importlib.import_module("server")
    assert server.is_production
    assert server.async_uploads is False


def test_hsts_only_when_https_only(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, "VERVFY_HTTPS_ONLY", "1")
    with TestClient(server.app) as client:
        assert client.get("/api/csrf").headers["strict-transport-security"] == "max-age=15552000"

    monkeypatch.setenv("VERVFY_HTTPS_ONLY", "0")
    server = importlib.reload(server)
    with TestClient(server.app) as client:
        assert "strict-transport-security" not in client.get("/api/csrf").headers


def test_backend_does_not_serve_legacy_ui(app_module):
    _, client = app_module
    assert client.get("/").status_code == 404
    assert client.get("/login").status_code == 405
    assert client.get("/register").status_code == 405
    assert client.get("/logout").status_code == 405
    assert client.get("/sw.js").status_code == 404
    assert client.get("/static/app.js").status_code == 404


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
    assert unknown.json()["detail"] == real.json()["detail"] == "Incorrect username or password"
    assert len(calls) == 1


def test_login_returns_503_when_login_rate_limit_backend_is_unavailable(app_module, monkeypatch):
    server, client = app_module
    _register(client)
    login_client = TestClient(server.app)
    csrf_token = _csrf(login_client)

    def unavailable(*_args):
        raise RuntimeError("rate-limit backend unavailable")

    monkeypatch.setattr(server.login_throttle, "is_locked", unavailable)
    response = login_client.post(
        "/login",
        data={"username": "alice", "password": "old-password", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Service temporarily unavailable, try again shortly"


def test_login_requires_username_even_when_account_has_email(app_module):
    server, client = app_module
    _register(client, email="alice@example.com")
    login_client = TestClient(server.app)

    failed = _login(login_client, username="ALICE@example.com", passphrase="wrong-password")
    assert failed.status_code == 400
    assert failed.json()["detail"] == "Incorrect username or password"

    email_login = _login(login_client, username="alice@example.com")
    assert email_login.status_code == 400
    successful = _login(login_client, username="alice")
    assert successful.status_code == 303
    assert successful.headers["location"] == "/"


def test_library_ids_are_validated(app_module):
    _, client = app_module
    _register(client)
    bad = '\"><img src=x onerror=alert(1)>'
    assert client.put(
        "/api/library/state",
        headers=_library_state_headers(client),
        json={"favorites": [bad], "playlists": [{"id": "ok", "name": "x", "trackIds": []}]},
    ).status_code == 422
    assert client.put(
        "/api/library/state",
        headers=_library_state_headers(client),
        json={"favorites": [], "playlists": [{"id": "abc_01-Z", "name": "x", "trackIds": ["abc_01-Z"]}]},
    ).status_code == 200
    assert client.put(
        "/api/library/state",
        headers=_library_state_headers(client),
        json={"favorites": [], "playlists": [{"id": bad, "name": "x", "trackIds": []}]},
    ).status_code == 422


def test_favorites_persist_for_owned_tracks(app_module):
    server, client = app_module
    _register(client)
    user = server.user_store.get_by_username("alice")
    with server.SessionLocal() as session:
        session.add(server.TrackRecord(
            id="track-one",
            user_id=user["id"],
            filename="song.wav",
            title="Song",
            artist="Artist",
            album="Album",
            duration=1,
            has_cover=False,
            size_bytes=10,
            cover_data=b"",
        ))
        session.commit()

    headers = _library_state_headers(client)
    saved = client.put(
        "/api/library/state",
        headers=headers,
        json={"favorites": ["track-one"], "playlists": []},
    )
    assert saved.status_code == 200
    assert saved.json()["favorites"] == ["track-one"]
    assert client.get("/api/library/state").json()["favorites"] == ["track-one"]


def test_library_state_etag_rejects_stale_and_missing_preconditions(app_module):
    _, client = app_module
    _register(client)
    state = client.get("/api/library/state")
    etag = state.headers["etag"]
    csrf = client.get("/api/csrf").json()["csrf_token"]
    assert client.put(
        "/api/library/state",
        headers={"X-CSRF-Token": csrf},
        json={"favorites": [], "playlists": []},
    ).status_code == 428

    first = client.put(
        "/api/library/state",
        headers={"X-CSRF-Token": csrf, "If-Match": etag},
        json={"favorites": [], "playlists": [{"id": "new-list", "name": "New", "trackIds": []}]},
    )
    assert first.status_code == 200
    assert first.headers["etag"] != etag
    stale = client.put(
        "/api/library/state",
        headers={"X-CSRF-Token": csrf, "If-Match": etag},
        json={"favorites": [], "playlists": []},
    )
    assert stale.status_code == 409
    assert stale.headers["etag"] == first.headers["etag"]
    assert client.get("/api/library/state").json()["playlists"][0]["id"] == "new-list"


def test_playlist_order_and_etag_round_trip(app_module):
    _, client = app_module
    _register(client)
    headers = _library_state_headers(client)
    playlists = [
        {"id": "second-list", "name": "Second", "trackIds": []},
        {"id": "first-list", "name": "First", "trackIds": []},
    ]

    saved = client.put(
        "/api/library/state",
        headers=headers,
        json={"favorites": [], "playlists": playlists},
    )
    assert saved.status_code == 200
    assert [item["id"] for item in saved.json()["playlists"]] == [
        "second-list",
        "first-list",
    ]

    fetched = client.get("/api/library/state")
    assert fetched.json()["playlists"] == saved.json()["playlists"]
    assert fetched.headers["etag"] == saved.headers["etag"]


def test_playlist_id_collision_between_users_is_rejected(app_module):
    server, client_a = app_module
    _register(client_a, username="alice")
    client_b = TestClient(server.app)
    _register(client_b, username="bob")

    first = client_a.put(
        "/api/library/state",
        headers=_library_state_headers(client_a),
        json={"favorites": [], "playlists": [
            {"id": "shared-list-id", "name": "Alice's list", "trackIds": []},
        ]},
    )
    assert first.status_code == 200
    before = client_b.get("/api/library/state")

    collision = client_b.put(
        "/api/library/state",
        headers=_library_state_headers(client_b),
        json={"favorites": [], "playlists": [
            {"id": "shared-list-id", "name": "Bob's list", "trackIds": []},
        ]},
    )
    assert collision.status_code == 409
    assert client_b.get("/api/library/state").json()["playlists"] == []
    assert client_b.get("/api/library/state").headers["etag"] == before.headers["etag"]
    assert client_a.get("/api/library/state").json()["playlists"][0]["name"] == "Alice's list"


def test_artist_photo_fetches_exact_deezer_match_and_caches(app_module, monkeypatch):
    server, _ = app_module
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            if url.endswith("/search/artist"):
                return FakeResponse({"data": [
                    {"name": "Tate McRae tribute", "id": 1},
                    {
                        "name": "Tate McRae",
                        "id": 2,
                        "picture_big": "https://cdn.dzcdn.net/tate-large.jpg",
                        "picture_medium": "https://cdn.dzcdn.net/tate.jpg",
                    },
                ]})
            if url.endswith("/artist/2/top"):
                return FakeResponse({"data": [{"title": "Greedy"}]})
            pytest.fail(f"Unexpected Deezer request: {url}")

    server._artist_photo_cache.clear()
    server._artist_photo_result_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    expected = ("https://cdn.dzcdn.net/tate.jpg", None)
    assert server._lookup_artist_photo("Tate McRae", ["Greedy"]) == expected
    assert server._lookup_artist_photo("Tate McRae", ["Greedy"]) == expected
    assert sum(url.endswith("/search/artist") for url in calls) == 1
    assert sum("/artist/2/top" in url for url in calls) == 1


def test_artist_route_caches_exact_deezer_match(app_module, monkeypatch):
    server, client = app_module
    _register(client)
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [
                {"id": 1, "name": "Tate McRae Tribute"},
                {
                    "id": 2,
                    "name": "Tate McRae",
                    "picture_medium": "https://cdn.dzcdn.net/tate.jpg",
                    "nb_fan": 123,
                },
            ]}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())

    first = client.get("/artists/Tate%20McRae")
    second = client.get("/artists/Tate%20McRae")

    assert first.status_code == 200
    assert first.json()["deezer_id"] == 2
    assert first.json()["picture"] == "https://cdn.dzcdn.net/tate.jpg"
    assert first.json()["fans"] == 123
    assert second.json() == first.json()
    assert len(calls) == 1


def test_deezer_quota_error_retries_once(app_module, monkeypatch):
    server, _ = app_module
    calls = []
    sleeps = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            if len(calls) == 1:
                return FakeResponse({"error": {"code": 4, "message": "quota"}})
            return FakeResponse({"data": [{"id": 2, "name": "Tate McRae"}]})

    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(server.time, "sleep", sleeps.append)

    assert server._fetch_deezer_artist("Tate McRae")["id"] == 2
    assert len(calls) == 2
    assert sleeps == [1]


def test_postgres_psycopg_disables_prepared_statements(app_module):
    server, _ = app_module
    import db
    assert server.engine.dialect.name == "sqlite"
    assert db.engine_connect_args("postgresql+psycopg://host/database") == {
        "prepare_threshold": None
    }
    assert db.engine_connect_args("sqlite:///database.db") == {}


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


def test_email_is_account_information_not_an_authentication_method(app_module):
    _, client = app_module
    _register(client)
    csrf = client.get("/api/csrf").json()["csrf_token"]
    response = client.put(
        "/api/account/email",
        headers={"X-CSRF-Token": csrf},
        json={"email": "Alice@example.com", "current_password": "old-password"},
    )
    assert response.status_code == 200
    assert response.json() == {"email": "alice@example.com"}
    assert client.get("/api/me").json()["email"] == "alice@example.com"

    csrf = client.get("/api/csrf").json()["csrf_token"]
    removed = client.put(
        "/api/account/email",
        headers={"X-CSRF-Token": csrf},
        json={"email": "", "current_password": "old-password"},
    )
    assert removed.status_code == 200
    assert removed.json() == {"email": None}
    assert client.get("/api/me").json()["email"] is None

    for path in ("/forgot-password", "/reset-password", "/verify-email"):
        assert client.get(path).status_code == 404


def test_current_password_failures_are_rate_limited(app_module):
    _, client = app_module
    _register(client)
    csrf = client.get("/api/csrf").json()["csrf_token"]
    payload = {"current_password": "wrong-password", "new_password": "new-password"}
    for _ in range(10):
        response = client.post("/api/account/password", headers={"X-CSRF-Token": csrf}, json=payload)
        assert response.status_code == 400
    response = client.post("/api/account/password", headers={"X-CSRF-Token": csrf}, json=payload)
    assert response.status_code == 429


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


def test_anonymous_csrf_bootstrap_is_json_and_not_cached(app_module):
    _, client = app_module
    response = client.get("/api/csrf")

    assert response.headers["cache-control"] == "no-store"
    assert isinstance(response.json()["csrf_token"], str)


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


def test_authenticated_user_cannot_access_another_users_library(app_module):
    server, client_a = app_module
    _register(client_a, username="alice")
    client_b = TestClient(server.app)
    _register(client_b, username="bob")

    response = client_a.put(
        "/api/library/state",
        headers=_library_state_headers(client_a),
        json={"favorites": [], "playlists": [{"id": "private", "name": "Private", "trackIds": []}]},
    )
    assert response.status_code == 200
    assert client_b.get("/api/library/state").json()["playlists"] == []
    assert client_b.get("/api/tracks").json()["tracks"] == []
    assert client_b.delete("/api/tracks/not-owned", headers={
        "X-CSRF-Token": client_b.get("/api/csrf").json()["csrf_token"]
    }).status_code == 404


def test_artist_profile_fetches_verified_wikipedia_result(app_module, monkeypatch):
    server, _ = app_module

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self.payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise server.httpx.HTTPError(f"status {self.status_code}")

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            if url.endswith("/search/artist"):
                return FakeResponse({"data": [{
                    "name": "Example Artist",
                    "id": 12,
                    "nb_fan": 42,
                    "picture_xl": "https://cdn-images.dzcdn.net/images/artist/example/1000x1000-000000-80-0-0.jpg",
                    "picture_medium": "https://cdn-images.dzcdn.net/images/artist/example/250x250-000000-80-0-0.jpg",
                }]})
            if url.endswith("/artist/12/top"):
                return FakeResponse({"data": [{"title": "Example Song"}]})
            return FakeResponse({
                "type": "standard",
                "title": "Example Artist",
                "description": "British rapper",
                "extract": "Example Artist is a British rapper known for influential recordings. More details.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Example_Artist"}},
            })

    server._artist_profile_cache.clear()
    server._artist_photo_cache.clear()
    server._artist_photo_result_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    profile = server._lookup_artist_profile("Example Artist", ["Example Song"])
    assert profile["bio"] == (
        "Example Artist is a British rapper known for influential recordings. More details."
    )
    assert "followers" not in profile
    assert profile["source"] == "Wikipedia"
    assert server._lookup_artist_photo("Example Artist", ["Example Song"]) == (
        "https://cdn-images.dzcdn.net/images/artist/example/250x250-000000-80-0-0.jpg",
        42,
    )


def test_tate_mcrae_profile_includes_verified_bio_and_official_website(app_module, monkeypatch):
    server, _ = app_module

    def unexpected_client(**kwargs):
        pytest.fail("A manually verified artist profile should not require network lookup")

    monkeypatch.setattr(server.httpx, "Client", unexpected_client)
    profile = server._lookup_artist_profile("Tate McRae", [])

    assert profile["bio"].startswith("Tate McRae is a Canadian singer, songwriter, and dancer")
    assert profile["website"] == "https://www.tatemcrae.com/"
    assert profile["website_label"] == "Official artist website"
    assert profile["source"] == "Wikipedia"
    assert profile["source_url"] == "https://en.wikipedia.org/wiki/Tate_McRae"


def test_artist_profile_uses_wikipedia_search_when_direct_summary_misses(app_module, monkeypatch):
    server, _ = app_module
    calls = []

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self.payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise server.httpx.HTTPError(f"status {self.status_code}")

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            if url.endswith("/search/artist"):
                return FakeResponse({"data": [{"name": "Example Artist", "id": 15, "nb_fan": 9}]})
            if url.endswith("/artist/15/top"):
                return FakeResponse({"data": [{"title": "Example Song"}]})
            if url.endswith("/w/api.php"):
                return FakeResponse({"query": {"search": [{"title": "Example Artist (rapper)"}]}})
            if url.rstrip("/").endswith("/page/summary/Example%20Artist"):
                return FakeResponse({}, status_code=404)
            if "page/summary/Example%20Artist%20%28rapper%29" in url:
                return FakeResponse({
                    "type": "standard",
                    "title": "Example Artist (rapper)",
                    "description": "American rapper",
                    "extract": "Example Artist is an American rapper.",
                    "content_urls": {
                        "desktop": {"page": "https://en.wikipedia.org/wiki/Example_Artist_(rapper)"}
                    },
                })
            pytest.fail(f"Unexpected request: {url}")

    server._artist_profile_cache.clear()
    server._artist_photo_cache.clear()
    server._artist_photo_result_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    profile = server._lookup_artist_profile("Example Artist", ["Example Song"])
    assert profile["bio"] == "Example Artist is an American rapper."
    assert profile["source"] == "Wikipedia"
    assert any(url.endswith("/w/api.php") for url in calls)


def test_artist_profile_uses_exact_wikipedia_match_without_deezer_title_match(app_module, monkeypatch):
    server, _ = app_module

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
            self.status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            if url.endswith("/search/artist"):
                return FakeResponse({"data": [{"id": 44, "name": "SZA"}]})
            if url.endswith("/artist/44/top"):
                return FakeResponse({"data": [{"title": "Another Song"}]})
            if url.endswith("/artist/44/albums"):
                return FakeResponse({"data": []})
            if url.endswith("/page/summary/SZA"):
                return FakeResponse({
                    "type": "standard",
                    "title": "SZA",
                    "description": "American singer and songwriter",
                    "extract": "SZA is an American singer and songwriter.",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/SZA"}},
                })
            pytest.fail(f"Unexpected request: {url}")

    server._artist_profile_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    profile = server._lookup_artist_profile("SZA", ["Different Song"])

    assert profile["bio"] == "SZA is an American singer and songwriter."
    assert profile["source"] == "Wikipedia"


def test_artist_profile_rejects_mismatched_wikipedia_summary(app_module, monkeypatch):
    server, _ = app_module

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self.payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise server.httpx.HTTPError(f"status {self.status_code}")

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            if url.endswith("/search/artist"):
                return FakeResponse({"data": [{"name": "Example Artist", "id": 13}]})
            if url.endswith("/artist/13/top"):
                return FakeResponse({"data": [{"title": "Example Song"}]})
            if url.endswith("/w/api.php"):
                return FakeResponse({"query": {"search": []}})
            return FakeResponse({
                "type": "standard",
                "title": "An unrelated artist",
                "description": "Musician",
                "extract": "Example Artist is a musician known for influential recordings.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Example_Artist"}},
            })

    server._artist_profile_cache.clear()
    server._artist_photo_cache.clear()
    server._artist_photo_result_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    assert server._lookup_artist_profile("Example Artist", ["Example Song"]) is None


@pytest.mark.parametrize("name", ["Dave", "Dave Santan", "Santan Dave"])
def test_dave_artist_photo_uses_verified_british_rapper_profile(app_module, monkeypatch, name):
    server, _ = app_module
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            pytest.fail(f"Verified portraits must not hit Deezer: {url}")

    server._artist_photo_cache.clear()
    server._artist_photo_result_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())

    assert server._lookup_artist_photo(name, ["Streatham"]) == (
        "https://cdn-images.dzcdn.net/images/artist/"
        "eb2c8952b7328fdf32b3546d5ffab8c2/500x500-000000-80-0-0.jpg",
        None,
    )
    assert calls == []
