"""Cleanup worker disabled until physical Storage deletion is reviewed."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

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
        """Return only after absence is confirmed."""


@dataclass(frozen=True)
class CleanupClaim:
    object_id: str
    path: str
    token: str


class CleanupWorker:
    def __init__(self, sessions, binding, storage: IdempotentStorage):
        if storage is None:
            raise ValueError("An explicit cleanup storage adapter is required")

        self.sessions = sessions
        self.binding = binding
        self.storage = storage

    def run_once(self) -> bool:
        raise RuntimeError(
            "Physical storage cleanup is disabled; "
            "no production Storage deleter is authorized"
        )


def main() -> None:
    raise RuntimeError(
        "Physical storage cleanup is disabled; "
        "no production Storage deleter is available"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
