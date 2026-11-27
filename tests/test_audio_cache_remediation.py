from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import uuid

import pytest

import audio_cache_remediation as repair
import audio_store
import storage_lifecycle


@pytest.fixture
def source(monkeypatch):
    monkeypatch.setenv("VERVFY_ENVIRONMENT", "test")
    monkeypatch.setenv("VERVFY_AUDIO_SECURITY_HARDENING", "1")
    monkeypatch.setenv("VERVFY_STORAGE_WRITES_PAUSED", "0")
    row = SimpleNamespace(storage_path="user/old.wav", media_version=uuid.uuid4(), size_bytes=3, filename="sample.wav")
    binding = SimpleNamespace(namespace_id=uuid.uuid4(), environment="test")
    monkeypatch.setattr(repair, "_snapshot", lambda *_: (row, binding))
    monkeypatch.setattr(repair, "_check_attachment_connection", lambda *_: None)
    monkeypatch.setattr(storage_lifecycle, "_binding", lambda *_: binding)
    monkeypatch.setattr(audio_store, "object_size", lambda _: 3)
    def download(_path, destination, size):
        assert size == 3
        with open(destination, "wb") as target:
            target.write(b"abc")
    monkeypatch.setattr(audio_store, "download_to_file", download)
    return row


def test_rehome_uses_verified_create_only_lifecycle_then_atomic_attachment(source):
    plan = repair.plan("user", "track")
    with patch.object(storage_lifecycle, "upload_file", return_value="v2/new/user/audio/object.wav") as upload, \
         patch.object(repair, "_attach_preserving_holds") as attach, \
         patch.object(audio_store, "delete") as delete:
        result = repair.apply(plan)
    assert len(result) == 64
    upload.assert_called_once()
    assert upload.call_args.args[0:2] == ("user", "audio")
    attach.assert_called_once()
    delete.assert_not_called()


def test_digest_change_aborts_before_reservation(source):
    plan = repair.plan("user", "track")
    plan["sha256"] = "0" * 64
    with patch.object(storage_lifecycle, "upload_file") as upload:
        with pytest.raises(audio_store.StorageError, match="digest"):
            repair.apply(plan)
        upload.assert_not_called()


def test_stale_plan_and_reference_drift_abort_before_upload(source):
    plan = repair.plan("user", "track")
    with patch.object(storage_lifecycle, "upload_file") as upload:
        with patch.object(repair.time, "time", return_value=plan["measured_at"] + 901):
            with pytest.raises(audio_store.StorageError, match="Fresh"):
                repair.apply(plan)
        source.media_version = uuid.uuid4()
        with pytest.raises(audio_store.StorageError, match="drifted"):
            repair.apply(plan)
        upload.assert_not_called()


def test_compare_and_swap_failure_preserves_reservation_without_refund_or_delete(source):
    plan = repair.plan("user", "track")
    with patch.object(storage_lifecycle, "upload_file", return_value="v2/new/user/audio/object.wav"), \
         patch.object(repair, "_attach_preserving_holds", side_effect=audio_store.StorageError("Attachment changed; new object remains charged for reconciliation")), \
         patch.object(audio_store, "delete") as delete:
        with pytest.raises(audio_store.StorageError, match="remains charged"):
            repair.apply(plan)
        delete.assert_not_called()


def test_quota_failure_never_changes_track_reference(source):
    plan = repair.plan("user", "track")
    with patch.object(storage_lifecycle, "upload_file", side_effect=storage_lifecycle.RetainedStorageQuotaExceeded("quota")), \
         patch.object(repair, "tenant_session") as session:
        with pytest.raises(storage_lifecycle.RetainedStorageQuotaExceeded):
            repair.apply(plan)
        session.assert_not_called()


def test_read_only_plan_allowed_while_writers_paused_but_apply_denied(source, monkeypatch):
    monkeypatch.setenv("VERVFY_STORAGE_WRITES_PAUSED", "1")
    plan = repair.plan("user", "track")
    with pytest.raises(storage_lifecycle.StorageWritersPaused):
        repair.apply(plan)


def test_attachment_requires_explicit_operator_and_rejects_runtime_privilege():
    with pytest.raises(audio_store.StorageError, match="Explicit staging operator"):
        repair._check_attachment_connection(None, object())
    connection = MagicMock()
    connection.in_transaction.return_value = True
    connection.execute.return_value.scalar_one.return_value = False
    with pytest.raises(audio_store.StorageError, match="runtime privileges must not be expanded"):
        repair._check_attachment_connection(connection, object())


def test_claimed_cleanup_aborts_before_track_update(source):
    connection = MagicMock()
    objects = MagicMock()
    objects.scalars.return_value.all.return_value = [uuid.uuid4()]
    jobs = MagicMock()
    jobs.mappings.return_value.all.return_value = [{"state": "claimed"}]
    connection.execute.side_effect = [MagicMock(), MagicMock(), MagicMock(), objects, jobs]
    with pytest.raises(audio_store.StorageError, match="separate review"):
        repair._attach_preserving_holds(connection, object(), "user", "track", source, "new-path")
    assert connection.execute.call_count == 5
