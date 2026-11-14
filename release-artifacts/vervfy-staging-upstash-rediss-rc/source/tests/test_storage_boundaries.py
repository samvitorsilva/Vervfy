"""Deterministic transfer deadlines, brief SQL locking, and writer inventory."""

import ast
import asyncio
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
import sqlalchemy as sa
import test_queued_artwork as artwork_tests

import audio_store
import library
import storage_lifecycle as lifecycle
from db import TrackRecord, UploadJob, User
from scripts import upload_worker


class StorageBoundaryTests(unittest.TestCase):
    setUpClass = classmethod(artwork_tests.QueuedArtworkTests.setUpClass.__func__)
    setUp = artwork_tests.QueuedArtworkTests.setUp
    tx = artwork_tests.QueuedArtworkTests.tx
    session = artwork_tests.QueuedArtworkTests.session
    handle = artwork_tests.QueuedArtworkTests.handle
    wav = artwork_tests.QueuedArtworkTests.wav
    object = artwork_tests.QueuedArtworkTests.object
    stage = artwork_tests.QueuedArtworkTests.stage
    artwork = artwork_tests.QueuedArtworkTests.artwork
    queued = artwork_tests.QueuedArtworkTests.queued
    completed_pending = artwork_tests.QueuedArtworkTests.completed_pending
    snapshot = artwork_tests.QueuedArtworkTests.snapshot
    assert_attached = artwork_tests.QueuedArtworkTests.assert_attached

    def paused_artwork(self, action):
        job_id, _staged, original = self.completed_pending()
        waiting = threading.Event()
        release = threading.Event()
        first = []
        upload = lifecycle.upload_bytes

        def paused(*args, **kwargs):
            path = upload(*args, **kwargs)
            if threading.get_ident() == first[0]:
                waiting.set()
                self.assertTrue(release.wait(10))
            return path

        def worker():
            first.append(threading.get_ident())
            return upload_worker.process(job_id, "a")

        with (
            patch.object(lifecycle, "upload_bytes", side_effect=paused),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            pending = pool.submit(worker)
            self.assertTrue(waiting.wait(10))
            try:
                action(job_id, original)
            finally:
                release.set()
            self.assertTrue(pending.result(timeout=15))
        return job_id, original

    def test_user_job_and_track_rows_are_not_locked_during_artwork_io(self):
        def inspect(job_id, _original):
            state = self.snapshot(job_id)
            with self.session("a") as session:
                self.assertIsNotNone(
                    session.get(User, "a", with_for_update={"nowait": True})
                )
                self.assertIsNotNone(
                    session.get(UploadJob, job_id, with_for_update={"nowait": True})
                )
                self.assertIsNotNone(
                    session.get(
                        TrackRecord,
                        {"id": state["track_id"], "user_id": "a"},
                        with_for_update={"nowait": True},
                    )
                )

        job_id, original = self.paused_artwork(inspect)
        self.assert_attached(job_id, original)

    def test_new_user_cover_can_commit_during_io_and_stale_candidate_is_held(self):
        newer = self.artwork((180, 40, 20))
        winner = []

        def replace(job_id, _original):
            state = self.snapshot(job_id)
            self.assertIsNotNone(
                library.Library("a").set_user_cover(state["track_id"], newer)
            )
            winner.append(self.snapshot(job_id)["path"])

        job_id, original = self.paused_artwork(replace)
        state = self.snapshot(job_id)
        self.assertEqual(state["path"], winner[0])
        self.assertEqual(self.objects["synthetic/" + state["path"]], newer)
        self.assertEqual(state["original"], original)
        self.assertIn("held", state["error"])

    def test_storage_network_has_no_idle_sql_transaction(self):
        seen = []
        original = self.handle

        def handle(request):
            with self.admin.connect() as connection:
                states = (
                    connection.exec_driver_sql(
                        "SELECT state FROM pg_stat_activity WHERE usename='app_runtime' AND pid<>pg_backend_pid()"
                    )
                    .scalars()
                    .all()
                )
            self.assertNotIn("idle in transaction", states)
            seen.append(request.method)
            return original(request)

        with patch.object(audio_store, "_transport", httpx.MockTransport(handle)):
            lifecycle.upload_bytes("a", "track-cover", self.artwork())
        self.assertEqual(seen, ["POST", "GET"])

    def test_overall_timeout_holds_upload_and_retry_uses_fresh_identity(self):
        allocated = []
        reserve = lifecycle._reserve

        def capture(*args):
            obj = reserve(*args)
            allocated.append(obj)
            return obj

        with (
            patch.object(lifecycle, "_reserve", side_effect=capture),
            patch.object(lifecycle, "NETWORK_DEADLINE_SECONDS", 0),
            self.assertRaisesRegex(audio_store.StorageError, "deadline"),
        ):
            lifecycle.upload_bytes("a", "track-cover", self.artwork())
        row = self.object(allocated[0].path)
        self.assertEqual(row.state, "hold")
        self.assertFalse(row.upload_verified)
        retried = lifecycle.upload_bytes("a", "track-cover", self.artwork())
        self.assertNotEqual(retried, allocated[0].path)

    def test_absolute_deadline_cancels_trickle_verification_and_preserves_original(
        self,
    ):
        job_id, _staged, original = self.completed_pending()
        timeouts = []
        real_timeout = asyncio.timeout
        closed = []

        def controlled(seconds):
            context = real_timeout(
                None if seconds == lifecycle.NETWORK_DEADLINE_SECONDS else seconds
            )
            if seconds == lifecycle.NETWORK_DEADLINE_SECONDS:
                timeouts.append(context)
            return context

        class Trickle(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"x"
                timeouts[0].reschedule(asyncio.get_running_loop().time())
                await asyncio.Event().wait()

            async def aclose(self):
                closed.append(True)

        handler = self.handle

        def trickle(request):
            response = handler(request)
            return (
                httpx.Response(200, stream=Trickle())
                if request.method == "GET"
                else response
            )

        with (
            patch.object(audio_store, "_transport", httpx.MockTransport(trickle)),
            patch.object(lifecycle.asyncio, "timeout", side_effect=controlled),
        ):
            self.assertFalse(upload_worker.process(job_id, "a"))
        self.assertTrue(closed)
        self.assertTrue(timeouts[0].expired())
        self.assertEqual(self.snapshot(job_id)["original"], original)
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)

    def test_sql_lock_wait_is_bounded_and_original_remains_retryable(self):
        job_id, _staged, original = self.completed_pending()
        state = self.snapshot(job_id)
        with self.session("a") as blocker:
            blocker.get(
                TrackRecord,
                {"id": state["track_id"], "user_id": "a"},
                with_for_update=True,
            )
            with patch.object(lifecycle, "LOCK_TIMEOUT_MS", 1):
                self.assertFalse(upload_worker.process(job_id, "a"))
            self.assertEqual(self.snapshot(job_id)["original"], original)
        self.assertTrue(upload_worker.process(job_id, "a"))
        self.assert_attached(job_id, original)

    def test_client_timeout_bounds_and_configuration_capture(self):
        binding = lifecycle.configured_binding()
        client = lifecycle._client(binding)
        self.assertEqual(
            (
                client.timeout.connect,
                client.timeout.read,
                client.timeout.write,
                client.timeout.pool,
            ),
            (5, 10, 10, 5),
        )
        asyncio.run(client.aclose())
        self.assertEqual(lifecycle.NETWORK_DEADLINE_SECONDS, 60)
        self.assertEqual(lifecycle.CLOSE_DEADLINE_SECONDS, 5)
        self.assertLess(lifecycle.LOCK_TIMEOUT_MS, lifecycle.STATEMENT_TIMEOUT_MS)

    def test_all_runtime_storage_writers_use_guarded_boundary_and_maintenance_is_retired(
        self,
    ):
        root = Path(__file__).resolve().parents[1]
        active = (
            "library.py",
            "server.py",
            "scripts/upload_worker.py",
            "cover_art.py",
            "auth.py",
            "artist_images.py",
        )
        for rel in active:
            tree = ast.parse((root / rel).read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "audio_store"
                ):
                    self.assertNotIn(
                        node.func.attr,
                        {
                            "upload",
                            "upload_file",
                            "delete",
                            "delete_many",
                            "delete_quietly",
                        },
                        rel,
                    )
        self.assertIsInstance(
            ast.parse((root / "migrate.py").read_text()).body[0], ast.Raise
        )
        for rel in (
            "scripts/migrate_audio_to_storage.py",
            "scripts/move_audio_to_storage.py",
            "scripts/backfill_cover_storage.py",
            "scripts/backfill_covers.py",
            "scripts/rebuild_covers.py",
            "scripts/migrate_local_data.py",
        ):
            main = next(
                n
                for n in ast.parse((root / rel).read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "main"
            )
            self.assertIsInstance(main.body[0], ast.Raise, rel)

    def test_all_cover_writers_release_sql_transactions_before_storage_io(self):
        from PIL import Image

        original = self.handle
        posts = []

        def inspect(request):
            if request.method == "POST":
                with self.admin.connect() as connection:
                    states = (
                        connection.exec_driver_sql(
                            "SELECT state FROM pg_stat_activity WHERE usename='app_runtime'"
                        )
                        .scalars()
                        .all()
                    )
                self.assertNotIn("idle in transaction", states)
                posts.append(request.url.path)
            return original(request)

        for kind in ("track", "album", "resolved", "restore"):
            with self.subTest(kind=kind):
                source = self.wav()
                lib = library.Library("a")
                track = lib.add_upload_file(Path(source).name, source)
                lib.update_metadata(
                    track.id, track.title, track.artist, "synthetic-" + kind
                )
                with patch.object(
                    audio_store, "_transport", httpx.MockTransport(inspect)
                ):
                    if kind == "track":
                        self.assertIsNotNone(
                            lib.set_user_cover(track.id, self.artwork())
                        )
                    elif kind == "album":
                        self.assertEqual(
                            lib.set_album_user_cover(track.id, self.artwork()), 1
                        )
                    elif kind == "resolved":
                        self.assertTrue(
                            lib.set_resolved_cover(track.id, "embedded", self.artwork())
                        )
                    else:
                        with (
                            patch.object(
                                lib,
                                "audio_bytes",
                                return_value=(
                                    Path(source).read_bytes(),
                                    "synthetic.wav",
                                ),
                            ),
                            patch.object(
                                library,
                                "_extract_cover",
                                return_value=Image.new("RGB", (8, 8)),
                            ),
                        ):
                            self.assertIsNotNone(lib.remove_user_cover(track.id))
        self.assertEqual(len(posts), 4)

    def test_sql_limits_are_local_and_source_pin_has_idle_ceiling(self):
        with self.session("a") as session:
            lifecycle.bound_transaction(session)
            limits = session.execute(
                sa.text(
                    "SELECT extract(epoch from current_setting('lock_timeout')::interval), extract(epoch from current_setting('statement_timeout')::interval), extract(epoch from current_setting('idle_in_transaction_session_timeout')::interval)"
                )
            ).one()
            self.assertEqual(tuple(limits), (1, 5, 70))
        with self.session("a") as session:
            self.assertEqual(
                session.execute(
                    sa.text(
                        "SELECT current_setting('idle_in_transaction_session_timeout')"
                    )
                ).scalar_one(),
                "0",
            )

    def test_redis_client_rejects_unbounded_url_options_before_any_connection(self):
        import os

        import upload_queue

        with patch.dict(
            os.environ, {"REDIS_URL": "redis://synthetic.example.test:6379/0"}
        ):
            client = upload_queue.client()
            try:
                options = client.connection_pool.connection_kwargs
                self.assertEqual(options["socket_connect_timeout"], 5)
                self.assertEqual(options["socket_timeout"], 5)
                self.assertEqual(options["retry"].get_retries(), 0)
            finally:
                client.close()
        for option in (
            "socket_timeout=0",
            "socket_connect_timeout=0",
            "socket_timeout=99",
        ):
            with (
                self.subTest(option=option),
                patch.dict(
                    os.environ,
                    {"REDIS_URL": "redis://synthetic.example.test:6379/0?" + option},
                ),
                self.assertRaisesRegex(RuntimeError, "bounded"),
            ):
                upload_queue.client()
