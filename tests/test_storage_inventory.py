"""Unknown-size accounting in a fresh socket-only PostgreSQL cluster."""

import concurrent.futures
import copy
import hashlib
import threading
import unittest
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
import test_staging_migrations as fixtures
from sqlalchemy.exc import DBAPIError

from storage_inventory import (
    InventoryBlocked,
    apply_inventory,
    measure_inventory,
    plan_digest,
    snapshot,
)
from storage_namespace import NamespaceBinding, initialize_namespace


class InventoryTests(unittest.TestCase):
    account_snapshot = staticmethod(fixtures.StagingPostgresTests.account_snapshot)

    @classmethod
    def setUpClass(cls):
        fixtures.StagingPostgresTests.setUpClass.__func__(cls)
        cls.migrator = sa.create_engine(cls.url.set(username="migration_owner"))
        cls.runtime = sa.create_engine(cls.url.set(username="app_runtime"))
        cls.addClassCleanup(cls.migrator.dispose)
        cls.addClassCleanup(cls.runtime.dispose)
        cls.binding = NamespaceBinding(
            uuid.uuid4(), "disposable-test", "https://vervfy.invalid", "synthetic"
        )
        # Test the restored current-head bootstrap guard as well.
        with cls.engine.begin() as c:
            initialize_namespace(c, cls.binding)
            initialize_namespace(c, cls.binding)

    def setUp(self):
        with self.engine.begin() as c:
            c.exec_driver_sql(
                "TRUNCATE vervfy_storage.cleanup_jobs,vervfy_storage.objects"
            )
            c.execute(
                sa.text("""INSERT INTO vervfy_storage.objects
                (id,namespace_id,path,kind,classification,state) VALUES
                (:id,1,'legacy/shared.mp3','legacy','legacy','hold')"""),
                {"id": uuid.uuid4()},
            )
            c.exec_driver_sql(
                "UPDATE vervfy_storage.quota_policy SET tenant_limit_bytes=20,total_limit_bytes=30"
            )

    def plan(self):
        with self.migrator.begin() as c:
            before = snapshot(c, self.binding)
        return measure_inventory(
            before,
            lambda path: {
                "bytes": 15,
                "sha256": hashlib.sha256(b"synthetic bytes").hexdigest(),
                "etag": '"test-version"',
            },
        )

    def apply(self, plan):
        with self.migrator.begin() as c:
            return apply_inventory(c, self.binding, plan, plan_digest(plan))

    def reserve(self, size):
        with self.runtime.begin() as c:
            c.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            return c.execute(
                sa.text(
                    "SELECT * FROM vervfy_storage.reserve_sized_object('audio','mp3',:n,20)"
                ),
                {"n": size},
            ).one()

    def test_reconciliation_unblocks_admission_without_refunds_or_owner_adoption(self):
        with self.assertRaisesRegex(DBAPIError, "reconciliation"):
            self.reserve(1)
        plan = self.plan()
        self.assertEqual(self.apply(plan), 1)
        self.assertEqual(self.apply(plan), 0)
        with self.engine.connect() as c:
            self.assertEqual(
                tuple(
                    c.exec_driver_sql(
                        "SELECT tenant_id,state,classification,reserved_bytes FROM vervfy_storage.objects"
                    ).one()
                ),
                (None, "hold", "legacy", 15),
            )
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.cleanup_jobs"
                ).scalar_one(),
                0,
            )
        self.reserve(15)
        with self.assertRaisesRegex(DBAPIError, "quota"):
            self.reserve(1)

    def test_tampered_stale_future_incomplete_and_zero_plans_leave_unknown(self):
        plan = self.plan()
        for change in ("digest", "stale", "future", "missing", "zero"):
            candidate = copy.deepcopy(plan)
            approved = plan_digest(candidate)
            if change == "digest":
                candidate["observations"][next(iter(candidate["observations"]))][
                    "bytes"
                ] = 1
            elif change in {"stale", "future"}:
                candidate["measured_at"] = (
                    datetime.now(UTC)
                    + timedelta(minutes=-16 if change == "stale" else 1)
                ).isoformat()
                approved = plan_digest(candidate)
            elif change == "missing":
                candidate["observations"] = {}
                approved = plan_digest(candidate)
            else:
                candidate["observations"][next(iter(candidate["observations"]))][
                    "bytes"
                ] = 0
                approved = plan_digest(candidate)
            with (
                self.subTest(change=change),
                self.migrator.begin() as c,
                self.assertRaises(InventoryBlocked),
            ):
                apply_inventory(c, self.binding, candidate, approved)
        with self.engine.connect() as c:
            self.assertIsNone(
                c.exec_driver_sql(
                    "SELECT reserved_bytes FROM vervfy_storage.objects"
                ).scalar_one()
            )

    def test_ledger_drift_and_known_charge_reduction_fail_closed(self):
        plan = self.plan()
        self.apply(plan)
        altered = copy.deepcopy(plan)
        altered["observations"][next(iter(altered["observations"]))]["bytes"] = 1
        with self.assertRaisesRegex(InventoryBlocked, "Ledger changed"):
            self.apply(altered)
        with self.engine.begin() as c:
            c.exec_driver_sql("UPDATE vervfy_storage.objects SET state='retired'")
        with self.assertRaisesRegex(InventoryBlocked, "Ledger changed"):
            self.apply(plan)

    def test_runtime_cannot_collect_apply_or_bootstrap(self):
        plan = self.plan()
        with self.runtime.begin() as c:
            with self.assertRaises(InventoryBlocked):
                snapshot(c, self.binding)
            with self.assertRaises(InventoryBlocked):
                apply_inventory(c, self.binding, plan, plan_digest(plan))
            with self.assertRaisesRegex(RuntimeError, "bootstrap administrator"):
                initialize_namespace(c, self.binding)

    def test_wrong_namespace_rolls_back_without_poisoning_transaction(self):
        from dataclasses import replace

        plan = self.plan()
        with self.migrator.begin() as c:
            with self.assertRaises(InventoryBlocked):
                apply_inventory(
                    c,
                    replace(self.binding, namespace_id=uuid.uuid4()),
                    plan,
                    plan_digest(plan),
                )
            self.assertEqual(
                c.exec_driver_sql("SELECT current_user").scalar_one(), "migration_owner"
            )
            self.assertEqual(c.exec_driver_sql("SELECT 1").scalar_one(), 1)

    def test_concurrent_apply_serializes_without_double_charge(self):
        plan = self.plan()
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait(timeout=5)
            return self.apply(plan)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _: attempt(), range(2))), [0, 1])
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT sum(reserved_bytes) FROM vervfy_storage.objects"
                ).scalar_one(),
                15,
            )

    def test_outer_rollback_preserves_unknown_guard(self):
        plan = self.plan()
        with self.migrator.connect() as c:
            transaction = c.begin()
            self.assertEqual(
                apply_inventory(c, self.binding, plan, plan_digest(plan)), 1
            )
            transaction.rollback()
        with self.assertRaisesRegex(DBAPIError, "reconciliation"):
            self.reserve(1)

    def test_namespace_cannot_enable_deletion(self):
        with self.engine.begin() as c:
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.exec_driver_sql(
                    "UPDATE vervfy_storage.namespaces SET physical_cleanup_enabled=true"
                )
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )

    def test_failure_mid_apply_rolls_back_all_charges_and_restores_role(self):
        with self.engine.begin() as c:
            c.execute(
                sa.text("""INSERT INTO vervfy_storage.objects
                (id,namespace_id,path,kind,classification,state)
                VALUES (:id,1,'legacy/z-last.mp3','legacy','legacy','hold')"""),
                {"id": uuid.uuid4()},
            )
            # This trigger exists exclusively in the disposable test cluster.
            c.exec_driver_sql("""CREATE FUNCTION public.reject_inventory_test() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN IF NEW.path='legacy/z-last.mp3' THEN
                RAISE EXCEPTION 'synthetic rejection'; END IF; RETURN NEW; END $$""")
            c.exec_driver_sql("""CREATE TRIGGER reject_inventory_test BEFORE UPDATE ON vervfy_storage.objects
                FOR EACH ROW EXECUTE FUNCTION public.reject_inventory_test()""")
        plan = self.plan()
        try:
            with self.migrator.begin() as c:
                with self.assertRaisesRegex(DBAPIError, "synthetic rejection"):
                    apply_inventory(c, self.binding, plan, plan_digest(plan))
                self.assertEqual(
                    c.exec_driver_sql("SELECT current_user").scalar_one(),
                    "migration_owner",
                )
            with self.engine.connect() as c:
                self.assertEqual(
                    c.exec_driver_sql(
                        "SELECT count(*) FROM vervfy_storage.objects WHERE reserved_bytes IS NULL"
                    ).scalar_one(),
                    2,
                )
        finally:
            with self.engine.begin() as c:
                c.exec_driver_sql(
                    "DROP TRIGGER reject_inventory_test ON vervfy_storage.objects"
                )
                c.exec_driver_sql("DROP FUNCTION public.reject_inventory_test()")

    def test_snapshot_works_in_read_only_transaction(self):
        with self.migrator.begin() as c:
            c.exec_driver_sql("SET TRANSACTION READ ONLY")
            self.assertEqual(len(snapshot(c, self.binding)["objects"]), 1)

    def test_bootstrap_unknown_revision_or_conflicting_binding_stays_closed(self):
        from dataclasses import replace

        with self.engine.connect() as c:
            transaction = c.begin()
            with self.assertRaisesRegex(RuntimeError, "different immutable binding"):
                initialize_namespace(
                    c, replace(self.binding, namespace_id=uuid.uuid4())
                )
            c.exec_driver_sql("UPDATE alembic_version SET version_num='unknown'")
            with self.assertRaisesRegex(RuntimeError, "supported lifecycle revision"):
                initialize_namespace(c, self.binding)
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT namespace_id FROM vervfy_storage.namespaces"
                ).scalar_one(),
                self.binding.namespace_id,
            )
            transaction.rollback()
