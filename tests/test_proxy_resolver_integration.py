"""Proxy/middleware/authentication boundaries with synthetic sessions only."""
import asyncio
import importlib

import httpx
import pytest
from click.testing import CliRunner
from starlette.requests import Request

import auth


@pytest.fixture
def server(monkeypatch):
    import server
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    # Inline handlers avoid unrelated thread/event-loop issues in the sandbox.
    async def inline(target, *args, **kwargs):
        return target(*args, **kwargs)
    monkeypatch.setattr(server, "run_in_threadpool", inline)
    monkeypatch.setattr("fastapi.routing.run_in_threadpool", inline)
    monkeypatch.setattr("fastapi.dependencies.utils.run_in_threadpool", inline)
    return server


@pytest.mark.parametrize("method,path", [
    ("POST", "/login"), ("POST", "/register"),
    ("POST", "/api/auth/forgot-password"),
    ("GET", "/api/auth/google/start"), ("POST", "/api/library/upload"),
])
def test_invalid_trusted_header_is_400_before_limiter(server, monkeypatch, method, path):
    monkeypatch.setattr(server.request_throttle, "allow", lambda *a: pytest.fail("Limiter ran before header rejection"))
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=("10.0.0.2", 1234), raise_app_exceptions=False), base_url="https://test.invalid") as client:
            response = await client.request(method, path, headers=[("x-forwarded-for", "203.0.113.9"), ("x-forwarded-for", "198.51.100.1")])
            assert response.status_code == 400
            assert response.json() == {"detail": "Invalid forwarded client address"}
            assert response.headers["cache-control"] == "no-store"
    asyncio.run(run())


def test_uvicorn_cli_flag_overrides_environment(monkeypatch):
    main = importlib.import_module("uvicorn.main")
    captured = {}
    monkeypatch.setattr(main, "run", lambda *a, **kw: captured.update(kw))
    result = CliRunner().invoke(main.main, ["server:app", "--host", "0.0.0.0", "--port", "10000", "--no-access-log", "--no-proxy-headers"], env={"UVICORN_PROXY_HEADERS": "true", "FORWARDED_ALLOW_IPS": "*"})
    assert result.exit_code == 0, result.output
    assert captured["proxy_headers"] is False


def test_identity_resolved_once_and_shared_across_request_wrappers(monkeypatch):
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    scope = {"type": "http", "client": ("10.0.0.2", 1234), "headers": [(b"x-forwarded-for", b"203.0.113.9")]}
    assert auth.client_ip(Request(scope)) == "203.0.113.9"
    monkeypatch.setattr(auth, "_resolve_client_ip", lambda *a: pytest.fail("Identity resolved twice"))
    assert auth.client_ip(Request(scope)) == "203.0.113.9"


@pytest.mark.parametrize("peer,header", [
    ("203.0.113.9", "malformed"), ("10.0.0.2", "203.0.113.9"),
])
def test_session_csrf_and_authentication_remain_intact(server, monkeypatch, peer, header):
    monkeypatch.setattr(server.request_throttle, "allow", lambda *a: True)
    monkeypatch.setattr(server.user_store, "get_by_username", lambda *a: pytest.fail("Invalid CSRF reached user lookup"))
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=(peer, 1234)), base_url="https://test.invalid", headers={"x-forwarded-for": header}) as client:
            response = await client.get("/api/csrf")
            assert response.status_code == 200
            token = response.json()["csrf_token"]
            assert token and "auralis_session" in client.cookies
            # Valid token remains bound to the signed synthetic session.
            assert (await client.get("/api/csrf")).json()["csrf_token"] == token
            response = await client.post("/login", data={"username": "synthetic", "password": "synthetic", "csrf_token": "wrong"})
            assert response.status_code == 403
            assert (await client.get("/api/me")).status_code == 401
    asyncio.run(run())
