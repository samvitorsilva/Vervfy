"""Fenced cleanup processing with a disabled-by-default worker entry point."""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass
from threading import Event
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
        """Confirm exact-key removal or provider-confirmed idempotent absence."""


@dataclass(frozen=True)
class CleanupClaim:
    object_id: str
    path: str
    token: str


class CleanupWorker:
    def __init__(
        self,
        sessions,
        binding: NamespaceBinding,
        storage: IdempotentStorage,
        *,
        require_enabled: bool = False,
    ):
        if storage is None:
            raise ValueError("An explicit cleanup storage adapter is required")
        self.sessions = sessions
        self.binding = binding
        self.storage = storage
        self.require_enabled = require_enabled

    def _claim(self) -> CleanupClaim | None:
        with self.sessions.begin() as session:
            if session.bind.dialect.name != "postgresql":
                raise audio_store.StorageError(
                    "Storage cleanup requires PostgreSQL lifecycle guards"
                )
            storage_lifecycle.validate_local_session(session)
            storage_lifecycle.bound_transaction(session)
            if self.require_enabled and not session.execute(
                text("SELECT vervfy_storage.cleanup_enabled()")
            ).scalar_one():
                return None
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
    enabled = os.environ.get("VERVFY_STORAGE_CLEANUP_ENABLED", "0").strip()
    if enabled not in {"0", "1"}:
        raise RuntimeError("VERVFY_STORAGE_CLEANUP_ENABLED must be 0 or 1")
    if enabled != "1":
        raise RuntimeError("Physical storage cleanup is disabled")

    from sqlalchemy.engine import make_url

    database_url = os.environ.get("DATABASE_URL", "").strip()
    try:
        parsed = make_url(database_url)
    except (TypeError, ValueError):
        raise RuntimeError("Cleanup worker DATABASE_URL is invalid") from None
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.username != "storage_cleanup_worker"
    ):
        raise RuntimeError(
            "Cleanup worker requires the restricted storage_cleanup_worker database role"
        )

    import storage_lifecycle
    from db import SessionLocal, engine
    from supabase_cleanup import SupabaseCleanupStorage

    binding = storage_lifecycle.configured_binding()
    adapter = SupabaseCleanupStorage(binding)
    with engine.connect() as connection:
        if not connection.execute(
            text("SELECT vervfy_storage.cleanup_enabled()")
        ).scalar_one():
            raise RuntimeError(
                "The database hard-disables physical cleanup; reviewed activation is required"
            )

    worker = CleanupWorker(
        SessionLocal, binding, adapter, require_enabled=True
    )
    stopping = Event()
    previous_handlers = {}

    def request_shutdown(signum, _frame):
        log.info("Cleanup worker received shutdown signal %s", signum)
        stopping.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, request_shutdown)

    processed = 0
    failures = 0
    last_heartbeat = time.monotonic()
    log.info("Storage cleanup worker started with serial bounded processing")
    try:
        while not stopping.is_set():
            try:
                did_work = worker.run_once()
                if did_work:
                    processed += 1
                    failures = 0
                else:
                    stopping.wait(1)
            except Exception as exc:
                failures += 1
                log.error("Cleanup cycle failed (%s)", type(exc).__name__)
                stopping.wait(min(30, 2 ** min(failures, 5)))
            now = time.monotonic()
            if now - last_heartbeat >= 60:
                log.info(
                    "Storage cleanup worker heartbeat processed=%d failures=%d",
                    processed,
                    failures,
                )
                last_heartbeat = now
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        engine.dispose()
        log.info("Storage cleanup worker stopped processed=%d failures=%d", processed, failures)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
