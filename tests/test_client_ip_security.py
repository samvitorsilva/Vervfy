"""Pure request/IP resolution checks: no database or network operations."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from auth import client_ip


def request(peer="10.0.0.2", values=()):
    return Request({"type": "http", "client": (peer, 1234) if peer is not None else None,
                    "headers": [(b"x-forwarded-for", value.encode()) for value in values]})


@pytest.fixture(autouse=True)
def trust(monkeypatch):
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_CIDRS", "10.0.0.0/24,2001:db8:ffff::/64")


def test_untrusted_peer_cannot_rotate_identity():
    for headers in [("198.51.100.1",), ("198.51.100.2",), ("bad", "other")]:
        assert client_ip(request("203.0.113.9", headers)) == "203.0.113.9"


def test_attacker_prefix_does_not_override_one_hop():
    assert client_ip(request(values=("198.51.100.99, 203.0.113.9",))) == "203.0.113.9"


def test_verified_two_hop_tail(monkeypatch):
    monkeypatch.setenv("VERVFY_TRUSTED_PROXY_HOPS", "2")
    assert client_ip(request(values=("198.51.100.99, 203.0.113.9, 10.0.0.3",))) == "203.0.113.9"
    with pytest.raises(HTTPException):
        client_ip(request(values=("198.51.100.99, 203.0.113.9",)))


@pytest.mark.parametrize("headers", [
    ("",), ("unknown",), ("203.0.113.1,",), (",203.0.113.1",),
    ("203.0.113.1,,10.0.0.3",), ("203.0.113.1:80",),
    ("[2001:db8::1]:443",), ("fe80::1%eth0",), ("010.0.0.1",),
    ("203.0.113.1", "198.51.100.2"), ("203.0.113.1\n",),
    (",".join(["203.0.113.1"] * 33),), ("x" * 2049,),
])
def test_trusted_peer_malformed_or_ambiguous_headers_rejected(headers):
    with pytest.raises(HTTPException) as error:
        client_ip(request(values=headers))
    assert error.value.status_code == 400
    assert error.value.detail == "Invalid forwarded client address"


@pytest.mark.parametrize("name,value", [
    ("VERVFY_TRUSTED_PROXY_HOPS", "0"), ("VERVFY_TRUSTED_PROXY_HOPS", "-1"),
    ("VERVFY_TRUSTED_PROXY_HOPS", "invalid"), ("VERVFY_TRUSTED_PROXY_HOPS", "33"),
    ("VERVFY_TRUSTED_PROXY_CIDRS", ""), ("VERVFY_TRUSTED_PROXY_CIDRS", "*"),
    ("VERVFY_TRUSTED_PROXY_CIDRS", "0.0.0.0/0"),
    ("VERVFY_TRUSTED_PROXY_CIDRS", "::/0"),
    ("VERVFY_TRUSTED_PROXY_CIDRS", "10.0.0.1/24"),
])
def test_disabled_or_invalid_trust_falls_back_to_peer(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    assert client_ip(request(values=("198.51.100.9",))) == "10.0.0.2"


def test_missing_header_or_peer_fallback():
    assert client_ip(request()) == "10.0.0.2"
    assert client_ip(request(None, ("198.51.100.1",))) == "unknown"
    assert client_ip(request("not-an-ip", ("198.51.100.1",))) == "unknown"


def test_ip_canonicalization_and_ipv6_proxy():
    assert client_ip(request("2001:db8:ffff::1", ("2001:0db8:0001::0001",))) == "2001:db8:1::1"
    assert client_ip(request(values=("::ffff:203.0.113.9",))) == "203.0.113.9"
    assert client_ip(request("::ffff:10.0.0.2", ("203.0.113.9",))) == "203.0.113.9"
