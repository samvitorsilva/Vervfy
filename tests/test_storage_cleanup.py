"""Cleanup leases run only against disposable PostgreSQL and synthetic objects."""

import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import sqlalchemy as sa
import test_storage_writers as writers
from sqlalchemy.orm import sessionmaker

import server
from scripts import storage_cleanup_worker as cleanup


class SimulatedCleanupCrash(BaseException):
    pass


class SyntheticStorage:
    def __init__(self, objects):
        self.objects = objects
        self.calls = []
        self.lock = threading.Lock()

    def delete_if_present(self, path):
        with self.lock:
            self.calls.append(path)
            self.objects.pop("synthetic/" + path, None)


class StorageCleanupTests(unittest.TestCase):
    setUpClass = classmethod(writers.StorageWriterTests.setUpClass.__func__)
    tx = writers.StorageWriterTests.tx
    session = writers.StorageWriterTests.session
    handle = writers.StorageWriterTests.handle
    object = writers.StorageWriterTests.object
    attach = writers.StorageWriterTests.attach

    def setUp(self):
        writers.StorageWriterTests.setUp(self)
        self.worker_sessions = sessionmaker(
            bind=self.engines["storage_cleanup_worker"],
            autoflush=False,
            expire_on_commit=False,
        )
        self.synthetic = SyntheticStorage(self.objects)

    def worker(self, storage=None, binding=None):
        return cleanup.CleanupWorker(
            self.worker_sessions, binding or self.binding, storage or self.synthetic
        )

    def cleanup_row(self, path):
        obj = self.object(path)
        with self.admin.connect() as connection:
            return connection.execute(
                sa.text("""
                SELECT j.state AS job_state,j.attempts,j.available_at,
                       j.claim_token,j.lease_until,j.error_code,j.exhaustion_reason,
                       o.state AS object_state
                FROM vervfy_storage.cleanup_jobs AS j
                JOIN vervfy_storage.objects AS o ON o.id=j.object_id
                WHERE j.object_id=:id
                """),
                {"id": obj.id},
            ).one()

    def make_due(self, path, *, expire_lease=False):
        obj = self.object(path)
        with self.admin.begin() as connection:
            if expire_lease:
                connection.execute(
                    sa.text("""
                    UPDATE vervfy_storage.cleanup_jobs
                    SET lease_until=pg_catalog.clock_timestamp()-interval '1 second'
                    WHERE object_id=:id
                    """),
                    {"id": obj.id},
                )
            else:
                connection.execute(
                    sa.text("""
                    UPDATE vervfy_storage.cleanup_jobs
                    SET available_at=pg_catalog.clock_timestamp()
                    WHERE object_id=:id
                    """),
                    {"id": obj.id},
                )

    def isolate_claim(self, path):
        obj = self.object(path)
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs
                SET available_at=pg_catalog.clock_timestamp()+interval '1 day'
                WHERE state='pending' AND object_id<>:id
                """),
                {"id": obj.id},
            )
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs
                SET available_at=pg_catalog.clock_timestamp()
                WHERE object_id=:id
                """),
                {"id": obj.id},
            )

    def managed(self, tenant="a", kind="audio", content=b"synthetic object"):
        import storage_lifecycle

        return storage_lifecycle.upload_bytes(tenant, kind, content)

    def orphan(self, tenant="a", kind="audio", content=b"synthetic object"):
        path = self.managed(tenant, kind, content)
        with self.tx(tenant=tenant) as connection:
            track = self.attach(connection, path, tenant=tenant)
            connection.execute(
                sa.text("DELETE FROM tracks WHERE id=:id"), {"id": track}
            )
        return path

    def test_unattached_reservation_remains_held(self):
        path = self.managed()
        self.assertFalse(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual((state.job_state, state.object_state), ("held", "ready"))
        self.assertIn("synthetic/" + path, self.objects)

    def test_namespace_mismatch_rolls_back_claim_before_adapter_call(self):
        import storage_lifecycle
        from storage_namespace import NamespaceBinding

        path = self.orphan()
        binding = storage_lifecycle.configured_binding()
        wrong = NamespaceBinding(
            uuid.uuid4(), binding.environment, binding.endpoint, binding.bucket
        )
        with self.assertRaises(sa.exc.DBAPIError):
            self.worker(binding=wrong).run_once()
        self.assertEqual(self.synthetic.calls, [])
        state = self.cleanup_row(path)
        self.assertEqual((state.job_state, state.object_state), ("pending", "live"))

    def test_shared_object_is_not_claimed_until_every_global_reference_is_gone(self):
        path = self.managed()
        with self.tx() as connection:
            first = self.attach(connection, path)
            second = self.attach(connection, path)

        worker = self.worker()
        with self.tx() as connection:
            connection.execute(
                sa.text("DELETE FROM tracks WHERE id=:id"), {"id": first}
            )
        self.assertFalse(worker.run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.error_code, state.object_state),
            ("pending", "referenced", "live"),
        )
        self.assertIn("synthetic/" + path, self.objects)

        with self.tx() as connection:
            connection.execute(
                sa.text("DELETE FROM tracks WHERE id=:id"), {"id": second}
            )
        self.make_due(path)
        self.assertTrue(worker.run_once())
        self.assertNotIn("synthetic/" + path, self.objects)
        self.assertEqual(self.cleanup_row(path).job_state, "done")

    def test_worker_checks_track_cover_artist_photo_and_upload_job_references(self):
        audio = self.managed(kind="audio", content=b"audio")
        cover = self.managed(kind="track-cover", content=b"cover")
        photo = self.managed(kind="artist-photo", content=b"photo")
        staged = self.managed(kind="staged-audio", content=b"staged")
        with self.tx() as connection:
            track = self.attach(connection, audio)
            connection.execute(
                sa.text("UPDATE tracks SET cover_path=:path WHERE id=:id"),
                {"path": cover, "id": track},
            )
            connection.execute(
                sa.text("""
                INSERT INTO artist_photos(user_id,normalized_artist_name,storage_path,source)
                VALUES('a','cleanup-reference-test',:path,'user')
                """),
                {"path": photo},
            )
            connection.execute(
                sa.text("""
                INSERT INTO upload_jobs(id,user_id,filename,storage_path,status,created_at)
                VALUES(:id,'a','synthetic.wav',:path,'processing',1)
                """),
                {"id": uuid.uuid4().hex, "path": staged},
            )
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs
                SET state='pending',available_at=pg_catalog.clock_timestamp()
                WHERE object_id IN (
                    SELECT id FROM vervfy_storage.objects
                    WHERE path IN (:audio,:cover,:photo,:staged)
                )
                """),
                {"audio": audio, "cover": cover, "photo": photo, "staged": staged},
            )

        worker = self.worker()
        self.assertFalse(worker.run_once())
        self.assertEqual(
            self.synthetic.calls,
            [],
        )
        for path in (audio, cover, photo, staged):
            state = self.cleanup_row(path)
            self.assertEqual(
                (state.job_state, state.error_code, state.object_state),
                ("pending", "referenced", "live"),
            )
            self.assertIn("synthetic/" + path, self.objects)

    def test_only_one_worker_claims_a_live_lease(self):
        path = self.orphan()
        self.isolate_claim(path)
        started = threading.Event()
        release = threading.Event()
        delegate = self.synthetic

        class PausedStorage:
            def delete_if_present(inner_self, key):
                started.set()
                if not release.wait(10):
                    raise TimeoutError("synthetic test pause expired")
                delegate.delete_if_present(key)

        first = self.worker(PausedStorage())
        second = self.worker()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(first.run_once)
            self.assertTrue(started.wait(10))
            calls_before = list(self.synthetic.calls)
            second.run_once()
            self.assertNotIn(path, self.synthetic.calls[len(calls_before) :])
            release.set()
            self.assertTrue(pending.result(timeout=15))
        self.assertEqual(self.synthetic.calls.count(path), 1)
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 1, "deleted"),
        )

    def test_expired_lease_reclaims_and_stale_worker_cannot_ack(self):
        path = self.orphan()
        self.isolate_claim(path)
        started = threading.Event()
        release = threading.Event()
        delegate = self.synthetic

        class PausedStorage:
            def delete_if_present(inner_self, key):
                started.set()
                if not release.wait(10):
                    raise TimeoutError("synthetic test pause expired")
                delegate.delete_if_present(key)

        first = self.worker(PausedStorage())
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(first.run_once)
            self.assertTrue(started.wait(10))
            self.make_due(path, expire_lease=True)
            self.assertTrue(self.worker().run_once())
            release.set()
            self.assertTrue(pending.result(timeout=15))

        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 2, "deleted"),
        )
        self.assertEqual(self.synthetic.calls.count(path), 2)

    def test_storage_failure_retries_and_ambiguous_success_is_idempotent(self):
        path = self.orphan()

        class FailingStorage:
            def delete_if_present(inner_self, key):
                raise cleanup.CleanupStorageFailure("storage_unavailable")

        self.assertTrue(self.worker(FailingStorage()).run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.error_code, state.object_state),
            ("pending", 1, "storage_unavailable", "deleting"),
        )
        self.assertIn("synthetic/" + path, self.objects)

        self.make_due(path)

        class AmbiguousStorage:
            def delete_if_present(inner_self, key):
                delegate = SyntheticStorageTestsProxy(self.objects)
                delegate.delete_if_present(key)
                raise cleanup.CleanupStorageFailure("storage_ambiguous")

        self.assertTrue(self.worker(AmbiguousStorage()).run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.error_code, state.object_state),
            ("pending", 2, "storage_ambiguous", "deleting"),
        )
        self.assertNotIn("synthetic/" + path, self.objects)

        self.make_due(path)
        self.assertTrue(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 3, "deleted"),
        )

    def test_provider_timeout_keeps_lease_and_recovers_after_expiry(self):
        path = self.orphan()

        class TimedOutStorage:
            def delete_if_present(inner_self, key):
                raise TimeoutError("synthetic provider timeout")

        with self.assertRaises(TimeoutError):
            self.worker(TimedOutStorage()).run_once()
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("claimed", 1, "deleting"),
        )
        self.assertIsNotNone(state.claim_token)
        self.assertIsNotNone(state.lease_until)
        self.assertIn("synthetic/" + path, self.objects)

        self.make_due(path, expire_lease=True)
        self.assertTrue(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 2, "deleted"),
        )

    def test_crash_after_synthetic_delete_recovers_after_lease_expiry(self):
        path = self.orphan()

        class CrashAfterDelete:
            def delete_if_present(inner_self, key):
                SyntheticStorageTestsProxy(self.objects).delete_if_present(key)
                raise SimulatedCleanupCrash()

        with self.assertRaises(SimulatedCleanupCrash):
            self.worker(CrashAfterDelete()).run_once()
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("claimed", 1, "deleting"),
        )
        self.assertNotIn("synthetic/" + path, self.objects)

        self.make_due(path, expire_lease=True)
        self.assertTrue(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 2, "deleted"),
        )

    def completion_fault_worker(self, path, *, lost_ack=False):
        """Fault only the second transaction: claim commits before storage deletion."""
        transactions = []

        @contextmanager
        def begin():
            transactions.append(len(transactions) + 1)
            completion = len(transactions) == 2
            with self.worker_sessions.begin() as session:
                execute = session.execute
                completed = []

                def observe(statement, *args, **kwargs):
                    result = execute(statement, *args, **kwargs)
                    if "SELECT vervfy_storage.complete_cleanup(" in str(statement):
                        frozen = result.freeze()
                        completed.append(frozen().scalar_one())
                        return frozen()
                    return result

                with patch.object(session, "execute", side_effect=observe):
                    yield session
                if completion:
                    self.assertEqual(completed, [True])
                    self.assertNotIn("synthetic/" + path, self.objects)
                    # An independent connection must still see the durable claim.
                    state = self.cleanup_row(path)
                    self.assertEqual(
                        (state.job_state, state.object_state), ("claimed", "deleting")
                    )
                    if not lost_ack:
                        # Real server error AFTER complete_cleanup has executed;
                        # the surrounding transaction must undo both state writes.
                        session.execute(sa.text("SELECT 1 / 0"))
            if completion and lost_ack:
                # The real commit has returned. Model loss of its acknowledgement
                # at the worker boundary without pretending the DB rolled back.
                raise ConnectionError(
                    "synthetic lost completion commit acknowledgement"
                )

        worker = cleanup.CleanupWorker(
            SimpleNamespace(begin=begin), self.binding, self.synthetic
        )
        return worker, transactions

    def assert_completion_fenced(self, path, token):
        with self.engines["storage_cleanup_worker"].begin() as connection:
            self.assertFalse(
                connection.execute(
                    sa.text("SELECT vervfy_storage.complete_cleanup(:id,:token)"),
                    {"id": self.object(path).id, "token": token},
                ).scalar_one()
            )

    def test_completion_transaction_failure_rolls_back_and_recovers(self):
        path = self.orphan()
        self.isolate_claim(path)
        worker, transactions = self.completion_fault_worker(path)
        with self.assertRaises(sa.exc.DBAPIError) as failure:
            worker.run_once()
        self.assertEqual(failure.exception.orig.sqlstate, "22012")
        self.assertEqual(transactions, [1, 2])
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("claimed", 1, "deleting"),
        )
        self.assertIsNotNone(state.claim_token)
        self.assertIsNotNone(state.lease_until)
        self.assertNotIn("synthetic/" + path, self.objects)
        self.assertFalse(self.worker().run_once())
        self.assertEqual(self.cleanup_row(path), state)
        self.assertEqual(self.synthetic.calls, [path])
        with self.assertRaises(sa.exc.DBAPIError), self.tx() as connection:
            self.attach(connection, path)

        self.make_due(path, expire_lease=True)
        self.assert_completion_fenced(path, state.claim_token)
        self.assertTrue(self.worker().run_once())
        recovered = self.cleanup_row(path)
        self.assertEqual(
            (recovered.job_state, recovered.attempts, recovered.object_state),
            ("done", 2, "deleted"),
        )
        self.assertIsNone(recovered.claim_token)
        self.assertIsNone(recovered.lease_until)
        self.assertEqual(self.synthetic.calls, [path, path])
        self.assert_completion_fenced(path, state.claim_token)
        self.assertFalse(self.worker().run_once())
        self.assertEqual(self.cleanup_row(path), recovered)
        self.assertEqual(self.synthetic.calls, [path, path])

    def test_lost_completion_commit_acknowledgement_keeps_durable_done(self):
        path = self.orphan()
        self.isolate_claim(path)
        tokens = []
        delegate = self.synthetic.delete_if_present

        def delete(key):
            tokens.append(self.cleanup_row(key).claim_token)
            delegate(key)

        worker, transactions = self.completion_fault_worker(path, lost_ack=True)
        with (
            patch.object(self.synthetic, "delete_if_present", side_effect=delete),
            self.assertRaisesRegex(ConnectionError, "lost completion commit"),
        ):
            worker.run_once()
        self.assertEqual(transactions, [1, 2])
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 1, "deleted"),
        )
        self.assertIsNone(state.claim_token)
        self.assertIsNone(state.lease_until)
        self.assertNotIn("synthetic/" + path, self.objects)
        self.assert_completion_fenced(path, tokens[0])
        for _ in range(3):
            self.assertFalse(self.worker().run_once())
        self.assertEqual(self.cleanup_row(path), state)
        self.assertEqual(self.synthetic.calls, [path])

    def test_eighth_completion_failure_requires_manual_review_without_redelete(self):
        path = self.orphan()
        self.isolate_claim(path)
        with self.admin.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE vervfy_storage.cleanup_jobs SET attempts=7 WHERE object_id=:id"
                ),
                {"id": self.object(path).id},
            )
        worker, transactions = self.completion_fault_worker(path)
        with self.assertRaises(sa.exc.DBAPIError) as failure:
            worker.run_once()
        self.assertEqual(failure.exception.orig.sqlstate, "22012")
        self.assertEqual(transactions, [1, 2])
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("claimed", 8, "deleting"),
        )
        self.assertFalse(self.worker().run_once())
        self.make_due(path, expire_lease=True)
        self.assertFalse(self.worker().run_once())
        exhausted = self.cleanup_row(path)
        self.assertEqual(
            (exhausted.job_state, exhausted.attempts, exhausted.object_state),
            ("manual_review", 8, "deleting"),
        )
        self.assertEqual(exhausted.exhaustion_reason, "attempt_limit_lease_expired")
        self.assertIsNone(exhausted.claim_token)
        self.assertIsNone(exhausted.lease_until)
        self.assert_completion_fenced(path, state.claim_token)
        self.make_due(path)
        self.assertFalse(self.worker().run_once())
        self.assertEqual(self.synthetic.calls, [path])
        self.assertNotIn("synthetic/" + path, self.objects)
        with self.assertRaises(sa.exc.DBAPIError), self.tx() as connection:
            self.attach(connection, path)

    def test_application_runtime_cannot_inspect_or_modify_manual_review_jobs(self):
        path = self.orphan()
        obj = self.object(path)
        with self.admin.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE vervfy_storage.objects SET state='deleting' WHERE id=:id"
                ),
                {"id": obj.id},
            )
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs SET state='manual_review',
                    attempts=8,exhaustion_reason='attempt_limit_reached'
                WHERE object_id=:id
                """),
                {"id": obj.id},
            )

        with self.engines["app_runtime"].begin() as connection:
            self.assertFalse(
                connection.execute(
                    sa.text("""
                    SELECT pg_catalog.has_table_privilege(
                        current_user,'vervfy_storage.cleanup_jobs','SELECT'
                    )
                    """)
                ).scalar_one()
            )
            with self.assertRaises(sa.exc.DBAPIError):
                connection.execute(
                    sa.text("""
                    SELECT state FROM vervfy_storage.cleanup_jobs
                    WHERE object_id=:id
                    """),
                    {"id": obj.id},
                )
        with (
            self.engines["app_runtime"].begin() as connection,
            self.assertRaises(sa.exc.DBAPIError),
        ):
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs SET state='pending'
                WHERE object_id=:id
                """),
                {"id": obj.id},
            )

        self.assertFalse(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("manual_review", 8, "deleting"),
        )
        self.assertEqual(state.exhaustion_reason, "attempt_limit_reached")
        self.assertEqual(self.synthetic.calls, [])

    def test_account_deletion_reports_pending_and_worker_recovers_all_media_jobs(self):
        tenant = uuid.uuid4().hex
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                INSERT INTO users(id,username,username_key,password_hash,created_at)
                VALUES(:id,:id,:id,'synthetic',1)
                """),
                {"id": tenant},
            )
        audio = self.managed(tenant, "audio", b"synthetic audio")
        cover = self.managed(tenant, "track-cover", b"synthetic cover")
        photo = self.managed(tenant, "artist-photo", b"synthetic photo")
        staged = self.managed(tenant, "staged-audio", b"synthetic staged audio")
        with self.tx(tenant=tenant) as connection:
            track = self.attach(connection, audio, tenant=tenant)
            connection.execute(
                sa.text("UPDATE tracks SET cover_path=:path WHERE id=:id"),
                {"path": cover, "id": track},
            )
            connection.execute(
                sa.text("""
                INSERT INTO artist_photos(user_id,normalized_artist_name,storage_path,source)
                VALUES(:user_id,'synthetic-artist',:path,'user')
                """),
                {"user_id": tenant, "path": photo},
            )
            connection.execute(
                sa.text("""
                INSERT INTO upload_jobs(id,user_id,filename,storage_path,status,created_at)
                VALUES(:id,:user_id,'synthetic.wav',:path,'processing',1)
                """),
                {"id": uuid.uuid4().hex, "user_id": tenant, "path": staged},
            )

        request = SimpleNamespace(
            session={"sid": "synthetic"},
            app=SimpleNamespace(state=SimpleNamespace(is_first_account=False)),
        )
        with (
            patch.object(server, "tenant_session", self.session),
            patch.object(server, "verify_account_action"),
            patch.object(server.user_store, "bump_session_version", return_value=1),
            patch.object(server.session_store, "revoke_user"),
            patch.object(server.user_store, "count", return_value=1),
        ):
            result = server.delete_account(
                server.AccountDeletionRequest(
                    current_password="synthetic", confirmation="DELETE"
                ),
                request,
                {"id": tenant, "password_hash": "synthetic"},
            )
        self.assertEqual(result, {"ok": True, "storage_cleanup": "pending"})
        self.assertEqual(request.session, {})

        with self.admin.connect() as connection:
            remaining_user = connection.execute(
                sa.text("SELECT count(*) FROM users WHERE id=:id"), {"id": tenant}
            ).scalar_one()
            jobs = connection.execute(
                sa.text("""
                SELECT j.state,count(*) FROM vervfy_storage.cleanup_jobs AS j
                JOIN vervfy_storage.objects AS o ON o.id=j.object_id
                WHERE o.tenant_id=:id GROUP BY j.state
                """),
                {"id": tenant},
            ).all()
        self.assertEqual(remaining_user, 0)
        self.assertEqual(jobs, [("pending", 4)])

        worker = self.worker()
        self.assertEqual(sum(worker.run_once() for _ in range(5)), 4)
        self.assertEqual(
            sum(
                key in self.objects
                for key in (
                    "synthetic/" + audio,
                    "synthetic/" + cover,
                    "synthetic/" + photo,
                    "synthetic/" + staged,
                )
            ),
            0,
        )
        with self.admin.connect() as connection:
            self.assertEqual(
                connection.execute(
                    sa.text("""
                    SELECT count(*) FROM vervfy_storage.cleanup_jobs AS j
                    JOIN vervfy_storage.objects AS o ON o.id=j.object_id
                    WHERE o.tenant_id=:id AND j.state<>'done'
                    """),
                    {"id": tenant},
                ).scalar_one(),
                0,
            )

    def assert_exhausted(self, path, reason, tokens):
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("manual_review", 8, "deleting"),
        )
        self.assertEqual(state.exhaustion_reason, reason)
        self.assertIsNone(state.claim_token)
        self.assertIsNone(state.lease_until)
        obj = self.object(path)
        for token in tokens:
            with self.engines["storage_cleanup_worker"].begin() as connection:
                for function, extra in (
                    ("complete_cleanup", ""),
                    ("retry_cleanup", ", 'storage_timeout'"),
                ):
                    self.assertFalse(
                        connection.execute(
                            sa.text(
                                f"SELECT vervfy_storage.{function}(:id,:token{extra})"
                            ),
                            {"id": obj.id, "token": token},
                        ).scalar_one()
                    )
        for _ in range(3):
            self.make_due(path, expire_lease=True)
            self.make_due(path)
            self.assertFalse(self.worker().run_once())
        self.assertEqual(self.cleanup_row(path).job_state, "manual_review")
        self.assertIn("synthetic/" + path, self.objects)
        with self.assertRaises(sa.exc.DBAPIError), self.tx() as connection:
            self.attach(connection, path)

    def test_eight_provider_failures_preserve_obligation_and_diagnostics(self):
        path = self.orphan()
        self.isolate_claim(path)
        tokens = []
        test = self

        class FailingStorage:
            def delete_if_present(self, key):
                tokens.append(test.cleanup_row(path).claim_token)
                raise cleanup.CleanupStorageFailure("storage_unavailable")

        for attempt in range(1, 9):
            self.make_due(path)
            self.assertTrue(self.worker(FailingStorage()).run_once())
            state = self.cleanup_row(path)
            self.assertEqual(state.attempts, attempt)
            self.assertEqual(state.error_code, "storage_unavailable")
            if attempt < 8:
                self.assertEqual(state.job_state, "pending")
                self.assertIsNone(state.exhaustion_reason)
                with self.admin.connect() as connection:
                    delay = connection.execute(
                        sa.text(
                            "SELECT EXTRACT(EPOCH FROM (:due - clock_timestamp()))"
                        ),
                        {"due": state.available_at},
                    ).scalar_one()
                self.assertGreater(float(delay), 5 * 2 ** (attempt - 1) - 3)
                self.assertFalse(self.worker().run_once())
        self.assert_exhausted(path, "attempt_limit_provider_failure", tokens)

    def test_eight_crashes_exhaust_without_ninth_adapter_call(self):
        path = self.orphan()
        self.isolate_claim(path)
        tokens = []
        test = self

        class CrashingStorage:
            def delete_if_present(self, key):
                tokens.append(test.cleanup_row(path).claim_token)
                raise SimulatedCleanupCrash()

        for attempt in range(1, 9):
            with self.assertRaises(SimulatedCleanupCrash):
                self.worker(CrashingStorage()).run_once()
            state = self.cleanup_row(path)
            self.assertEqual((state.job_state, state.attempts), ("claimed", attempt))
            self.assertFalse(self.worker().run_once())
            self.make_due(path, expire_lease=True)
        self.assertFalse(self.worker(CrashingStorage()).run_once())
        self.assertEqual(len(set(tokens)), 8)
        self.assert_exhausted(path, "attempt_limit_lease_expired", tokens)

    def test_mixed_failures_and_crashes_share_budget_and_keep_last_error(self):
        path = self.orphan()
        self.isolate_claim(path)

        class FailingStorage:
            def delete_if_present(self, key):
                raise cleanup.CleanupStorageFailure("storage_ambiguous")

        for _ in range(7):
            self.make_due(path)
            self.worker(FailingStorage()).run_once()
        self.make_due(path)

        class CrashingStorage:
            def delete_if_present(self, key):
                raise SimulatedCleanupCrash()

        with self.assertRaises(SimulatedCleanupCrash):
            self.worker(CrashingStorage()).run_once()
        token = self.cleanup_row(path).claim_token
        self.make_due(path, expire_lease=True)
        self.assertFalse(self.worker().run_once())
        self.assertEqual(self.cleanup_row(path).error_code, "storage_ambiguous")
        self.assert_exhausted(path, "attempt_limit_lease_expired", [token])

    def test_eighth_claim_can_complete_successfully(self):
        path = self.orphan()
        self.isolate_claim(path)
        with self.admin.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE vervfy_storage.cleanup_jobs SET attempts=7 WHERE object_id=:id"
                ),
                {"id": self.object(path).id},
            )
        self.assertTrue(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (state.job_state, state.attempts, state.object_state),
            ("done", 8, "deleted"),
        )

    def test_existing_over_limit_pending_job_never_gets_another_token(self):
        path = self.orphan()
        self.isolate_claim(path)
        with self.admin.begin() as connection:
            connection.execute(
                sa.text("""
                UPDATE vervfy_storage.cleanup_jobs SET attempts=12,
                    error_code='storage_rejected' WHERE object_id=:id
            """),
                {"id": self.object(path).id},
            )
            connection.execute(
                sa.text(
                    "UPDATE vervfy_storage.objects SET state='deleting' WHERE id=:id"
                ),
                {"id": self.object(path).id},
            )
        self.assertFalse(self.worker().run_once())
        state = self.cleanup_row(path)
        self.assertEqual(
            (
                state.job_state,
                state.attempts,
                state.object_state,
                state.error_code,
                state.exhaustion_reason,
            ),
            (
                "manual_review",
                12,
                "deleting",
                "storage_rejected",
                "attempt_limit_reached",
            ),
        )
        self.assertEqual(self.synthetic.calls, [])

    def test_production_worker_entry_point_fails_before_storage_or_database_use(self):
        with self.assertRaisesRegex(
            RuntimeError, "Physical storage cleanup is disabled"
        ):
            cleanup.main()
        self.assertEqual(self.requests, [])
        with self.admin.connect() as connection:
            self.assertFalse(
                connection.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )


class SyntheticStorageTestsProxy:
    def __init__(self, objects):
        self.storage = SyntheticStorage(objects)

    def delete_if_present(self, path):
        self.storage.delete_if_present(path)
