"""Disposable rehearsal only. Never imported by application or worker entry points.

Storage is deliberately memory-only: no filesystem or network deletion capability.
SQL capabilities are installed only by the disposable PostgreSQL test fixture.
"""

from dataclasses import dataclass, field

from sqlalchemy import text

from scripts.storage_cleanup_worker import CleanupClaim, CleanupStorageFailure
from storage_adapters import (
    LOCAL_NAMESPACE_ENVIRONMENT,
    LOCAL_STORAGE_BUCKET,
    LOCAL_STORAGE_ENDPOINT,
    validate_database_session,
)
from storage_namespace import ManagedStorageBoundary


@dataclass
class SyntheticStorage:
    objects: dict[str, bytes] = field(default_factory=dict)
    failure: str | None = None
    calls: list[str] = field(default_factory=list)

    def delete_if_present(self, path):
        self.calls.append(path)
        if self.failure == "storage_timeout":
            raise CleanupStorageFailure(self.failure)
        if self.failure != "still_present":
            self.objects.pop(path, None)
        if self.failure and self.failure != "still_present":
            raise CleanupStorageFailure(self.failure)

    def absent(self, path):
        return path not in self.objects


class IsolatedCleanupWorker:
    def __init__(self, engine, binding, storage):
        if type(storage) is not SyntheticStorage:
            raise ValueError("Only synthetic in-memory storage is accepted")
        self.engine, self.binding, self.storage = engine, binding, storage

    def preflight(self):
        """Reject unsafe configuration before checking out any connection."""
        if type(self.storage) is not SyntheticStorage:
            raise ValueError("Only synthetic in-memory storage is accepted")
        if (self.binding.environment, self.binding.endpoint, self.binding.bucket) != (
            LOCAL_NAMESPACE_ENVIRONMENT,
            LOCAL_STORAGE_ENDPOINT,
            LOCAL_STORAGE_BUCKET,
        ):
            raise RuntimeError("Synthetic namespace required")
        validate_database_session(self.engine)
        if self.engine.url.username != "storage_cleanup_worker":
            raise RuntimeError("Restricted cleanup login required")

    def validate(self, connection):
        # Recheck after checkout too, before any authorization or storage I/O.
        self.preflight()
        identity = connection.execute(
            text("SELECT current_user, session_user, inet_server_addr()")
        ).one()
        if tuple(identity) != (
            "storage_cleanup_worker",
            "storage_cleanup_worker",
            None,
        ):
            raise RuntimeError("Restricted local connection required")
        connection.execute(text("SET LOCAL lock_timeout='1s'"))
        connection.execute(text("SET LOCAL statement_timeout='5s'"))
        connection.execute(text("SET LOCAL idle_in_transaction_session_timeout='10s'"))
        if (
            connection.execute(text("SHOW transaction_isolation")).scalar_one()
            != "read committed"
        ):
            raise RuntimeError("Cleanup requires READ COMMITTED")
        connection.execute(
            text(
                "SELECT vervfy_storage.validate_namespace(:id,:env,:endpoint,:bucket)"
            ),
            {
                "id": self.binding.namespace_id,
                "env": self.binding.environment,
                "endpoint": self.binding.endpoint,
                "bucket": self.binding.bucket,
            },
        )

    def claim(self):
        self.preflight()
        with self.engine.begin() as connection:
            self.validate(connection)
            row = connection.execute(
                text("SELECT * FROM cleanup_rehearsal.claim()")
            ).first()
            if row is None:
                return None
            ManagedStorageBoundary(connection, self.binding).validate(row.object_path)
            claim = CleanupClaim(row.object_id, row.object_path, row.claim_token)
        # A failed/ambiguous commit never reaches storage.
        return claim

    def process(self, claim):
        self.preflight()
        with self.engine.begin() as connection:
            self.validate(connection)
            ManagedStorageBoundary(connection, self.binding).validate(claim.path)
            parameters = {
                "id": claim.object_id,
                "token": claim.token,
                "path": claim.path,
            }
            authorized = connection.execute(
                text("SELECT cleanup_rehearsal.authorize(:id,:token,:path)"), parameters
            ).scalar_one()
            if not authorized:
                raise RuntimeError("Cleanup claim rejected")
            # Object and job locks remain held through synthetic I/O. Attachment
            # triggers take the same object lock; other claimers SKIP LOCKED.
            try:
                self.storage.delete_if_present(claim.path)
                if not self.storage.absent(claim.path):
                    raise CleanupStorageFailure("storage_ambiguous")
            except CleanupStorageFailure as exc:
                parameters["code"] = exc.code
                accepted = connection.execute(
                    text("SELECT vervfy_storage.retry_cleanup(:id,:token,:code)"),
                    parameters,
                ).scalar_one()
            else:
                accepted = connection.execute(
                    text("SELECT vervfy_storage.complete_cleanup(:id,:token)"),
                    parameters,
                ).scalar_one()
            if not accepted:
                raise RuntimeError("Cleanup lease expired before persistence")

    def run_once(self):
        claim = self.claim()
        if claim is None:
            return False
        self.process(claim)
        return True
