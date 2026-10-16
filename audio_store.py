"""Audio file storage in a private Supabase Storage bucket (plain REST via httpx).

Audio used to live in Postgres (``tracks.audio_data``).  Every stream request
pulled the whole blob out of the database, which is what burned through the
free plan's egress allowance.  Audio now lives in Storage and Postgres only
keeps the object path (``tracks.storage_path``).

Environment variables (set them on Render, never ship them to the browser):

    SUPABASE_URL           https://<project-ref>.supabase.co
    SUPABASE_SERVICE_KEY   the ``service_role`` key
    SUPABASE_BUCKET        bucket name, default ``songs`` (keep it private)
"""
from __future__ import annotations

import functools
import logging
import mimetypes
import os
import re
from urllib.parse import quote, urlsplit

import httpx

log = logging.getLogger("vervfy.audio_store")

# Tests can inject an ``httpx.MockTransport`` here.
_transport: httpx.BaseTransport | None = None
_shared_client: httpx.Client | None = None
_shared_client_key: tuple[str, str, str, int] | None = None


class StorageError(RuntimeError):
    """Storage is misconfigured or Supabase refused / failed a request."""


def _scrub(text: str) -> str:
    """Never let the key (or a mis-pasted one) leak into an error message."""
    url, key, _ = _settings()
    for secret in (key, url):
        if secret:
            text = text.replace(secret, "***")
    return text


def _wrap_errors(fn):
    """Network problems (bad URL, DNS, timeout...) surface as StorageError, not a bare 500."""

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except StorageError:
            raise
        except (httpx.HTTPError, httpx.InvalidURL, ValueError, OSError) as exc:  # ValueError covers UnicodeError
            raise StorageError(_scrub(f"{type(exc).__name__}: {exc}")[:300]) from exc

    return inner


_HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9-]{1,63}\.)*[A-Za-z0-9-]{1,63}$")


def _validate_url(url: str) -> None:
    """Fail with a clear message if SUPABASE_URL is not a plain https://<ref>.supabase.co address."""
    parts = urlsplit(url)
    try:
        host = parts.hostname or ""
    except ValueError:
        host = ""
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or not _HOST_RE.match(host)
        or parts.path.strip("/")
    ):
        raise StorageError(
            "SUPABASE_URL is not a valid project URL - it must look like https://<project-ref>.supabase.co "
            "(no path, and the secret key belongs in SUPABASE_SERVICE_KEY, not here)"
        )


def _settings() -> tuple[str, str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    bucket = os.environ.get("SUPABASE_BUCKET", "songs").strip() or "songs"
    return url, key, bucket


def enabled() -> bool:
    """True when Storage is configured; otherwise the app keeps the legacy DB path."""
    url, key, _ = _settings()
    return bool(url and key)


def _new_client() -> httpx.Client:
    url, key, _ = _settings()
    if not (url and key):
        raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    _validate_url(url)
    client = httpx.Client(
        base_url=f"{url}/storage/v1",
        headers={"Authorization": f"Bearer {key}", "apikey": key},
        timeout=httpx.Timeout(60.0, connect=10.0),
        transport=_transport,
    )
    client.headers["Authorization"] = "Bearer " + key
    return client


def _client() -> httpx.Client:
    global _shared_client, _shared_client_key
    url, key, bucket = _settings()
    client_key = (url, key, bucket, id(_transport))
    if _shared_client is None or _shared_client_key != client_key:
        close_client()
        _shared_client = _new_client()
        _shared_client_key = client_key
    return _shared_client


def close_client() -> None:
    """Close pooled Storage connections when the application shuts down."""
    global _shared_client, _shared_client_key
    if _shared_client is not None:
        _shared_client.close()
        _shared_client = None
        _shared_client_key = None


def _object_url(path: str, *, authenticated: bool = False) -> str:
    _, _, bucket = _settings()
    prefix = "/object/authenticated" if authenticated else "/object"
    return f"{prefix}/{quote(bucket, safe='')}/{quote(path, safe='/')}"


def object_path(user_id: str, track_id: str, filename: str) -> str:
    """Stable, ASCII-only object key: ``<user_id>/<track_id><.ext>``."""
    ext = os.path.splitext(filename)[1].lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext):
        ext = ""
    return f"{user_id}/{track_id}{ext}"


def cover_object_path(user_id: str, track_id: str) -> str:
    """Stable user-scoped object key for a normalized JPEG track cover."""
    return f"covers/{user_id}/{track_id}.jpg"


def guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "audio/mpeg"


@_wrap_errors
def upload(path: str, data: bytes | bytearray | memoryview, content_type: str = "audio/mpeg") -> None:
    client = _client()
    resp = client.post(
        _object_url(path),
        content=bytes(data),  # httpx would iterate a bytearray as ints
        headers={"Content-Type": content_type, "x-upsert": "true"},
    )
    if resp.status_code >= 300:
        raise StorageError(f"upload failed ({resp.status_code}): {resp.text[:200]}")


