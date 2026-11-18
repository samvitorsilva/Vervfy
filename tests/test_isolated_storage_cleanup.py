"""Real PostgreSQL RLS and concurrency rehearsal; all bytes are synthetic."""

import os
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from unittest.mock import patch

import sqlalchemy as sa
import test_staging_migrations as staging
from isolated_storage_cleanup import IsolatedCleanupWorker, SyntheticStorage
from sqlalchemy.exc import DBAPIError

from storage_namespace import NamespaceBinding


def _install_cleanup_authorizer(c):
    # Even an empty parameter mapping makes psycopg parse %ROWTYPE as %R.
    # Keep this static DDL unparameterized; value-bearing SQL stays bound.
    c.exec_driver_sql(
        """CREATE FUNCTION cleanup_rehearsal.authorize(p_id uuid,p_token uuid,p_path text)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE obj vervfy_storage.objects%ROWTYPE;
                job vervfy_storage.cleanup_jobs%ROWTYPE;
                ns uuid;
        BEGIN
            SELECT * INTO obj FROM vervfy_storage.objects WHERE id=p_id FOR UPDATE;
            IF NOT FOUND THEN RETURN false; END IF;
            SELECT * INTO job FROM vervfy_storage.cleanup_jobs WHERE object_id=p_id FOR UPDATE;
            IF NOT FOUND THEN RETURN false; END IF;
            SELECT namespace_id INTO STRICT ns FROM vervfy_storage.namespaces
                WHERE id=obj.namespace_id AND environment='disposable-test'
                AND endpoint='https://vervfy.invalid' AND bucket='synthetic'
                AND NOT physical_cleanup_enabled;
            RETURN job.state='claimed' AND p_token IS NOT NULL
                AND job.claim_token=p_token AND job.lease_until>clock_timestamp()
                AND obj.path=p_path AND obj.classification='managed'
                AND obj.upload_verified AND obj.state='deleting'
                AND job.requested_by IS NOT DISTINCT FROM obj.tenant_id
                AND split_part(p_path,'/',2)=ns::text
                AND split_part(p_path,'/',3)=obj.tenant_id
                AND split_part(p_path,'/',4)=obj.kind
                AND split_part(split_part(p_path,'/',5),'.',1)=obj.id::text
                AND NOT vervfy_storage._has_references(obj.path);
        END $$""",
        execution_options={"no_parameters": True},
    )


