"""Exact route matching behind TLS termination; no redirects or body replay."""
import asyncio

import httpx
import pytest
from test_proxy_https_readiness import setup


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/csrf/"), ("GET", "/api/me/"),
    ("GET", "/api/auth/google/start/"),
    ("GET", "/api/auth/google/callback/"),
    ("POST", "/login/"), ("POST", "/register/"),
    ("POST", "/api/library/upload/"),
    ("GET", "/healthz/"), ("HEAD", "/healthz/"),
])
def test_noncanonical_slash_routes_do_not_redirect(setup, method, path):
    _, app = setup
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.example", follow_redirects=False) as client:
            response = await client.request(method, path, headers={
                "x-forwarded-host": "attacker.invalid",
                "x-forwarded-proto": "https",
                "x-forwarded-for": "malformed",
            })
            assert response.status_code == 404
            assert "location" not in response.headers
            assert response.headers["strict-transport-security"].startswith("max-age=")
    asyncio.run(run())


@pytest.mark.parametrize("method,path,status", [
    ("GET", "/healthz", 200), ("HEAD", "/healthz", 200),
    ("GET", "/api/csrf", 200), ("GET", "/api/me", 401),
    ("POST", "/login", 422),
    ("POST", "/api/library/upload", 401),
])
def test_canonical_routes_keep_their_method_and_authentication_behavior(setup, method, path, status):
    _, app = setup
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://app.example", follow_redirects=False) as client:
            response = await client.request(method, path)
            assert response.status_code == status
            assert "location" not in response.headers
    asyncio.run(run())
