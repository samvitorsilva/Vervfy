import pytest

from scripts.storage_cleanup_worker import CleanupWorker


class NeverDeleteStorage:
    def __init__(self):
        self.calls = []

    def delete_if_present(self, path):
        self.calls.append(path)


def test_run_once_never_claims_or_deletes():
    storage = NeverDeleteStorage()

    worker = CleanupWorker(
        sessions=object(),
        binding=object(),
        storage=storage,
    )

    with pytest.raises(
        RuntimeError,
        match="Physical storage cleanup is disabled",
    ):
        worker.run_once()

    assert storage.calls == []
