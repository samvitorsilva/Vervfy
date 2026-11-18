"""Real PostgreSQL checks in the existing fresh disposable-cluster fixture only."""

import concurrent.futures
import threading
import unittest
import uuid

import sqlalchemy as sa
import test_staging_migrations as fixtures
from sqlalchemy.exc import DBAPIError


class StorageQuotaPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StagingPostgresTests.setUpClass.__func__(cls)
        cls.runtime = sa.create_engine(cls.url.set(username="app_runtime"))
        cls.addClassCleanup(cls.runtime.dispose)
        with cls.engine.begin() as c:
            c.execute(
                sa.text("""INSERT INTO vervfy_storage.namespaces VALUES
                (1,:id,'disposable-test','https://vervfy.invalid','synthetic',false)"""),
                {"id": uuid.uuid4()},
            )

    # Used by the shared fixture before/after applying migrations.
    account_snapshot = staticmethod(fixtures.StagingPostgresTests.account_snapshot)

    def setUp(self):
        # This engine is exclusively the new temporary cluster above.
        with self.engine.begin() as c:
            c.exec_driver_sql(
                "TRUNCATE vervfy_storage.cleanup_jobs, vervfy_storage.objects"
            )
            c.exec_driver_sql(
                "UPDATE vervfy_storage.quota_policy SET tenant_limit_bytes=20,total_limit_bytes=30"
            )

    def reserve(self, actor="a", size=15, limit=20, connection=None):
        def run(c):
            c.execute(
                sa.text("SELECT set_config('app.current_user_id',:actor,true)"),
                {"actor": actor},
            )
            return c.execute(
                sa.text(
                    "SELECT * FROM vervfy_storage.reserve_sized_object('audio','mp3',:size,:limit)"
                ),
                {"size": size, "limit": limit},
            ).one()

        if connection is not None:
            return run(connection)
        with self.runtime.begin() as c:
            return run(c)

    def test_tenant_ceiling_cannot_be_raised_by_caller_and_global_cap_is_shared(self):
        self.reserve(size=20, limit=999999)
        with self.assertRaises(DBAPIError):
            self.reserve(size=1, limit=999999)
        self.reserve(actor="b", size=10)
        with self.assertRaises(DBAPIError):
            self.reserve(actor="b", size=1)

    def test_retired_failed_and_deleted_objects_remain_charged(self):
        for state in ("retired", "hold", "deleted"):
            with self.subTest(state=state):
                self.setUp()
                obj = self.reserve()
                with self.engine.begin() as c:
                    c.execute(
                        sa.text(
                            "UPDATE vervfy_storage.objects SET state=:state WHERE id=:id"
                        ),
                        {"state": state, "id": obj.object_id},
                    )
                with self.assertRaises(DBAPIError):
                    self.reserve(size=6)

    def test_legacy_unknown_inventory_blocks_admission(self):
        with self.engine.begin() as c:
            c.execute(
                sa.text("""INSERT INTO vervfy_storage.objects
                (id,namespace_id,path,kind,classification,state)
                VALUES (:id,1,'synthetic-legacy','legacy','legacy','hold')"""),
                {"id": uuid.uuid4()},
            )
        with self.assertRaisesRegex(DBAPIError, "reconciliation"):
            self.reserve()

    def test_acl_rls_and_production_cleanup_remain_closed(self):
        obj = self.reserve()
        with self.runtime.begin() as c:
            c.execute(sa.text("SELECT set_config('app.current_user_id','b',true)"))
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.objects"
                ).scalar_one(),
                0,
            )
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT has_function_privilege(current_user,'vervfy_storage.reserve_object(text,text)','EXECUTE')"
                ).scalar_one()
            )
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT has_function_privilege(current_user,'vervfy_storage.claim_next_cleanup()','EXECUTE')"
                ).scalar_one()
            )
        for sql in (
            "SELECT * FROM vervfy_storage.reserve_object('audio','mp3')",
            "UPDATE vervfy_storage.quota_policy SET tenant_limit_bytes=99999",
            f"UPDATE vervfy_storage.objects SET reserved_bytes=1 WHERE id='{obj.object_id}'",
        ):
            with self.assertRaises(DBAPIError), self.runtime.begin() as c:
                c.exec_driver_sql(sql)
        with self.engine.connect() as c:
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT has_function_privilege('storage_cleanup_worker','vervfy_storage.claim_next_cleanup()','EXECUTE')"
                ).scalar_one()
            )

    def test_concurrent_admission_only_one_fits(self):
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait(timeout=5)
            try:
                self.reserve()
                return True
            except DBAPIError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT sum(reserved_bytes) FROM vervfy_storage.objects"
                ).scalar_one(),
                15,
            )

    def test_rolled_back_reservation_never_charged(self):
        with self.runtime.connect() as c:
            transaction = c.begin()
            self.reserve(connection=c)
            transaction.rollback()
        self.reserve(size=20)

    def test_invalid_size_actor_and_repeatable_read_fail_closed(self):
        for actor, size, limit in (
            ("missing", 1, 20),
            ("a", 0, 20),
            ("a", -1, 20),
            ("a", 1, 0),
        ):
            with self.assertRaises(DBAPIError):
                self.reserve(actor=actor, size=size, limit=limit)
        with (
            self.assertRaises(DBAPIError),
            self.runtime.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as c,
        ):
            self.reserve(connection=c)
