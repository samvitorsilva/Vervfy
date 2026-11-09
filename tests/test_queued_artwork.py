"""Crash boundaries use real restricted PostgreSQL and synthetic Storage only."""

import io
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from unittest.mock import patch

import sqlalchemy as sa
import test_storage_writers as writers
from PIL import Image
from sqlalchemy.orm import undefer

import library
import storage_lifecycle
from db import TrackRecord, UploadJob
from scripts import upload_worker


class SimulatedCrash(BaseException):
    """Bypass application exception handling without killing a real process."""


class QueuedArtworkTests(unittest.TestCase):
    setUpClass = classmethod(writers.StorageWriterTests.setUpClass.__func__)
    setUp = writers.StorageWriterTests.setUp
    tx = writers.StorageWriterTests.tx
    session = writers.StorageWriterTests.session
    handle = writers.StorageWriterTests.handle
    wav = writers.StorageWriterTests.wav
    object = writers.StorageWriterTests.object
    stage = writers.StorageWriterTests.stage
    wait_blocked = writers.StorageWriterTests.wait_blocked

    def artwork(self, color=(40, 80, 160)):
        out = io.BytesIO()
        Image.new("RGB", (32, 32), color).save(out, "PNG")
        return out.getvalue()

    def queued(self):
        job_id, path, _data = self.stage()
        original = self.artwork()
        with self.session("a") as session:
            session.get(UploadJob, job_id).cover_data = original
            session.commit()
        return job_id, path, original

    def snapshot(self, job_id):
        with self.session("a") as session:
            job = session.scalar(
                sa.select(UploadJob)
                .options(undefer(UploadJob.cover_data))
                .where(UploadJob.id == job_id)
            )
            track = (
                session.get(TrackRecord, {"id": job.track_id, "user_id": "a"})
                if job.track_id
                else None
            )
            return {
                "status": job.status,
                "original": job.cover_data,
                "fence": job.processing_token,
                "error": job.error,
                "track_id": job.track_id,
                "path": track.cover_path if track else None,
                "version": track.media_version if track else None,
            }

    def completed_pending(self):
        job_id, staged, original = self.queued()
        with patch.object(upload_worker, "_complete_artwork", return_value=False):
            self.assertFalse(upload_worker.process(job_id, "a"))
        state = self.snapshot(job_id)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["original"], original)
        self.assertEqual(state["fence"], state["version"])
        return job_id, staged, original

    def assert_attached(self, job_id, expected):
        state = self.snapshot(job_id)
        self.assertIsNone(state["original"])
        self.assertIsNone(state["fence"])
        self.assertIsNone(state["error"])
        self.assertEqual(state["status"], "completed")
        self.assertEqual(
            self.objects["synthetic/" + state["path"]],
            upload_worker.uploaded_cover(expected),
        )
        obj = self.object(state["path"])
        self.assertTrue(obj.upload_verified)
        self.assertEqual(obj.state, "live")
        return state

    def test_crash_before_artwork_upload_preserves_original_and_completed_retry(self):
        job_id, staged, original = self.queued()
        with (
            patch.object(
                storage_lifecycle, "upload_bytes", side_effect=SimulatedCrash()
            ),
            self.assertRaises(SimulatedCrash),
        ):
            upload_worker.process(job_id, "a")
        state = self.snapshot(job_id)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["original"], original)
        self.assertEqual(state["fence"], state["version"])
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)
        self.assertIn("synthetic/" + staged, self.objects)

    def test_crash_after_upload_before_attachment_keeps_both_copies(self):
        job_id, _staged, original = self.completed_pending()
        upload = storage_lifecycle.upload_bytes
        candidates = []

        def interrupted(*args, **kwargs):
            path = upload(*args, **kwargs)
            candidates.append(path)
            raise SimulatedCrash()

        with (
            patch.object(storage_lifecycle, "upload_bytes", side_effect=interrupted),
            self.assertRaises(SimulatedCrash),
        ):
            upload_worker.process(job_id, "a")
        self.assertEqual(self.snapshot(job_id)["original"], original)
        self.assertIn("synthetic/" + candidates[0], self.objects)
        with self.admin.connect() as connection:
            self.assertEqual(
                connection.execute(
                    sa.text(
                        "SELECT j.state FROM vervfy_storage.cleanup_jobs j JOIN vervfy_storage.objects o ON o.id=j.object_id WHERE o.path=:p"
                    ),
                    {"p": candidates[0]},
                ).scalar_one(),
                "held",
            )
        self.assertTrue(upload_worker.process(job_id, "a"))
        final = self.assert_attached(job_id, original)
        self.assertNotEqual(final["path"], candidates[0])
        self.assertIn("synthetic/" + candidates[0], self.objects)

    @contextmanager
    def crash_at_commit(self, tenant, job_id, event):
        with self.session(tenant) as session:

            @sa.event.listens_for(session, event)
            def crash(current):
                for row in current.identity_map.values():
                    if (
                        isinstance(row, UploadJob)
                        and row.id == job_id
                        and row.__dict__.get("cover_data", "unloaded") is None
                        and row.processing_token is None
                    ):
                        raise SimulatedCrash()

            yield session

    def test_crash_after_attachment_flush_before_commit_rolls_back_source_clear(self):
        job_id, _staged, original = self.completed_pending()

        def factory(tenant):
            return self.crash_at_commit(tenant, job_id, "before_commit")

        with (
            patch.object(upload_worker, "tenant_session", factory),
            self.assertRaises(SimulatedCrash),
        ):
            upload_worker.process(job_id, "a")
        state = self.snapshot(job_id)
        self.assertEqual(state["original"], original)
        self.assertIsNone(state["path"])
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)

    def test_crash_after_attachment_commit_before_ack_is_idempotent(self):
        job_id, _staged, original = self.completed_pending()

        def factory(tenant):
            return self.crash_at_commit(tenant, job_id, "after_commit")

        with (
            patch.object(upload_worker, "tenant_session", factory),
            self.assertRaises(SimulatedCrash),
        ):
            upload_worker.process(job_id, "a")
        state = self.assert_attached(job_id, original)
        count = len(self.requests)
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assertEqual(self.snapshot(job_id)["path"], state["path"])
        self.assertEqual(len(self.requests), count)

    def test_completed_job_retry_uploads_only_pending_artwork(self):
        job_id, staged, original = self.completed_pending()
        audio_posts = [
            r for r in self.requests if r.method == "POST" and "/audio/" in r.url.path
        ]
        self.assertEqual(len(audio_posts), 1)
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)
        self.assertEqual(
            len(
                [
                    r
                    for r in self.requests
                    if r.method == "POST" and "/audio/" in r.url.path
                ]
            ),
            1,
        )
        self.assertIn("synthetic/" + staged, self.objects)

    def test_duplicate_artwork_workers_attach_once_and_hold_unused_candidate(self):
        job_id, _staged, original = self.completed_pending()
        uploaded = threading.Event()
        release = threading.Event()
        first_thread = []
        candidates = []
        upload = storage_lifecycle.upload_bytes

        def paused_upload(*args, **kwargs):
            path = upload(*args, **kwargs)
            candidates.append(path)
            if threading.get_ident() == first_thread[0]:
                uploaded.set()
                self.assertTrue(release.wait(10))
            return path

        def first():
            first_thread.append(threading.get_ident())
            return upload_worker.process(job_id, "a")

        with (
            patch.object(storage_lifecycle, "upload_bytes", side_effect=paused_upload),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            pending = pool.submit(first)
            self.assertTrue(uploaded.wait(10))
            try:
                self.assertTrue(upload_worker.process(job_id, "a"))
                winner = self.assert_attached(job_id, original)
            finally:
                release.set()
            self.assertTrue(pending.result(timeout=15))
        final = self.assert_attached(job_id, original)
        self.assertEqual(final["path"], winner["path"])
        self.assertEqual(final["version"], winner["version"])
        self.assertEqual(len(candidates), 2)
        unused = next(path for path in candidates if path != final["path"])
        self.assertIn("synthetic/" + unused, self.objects)
        with self.admin.connect() as connection:
            self.assertEqual(
                connection.execute(
                    sa.text(
                        "SELECT j.state FROM vervfy_storage.cleanup_jobs j JOIN vervfy_storage.objects o ON o.id=j.object_id WHERE o.path=:p"
                    ),
                    {"p": unused},
                ).scalar_one(),
                "held",
            )

    def test_stale_completed_job_cannot_overwrite_newer_user_artwork(self):
        job_id, _staged, original = self.completed_pending()
        before = self.snapshot(job_id)
        newer = self.artwork((160, 40, 80))
        library.Library("a").set_user_cover(before["track_id"], newer)
        current = self.snapshot(job_id)
        count = len(self.requests)
        self.assertTrue(upload_worker.process(job_id, "a"))
        final = self.snapshot(job_id)
        self.assertEqual(final["original"], original)
        self.assertEqual(final["path"], current["path"])
        self.assertEqual(final["version"], current["version"])
        self.assertEqual(len(self.requests), count)
        self.assertIn("held", final["error"])

    def test_database_attachment_failure_does_not_consume_source(self):
        job_id, _staged, original = self.completed_pending()

        def reject(_connection, _cursor, statement, _parameters, _context, _many):
            if statement.startswith("UPDATE tracks SET"):
                raise RuntimeError("Synthetic attachment failure")

        sa.event.listen(self.engines["app_runtime"], "before_cursor_execute", reject)
        try:
            self.assertFalse(upload_worker.process(job_id, "a"))
        finally:
            sa.event.remove(
                self.engines["app_runtime"], "before_cursor_execute", reject
            )
        self.assertEqual(self.snapshot(job_id)["original"], original)
        self.assertIsNone(self.snapshot(job_id)["path"])
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)

    def test_ambiguous_upload_failure_retains_original_for_retry(self):
        job_id, _staged, original = self.completed_pending()
        self.fault = "after_store"
        self.assertFalse(upload_worker.process(job_id, "a"))
        self.assertEqual(self.snapshot(job_id)["original"], original)
        self.fault = None
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)

    def test_unknown_legacy_fence_is_held_and_cross_account_retry_has_no_authority(
        self,
    ):
        job_id, _staged, original = self.completed_pending()
        count = len(self.requests)
        self.assertTrue(upload_worker.process(job_id, "b"))
        self.assertEqual(self.snapshot(job_id)["original"], original)
        with self.session("a") as session:
            session.get(UploadJob, job_id).processing_token = None
            session.commit()
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assertEqual(self.snapshot(job_id)["original"], original)
        self.assertIsNone(self.snapshot(job_id)["path"])
        self.assertEqual(len(self.requests), count)

    def test_invalid_artwork_is_held_without_storage_io(self):
        job_id, _staged, _original = self.completed_pending()
        with self.session("a") as session:
            session.get(UploadJob, job_id).cover_data = b"synthetic invalid artwork"
            session.commit()
        count = len(self.requests)
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assertEqual(
            self.snapshot(job_id)["original"], b"synthetic invalid artwork"
        )
        self.assertEqual(len(self.requests), count)

    def test_duplicate_track_keeps_existing_artwork_and_original_sidecar(self):
        source = self.wav()
        existing = library.Library("a").add_upload_file("duplicate.wav", source)
        newer = self.artwork((80, 160, 40))
        library.Library("a").set_user_cover(existing.id, newer)
        import uuid

        import server

        job_id = uuid.uuid4().hex
        with patch.object(server.upload_queue, "enqueue"):
            server._queue_staged_upload(job_id, "a", "duplicate.wav", source)
        original = self.artwork()
        with self.session("a") as session:
            session.get(UploadJob, job_id).cover_data = original
            session.commit()
        self.assertTrue(upload_worker.process(job_id, "a"))
        state = self.snapshot(job_id)
        self.assertEqual(state["original"], original)
        self.assertEqual(self.objects["synthetic/" + state["path"]], newer)
        self.assertIsNone(state["fence"])

    def test_retryable_or_stale_delivery_does_not_acknowledge_the_lease(self):
        for done in (False, True):
            with (
                self.subTest(done=done),
                patch.object(
                    upload_worker.upload_queue,
                    "dequeue",
                    side_effect=[("synthetic-job", "a"), SimulatedCrash()],
                ),
                patch.object(
                    upload_worker.upload_queue, "keep_lease", return_value=nullcontext()
                ),
                patch.object(upload_worker, "process", return_value=done),
                patch.object(upload_worker.upload_queue, "acknowledge") as acknowledge,
                self.assertRaises(SimulatedCrash),
            ):
                upload_worker.main()
            if done:
                acknowledge.assert_called_once_with("synthetic-job", "a")
            else:
                acknowledge.assert_not_called()

    def test_stale_audio_attempt_leaves_winners_lease_unacknowledged(self):
        job_id, _staged, _original = self.queued()
        with patch.object(
            library.Library,
            "add_upload_file",
            side_effect=library.StaleUploadOperation("synthetic stale attempt"),
        ):
            self.assertFalse(upload_worker.process(job_id, "a"))
        state = self.snapshot(job_id)
        self.assertIsNotNone(state["original"])
        self.assertEqual(state["status"], "processing")

    def test_real_redis_expired_lease_redelivers_completed_artwork_after_crash(self):
        import shutil
        import subprocess
        import tempfile
        import time
        from pathlib import Path

        import redis

        if not shutil.which("redis-server"):
            self.fail(
                "Disposable redis-server is required for crash recovery verification"
            )
        job_id, _staged, original = self.completed_pending()
        with tempfile.TemporaryDirectory(prefix="vervfy-artwork-redis-") as directory:
            socket = str(Path(directory) / "redis.sock")
            process = subprocess.Popen(
                [
                    shutil.which("redis-server"),
                    "--port",
                    "0",
                    "--unixsocket",
                    socket,
                    "--unixsocketperm",
                    "700",
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                    "--dir",
                    directory,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            client = redis.Redis(unix_socket_path=socket, decode_responses=True)
            try:
                deadline = time.monotonic() + 5
                while True:
                    try:
                        client.ping()
                        break
                    except redis.RedisError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("Disposable Redis did not start")
                        time.sleep(0.01)

                def factory():
                    return redis.Redis(unix_socket_path=socket, decode_responses=True)

                queue_api = upload_worker.upload_queue
                with (
                    patch.object(queue_api, "client", side_effect=factory),
                    patch.object(queue_api.time, "time", return_value=1000),
                ):
                    queue_api.enqueue(job_id, "a")
                    self.assertEqual(queue_api.dequeue(timeout=0), (job_id, "a"))
                    with (
                        patch.object(
                            storage_lifecycle,
                            "upload_bytes",
                            side_effect=SimulatedCrash(),
                        ),
                        self.assertRaises(SimulatedCrash),
                    ):
                        upload_worker.process(job_id, "a")
                    self.assertEqual(client.zcard(queue_api.LEASE_KEY), 1)
                    self.assertEqual(self.snapshot(job_id)["original"], original)
                with (
                    patch.object(queue_api, "client", side_effect=factory),
                    patch.object(
                        queue_api.time,
                        "time",
                        return_value=1000 + queue_api.LEASE_SECONDS + 1,
                    ),
                ):
                    self.assertEqual(queue_api.dequeue(timeout=0), (job_id, "a"))
                    self.assertTrue(upload_worker.process(job_id, "a"))
                    queue_api.acknowledge(job_id, "a")
                    self.assertEqual(client.zcard(queue_api.LEASE_KEY), 0)
                    self.assert_attached(job_id, original)
            finally:
                client.close()
                process.terminate()
                process.wait(timeout=5)

    def test_superseded_attempt_that_fails_does_not_acknowledge_active_winner(self):
        import uuid

        job_id, _staged, original = self.queued()
        replacement = uuid.uuid4()

        def superseded(*_args, **_kwargs):
            with self.session("a") as session:
                job = session.get(UploadJob, job_id)
                job.processing_token = replacement
                session.commit()
            raise RuntimeError("Synthetic failed superseded attempt")

        with patch.object(library.Library, "add_upload_file", side_effect=superseded):
            self.assertFalse(upload_worker.process(job_id, "a"))
        state = self.snapshot(job_id)
        self.assertEqual(state["fence"], replacement)
        self.assertEqual(state["original"], original)
        self.assertEqual(state["status"], "processing")
