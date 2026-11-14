"""Filesystem storage isolation tests; all bytes and database targets are synthetic."""

import hashlib
import os
import tempfile
import unittest
import uuid
import wave
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

import audio_store
import db
import library
import storage_lifecycle
from cover_art import generated_cover
from scripts import storage_cleanup_worker as cleanup_worker
from storage_adapters import (
    FilesystemStorageAdapter,
    LocalStorageConfigurationError,
    LocalStorageError,
    local_storage_selected,
    validate_local_configuration,
    validate_local_source,
)


def managed_path(kind="track-cover"):
    return (
        "v2/00000000-0000-0000-0000-000000000001/synthetic-user/"
        f"{kind}/00000000-0000-0000-0000-000000000002.jpg"
    )


class FilesystemAdapterTests(unittest.TestCase):
    def setUp(self):
        self.database = self.enterContext(
            tempfile.TemporaryDirectory(prefix="vervfy-storage-pg-")
        )
        self.storage = self.enterContext(
            tempfile.TemporaryDirectory(prefix="vervfy-storage-fs-")
        )
        self.environment = {
            "VERVFY_ENVIRONMENT": "local-test",
            "VERVFY_STORAGE_BACKEND": "filesystem",
            "VERVFY_LOCAL_STORAGE_ROOT": self.storage,
            "DATABASE_URL": str(
                sa.URL.create(
                    "postgresql+psycopg",
                    username="app_runtime",
                    database="postgres",
                    query={"host": self.database},
                )
            ),
        }
        self.enterContext(patch.dict(os.environ, self.environment, clear=True))
        self.adapter = FilesystemStorageAdapter.from_environment()

    def test_create_only_upload_download_and_range_round_trip(self):
        path = managed_path()
        data = b"synthetic immutable media"
        digest = hashlib.sha256(data).digest()
        repository = Path(__file__).resolve().parents[1]
        self.assertFalse(self.adapter.root.is_relative_to(repository))
        self.adapter.upload_file(path, BytesIO(data), len(data), digest)
        stored = Path(self.storage, *path.split("/"))
        self.assertEqual(stored.read_bytes(), data)
        self.assertEqual(self.adapter.read_range(path, 4, 11), data[4:12])
        self.assertEqual(self.adapter.object_size(path), len(data))

        with self.assertRaisesRegex(LocalStorageError, "already exists"):
            self.adapter.upload_file(path, BytesIO(b"replacement"), 11, hashlib.sha256(b"replacement").digest())
        self.assertEqual(stored.read_bytes(), data)

        destination = Path(self.storage).parent / (
            "vervfy-download-" + uuid.uuid4().hex
        )
        try:
            self.assertEqual(
                self.adapter.download_to_file(path, str(destination), len(data)),
                len(data),
            )
            self.assertEqual(destination.read_bytes(), data)
        finally:
            destination.unlink(missing_ok=True)

    def test_empty_object_download_uses_a_validated_destination(self):
        path = managed_path()
        self.adapter.upload_file(path, BytesIO(b""), 0, hashlib.sha256(b"").digest())
        destination = Path(self.storage).parent / (
            "vervfy-empty-download-" + uuid.uuid4().hex
        )
        try:
            self.assertEqual(self.adapter.download_to_file(path, str(destination), 0), 0)
            self.assertEqual(destination.read_bytes(), b"")
        finally:
            destination.unlink(missing_ok=True)

    def test_path_traversal_and_symlinked_directory_are_rejected(self):
        outside = Path(self.storage).parent / ("vervfy-outside-" + uuid.uuid4().hex)
        outside.mkdir(mode=0o700)
        try:
            with self.assertRaises(LocalStorageError):
                self.adapter.upload_file(
                    "../../" + outside.name + "/escape",
                    BytesIO(b"synthetic"),
                    9,
                    hashlib.sha256(b"synthetic").digest(),
                )

            os.symlink(outside, Path(self.storage) / "v2")
            with self.assertRaises(LocalStorageError):
                self.adapter.upload_file(
                    managed_path(),
                    BytesIO(b"synthetic"),
                    9,
                    hashlib.sha256(b"synthetic").digest(),
                )
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            if (Path(self.storage) / "v2").is_symlink():
                (Path(self.storage) / "v2").unlink()
            outside.rmdir()

    def test_download_refuses_a_destination_inside_the_object_root(self):
        path = managed_path()
        data = b"synthetic"
        self.adapter.upload_file(
            path, BytesIO(data), len(data), hashlib.sha256(data).digest()
        )
        stored = Path(self.storage, *path.split("/"))
        with self.assertRaises(LocalStorageError):
            self.adapter.download_to_file(path, str(stored), len(data))
        self.assertEqual(stored.read_bytes(), data)

    def test_download_rejects_a_symlinked_destination_directory(self):
        path = managed_path()
        data = b"synthetic"
        self.adapter.upload_file(
            path, BytesIO(data), len(data), hashlib.sha256(data).digest()
        )
        outside = Path(self.storage).parent / ("vervfy-download-outside-" + uuid.uuid4().hex)
        link = Path(self.storage).parent / ("vervfy-download-link-" + uuid.uuid4().hex)
        outside.mkdir(mode=0o700)
        try:
            os.symlink(outside, link)
            with self.assertRaises(LocalStorageError):
                self.adapter.download_to_file(
                    path, str(link / "escape"), len(data)
                )
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            link.unlink(missing_ok=True)
            outside.rmdir()

    def test_missing_object_cleanup_is_idempotent(self):
        self.adapter.delete_if_present(managed_path())

    def test_local_mode_rejects_production_endpoints_and_databases(self):
        with patch.dict(os.environ, {"SUPABASE_SERVICE_KEY": "synthetic-secret"}):
            with self.assertRaisesRegex(
                LocalStorageConfigurationError, "Supabase endpoints"
            ):
                validate_local_configuration()
        with patch.dict(
            os.environ, {"SUPABASE_URL": "https://project.supabase.co"}
        ):
            with self.assertRaisesRegex(
                LocalStorageConfigurationError, "Supabase endpoints"
            ):
                validate_local_configuration()

        remote = sa.URL.create(
            "postgresql+psycopg",
            username="app_runtime",
            password="synthetic",
            host="db.example.test",
            database="postgres",
        )
        with patch.dict(os.environ, {"DATABASE_URL": str(remote)}):
            with self.assertRaises(LocalStorageConfigurationError):
                validate_local_configuration()
            with self.assertRaises(LocalStorageConfigurationError):
                db.database_url()

        with patch.dict(
            os.environ,
            {"VERVFY_ENVIRONMENT": "production"},
        ):
            with self.assertRaises(LocalStorageConfigurationError):
                validate_local_configuration()

    def test_local_storage_root_symlink_and_non_tmp_upload_source_are_rejected(self):
        outside = Path(self.storage).parent / ("vervfy-root-target-" + uuid.uuid4().hex)
        outside.mkdir(mode=0o700)
        link = Path(self.storage).parent / ("vervfy-root-link-" + uuid.uuid4().hex)
        try:
            os.symlink(outside, link)
            with patch.dict(
                os.environ, {"VERVFY_LOCAL_STORAGE_ROOT": str(link)}
            ):
                with self.assertRaisesRegex(
                    LocalStorageConfigurationError, "must not be a symlink"
                ):
                    validate_local_configuration()
            with self.assertRaisesRegex(LocalStorageError, "must be under /tmp"):
                validate_local_source(__file__)
        finally:
            link.unlink(missing_ok=True)
            outside.rmdir()

    def test_local_test_requires_explicit_backend_selection(self):
        os.environ.pop("VERVFY_STORAGE_BACKEND")
        with self.assertRaisesRegex(
            LocalStorageConfigurationError, "requires VERVFY_STORAGE_BACKEND"
        ):
            local_storage_selected()


class FilesystemLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_storage_lifecycle import StorageLifecycleTests

        StorageLifecycleTests.setUpClass.__func__(cls)

    def setUp(self):
        self.files = self.enterContext(
            tempfile.TemporaryDirectory(prefix="vervfy-fs-input-")
        )
        self.storage = self.enterContext(
            tempfile.TemporaryDirectory(prefix="vervfy-fs-storage-")
        )
        self.environment = {
            "VERVFY_ENVIRONMENT": "local-test",
            "VERVFY_STORAGE_BACKEND": "filesystem",
            "VERVFY_LOCAL_STORAGE_ROOT": self.storage,
            "VERVFY_STORAGE_NAMESPACE_ID": str(self.binding.namespace_id),
            "DATABASE_URL": self.engines["app_runtime"].url.render_as_string(
                hide_password=False
            ),
        }
        self.enterContext(patch.dict(os.environ, self.environment, clear=True))
        for module in (library, storage_lifecycle):
            self.enterContext(
                patch.object(module, "tenant_session", self.session)
            )
        self.enterContext(patch.object(db, "tenant_session", self.session))
        requests = []

        def unexpected_request(request):
            requests.append(request)
            raise AssertionError("Local filesystem mode attempted network access")

        self.enterContext(
            patch.object(
                audio_store,
                "_transport",
                httpx.MockTransport(unexpected_request),
            )
        )
        self.requests = requests

    def test_local_upload_download_audio_and_artwork_need_no_supabase(self):
        media_path = storage_lifecycle.upload_bytes("a", "staged-audio", b"synthetic audio")
        destination = Path(self.files) / "downloaded.synthetic"
        with self.session("a") as session:
            count = storage_lifecycle.download_staged(
                session, media_path, str(destination), 64
            )
        self.assertEqual(count, len(b"synthetic audio"))
        self.assertEqual(destination.read_bytes(), b"synthetic audio")

        source = self.wav()
        track = library.Library("a").add_upload_file(
            Path(source).name, source
        )
        artwork = generated_cover("synthetic track")
        updated = library.Library("a").set_user_cover(track.id, artwork)
        self.assertIsNotNone(updated)
        info = library.Library("a").audio_info(track.id)
        cover_path = library.Library("a").get(track.id).cover_path
        storage_root = Path(self.storage)
        self.assertEqual(
            (storage_root / cover_path).read_bytes(),
            artwork,
        )
        self.assertEqual(
            audio_store.read_range(info.storage_path, 0, 15),
            Path(source).read_bytes()[:16],
        )
        with self.assertRaisesRegex(
            audio_store.StorageError, "do not have signed URLs"
        ):
            audio_store.create_signed_url(info.storage_path)
        self.assertEqual(self.requests, [])

    def test_interrupted_local_upload_is_held_and_retry_gets_a_new_identity(self):
        from storage_adapters import LocalStorageError

        original = FilesystemStorageAdapter.upload_file
        allocated = []
        reserve = storage_lifecycle._reserve

        def capture(*args):
            obj = reserve(*args)
            allocated.append(obj)
            return obj

        def interrupted(adapter, path, source, size, digest):
            original(adapter, path, source, size, digest)
            raise LocalStorageError("synthetic interrupted completion")

        with (
            patch.object(storage_lifecycle, "_reserve", side_effect=capture),
            patch.object(
                FilesystemStorageAdapter, "upload_file", new=interrupted
            ),
            self.assertRaises(audio_store.StorageError),
        ):
            storage_lifecycle.upload_bytes("a", "track-cover", b"synthetic artwork")

        failed = allocated[0]
        self.assertEqual(self.object(failed.path).state, "hold")
        self.assertEqual(
            (Path(self.storage) / failed.path).read_bytes(),
            b"synthetic artwork",
        )
        retry = storage_lifecycle.upload_bytes(
            "a", "track-cover", b"synthetic artwork"
        )
        self.assertNotEqual(retry, failed.path)
        self.assertEqual(self.requests, [])

    def test_zero_byte_download_cannot_truncate_a_managed_object(self):
        path = storage_lifecycle.upload_bytes(
            "a", "staged-audio", b"synthetic object contents"
        )
        stored = Path(self.storage) / path
        original = stored.read_bytes()

        with self.assertRaises(audio_store.StorageError):
            audio_store.download_to_file(path, str(stored), 0)

        self.assertEqual(stored.read_bytes(), original)
        self.assertEqual(self.requests, [])

    def test_reference_protection_and_cleanup_retry_stay_inside_local_root(self):
        from sqlalchemy.orm import sessionmaker

        path = storage_lifecycle.upload_bytes("a", "audio", b"synthetic cleanup media")
        track_id = self.attach_path(path)
        stored = Path(self.storage) / path
        self.assertTrue(stored.is_file())

        worker_sessions = sessionmaker(
            bind=self.engines["storage_cleanup_worker"],
            autoflush=False,
            expire_on_commit=False,
        )
        adapter = FilesystemStorageAdapter.from_environment()
        worker = cleanup_worker.CleanupWorker(
            worker_sessions, self.binding, adapter
        )
        obj = self.object(path)
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs
                SET state='pending',available_at=pg_catalog.clock_timestamp()
                WHERE object_id=:id
                """),
                {"id": obj.id},
            )
        self.assertFalse(worker.run_once())
        self.assertTrue(stored.is_file())

        with self.tx() as connection:
            connection.execute(
                sa.text("DELETE FROM tracks WHERE id=:id"), {"id": track_id}
            )
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs
                SET available_at=pg_catalog.clock_timestamp()
                WHERE object_id=:id
                """),
                {"id": obj.id},
            )

        class FailOnce:
            def delete_if_present(self, object_path):
                raise cleanup_worker.CleanupStorageFailure("storage_unavailable")

        retrying_worker = cleanup_worker.CleanupWorker(
            worker_sessions, self.binding, FailOnce()
        )
        self.assertTrue(retrying_worker.run_once())
        self.assertTrue(stored.is_file())
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs
                SET available_at=pg_catalog.clock_timestamp()
                WHERE object_id=:id
                """),
                {"id": obj.id},
            )
        self.assertTrue(worker.run_once())
        self.assertFalse(stored.exists())
        self.assertEqual(self.cleanup_state(obj.id), "done")

    @contextmanager
    def session(self, tenant):
        with Session(self.engines["app_runtime"], expire_on_commit=False) as session:
            @sa.event.listens_for(session, "after_begin")
            def set_context(_session, _transaction, connection):
                connection.execute(
                    sa.text(
                        "SELECT set_config('app.current_user_id',:tenant,true)"
                    ),
                    {"tenant": tenant},
                )

            yield session

    @contextmanager
    def tx(self, role="app_runtime", tenant="a"):
        with self.engines[role].begin() as connection:
            connection.execute(
                sa.text("SELECT set_config('app.current_user_id',:tenant,true)"),
                {"tenant": tenant},
            )
            yield connection

    def wav(self):
        path = Path(self.files) / (uuid.uuid4().hex + ".wav")
        with wave.open(str(path), "wb") as source:
            source.setnchannels(1)
            source.setsampwidth(2)
            source.setframerate(8000)
            source.writeframes(uuid.uuid4().bytes * 1000)
        return str(path)

    def object(self, path):
        with self.admin.connect() as connection:
            return connection.execute(
                sa.text("""
                SELECT id,state,classification,upload_verified
                FROM vervfy_storage.objects WHERE path=:path
                """),
                {"path": path},
            ).one()

    def attach(self, connection, path, tenant="a", ident=None):
        ident = ident or uuid.uuid4().hex
        connection.execute(
            sa.text("""
            INSERT INTO tracks
              (id,user_id,filename,title,artist,album,duration,has_cover,
               cover_source,storage_path)
            VALUES(:id,:tenant,'synthetic.wav','t','r','l',1,false,'generated',:path)
            """),
            {"id": ident, "tenant": tenant, "path": path},
        )
        return ident

    def attach_path(self, path):
        with self.tx() as connection:
            return self.attach(connection, path)

    def cleanup_state(self, object_id):
        with self.admin.connect() as connection:
            return connection.execute(
                sa.text("""
                SELECT state FROM vervfy_storage.cleanup_jobs
                WHERE object_id=:id
                """),
                {"id": object_id},
            ).scalar_one()
