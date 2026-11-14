"""Immutable storage operations with short SQL transactions and bounded network I/O.

Every reservation/outbox obligation commits before I/O. No operation can delete
objects. Unknown completion stays held and retries allocate fresh identities.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from sqlalchemy import text

import audio_store
from db import tenant_session
from storage_adapters import (
    FilesystemStorageAdapter,
    LOCAL_STORAGE_BUCKET,
    LOCAL_STORAGE_ENDPOINT,
    LOCAL_NAMESPACE_ENVIRONMENT,
    LocalStorageConfigurationError,
    LocalStorageError,
    local_storage_selected,
    validate_local_source,
    validate_database_session,
)
from storage_namespace import ManagedStorageBoundary, NamespaceBinding

log = logging.getLogger(__name__)
NETWORK_DEADLINE_SECONDS = 60
CLOSE_DEADLINE_SECONDS = 5
LOCK_TIMEOUT_MS = 1000
STATEMENT_TIMEOUT_MS = 5000
IDLE_TRANSACTION_TIMEOUT_MS = 70000


def bound_transaction(session) -> None:
    """Transaction-local USERSET limits; no role grants or persistent settings."""
    if (
        getattr(getattr(getattr(session, "bind", None), "dialect", None), "name", None)
        == "postgresql"
    ):
        session.execute(text(f"SET LOCAL lock_timeout='{LOCK_TIMEOUT_MS}ms'"))
        session.execute(text(f"SET LOCAL statement_timeout='{STATEMENT_TIMEOUT_MS}ms'"))
        session.execute(
            text(
                f"SET LOCAL idle_in_transaction_session_timeout='{IDLE_TRANSACTION_TIMEOUT_MS}ms'"
            )
        )


def configured_binding() -> NamespaceBinding:
    try:
        local_backend = local_storage_selected()
    except LocalStorageConfigurationError as exc:
        raise audio_store.StorageError(str(exc)) from None
    if local_backend:
        endpoint, bucket = LOCAL_STORAGE_ENDPOINT, LOCAL_STORAGE_BUCKET
    else:
        endpoint, _, bucket = audio_store._settings()
    try:
        ident = uuid.UUID(os.environ.get("VERVFY_STORAGE_NAMESPACE_ID", ""))
    except ValueError:
        raise audio_store.StorageError(
            "Explicit storage namespace identity required"
        ) from None
    environment = (
        LOCAL_NAMESPACE_ENVIRONMENT
        if local_backend
        else os.environ.get("VERVFY_ENVIRONMENT", "")
    )
    if not environment:
        raise audio_store.StorageError(
            "Explicit storage namespace environment required"
        )
    return NamespaceBinding(ident, environment, endpoint, bucket)


def validate_local_session(session) -> None:
    try:
        if local_storage_selected():
            validate_database_session(session.bind)
    except LocalStorageConfigurationError as exc:
        raise audio_store.StorageError(str(exc)) from None


def _validate(session, path: str, *, legacy_read=False):
    if session.bind.dialect.name != "postgresql":
        raise audio_store.StorageError(
            "Managed storage requires PostgreSQL lifecycle guards"
        )
    validate_local_session(session)
    bound_transaction(session)
    binding = configured_binding()
    if legacy_read and not path.startswith("v2/"):
        session.execute(
            text(
                "SELECT vervfy_storage.validate_namespace(:id,:env,:endpoint,:bucket)"
            ),
            {
                "id": binding.namespace_id,
                "env": binding.environment,
                "endpoint": binding.endpoint,
                "bucket": binding.bucket,
            },
        )
    else:
        ManagedStorageBoundary(session.connection(), binding).validate(path)
    return binding


def _binding(user_id, path, *, legacy_read=False):
    with tenant_session(user_id) as session:
        return _validate(session, path, legacy_read=legacy_read)


def _client(binding):
    try:
        if local_storage_selected():
            raise audio_store.StorageError(
                "Local filesystem storage must not use a Supabase client"
            )
    except LocalStorageConfigurationError as exc:
        raise audio_store.StorageError(str(exc)) from None
    endpoint, key, bucket = audio_store._settings()
    if (endpoint, bucket) != (binding.endpoint, binding.bucket) or not key:
        raise audio_store.StorageError(
            "Storage settings changed after namespace validation"
        )
    return httpx.AsyncClient(
        base_url=binding.endpoint + "/storage/v1",
        headers={
            "Authorization": "Bearer " + key,
            "apikey": key,
            "Accept-Encoding": "identity",
        },
        timeout=httpx.Timeout(connect=5, read=10, write=10, pool=5),
        transport=audio_store._transport,
        follow_redirects=False,
    )


@asynccontextmanager
async def _network(binding):
    client = _client(binding)
    try:
        # Covers DNS/connect, upload, response headers/body and byte verification;
        # unlike an inactivity timeout this also cancels a slow trickle response.
        async with asyncio.timeout(NETWORK_DEADLINE_SECONDS):
            yield client
    finally:
        async with asyncio.timeout(CLOSE_DEADLINE_SECONDS):
            await client.aclose()


def _run(factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise audio_store.StorageError(
            "Synchronous storage operations require a worker thread"
        )
    try:
        return asyncio.run(factory())
    except (TimeoutError, httpx.TimeoutException):
        raise audio_store.StorageError(
            "Storage operation exceeded its bounded deadline"
        ) from None
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, OSError) as exc:
        # Never retain provider messages/URLs or credential-bearing exception chains.
        raise audio_store.StorageError(
            f"Storage operation failed ({type(exc).__name__})"
        ) from None


def _url(binding, path, *, read=False):
    return (
        ("/object/authenticated/" if read else "/object/")
        + quote(binding.bucket, safe="")
        + "/"
        + quote(path, safe="/")
    )


@dataclass(frozen=True)
class Reservation:
    object_id: uuid.UUID
    path: str
    token: uuid.UUID


def _advance(user_id, reservation, state):
    with tenant_session(user_id) as session:
        validate_local_session(session)
        bound_transaction(session)
        session.execute(
            text("SELECT vervfy_storage.advance_upload(:id,:token,:state)"),
            {"id": reservation.object_id, "token": reservation.token, "state": state},
        )
        session.commit()


def _reserve(user_id, kind, extension):
    try:
        local_storage_selected()
    except LocalStorageConfigurationError as exc:
        raise audio_store.StorageError(str(exc)) from None
    with tenant_session(user_id) as session:
        if session.bind.dialect.name != "postgresql":
            raise audio_store.StorageError("Managed storage requires PostgreSQL")
        validate_local_session(session)
        bound_transaction(session)
        row = session.execute(
            text("SELECT * FROM vervfy_storage.reserve_object(:kind,:ext)"),
            {"kind": kind, "ext": extension},
        ).one()
        obj = Reservation(row.object_id, row.object_path, row.upload_token)
        _validate(session, obj.path)
        session.execute(
            text("SELECT vervfy_storage.request_cleanup(:id)"), {"id": obj.object_id}
        )
        session.commit()
        return obj


def _digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.digest()


async def _transfer(binding, path, source, content_type, size, expected_digest):
    async def chunks():
        while chunk := source.read(64 * 1024):
            # Local file access is deliberately outside the network guarantee;
            # this checkpoint makes network/body cancellation cooperative.
            await asyncio.sleep(0)
            yield chunk

    async with _network(binding) as client:
        async with client.stream(
            "POST",
            _url(binding, path),
            content=chunks(),
            headers={
                "Content-Type": content_type,
                "Content-Length": str(size),
                "x-upsert": "false",
                "Cache-Control": "max-age=31536000",
            },
        ) as response:
            if response.status_code >= 300:
                raise audio_store.StorageError("Create-only upload was not confirmed")
        digest = hashlib.sha256()
        count = 0
        async with client.stream("GET", _url(binding, path, read=True)) as response:
            if (
                response.status_code != 200
                or response.headers.get("content-encoding", "identity") != "identity"
            ):
                raise audio_store.StorageError("Storage verification failed")
            async for chunk in response.aiter_bytes():
                count += len(chunk)
                if count > size:
                    raise audio_store.StorageError("Storage verification size mismatch")
                digest.update(chunk)
        if count != size or digest.digest() != expected_digest:
            raise audio_store.StorageError("Storage verification digest mismatch")


def upload_file(user_id, kind, file_path, content_type, extension):
    try:
        local_backend = local_storage_selected()
    except LocalStorageConfigurationError as exc:
        raise audio_store.StorageError(str(exc)) from None
    if not re.fullmatch(r"[a-z0-9]{1,5}", extension):
        raise audio_store.StorageError("Invalid storage extension")
    if local_backend:
        try:
            validate_local_source(file_path)
        except LocalStorageError as exc:
            raise audio_store.StorageError(str(exc)) from None
    size = os.path.getsize(file_path)
    expected_digest = _digest(file_path)
    obj = _reserve(user_id, kind, extension)
    try:
        _advance(user_id, obj, "uploading")
        # Binding is immutable in SQL; close validation transaction before I/O.
        # Both requests use one captured, validated endpoint/bucket/client.
        binding = _binding(user_id, obj.path)
        with open(file_path, "rb") as source:
            if local_backend:
                try:
                    FilesystemStorageAdapter.from_environment().upload_file(
                        obj.path, source, size, expected_digest
                    )
                except LocalStorageError as exc:
                    raise audio_store.StorageError(str(exc)) from None
            else:
                _run(
                    lambda: _transfer(
                        binding, obj.path, source, content_type, size, expected_digest
                    )
                )
        _advance(user_id, obj, "ready")
        return obj.path
    except BaseException:
        try:
            _advance(user_id, obj, "hold")
        except Exception:
            log.exception(
                "Could not persist upload hold for reservation %s", obj.object_id
            )
        raise


def upload_bytes(user_id, kind, data, content_type="image/jpeg", extension="jpg"):
    with tempfile.NamedTemporaryFile(suffix="." + extension) as source:
        source.write(data)
        source.flush()
        return upload_file(user_id, kind, source.name, content_type, extension)


async def _download(binding, path, target, max_bytes):
    count = 0
    async with (
        _network(binding) as client,
        client.stream("GET", _url(binding, path, read=True)) as response,
    ):
        if (
            response.status_code != 200
            or response.headers.get("content-encoding", "identity") != "identity"
        ):
            raise audio_store.StorageError("Staged upload unavailable")
        async for chunk in response.aiter_bytes():
            count += len(chunk)
            if count > max_bytes:
                raise audio_store.StorageError("Staged upload exceeds size limit")
            target.write(chunk)
    if not count:
        raise audio_store.StorageError("Staged upload is empty")
    return count


def download_staged(session, path, destination, max_bytes):
    """The source job-row lock stays pinned during this bounded source read."""
    try:
        local_backend = local_storage_selected()
    except LocalStorageConfigurationError as exc:
        raise audio_store.StorageError(str(exc)) from None
    binding = _validate(session, path, legacy_read=True)
    if local_backend:
        try:
            return FilesystemStorageAdapter.from_environment().download_to_file(
                path, destination, max_bytes
            )
        except LocalStorageError as exc:
            raise audio_store.StorageError(str(exc)) from None
    with open(destination, "wb") as target:
        return _run(lambda: _download(binding, path, target, max_bytes))


async def _bucket_private(binding):
    data = bytearray()
    async with (
        _network(binding) as client,
        client.stream("GET", "/bucket/" + quote(binding.bucket, safe="")) as response,
    ):
        if (
            response.status_code != 200
            or response.headers.get("content-encoding", "identity") != "identity"
        ):
            raise audio_store.StorageError("Bucket privacy verification failed")
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > 65536:
                raise audio_store.StorageError("Bucket metadata exceeds size limit")
    payload = json.loads(data)
    return isinstance(payload, dict) and payload.get("public") is False


def require_private_bucket():
    binding = _binding("namespace-preflight", "binding-preflight", legacy_read=True)
    try:
        if local_storage_selected():
            return FilesystemStorageAdapter.from_environment().is_private()
    except (LocalStorageConfigurationError, LocalStorageError) as exc:
        raise audio_store.StorageError(str(exc)) from None
    return _run(lambda: _bucket_private(binding))
