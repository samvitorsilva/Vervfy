"""Staging-only copy-on-write remediation. No overwrite, delete, refund or ACL edits.

Old links and already cached bytes are deliberately not claimed to be revoked.
New references use new, verified, quota-charged immutable identities. Failed CAS
attachments leave their new reservation charged for the existing reconciliation
procedures; this module never bypasses the disabled physical cleanup pipeline.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
import uuid

from sqlalchemy import select, update, text

import audio_security
import audio_store
import storage_lifecycle
from db import TrackRecord, tenant_session


def _trial(*, write=False):
    if os.environ.get("VERVFY_ENVIRONMENT") not in {"staging", "test", "development"} or not audio_security.enabled():
        raise audio_store.StorageError("Explicit isolated audio trial is required")
    if write:
        storage_lifecycle.require_storage_writes_enabled()


def _snapshot(user_id, track_id):
    with tenant_session(user_id) as session:
        row = session.execute(select(
            TrackRecord.storage_path, TrackRecord.media_version,
            TrackRecord.size_bytes, TrackRecord.filename,
        ).where(TrackRecord.user_id == user_id, TrackRecord.id == track_id)).one_or_none()
        if row is None or not row.storage_path or not row.media_version or row.size_bytes <= 0:
            raise audio_store.StorageError("Stored audio snapshot is unavailable")
        # Validate the actual immutable database binding even for a legacy source.
        binding = storage_lifecycle._validate(session, row.storage_path, legacy_read=True)
        return row, binding


def _copy_source(path, size, destination):
    if audio_store.object_size(path) != size:
        raise audio_store.StorageError("Source size differs from the approved snapshot")
    audio_store.download_to_file(path, destination, size)
    return storage_lifecycle._digest(destination).hex()


def plan(user_id: str, track_id: str) -> dict:
    """Read-only plan. Contains hashes and target IDs, never credentials or URLs."""
    _trial()
    row, binding = _snapshot(user_id, track_id)
    with tempfile.NamedTemporaryFile() as target:
        digest = _copy_source(row.storage_path, row.size_bytes, target.name)
    return {
        "format": 1, "user_id": user_id, "track_id": track_id,
        "namespace_id": str(binding.namespace_id), "environment": binding.environment,
        "path_hash": hashlib.sha256(row.storage_path.encode()).hexdigest(),
        "media_version": str(row.media_version), "size": row.size_bytes,
        "sha256": digest, "measured_at": time.time(),
    }


def _check_attachment_connection(connection, binding):
    if connection is None or not connection.in_transaction():
        raise audio_store.StorageError("Explicit staging operator transaction required to preserve cleanup holds")
    privileged = connection.execute(text("SELECT rolsuper OR rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=current_user")).scalar_one()
    if not privileged:
        raise audio_store.StorageError("Staging repair requires an existing privileged operator; runtime privileges must not be expanded")
    connection.execute(text("SELECT vervfy_storage.validate_namespace(:id,:environment,:endpoint,:bucket)"), {
        "id": binding.namespace_id, "environment": binding.environment,
        "endpoint": binding.endpoint, "bucket": binding.bucket,
    })


def _attach_preserving_holds(connection, binding, user_id, track_id, row, new_path):
    _check_attachment_connection(connection, binding)
    # All attachment/outbox changes share one savepoint and the caller's staging
    # operator transaction. No grants, policies or namespace settings are changed.
    with connection.begin_nested():
        connection.execute(text("SET LOCAL lock_timeout='1000ms'"))
        connection.execute(text("SET LOCAL statement_timeout='5000ms'"))
        connection.execute(text("SELECT set_config('app.current_user_id',:actor,true)"), {"actor": user_id})
        objects = connection.execute(text("SELECT id FROM vervfy_storage.objects WHERE path IN (:old,:new) ORDER BY path COLLATE \"C\" FOR UPDATE"), {"old": row.storage_path, "new": new_path}).scalars().all()
        jobs = connection.execute(text("SELECT object_id,state,available_at,claim_token,lease_until,error_code FROM vervfy_storage.cleanup_jobs WHERE object_id = ANY(:ids) ORDER BY object_id FOR UPDATE"), {"ids": objects}).mappings().all()
        if any(job["state"] not in {"held", "pending"} for job in jobs):
            raise audio_store.StorageError("Cleanup state requires separate review; attachment aborted")
        held = [job for job in jobs if job["state"] == "held"]
        result = connection.execute(update(TrackRecord).where(
            TrackRecord.user_id == user_id, TrackRecord.id == track_id,
            TrackRecord.storage_path == row.storage_path,
            TrackRecord.media_version == row.media_version,
            TrackRecord.size_bytes == row.size_bytes,
        ).values(storage_path=new_path, media_version=uuid.uuid4()))
        if result.rowcount != 1:
            raise audio_store.StorageError("Attachment changed; new object remains charged for reconciliation")
        if held:
            connection.execute(text("UPDATE vervfy_storage.cleanup_jobs SET state='held',available_at=:available_at,claim_token=:claim_token,lease_until=:lease_until,error_code=:error_code WHERE object_id=:object_id AND state='pending'"), [dict(job) for job in held])
            remaining = connection.execute(text("SELECT count(*) FROM vervfy_storage.cleanup_jobs WHERE object_id = ANY(:ids) AND state='held'"), {"ids": [job["object_id"] for job in held]}).scalar_one()
            if remaining != len(held):
                raise audio_store.StorageError("Cleanup hold changed; attachment rolled back")


def apply(approved_plan: dict, *, attachment_connection=None) -> str:
    """Caller supplies a freshly reviewed plan; never called by HTTP or startup."""
    _trial(write=True)
    expected_keys = {"format", "user_id", "track_id", "namespace_id", "environment", "path_hash", "media_version", "size", "sha256", "measured_at"}
    if set(approved_plan) != expected_keys or approved_plan["format"] != 1:
        raise audio_store.StorageError("Invalid audio cache plan")
    age = time.time() - approved_plan["measured_at"]
    if not 0 <= age <= 900:
        raise audio_store.StorageError("Fresh audio cache plan required")
    user_id, track_id = approved_plan["user_id"], approved_plan["track_id"]
    row, binding = _snapshot(user_id, track_id)
    _check_attachment_connection(attachment_connection, binding)
    if (str(binding.namespace_id), binding.environment,
        hashlib.sha256(row.storage_path.encode()).hexdigest(), str(row.media_version), row.size_bytes) != (
        approved_plan["namespace_id"], approved_plan["environment"],
        approved_plan["path_hash"], approved_plan["media_version"], approved_plan["size"]):
        raise audio_store.StorageError("Audio cache plan drifted")
    extension = os.path.splitext(row.filename)[1].lower().lstrip(".")
    with tempfile.NamedTemporaryFile(suffix="." + extension) as target:
        digest = _copy_source(row.storage_path, row.size_bytes, target.name)
        if digest != approved_plan["sha256"]:
            raise audio_store.StorageError("Source digest differs from the approved plan")
        # Reuses existing namespace, retained-byte quota, verification and hold logic.
        new_path = storage_lifecycle.upload_file(user_id, "audio", target.name,
            audio_store.guess_content_type(row.filename), extension)
    storage_lifecycle.require_storage_writes_enabled()
    storage_lifecycle._binding(user_id, new_path)
    _attach_preserving_holds(attachment_connection, binding, user_id, track_id, row, new_path)
    # The caller must commit its explicit staging operator transaction.
    return hashlib.sha256(new_path.encode()).hexdigest()