@_wrap_errors
def upload_file(path: str, file_path: str, content_type: str = "audio/mpeg") -> None:
    """Stream a local file to Storage without retaining the audio in memory."""
    client = _client()
    with open(file_path, "rb") as source:
        response = client.post(
            _object_url(path),
            content=source,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
    if response.status_code >= 300:
        raise StorageError(
            f"upload failed ({response.status_code}): {response.text[:200]}"
        )


@_wrap_errors
def create_signed_url(path: str, expires_in: int = 3600) -> str:
    """Create a direct-to-Storage URL for one object in the private bucket."""
    _, _, bucket = _settings()
    client = _client()
    response = client.post(
        f"/object/sign/{quote(bucket, safe='')}/{quote(path, safe='/')}",
        json={"expiresIn": expires_in},
    )
    if response.status_code >= 300:
        raise StorageError(
            f"signed URL creation failed ({response.status_code}): {response.text[:200]}"
        )
    payload = response.json()
    signed_path = payload.get("signedURL") if isinstance(payload, dict) else None
    if not isinstance(signed_path, str) or not signed_path:
        raise StorageError("signed URL creation returned no URL")
    if signed_path.startswith("https://"):
        if not signed_path.startswith(_settings()[0] + "/"):
            raise StorageError("signed URL points outside the configured Supabase project")
        return signed_path
    if not signed_path.startswith("/"):
        signed_path = "/" + signed_path
    return f"{_settings()[0]}/storage/v1{signed_path}"


@_wrap_errors
def delete(path: str) -> None:
    client = _client()
    resp = client.delete(_object_url(path))
    if resp.status_code >= 300 and resp.status_code != 404:
        raise StorageError(f"delete failed ({resp.status_code}): {resp.text[:200]}")


def delete_quietly(path: str | None) -> None:
    """Best-effort delete for cleanup paths; never raises."""
    if not path:
        return
    try:
        delete(path)
    except Exception:  # noqa: BLE001 - cleanup must not break the request
        log.warning("could not delete storage object %s", path, exc_info=True)


@_wrap_errors
def delete_many(paths: list[str]) -> None:
    """Delete account-owned objects, raising if Storage cannot confirm deletion."""
    paths = [p for p in paths if p]
    for i in range(0, len(paths), 100):
        chunk = paths[i : i + 100]
        _, _, bucket = _settings()
        client = _client()
        resp = client.request(
            "DELETE",
            f"/object/{quote(bucket, safe='')}",
            json={"prefixes": chunk},
        )
        if resp.status_code >= 300:
            raise StorageError(
                f"bulk delete failed ({resp.status_code}): {resp.text[:200]}"
            )


@_wrap_errors
def read_range(path: str, start: int, end: int) -> bytes:
    """Return bytes ``start..end`` (inclusive) of an object."""
    if start < 0 or end < start:
        raise StorageError("invalid byte range")
    _, resp = open_range(path, start, end)
    try:
        remaining = end - start + 1
        skip = start if resp.status_code == 200 else 0
        result = bytearray()
        for chunk in resp.iter_bytes(64 * 1024):
            if skip:
                skipped = min(skip, len(chunk))
                chunk = chunk[skipped:]
                skip -= skipped
            if not chunk:
                continue
            result.extend(chunk[:remaining])
            remaining -= min(remaining, len(chunk))
            if remaining == 0:
                break
        return bytes(result)
    finally:
        resp.close()


def read_all(path: str, size: int) -> bytes:
    """Read a staged object for worker processing, bounded by its known size."""
    if size < 0:
        raise StorageError("invalid staged object size")
    return read_range(path, 0, max(size - 1, 0)) if size else b""


@_wrap_errors
def download_to_file(path: str, destination: str, size: int) -> None:
    """Stream a staged object to disk in bounded chunks."""
    if size < 0:
        raise StorageError("invalid staged object size")
    if size == 0:
        open(destination, "wb").close()
        return
    _, response = open_range(path, 0, size - 1)
    try:
        written = 0
        with open(destination, "wb") as target:
            for chunk in response.iter_bytes(64 * 1024):
                if not chunk:
                    continue
                target.write(chunk[: size - written])
                written += min(len(chunk), size - written)
                if written >= size:
                    break
        if written != size:
            raise StorageError(
                f"read returned {written} bytes; expected {size}"
            )
    finally:
        response.close()


@_wrap_errors
def open_range(path: str, start: int, end: int) -> tuple[httpx.Client, httpx.Response]:
    """Open a streaming ranged GET.  The caller must close both objects."""
    client = _client()
    try:
        request = client.build_request(
            "GET", _object_url(path, authenticated=True), headers={"Range": f"bytes={start}-{end}"}
        )
        resp = client.send(request, stream=True)
        if resp.status_code not in (200, 206):
            body = resp.read()[:200]
            resp.close()
            raise StorageError(f"read failed ({resp.status_code}): {body!r}")
    except Exception:
        raise
    return client, resp


@_wrap_errors
def object_size(path: str) -> int | None:
    """Size in bytes of a stored object, or None if it does not exist."""
    client = _client()
    resp = client.get(_object_url(path, authenticated=True), headers={"Range": "bytes=0-0"})
    if resp.status_code == 404 or resp.status_code == 400:
        return None
    if resp.status_code == 206:
        match = re.search(r"/(\d+)\s*$", resp.headers.get("content-range", ""))
        return int(match.group(1)) if match else None
    if resp.status_code == 200:
        return len(resp.content)
    raise StorageError(f"stat failed ({resp.status_code}): {resp.text[:200]}")


@_wrap_errors
def bucket_exists() -> bool:
    _, _, bucket = _settings()
    client = _client()
    resp = client.get(f"/bucket/{quote(bucket, safe='')}")
    return resp.status_code == 200
