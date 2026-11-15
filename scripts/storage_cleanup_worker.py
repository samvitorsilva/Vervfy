"""Lease cleanup obligations without providing a production Storage deleter."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text

import audio_store
import storage_lifecycle
from storage_namespace import ManagedStorageBoundary, NamespaceBinding

log = logging.getLogger("vervfy.storage_cleanup_worker")

FAILURE_CODES = {
    "storage_unavailable",
    "storage_timeout",
    "storage_ambiguous",
    "storage_rejected",
    "storage_unknown",
}


class CleanupStorageFailure(RuntimeError):
    def __init__(self, code: str):
        if code not in FAILURE_CODES:
            raise ValueError("Invalid cleanup storage failure code")
        self.code = code
        super().__init__(code)


class IdempotentStorage(Protocol):
    def delete_if_present(self, path: str) -> None:
        """Return only after absence is confirmed; missing objects count as success."""


@dataclass(frozen=True)
class CleanupClaim:
    object_id: str
    path: str
    token: str


class CleanupWorker:
    def __init__(self, sessions, binding: NamespaceBinding, storage: IdempotentStorage):
        if storage is None:
            raise ValueError("An explicit cleanup storage adapter is required")
        self.sessions = sessions
        self.binding = binding
        self.storage = storage

    def _claim(self) -> CleanupClaim | None:
        with self.sessions.begin() as session:
            if session.bind.dialect.name != "postgresql":
                raise audio_store.StorageError(
                    "Storage cleanup requires PostgreSQL lifecycle guards"
                )
            storage_lifecycle.validate_local_session(session)
            storage_lifecycle.bound_transaction(session)
            row = session.execute(
                text("SELECT * FROM vervfy_storage.claim_next_cleanup()")
            ).mappings().first()
            if row is None:
                return None
            ManagedStorageBoundary(session.connection(), self.binding).validate(
                row["object_path"]
            )
            return CleanupClaim(
                str(row["object_id"]), row["object_path"], str(row["claim_token"])
            )

    def run_once(self) -> bool:
        claim = self._claim()
        if claim is None:
            return False
        try:
            self.storage.delete_if_present(claim.path)
        except CleanupStorageFailure as exc:
            with self.sessions.begin() as session:
                storage_lifecycle.validate_local_session(session)
                storage_lifecycle.bound_transaction(session)
                rescheduled = session.execute(
                    text(
                        "SELECT vervfy_storage.retry_cleanup(:object_id,:token,:code)"
                    ),
                    {
                        "object_id": claim.object_id,
                        "token": claim.token,
                        "code": exc.code,
                    },
                ).scalar_one()
            if not rescheduled:
                log.warning("Cleanup retry fence expired for object %s", claim.object_id)
            return True

        with self.sessions.begin() as session:
            storage_lifecycle.validate_local_session(session)
            storage_lifecycle.bound_transaction(session)
            completed = session.execute(
                text("SELECT vervfy_storage.complete_cleanup(:object_id,:token)"),
                {"object_id": claim.object_id, "token": claim.token},
            ).scalar_one()
        if not completed:
            log.warning("Cleanup completion fence expired for object %s", claim.object_id)
        return True


def main() -> None:
    raise RuntimeError(
        "Physical storage cleanup is disabled; no production Storage deleter is available"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