class IsolatedCleanupTests(unittest.TestCase):
    account_snapshot = staticmethod(staging.StagingPostgresTests.account_snapshot)

    @classmethod
    def setUpClass(cls):
        original = tempfile.TemporaryDirectory

        def directory(*args, **kwargs):
            kwargs["prefix"] = "vervfy-storage-pg-"
            return original(*args, **kwargs)

        with patch.object(tempfile, "TemporaryDirectory", directory):
            staging.StagingPostgresTests.setUpClass.__func__(cls)
        cls.binding = NamespaceBinding(
            uuid.uuid4(), "disposable-test", "https://vervfy.invalid", "synthetic"
        )
        cls.runtime = sa.create_engine(cls.url.set(username="app_runtime"))
        cls.worker_engine = sa.create_engine(
            cls.url.set(username="storage_cleanup_worker")
        )
        cls.addClassCleanup(cls.runtime.dispose)
        cls.addClassCleanup(cls.worker_engine.dispose)
        # No modification of existing production functions, ACLs or migrations.
        # These wrappers exist solely in the newly created private socket cluster.
        with cls.engine.begin() as c:
            c.execute(
                sa.text("""INSERT INTO vervfy_storage.namespaces
                VALUES (1,:id,'disposable-test','https://vervfy.invalid','synthetic',false)"""),
                {"id": cls.binding.namespace_id},
            )
            c.exec_driver_sql(
                "CREATE SCHEMA cleanup_rehearsal AUTHORIZATION vervfy_storage_lifecycle_owner"
            )
            c.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
            c.exec_driver_sql("""CREATE FUNCTION cleanup_rehearsal.claim()
                RETURNS TABLE(object_id uuid,object_path text,claim_token uuid)
                LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp
                AS $$ SELECT * FROM vervfy_storage.claim_next_cleanup() $$""")
            _install_cleanup_authorizer(c)
            c.exec_driver_sql(
                "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA cleanup_rehearsal FROM PUBLIC"
            )
            c.exec_driver_sql(
                "GRANT USAGE ON SCHEMA cleanup_rehearsal TO storage_cleanup_worker"
            )
            c.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA cleanup_rehearsal TO storage_cleanup_worker"
            )

    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "PATH": os.environ.get("PATH", ""),
                "VERVFY_ENVIRONMENT": "local-test",
                "VERVFY_STORAGE_BACKEND": "filesystem",
                "DATABASE_URL": self.runtime.url.render_as_string(hide_password=False),
            },
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.storage = SyntheticStorage()
        self.worker = IsolatedCleanupWorker(
            self.worker_engine, self.binding, self.storage
        )
        # Tests own this whole disposable database. Preserve records while
        # preventing earlier test obligations from participating in later claims.
        with self.engine.begin() as c:
            c.exec_driver_sql("UPDATE vervfy_storage.cleanup_jobs SET state='held'")

    def reserve(self, actor="a", queue=True):
        with self.runtime.begin() as c:
            c.execute(
                sa.text("SELECT set_config('app.current_user_id',:actor,true)"),
                {"actor": actor},
            )
            row = c.exec_driver_sql(
                "SELECT * FROM vervfy_storage.reserve_sized_object('audio','mp3',15,157286400)"
            ).one()
            for state in ("uploading", "ready"):
                c.execute(
                    sa.text("SELECT vervfy_storage.advance_upload(:id,:token,:state)"),
                    {"id": row.object_id, "token": row.upload_token, "state": state},
                )
            if queue:
                c.execute(
                    sa.text("SELECT vervfy_storage.request_cleanup(:id)"),
                    {"id": row.object_id},
                )
        self.storage.objects[row.object_path] = b"synthetic audio"
        return row

    def job(self, obj):
        with self.engine.connect() as c:
            return c.execute(
                sa.text(
                    "SELECT * FROM vervfy_storage.cleanup_jobs WHERE object_id=:id"
                ),
                {"id": obj.object_id},
            ).one()

    def update(self, obj, sql):
        with self.engine.begin() as c:
            c.execute(
                sa.text(
                    "UPDATE vervfy_storage.cleanup_jobs SET "
                    + sql
                    + " WHERE object_id=:id"
                ),
                {"id": obj.object_id},
            )

    def test_success_and_absent_object_are_idempotent(self):
        for already_absent in (False, True):
            obj = self.reserve()
            if already_absent:
                self.storage.objects.clear()
            self.assertTrue(self.worker.run_once())
            self.assertEqual(self.job(obj).state, "done")
            self.assertNotIn(obj.object_path, self.storage.objects)
            self.assertFalse(self.worker.run_once())

    def test_cross_account_request_and_attachment_denied_by_real_login(self):
        obj = self.reserve(queue=False)
        for sql in (
            "SELECT vervfy_storage.request_cleanup(:id)",
            "UPDATE tracks SET storage_path=:path WHERE id='track-b'",
        ):
            with self.assertRaises(DBAPIError), self.runtime.begin() as c:
                c.exec_driver_sql("SELECT set_config('app.current_user_id','b',true)")
                c.execute(sa.text(sql), {"id": obj.object_id, "path": obj.object_path})
        self.assertFalse(self.worker.run_once())
        self.assertEqual(self.storage.calls, [])

    def test_references_and_retirement_fence(self):
        obj = self.reserve()
        with self.runtime.begin() as c:
            c.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            c.execute(
                sa.text("UPDATE tracks SET storage_path=:p WHERE id='embedded'"),
                {"p": obj.object_path},
            )
        self.assertFalse(self.worker.run_once())
        self.assertEqual(self.job(obj).error_code, "referenced")
        with self.runtime.begin() as c:
            c.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            c.exec_driver_sql("UPDATE tracks SET storage_path=NULL WHERE id='embedded'")
        self.update(obj, "available_at=clock_timestamp()")
        claim = self.worker.claim()
        with self.assertRaises(DBAPIError), self.runtime.begin() as c:
            c.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            c.execute(
                sa.text("UPDATE tracks SET storage_path=:p WHERE id='embedded'"),
                {"p": obj.object_path},
            )
        self.worker.process(claim)

    def test_concurrent_workers_only_one_claim(self):
        obj = self.reserve()
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: self.worker.claim(), range(2)))
        self.assertEqual(sum(c is not None for c in claims), 1)
        self.worker.process(next(c for c in claims if c))
        self.assertEqual(self.job(obj).attempts, 1)

    def test_expired_replayed_and_forged_claims(self):
        obj = self.reserve()
        claim = self.worker.claim()
        for invalid in (
            replace(claim, token=uuid.uuid4()),
            replace(claim, path=claim.path.replace("/a/", "/b/")),
        ):
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                self.worker.process(invalid)
        self.update(obj, "lease_until=clock_timestamp()-interval '1 second'")
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            self.worker.process(claim)
        newer = self.worker.claim()
        self.assertNotEqual(newer.token, claim.token)
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            self.worker.process(claim)
        self.assertEqual(self.storage.calls, [])
        self.worker.process(newer)
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            self.worker.process(newer)

    def test_timeout_ambiguous_partial_failure_and_absence_verification(self):
        for failure in (
            "storage_timeout",
            "storage_ambiguous",
            "storage_unavailable",
            "storage_rejected",
            "storage_unknown",
            "still_present",
        ):
            obj = self.reserve()
            self.storage.failure = failure
            self.worker.run_once()
            job = self.job(obj)
            self.assertEqual(job.state, "pending")
            self.assertEqual(
                job.error_code,
                "storage_ambiguous" if failure == "still_present" else failure,
            )
            self.assertFalse(self.worker.run_once())
            self.storage.failure = None
            self.update(obj, "available_at=clock_timestamp()")
            self.worker.run_once()
            self.assertEqual(self.job(obj).state, "done")

    def test_retry_exhaustion_and_backoff(self):
        obj = self.reserve()
        self.storage.failure = "storage_timeout"
        for attempt in range(1, 9):
            self.worker.run_once()
            job = self.job(obj)
            self.assertEqual(job.attempts, attempt)
            with self.engine.connect() as c:
                delay = c.execute(
                    sa.text(
                        "SELECT extract(epoch FROM available_at-clock_timestamp()) FROM vervfy_storage.cleanup_jobs WHERE object_id=:id"
                    ),
                    {"id": obj.object_id},
                ).scalar_one()
            self.assertAlmostEqual(
                float(delay), min(3600, 5 * 2 ** (attempt - 1)), delta=2
            )
            self.update(obj, "available_at=clock_timestamp()")
        self.assertEqual(self.job(obj).state, "manual_review")
        self.assertFalse(self.worker.run_once())
        self.assertIn(obj.object_path, self.storage.objects)

    def test_expired_eighth_claim_retained_for_manual_review(self):
        obj = self.reserve()
        self.update(obj, "attempts=7")
        self.worker.claim()
        self.update(obj, "lease_until=clock_timestamp()-interval '1 second'")
        self.assertIsNone(self.worker.claim())
        self.assertEqual(self.job(obj).state, "manual_review")
        self.assertEqual(self.job(obj).exhaustion_reason, "attempt_limit_lease_expired")

    def test_namespace_mismatch_and_immutable_binding(self):
        self.reserve()
        self.worker.binding = replace(self.binding, namespace_id=uuid.uuid4())
        with self.assertRaises(DBAPIError):
            self.worker.run_once()
        with self.assertRaises(DBAPIError), self.engine.begin() as c:
            c.exec_driver_sql("UPDATE vervfy_storage.namespaces SET bucket='different'")
        self.assertEqual(self.storage.calls, [])

    def test_database_commit_failures_before_and_after_io(self):
        obj = self.reserve()

        def fail_commit(connection):
            raise RuntimeError("synthetic commit failure")

        sa.event.listen(self.worker_engine, "commit", fail_commit)
        try:
            with self.assertRaisesRegex(RuntimeError, "commit failure"):
                self.worker.claim()
        finally:
            sa.event.remove(self.worker_engine, "commit", fail_commit)
        self.assertEqual(self.storage.calls, [])
        self.assertEqual(self.job(obj).attempts, 0)
        claim = self.worker.claim()
        sa.event.listen(self.worker_engine, "commit", fail_commit)
        try:
            with self.assertRaisesRegex(RuntimeError, "commit failure"):
                self.worker.process(claim)
        finally:
            sa.event.remove(self.worker_engine, "commit", fail_commit)
        self.assertEqual(self.job(obj).state, "claimed")
        self.worker.process(claim)
        self.assertEqual(self.job(obj).state, "done")

    def test_production_claim_acl_still_revoked_and_tables_inaccessible(self):
        with self.worker_engine.connect() as c:
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT has_function_privilege(current_user,'vervfy_storage.claim_next_cleanup()','EXECUTE')"
                ).scalar_one()
            )
        for sql in (
            "SELECT * FROM vervfy_storage.objects",
            "SELECT * FROM vervfy_storage.claim_next_cleanup()",
        ):
            with self.assertRaises(DBAPIError), self.worker_engine.begin() as c:
                c.exec_driver_sql(sql)
        with self.engine.connect() as c:
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )

    def test_claim_locked_during_io_cannot_be_reclaimed(self):
        obj = self.reserve()
        claim = self.worker.claim()
        entered, release = Event(), Event()
        original = SyntheticStorage.delete_if_present

        def blocked(storage, path):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Synthetic test synchronization timed out")
            original(storage, path)

        with (
            patch.object(SyntheticStorage, "delete_if_present", blocked),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            pending = pool.submit(self.worker.process, claim)
            try:
                self.assertTrue(entered.wait(5))
                self.assertIsNone(self.worker.claim())
            finally:
                release.set()
            pending.result(timeout=5)
        self.assertEqual(self.job(obj).state, "done")
        self.assertEqual(self.storage.calls, [obj.object_path])

    def test_authorization_database_error_stops_before_storage(self):
        self.reserve()
        claim = self.worker.claim()
        with self.engine.begin() as c:
            c.exec_driver_sql(
                "REVOKE EXECUTE ON FUNCTION cleanup_rehearsal.authorize(uuid,uuid,text) FROM storage_cleanup_worker"
            )
        try:
            with self.assertRaises(DBAPIError):
                self.worker.process(claim)
            self.assertEqual(self.storage.calls, [])
        finally:
            with self.engine.begin() as c:
                c.exec_driver_sql(
                    "GRANT EXECUTE ON FUNCTION cleanup_rehearsal.authorize(uuid,uuid,text) TO storage_cleanup_worker"
                )

    def test_unknown_storage_exception_preserves_claim(self):
        obj = self.reserve()
        claim = self.worker.claim()
        with (
            patch.object(
                SyntheticStorage,
                "delete_if_present",
                side_effect=OSError("synthetic failure"),
            ),
            self.assertRaises(OSError),
        ):
            self.worker.process(claim)
        self.assertEqual(self.job(obj).state, "claimed")
        self.assertIn(obj.object_path, self.storage.objects)

    def test_lease_expiry_during_io_does_not_mark_done(self):
        obj = self.reserve()
        claim = self.worker.claim()
        # The restricted worker cannot mutate tables: use a narrowly scoped
        # test-only definer function to expire its own locked job instead.
        with self.engine.begin() as c:
            c.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
            c.exec_driver_sql("""CREATE FUNCTION cleanup_rehearsal.expire(p_id uuid, p_token uuid)
                RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp
                AS $$ UPDATE vervfy_storage.cleanup_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE object_id=p_id AND claim_token=p_token AND state='claimed' $$""")
            c.exec_driver_sql(
                "REVOKE ALL ON FUNCTION cleanup_rehearsal.expire(uuid,uuid) FROM PUBLIC"
            )
            c.exec_driver_sql(
                "GRANT EXECUTE ON FUNCTION cleanup_rehearsal.expire(uuid,uuid) TO storage_cleanup_worker"
            )

        def expire(connection, cursor, statement, parameters, context, executemany):
            if "complete_cleanup" in statement:
                cursor.execute(
                    "SELECT cleanup_rehearsal.expire(%s,%s)",
                    (obj.object_id, claim.token),
                )

        def drop_expiry_helper():
            with self.engine.begin() as c:
                c.exec_driver_sql("DROP FUNCTION cleanup_rehearsal.expire(uuid,uuid)")

        self.addCleanup(drop_expiry_helper)
        sa.event.listen(self.worker_engine, "before_cursor_execute", expire)
        try:
            with self.assertRaisesRegex(RuntimeError, "expired"):
                self.worker.process(claim)
        finally:
            sa.event.remove(self.worker_engine, "before_cursor_execute", expire)
        self.assertEqual(self.job(obj).state, "claimed")
        self.assertNotIn(obj.object_path, self.storage.objects)
        self.worker.process(claim)
        self.assertEqual(self.job(obj).state, "done")
