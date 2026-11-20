"""Synthetic ASGI requests through real Uvicorn middleware; no network I/O."""
import asyncio

import httpx
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from uvicorn import Config

from auth import client_ip


def call(monkeypatch, *, peer, xff=(), uvicorn_trust=None, proxy_headers=True,
         hops="1", cidrs="10.0.0.0/24"):
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", hops)
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_CIDRS", cidrs)
    async def app(scope, receive, send):
        response = JSONResponse({"asgi_peer": scope["client"][0],
                                 "resolved": client_ip(Request(scope))})
        await response(scope, receive, send)
    config = Config(app, host="0.0.0.0", proxy_headers=proxy_headers,
                    forwarded_allow_ips=uvicorn_trust, log_config=None,
                    lifespan="off")
    config.load()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=config.loaded_app, client=(peer, 1234)), base_url="http://test.invalid") as client:
            return (await client.get("/", headers=[("x-forwarded-for", value) for value in xff])).json()
    return asyncio.run(run())


def test_defaults_rewrite_loopback_before_resolver(monkeypatch):
    result = call(monkeypatch, peer="127.0.0.1", xff=("203.0.113.9",), cidrs="")
    assert result == {"asgi_peer": "203.0.113.9", "resolved": "203.0.113.9"}


def test_defaults_leave_nonloopback_peer_untouched(monkeypatch):
    result = call(monkeypatch, peer="10.0.0.2", xff=("198.51.100.1, 203.0.113.9",))
    assert result == {"asgi_peer": "10.0.0.2", "resolved": "203.0.113.9"}


def test_disabled_uvicorn_preserves_app_trust_boundary(monkeypatch):
    result = call(monkeypatch, peer="203.0.113.9", xff=("198.51.100.1",), proxy_headers=False)
    assert result == {"asgi_peer": "203.0.113.9", "resolved": "203.0.113.9"}


def test_wildcard_upstream_defeats_fallback(monkeypatch):
    result = call(monkeypatch, peer="203.0.113.9", xff=("198.51.100.1",), uvicorn_trust="*", cidrs="")
    # Regression demonstrates an unsafe deployment combination, not safe behavior.
    assert result == {"asgi_peer": "198.51.100.1", "resolved": "198.51.100.1"}


def test_source_restricted_uvicorn_only_resolution(monkeypatch):
    result = call(monkeypatch, peer="10.0.0.2", xff=("198.51.100.1, 203.0.113.9",), uvicorn_trust="10.0.0.0/24", hops="0")
    assert result == {"asgi_peer": "203.0.113.9", "resolved": "203.0.113.9"}


@pytest.mark.parametrize("xff", [(), ("198.51.100.1", "203.0.113.9")])
def test_untrusted_socket_safe_with_proxy_rewriting_disabled(monkeypatch, xff):
    assert call(monkeypatch, peer="203.0.113.9", xff=xff, proxy_headers=False)["resolved"] == "203.0.113.9"


def test_actual_server_middleware_malformed_header_is_400(monkeypatch):
    import server
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=("10.0.0.2", 1234), raise_app_exceptions=False), base_url="http://test.invalid") as client:
            response = await client.post("/login", headers={"x-forwarded-for": "malformed"})
            assert response.status_code == 400
            assert response.json() == {"detail": "Invalid forwarded client address"}
            assert response.headers["cache-control"] == "no-store"
    asyncio.run(run())
