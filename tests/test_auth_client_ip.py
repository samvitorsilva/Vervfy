from starlette.requests import Request

import auth


def _request(peer: str, forwarded_for: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", forwarded_for.encode())],
            "client": (peer, 1234),
            "server": ("example.test", 443),
        }
    )


def test_client_ip_ignores_forwarded_for_without_trusted_hops(monkeypatch):
    monkeypatch.delenv("VERVFY_TRUSTED_PROXY_HOPS", raising=False)
    request = _request("10.0.0.8", "198.51.100.77")

    assert auth.client_ip(request) == "10.0.0.8"


def test_client_ip_uses_only_the_rightmost_address_from_one_trusted_hop(
    monkeypatch,
):
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "1")
    request = _request("10.0.0.8", "198.51.100.77, 203.0.113.9")

    assert auth.client_ip(request) == "203.0.113.9"
