"""TLS-terminated Render model: external HTTPS, internal HTTP, no proxy trust."""
import asyncio
from http.cookies import SimpleCookie

import httpx
import pytest
from uvicorn import Config


@pytest.fixture
def setup(monkeypatch):
    import server
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "0")
    monkeypatch.delenv("VERVFY_TRUSTED_PROXY_CIDRS", raising=False)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    # SessionMiddleware captures this setting at application import/startup.
    assert server.https_only is True, "Start tests with VERVFY_HTTPS_ONLY=1"
    async def inline(target, *args, **kwargs):
        return target(*args, **kwargs)
    monkeypatch.setattr(server, "run_in_threadpool", inline)
    monkeypatch.setattr("fastapi.routing.run_in_threadpool", inline)
    monkeypatch.setattr("fastapi.dependencies.utils.run_in_threadpool", inline)
    monkeypatch.setattr(server.request_throttle, "allow", lambda *a: True)
    async def inner(scope, receive, send):
        assert scope["scheme"] == "http"
        assert scope["client"][0] == "10.0.0.2"
        await server.app(scope, receive, send)
    config = Config(inner, proxy_headers=False, log_config=None, lifespan="off")
    config.load()
    async def tls_terminated(scope, receive, send):
        scope = dict(scope, scheme="http", client=("10.0.0.2", 1234))
        await config.loaded_app(scope, receive, send)
    return server, tls_terminated


def test_secure_session_cookie_csrf_and_hsts_over_internal_http(setup):
    server, app = setup
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.example", headers={"x-forwarded-for": "malformed", "x-forwarded-proto": "https"}) as client:
            response = await client.get("/api/csrf")
            assert response.status_code == 200
            cookie = SimpleCookie(response.headers["set-cookie"])["auralis_session"]
            assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "lax"
            assert response.headers["strict-transport-security"].startswith("max-age=")
            token = response.json()["csrf_token"]
            assert (await client.get("/api/csrf")).json()["csrf_token"] == token
            assert (await client.get("/api/me")).status_code == 401
    asyncio.run(run())


def test_invalid_csrf_rejected_before_credentials_under_tls_termination(setup, monkeypatch):
    server, app = setup
    monkeypatch.setattr(server.user_store, "get_by_username", lambda *a: pytest.fail("CSRF failure touched credentials"))
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.example") as client:
            await client.get("/api/csrf")
            response = await client.post("/login", data={"username": "synthetic", "password": "synthetic", "csrf_token": "wrong"})
            assert response.status_code == 403
    asyncio.run(run())


def test_google_start_and_failed_callback_use_fixed_config_not_forwarded_scheme(setup, monkeypatch):
    from google_oauth import GoogleOAuthConfig, OAuthTransactionError
    server, app = setup
    config = GoogleOAuthConfig(client_id="synthetic", client_secret="synthetic", redirect_uri="https://app.example/api/auth/google/callback", frontend_origin="https://app.example", redis_url="redis://unused", identity_lookup_database_url="postgresql+psycopg://unused", test_user_email="synthetic@example.com")
    class Flow:
        async def create_authorization_url(self, binding, **kwargs):
            return "https://accounts.google.com/mock?redirect_uri=https%3A%2F%2Fapp.example%2Fapi%2Fauth%2Fgoogle%2Fcallback"
        async def consume_transaction(self, *args):
            raise OAuthTransactionError("synthetic rejected state")
    monkeypatch.setattr(server, "google_oauth_config", config)
    monkeypatch.setattr(server, "google_oauth_service", Flow())
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.example", headers={"x-forwarded-proto": "http", "x-forwarded-host": "attacker.invalid"}, follow_redirects=False) as client:
            response = await client.get("/api/auth/google/start")
            assert response.status_code == 303
            assert response.headers["location"].startswith("https://accounts.google.com/")
            assert "attacker" not in response.headers["location"]
            cookie = SimpleCookie(response.headers["set-cookie"])[config.browser_cookie_name]
            assert cookie["secure"] and cookie["httponly"] and cookie["path"] == "/"
            response = await client.get("/api/auth/google/callback?state=synthetic&code=synthetic")
            assert response.status_code == 303
            assert response.headers["location"] == "/login?google=failed"
            assert response.headers["referrer-policy"] == "no-referrer"
    asyncio.run(run())


def test_slash_variant_rejected_without_internal_http_redirect(setup):
    _, app = setup
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.example", follow_redirects=False) as client:
            response = await client.get("/api/csrf/")
            assert response.status_code == 404
            assert "location" not in response.headers
    asyncio.run(run())
