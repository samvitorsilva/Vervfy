"""Mocked provider reads only; never contact hosted storage."""

import asyncio
import uuid

import httpx
import pytest

from scripts.storage_inventory_reconcile import ReadOnlyObserver
from storage_inventory import InventoryBlocked
from storage_namespace import NamespaceBinding

BINDING = NamespaceBinding(
    uuid.uuid4(), "disposable-test", "https://vervfy.invalid", "synthetic"
)


def observe(handler, **kwargs):
    return ReadOnlyObserver(
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False
        ),
        BINDING,
        **kwargs,
    )("legacy/a b.mp3")


def test_matching_complete_reads_use_only_authenticated_gets():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "vervfy.invalid"
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(
            200, content=b"synthetic", headers={"etag": '"immutable"'}
        )

    result = observe(handler)
    assert result["bytes"] == 9
    assert len(result["sha256"]) == 64
    assert len(requests) == 2


@pytest.mark.parametrize(
    "status,headers,body",
    [
        (404, {}, b"not found"),
        (403, {}, b"denied"),
        (302, {"location": "https://elsewhere.invalid"}, b""),
        (200, {}, b"bytes"),
        (200, {"etag": 'W/"weak"'}, b"bytes"),
        (200, {"etag": '"v"'}, b""),
        (200, {"etag": '"v"', "content-length": "999"}, b"bytes"),
        (200, {"etag": '"v"', "content-encoding": "unsupported"}, b"bytes"),
    ],
)
def test_missing_unversioned_empty_redirect_or_partial_results_block(
    status, headers, body
):
    with pytest.raises(InventoryBlocked):
        observe(lambda request: httpx.Response(status, headers=headers, content=body))


@pytest.mark.parametrize("changed", ["bytes", "etag"])
def test_changing_content_or_version_fails_closed(changed):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(
            200,
            content=b"old" if count == 1 or changed == "etag" else b"new",
            headers={"etag": f'"{count if changed == "etag" else 1}"'},
        )

    with pytest.raises(InventoryBlocked):
        observe(handler)


def test_bounds_and_provider_errors_are_redacted():
    with pytest.raises(InventoryBlocked):
        observe(
            lambda request: httpx.Response(
                200, content=b"too large", headers={"etag": '"v"'}
            ),
            max_bytes=2,
        )

    async def slow(request):
        await asyncio.sleep(0.05)
        return httpx.Response(200, content=b"data", headers={"etag": '"v"'})

    with pytest.raises(InventoryBlocked):
        observe(slow, deadline=0.01)

    def handler(request):
        raise httpx.ReadTimeout("PRIVATE CREDENTIALS")

    with pytest.raises(InventoryBlocked) as error:
        observe(handler)
    assert "PRIVATE" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize(
    "path", ["", "../other/key", "a/../key", "/key", "a//key", "a\\key", "a\x00key"]
)
def test_unsafe_paths_never_reach_provider(path):
    def never(request):
        raise AssertionError("Unsafe path reached provider")

    with pytest.raises(InventoryBlocked):
        ReadOnlyObserver(
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(never)), BINDING
        )(path)


def test_absolute_deadline_also_interrupts_slow_trickling_body():
    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(0.002)
                yield b"x"

    def handler(request):
        return httpx.Response(200, headers={"etag": '"v"'}, stream=Trickle())

    with pytest.raises(InventoryBlocked, match="timed out"):
        observe(handler, deadline=0.01)
