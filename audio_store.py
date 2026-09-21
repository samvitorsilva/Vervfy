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
    if parts.scheme not in ("http", "https") or not _HOST_RE.match(host) or parts.path.strip("/"):
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


def _client() -> httpx.Client:
    url, key, _ = _settings()
    if not (url and key):
        raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    _validate_url(url)
    return httpx.Client(
        base_url=f"{url}/storage/v1",
        headers={"Authorization": f"Bearer {key}", "apikey": key},
        timeout=httpx.Timeout(60.0, connect=10.0),
        transport=_transport,
    )


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


def guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "audio/mpeg"


@_wrap_errors
def upload(path: str, data: bytes | bytearray | memoryview, content_type: str = "audio/mpeg") -> None:
    with _client() as client:
        resp = client.post(
            _object_url(path),
            content=bytes(data),  # httpx would iterate a bytearray as ints
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
    if resp.status_code >= 300:
        raise StorageError(f"upload failed ({resp.status_code}): {resp.text[:200]}")


@_wrap_errors
def delete(path: str) -> None:
    with _client() as client:
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


def delete_many_quietly(paths: list[str]) -> None:
    """Bulk best-effort delete (account deletion); never raises."""
    paths = [p for p in paths if p]
    for i in range(0, len(paths), 100):
        chunk = paths[i : i + 100]
        try:
            _, _, bucket = _settings()
            with _client() as client:
                resp = client.request("DELETE", f"/object/{quote(bucket, safe='')}", json={"prefixes": chunk})
            if resp.status_code >= 300:
                log.warning("bulk storage delete failed (%s): %s", resp.status_code, resp.text[:200])
        except Exception:  # noqa: BLE001
            log.warning("bulk storage delete failed", exc_info=True)


@_wrap_errors
def read_range(path: str, start: int, end: int) -> bytes:
    """Return bytes ``start..end`` (inclusive) of an object."""
    with _client() as client:
        resp = client.get(_object_url(path, authenticated=True), headers={"Range": f"bytes={start}-{end}"})
    if resp.status_code == 206:
        return resp.content
    if resp.status_code == 200:  # server ignored Range; slice locally
        return resp.content[start : end + 1]
    raise StorageError(f"read failed ({resp.status_code}): {resp.text[:200]}")


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
        if resp.status_code == 200 and start > 0:
            resp.close()
            raise StorageError("storage ignored the Range header")
    except Exception:
        client.close()
        raise
    return client, resp


@_wrap_errors
def object_size(path: str) -> int | None:
    """Size in bytes of a stored object, or None if it does not exist."""
    with _client() as client:
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
    with _client() as client:
        resp = client.get(f"/bucket/{quote(bucket, safe='')}")
    return resp.status_code == 200
