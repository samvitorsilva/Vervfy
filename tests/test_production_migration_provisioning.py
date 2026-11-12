"""Provisioning and runner checks against a disposable TLS PostgreSQL cluster."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from scripts.production_migration import (
    MigrationBlocked,
    REQUIRED_TABLES,
    TARGET_REVISION,
    ProductionTarget,
    preflight,
    validate_migration_chain,
)

ROOT = Path(__file__).resolve().parents[1]
PROVISION_SQL = ROOT / "scripts" / "provision_production_migration.sql"


class ProductionProvisioningPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binaries = ("initdb", "pg_ctl", "psql", "openssl")
        if os.getuid() == 0 or not all(shutil.which(binary) for binary in binaries):
            raise unittest.SkipTest("Requires non-root local PostgreSQL and OpenSSL binaries")

        cls.directory = tempfile.TemporaryDirectory(prefix="vervfy-production-test-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
        cls.data_dir = cls.root / "data"
        cls.cert_file = cls.root / "server.crt"
        cls.key_file = cls.root / "server.key"
        subprocess.run(
            [
                "openssl", "req", "-new", "-x509", "-days", "1", "-nodes",
                "-subj", "/CN=localhost", "-keyout", str(cls.key_file),
                "-out", str(cls.cert_file),
            ],
            env=cls.env,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "initdb", "-D", str(cls.data_dir), "-A", "trust", "-U", "postgres",
                "--no-locale", "--encoding=UTF8",
            ],
            env=cls.env,
            check=True,
            capture_output=True,
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            cls.port = listener.getsockname()[1]
        startup = subprocess.run(
            [
                "pg_ctl", "-D", str(cls.data_dir), "-l", str(cls.root / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {cls.port} -c ssl=on "
                f"-c unix_socket_directories={cls.root} "
                f"-c ssl_cert_file={cls.cert_file} -c ssl_key_file={cls.key_file}",
                "-w", "start",
            ],
            env=cls.env,
            check=False,
            capture_output=True,
        )
        if startup.returncode:
            log = (cls.root / "postgres.log").read_text()
            raise AssertionError(
                f"Disposable PostgreSQL failed to start:\n{startup.stderr.decode()}\n{log}"
            )
        cls.addClassCleanup(
            subprocess.run,
            ["pg_ctl", "-D", str(cls.data_dir), "-m", "fast", "-w", "stop"],
            env=cls.env,
            check=True,
            capture_output=True,
        )

        cls.bootstrap_url = sa.URL.create(
            "postgresql+psycopg",
            username="postgres",
            host="127.0.0.1",
            port=cls.port,
            database="postgres",
            query={"sslmode": "require"},
        )
        cls.bootstrap_engine = sa.create_engine(cls.bootstrap_url)
        cls.addClassCleanup(cls.bootstrap_engine.dispose)
        with cls.bootstrap_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE ROLE test_admin LOGIN SUPERUSER"
            )
        cls.admin_url = cls.bootstrap_url
        cls.admin_engine = sa.create_engine(cls.admin_url)
        cls.addClassCleanup(cls.admin_engine.dispose)
        with cls.admin_engine.connect() as connection:
            if connection.exec_driver_sql(
                "SELECT current_setting('server_version_num')::integer"
            ).scalar_one() < 160000:
                raise unittest.SkipTest("Requires PostgreSQL 16 or newer")
        with cls.admin_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE ROLE app_runtime NOLOGIN NOINHERIT NOSUPERUSER "
                "NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
            )

        cls._upgrade_baseline()
        with cls.admin_engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE public.users ADD COLUMN provisioning_test_id bigserial"
            )
            connection.exec_driver_sql("""
                REVOKE ALL ON TABLE public.users, public.tracks, public.favorites,
                    public.playlists, public.playlist_tracks, public.upload_jobs,
                    public.artist_photos, public.track_listens, public.artist_images,
                    public.track_cover_cache FROM app_runtime
            """)
            connection.exec_driver_sql(
                "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_runtime"
            )
        cls._run_provisioning_sql()

        cls.migration_url = cls.admin_url.set(username="vervfy_prod_migrator")
        cls.migration_engine = sa.create_engine(cls.migration_url)
        cls.addClassCleanup(cls.migration_engine.dispose)
        cls.target = ProductionTarget(
            url=cls.migration_url,
            project_ref="abcdefghijklmnopqrst",
            database="postgres",
            username="vervfy_prod_migrator",
        )

    @classmethod
    def _run_provisioning_sql(cls):
        result = subprocess.run(
            [
                "psql", "-X", "-v", "ON_ERROR_STOP=1",
                "--host", "127.0.0.1", "--port", str(cls.port),
                "--username", "postgres", "--dbname", "postgres",
                "--file", str(PROVISION_SQL),
            ],
            env=cls.env,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise AssertionError(
                f"Disposable provisioning SQL failed:\n{result.stdout}\n{result.stderr}"
            )

    @classmethod
    def _upgrade_baseline(cls):
        database_url = cls.admin_url.render_as_string(hide_password=False)
        environment = {
            "DATABASE_URL": database_url,
            "MIGRATION_DATABASE_URL": database_url,
        }
        with patch.dict(os.environ, environment):
            os.environ.pop("VERVFY_ENVIRONMENT", None)
            os.environ.pop("VERVFY_STAGING_PROFILE", None)
            command.upgrade(Config(str(ROOT / "alembic.ini")), "0019_track_listens")

    def test_postgres_application_acl_survives_ownership_transfers(self):
        with self.admin_engine.connect() as connection:
            self.assertIsNone(
                connection.execute(
                    sa.text(
                        "SELECT oid FROM pg_catalog.pg_roles "
                        "WHERE rolname='supabase_admin'"
                    )
                ).scalar_one_or_none()
            )
            for table in REQUIRED_TABLES:
                privileges = set(
                    connection.execute(
                        sa.text("""
                            SELECT acl.privilege_type
                            FROM pg_catalog.pg_class AS c
                            CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) AS acl
                            WHERE c.oid=pg_catalog.to_regclass(:table)
                              AND acl.grantee='postgres'::regrole
                        """),
                        {"table": f"public.{table}"},
                    ).scalars()
                )
                self.assertTrue(
                    {"SELECT", "INSERT", "UPDATE", "DELETE"} <= privileges,
                    (table, privileges),
                )
                owner = connection.execute(
                    sa.text("""
                        SELECT pg_catalog.pg_get_userbyid(c.relowner)
                        FROM pg_catalog.pg_class c
                        WHERE c.oid=pg_catalog.to_regclass(:table)
                    """),
                    {"table": f"public.{table}"},
                ).scalar_one()
                self.assertEqual(owner, "vervfy_prod_migrator", table)

            sequence_privileges = set(connection.execute(
                sa.text("""
                    SELECT acl.privilege_type
                    FROM pg_catalog.pg_class AS c
                    CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) AS acl
                    WHERE c.oid=pg_catalog.pg_get_serial_sequence(
                        'public.users', 'provisioning_test_id'
                    )::regclass
                      AND acl.grantee='postgres'::regrole
                """)
            ).scalars())
            self.assertEqual(sequence_privileges, {"USAGE", "SELECT", "UPDATE"})
            sequence_owner = connection.execute(
                sa.text("""
                    SELECT pg_catalog.pg_get_userbyid(c.relowner)
                    FROM pg_catalog.pg_class AS c
                    WHERE c.oid=pg_catalog.pg_get_serial_sequence(
                        'public.users', 'provisioning_test_id'
                    )::regclass
                """)
            ).scalar_one()
            self.assertEqual(sequence_owner, "vervfy_prod_migrator")

    def test_app_runtime_application_acl_after_ownership_transfers(self):
        with self.admin_engine.connect() as connection:
            schema_access = connection.execute(
                sa.text("""
                    SELECT has_database_privilege('app_runtime', 'postgres', 'CONNECT'),
                           has_schema_privilege('app_runtime', 'public', 'USAGE')
                """)
            ).one()
            self.assertEqual(tuple(schema_access), (True, True))

            for table in REQUIRED_TABLES:
                privileges = {
                    privilege: connection.execute(
                        sa.text(
                            "SELECT has_table_privilege("
                            "'app_runtime', :table, :privilege)"
                        ),
                        {"table": f"public.{table}", "privilege": privilege},
                    ).scalar_one()
                    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
                }
                self.assertEqual(
                    privileges,
                    {
                        "SELECT": True,
                        "INSERT": True,
                        "UPDATE": True,
                        "DELETE": True,
                    },
                    (table, privileges),
                )

            sequence_privileges = connection.execute(sa.text("""
                SELECT pg_catalog.has_sequence_privilege(
                           'app_runtime', seq.oid, 'USAGE'
                       )
                   AND pg_catalog.has_sequence_privilege(
                           'app_runtime', seq.oid, 'SELECT'
                       )
                   AND pg_catalog.has_sequence_privilege(
                           'app_runtime', seq.oid, 'UPDATE'
                       )
                FROM pg_catalog.pg_class AS seq
                JOIN pg_catalog.pg_namespace AS ns ON ns.oid = seq.relnamespace
                JOIN pg_catalog.pg_depend AS d
                  ON d.objid = seq.oid
                 AND d.classid = 'pg_catalog.pg_class'::regclass
                 AND d.refclassid = 'pg_catalog.pg_class'::regclass
                 AND d.deptype IN ('a', 'i')
                JOIN pg_catalog.pg_class AS tbl ON tbl.oid = d.refobjid
                JOIN pg_catalog.pg_namespace AS tbl_ns ON tbl_ns.oid = tbl.relnamespace
                WHERE seq.relkind = 'S'
                  AND tbl_ns.nspname = 'public'
                  AND tbl.relname = ANY(:tables)
            """), {"tables": list(REQUIRED_TABLES)}).scalars().all()
            self.assertTrue(sequence_privileges)
            self.assertTrue(all(sequence_privileges), sequence_privileges)

    def test_migrator_passes_runner_preflight_and_upgrades_0020_to_0028(self):
        validate_migration_chain()
        with self.migration_engine.connect() as connection:
            preflight(connection, self.target)
            session_target = ProductionTarget(
                url=self.migration_url,
                project_ref=self.target.project_ref,
                database="postgres",
                username="vervfy_prod_migrator",
                connection_mode="session",
            )
            preflight(connection, session_target)

            qualified_login_target = ProductionTarget(
                url=self.migration_url,
                project_ref=self.target.project_ref,
                database="postgres",
                username=f"vervfy_prod_migrator.{self.target.project_ref}",
                connection_mode="session",
            )
            with self.assertRaisesRegex(MigrationBlocked, "Connected login"):
                preflight(connection, qualified_login_target)

            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            with patch.dict(
                os.environ,
                {
                    "DATABASE_URL": self.migration_url.render_as_string(
                        hide_password=False
                    ),
                    "MIGRATION_DATABASE_URL": self.migration_url.render_as_string(
                        hide_password=False
                    ),
                },
            ):
                os.environ.pop("VERVFY_ENVIRONMENT", None)
                os.environ.pop("VERVFY_STAGING_PROFILE", None)
                command.upgrade(config, TARGET_REVISION)
            self.assertEqual(
                connection.execute(
                    sa.text("SELECT version_num FROM public.alembic_version")
                ).scalars().all(),
                [TARGET_REVISION],
            )

if __name__ == "__main__":
    unittest.main()
