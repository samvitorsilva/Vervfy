"""Managed upload boundary for later writer integration; no application callers yet.

No automatic initialization, deletion, or fallback to unbound storage is provided.
"""

import re
import uuid
from dataclasses import dataclass

import sqlalchemy as sa

import audio_store
from storage_adapters import (
    LOCAL_STORAGE_BUCKET,
    LOCAL_STORAGE_ENDPOINT,
    LocalStorageConfigurationError,
    local_storage_selected,
)


@dataclass(frozen=True)
class NamespaceBinding:
    namespace_id: uuid.UUID
    environment: str
    endpoint: str
    bucket: str


class ManagedStorageBoundary:
    """Pre-I/O validation only; offers no upload or deletion entry point."""

    def __init__(self, connection, binding: NamespaceBinding):
        self.connection = connection
        self.binding = binding

    def validate(self, path: str) -> None:
        try:
            local_backend = local_storage_selected()
        except LocalStorageConfigurationError as exc:
            raise audio_store.StorageError(str(exc)) from None
        if local_backend:
            endpoint, bucket = LOCAL_STORAGE_ENDPOINT, LOCAL_STORAGE_BUCKET
        else:
            endpoint, _, bucket = audio_store._settings()
        if (endpoint, bucket) != (self.binding.endpoint, self.binding.bucket):
            raise audio_store.StorageError(
                "Managed storage configuration differs from binding"
            )
        self.connection.execute(
            sa.text(
                "SELECT vervfy_storage.validate_namespace(:id,:environment,:endpoint,:bucket)"
            ),
            {
                "id": self.binding.namespace_id,
                "environment": self.binding.environment,
                "endpoint": endpoint,
                "bucket": bucket,
            },
        )
        prefix = "v2/" + str(self.binding.namespace_id) + "/"
        if not path.startswith(prefix) or not re.fullmatch(
            r"v2/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[A-Za-z0-9_-]{1,32}/(?:audio|track-cover|album-cover|artist-photo|staged-audio)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[a-z0-9]{1,5}",
            path,
        ):
            raise audio_store.StorageError("Invalid managed storage object identity")


def initialize_namespace(connection, binding: NamespaceBinding) -> NamespaceBinding:
    """Bind storage once in the caller's transaction; never contacts storage.

    A separately authorized bootstrap administrator with RLS bypass and table
    privileges must call this explicitly. No application startup caller exists.
    Exact retries are harmless; any different binding requires reviewed recovery.
    """
    if (
        not isinstance(binding.namespace_id, uuid.UUID)
        or binding.namespace_id.int == 0
        or re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", binding.environment) is None
        or len(binding.endpoint) >= 300
        or re.fullmatch(r"https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", binding.endpoint)
        is None
        or re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", binding.bucket) is None
    ):
        raise ValueError("Invalid immutable storage binding")
    if connection.dialect.name != "postgresql" or not connection.in_transaction():
        raise RuntimeError("Namespace initialization requires a PostgreSQL transaction")
    # A savepoint rolls back the insert on every validation failure, even when
    # the caller catches the exception and later commits its outer transaction.
    with connection.begin_nested():
        privileged = connection.execute(
            sa.text("""
            SELECT rolsuper OR rolbypassrls FROM pg_catalog.pg_roles
            WHERE rolname=current_user
        """)
        ).scalar_one()
        if not privileged:
            raise RuntimeError(
                "Namespace initialization requires a bootstrap administrator"
            )
        revision = (
            connection.execute(
                sa.text("SELECT version_num FROM public.alembic_version")
            )
            .scalars()
            .all()
        )
        if revision != ["0027_storage_lifecycle"]:
            raise RuntimeError(
                "Namespace initialization requires release revision 0027"
            )
        # Serialize empty-table initializers as well as retries. No UPDATE is
        # attempted: the immutable trigger also rejects no-op UPDATE statements.
        connection.execute(
            sa.text("LOCK TABLE vervfy_storage.namespaces IN EXCLUSIVE MODE")
        )
        values = {
            "namespace_id": binding.namespace_id,
            "environment": binding.environment,
            "endpoint": binding.endpoint,
            "bucket": binding.bucket,
        }
        connection.execute(
            sa.text("""
            INSERT INTO vervfy_storage.namespaces
                (id, namespace_id, environment, endpoint, bucket, physical_cleanup_enabled)
            VALUES (1, :namespace_id, :environment, :endpoint, :bucket, false)
            ON CONFLICT (id) DO NOTHING
        """),
            values,
        )
        actual = connection.execute(
            sa.text("""
            SELECT namespace_id, environment, endpoint, bucket, physical_cleanup_enabled
            FROM vervfy_storage.namespaces WHERE id=1
        """)
        ).one()
        if tuple(actual) != (*values.values(), False):
            raise RuntimeError(
                "Storage namespace already has a different immutable binding"
            )
    return binding
