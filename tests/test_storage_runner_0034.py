"""Real runner guards over verified TLS against disposable local PostgreSQL."""

import socket
import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import sqlalchemy as sa
import test_staging_migrations as fixtures

from alembic import command
from scripts import storage_production_migration as runner


class Runner0034Tests(unittest.TestCase):
    start_revision = runner.START_REVISION
    account_snapshot = staticmethod(fixtures.StagingPostgresTests.account_snapshot)

    @classmethod
    def setUpClass(cls):
        original = command.upgrade

        def baseline(config, revision, *args, **kwargs):
            return original(
                config,
                cls.start_revision if revision == "head" else revision,
                *args,
                **kwargs,
            )

        with patch.object(command, "upgrade", baseline):
            fixtures.StagingPostgresTests.setUpClass.__func__(cls)
        cert, key = cls.root / "server.crt", cls.root / "server.key"
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-nodes",
                "-newkey",
                "rsa:2048",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=IP:127.0.0.1",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            capture_output=True,
        )
        key.chmod(0o600)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with (cls.root / "data/postgresql.conf").open("a") as out:
            out.write(
                f"\nssl=on\nssl_cert_file='{cert}'\nssl_key_file='{key}'\nlisten_addresses='127.0.0.1'\nport={port}\n"
            )
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(cls.root / "data"),
                "-l",
                str(cls.root / "log"),
                "-o",
                f"-p {port} -k {cls.root} -c listen_addresses=127.0.0.1 -c unix_socket_permissions=0700",
                "-w",
                "restart",
            ],
            check=True,
            capture_output=True,
        )
        cls.engine.dispose()
        cls.url = sa.URL.create(
            "postgresql+psycopg",
            username="test_admin",
            host="127.0.0.1",
            port=port,
            database="postgres",
            query={"sslmode": "verify-full", "sslrootcert": str(cert)},
        )
        cls.engine = sa.create_engine(cls.url)
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.begin() as c:
            # Model the reviewed grantor topology inside this new test cluster.
            # No runtime permissions or runner guards are modified.
            c.exec_driver_sql("""UPDATE pg_catalog.pg_auth_members SET grantor='postgres'::regrole
                WHERE roleid IN ('vervfy_storage_lifecycle_owner'::regrole,'vervfy_storage_cleanup'::regrole)
                  AND member IN ('migration_owner'::regrole,'storage_cleanup_worker'::regrole)""")
            c.exec_driver_sql("""INSERT INTO vervfy_storage.namespaces VALUES
                (1,'31daf7cc-8563-411f-94c7-944d607d1ef1','production',
                'https://llxmskxxchpmeavorusj.supabase.co','songs',false)""")

    def target(self):
        return runner.ProductionTarget(
            self.url.set(username="migration_owner"),
            runner.PRODUCTION_PROJECT_REF,
            "postgres",
            "migration_owner",
            start_revision=self.start_revision,
        )

    def upgrade(self):
        expiry = (datetime.now(UTC) + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        runner.run_upgrade(self.target(), expiry)

    def test_guarded_upgrade_preserves_data_and_rolls_back_on_postflight_rejection(
        self,
    ):
        runner.validate_migration_chain()
        original_postflight = runner._verify_followup_result

        def rejected_postflight(connection):
            original_postflight(connection)
            raise runner.MigrationBlocked("Synthetic final verification rejection")

        with (
            patch.object(runner, "_verify_followup_result", rejected_postflight),
            self.assertRaisesRegex(runner.MigrationBlocked, "Synthetic final"),
        ):
            self.upgrade()
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one(),
                self.start_revision,
            )
            self.assertIsNone(
                c.exec_driver_sql(
                    "SELECT to_regclass('vervfy_storage.quota_policy')"
                ).scalar_one()
            )
            self.assertEqual(self.account_snapshot(c), self.pre_upgrade_snapshot)
        self.upgrade()
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one(),
                runner.TARGET_REVISION,
            )
            self.assertEqual(self.account_snapshot(c), self.pre_upgrade_snapshot)
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )
        from scripts.storage_inventory_reconcile import verify_connection

        engine = sa.create_engine(self.target().url)
        try:
            with engine.begin() as c:
                c.exec_driver_sql("SET TRANSACTION READ ONLY")
                verify_connection(c, self.target())
        finally:
            engine.dispose()
        # The same fixture also checks a wrong starting boundary is rejected.
        with self.assertRaisesRegex(runner.MigrationBlocked, "Expected exactly"):
            self.upgrade()


class RunnerFrom0033Tests(Runner0034Tests):
    start_revision = "0033_cleanup_claims_disabled"
