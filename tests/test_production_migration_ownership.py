"""Ownership provisioning on disposable PostgreSQL; no Alembic migrations."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import psycopg

PROVISION_SQL = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "provision_production_migration.sql"
).read_text()
TABLES = (
    "users",
    "tracks",
    "favorites",
    "playlists",
    "playlist_tracks",
    "upload_jobs",
    "artist_photos",
    "track_listens",
    "artist_images",
    "track_cover_cache",
    "alembic_version",
)
ROLES = (
    "vervfy_prod_migrator",
    "app_runtime",
    "google_auth_lookup",
    "vervfy_identity_lookup_owner",
    "vervfy_identity_lookup",
)


class ProductionOwnershipPostgresTests(unittest.TestCase):
    def setUp(self):
        if os.getuid() == 0 or not all(
            shutil.which(binary) for binary in ("initdb", "pg_ctl", "postgres")
        ):
            self.skipTest("Requires non-root local PostgreSQL binaries")
        directory = tempfile.TemporaryDirectory(prefix="vervfy-owner-test-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        data = root / "data"
        env = {
            key: value for key, value in os.environ.items() if not key.startswith("PG")
        }
        subprocess.run(
            [
                "initdb",
                "-D",
                str(data),
                "-A",
                "trust",
                "-U",
                "supabase_admin",
                "--no-locale",
                "--encoding=UTF8",
            ],
            env=env,
            check=True,
            capture_output=True,
        )
        # Unix socket in a unique temporary directory; no TCP or hosted targets.
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(data),
                "-l",
                str(root / "postgres.log"),
                "-o",
                f"-c listen_addresses='' -c unix_socket_directories={root}",
                "-w",
                "start",
            ],
            env=env,
            check=True,
            capture_output=True,
        )
        self.addCleanup(
            subprocess.run,
            ["pg_ctl", "-D", str(data), "-m", "fast", "-w", "stop"],
            env=env,
            check=True,
            capture_output=True,
        )
        self.admin = psycopg.connect(
            host=str(root),
            port=5432,
            dbname="postgres",
            user="supabase_admin",
            autocommit=True,
        )
        self.addCleanup(self.admin.close)
        if int(self.admin.execute("SHOW server_version_num").fetchone()[0]) < 160000:
            self.skipTest("Requires PostgreSQL 16 or newer")
        self.admin.execute("""
            CREATE ROLE postgres LOGIN CREATEROLE CREATEDB NOSUPERUSER NOBYPASSRLS;
            ALTER DATABASE postgres OWNER TO postgres;
            ALTER SCHEMA public OWNER TO postgres;
        """)
        self.postgres = psycopg.connect(
            host=str(root),
            port=5432,
            dbname="postgres",
            user="postgres",
            autocommit=True,
        )
        self.addCleanup(self.postgres.close)
        # Minimal revision-0019 catalog fixture, without running migrations.
        self.postgres.execute("""
            CREATE TABLE public.users (id bigserial PRIMARY KEY, session_version integer);
            CREATE TABLE public.tracks (
                id bigint, cover_source text,
                CONSTRAINT ck_tracks_cover_source CHECK (cover_source IS NULL)
            );
            CREATE TABLE public.alembic_version (version_num text);
            INSERT INTO public.alembic_version VALUES ('0019_track_listens');
            INSERT INTO public.users (session_version) VALUES (7);
        """)
        for table in TABLES[2:-1]:
            self.postgres.execute(f"CREATE TABLE public.{table} (id bigint)")

    def managed_roles(self):
        for role in ROLES:
            login = (
                "LOGIN"
                if role in ("vervfy_prod_migrator", "google_auth_lookup")
                else "NOLOGIN"
            )
            self.admin.execute(
                f"CREATE ROLE {role} {login} NOINHERIT NOSUPERUSER NOBYPASSRLS "
                "NOCREATEDB NOCREATEROLE NOREPLICATION"
            )
            self.admin.execute(
                f"GRANT {role} TO postgres WITH ADMIN TRUE, INHERIT FALSE, SET FALSE"
            )

    def managed_memberships(self):
        return self.admin.execute("""
            SELECT roleid, member, grantor, admin_option, inherit_option, set_option
            FROM pg_auth_members WHERE grantor = 'supabase_admin'::regrole
            ORDER BY roleid, member
        """).fetchall()

    def verify_provisioned(self):
        self.assertEqual(
            self.postgres.execute("""
            SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user
        """).fetchone(),
            (False, False),
        )
        self.assertEqual(
            self.postgres.execute("""
            SELECT pg_has_role('postgres', 'vervfy_prod_migrator', 'SET'),
                   pg_has_role('postgres', 'vervfy_prod_migrator', 'USAGE')
        """).fetchone(),
            (True, True),
        )
        self.assertEqual(
            self.postgres.execute("""
            SELECT rolcanlogin, rolinherit, rolsuper, rolbypassrls, rolcreatedb,
                   rolcreaterole, rolreplication
            FROM pg_roles WHERE rolname = 'vervfy_prod_migrator'
        """).fetchone(),
            (True, False, False, False, False, False, False),
        )
        for table in (*TABLES, "users_id_seq"):
            self.assertEqual(
                self.postgres.execute(
                    "SELECT relowner::regrole::text FROM pg_class WHERE oid = %s::regclass",
                    (f"public.{table}",),
                ).fetchone(),
                ("vervfy_prod_migrator",),
            )
        for role in ("postgres", "app_runtime"):
            for table in TABLES[:-1]:
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    self.assertTrue(
                        self.postgres.execute(
                            "SELECT has_table_privilege(%s, %s, %s)",
                            (role, f"public.{table}", privilege),
                        ).fetchone()[0]
                    )
            for privilege in ("USAGE", "SELECT", "UPDATE"):
                self.assertTrue(
                    self.postgres.execute(
                        "SELECT has_sequence_privilege(%s, 'public.users_id_seq', %s)",
                        (role, privilege),
                    ).fetchone()[0]
                )
        self.assertEqual(
            self.postgres.execute("""
            SELECT roleid::regrole::text, admin_option, inherit_option, set_option
            FROM pg_auth_members WHERE member = 'vervfy_prod_migrator'::regrole
        """).fetchall(),
            [("vervfy_identity_lookup_owner", False, False, True)],
        )
        self.assertEqual(
            self.postgres.execute("""
            SELECT count(*) FROM pg_auth_members WHERE member = 'app_runtime'::regrole
        """).fetchone(),
            (0,),
        )
        self.assertEqual(
            self.postgres.execute(
                "SELECT session_version FROM public.users"
            ).fetchall(),
            [(7,)],
        )
        self.assertEqual(
            self.postgres.execute(
                "SELECT version_num FROM public.alembic_version"
            ).fetchall(),
            [("0019_track_listens",)],
        )

    def test_managed_admin_membership_reproduces_42501_then_provisions(self):
        self.managed_roles()
        managed = self.managed_memberships()
        # ADMIN is present but SET is false: reproduce the exact failing statement.
        self.postgres.execute(
            "GRANT USAGE, CREATE ON SCHEMA public TO vervfy_prod_migrator"
        )
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as error:
            self.postgres.execute(
                "ALTER TABLE public.users OWNER TO vervfy_prod_migrator"
            )
        self.assertEqual(error.exception.sqlstate, "42501")
        self.assertEqual(
            error.exception.diag.message_primary,
            'must be able to SET ROLE "vervfy_prod_migrator"',
        )
        self.postgres.execute(PROVISION_SQL)
        self.verify_provisioned()
        self.assertEqual(self.managed_memberships(), managed)
        # Repeating provisioning must preserve both grantors' membership rows.
        self.postgres.execute(PROVISION_SQL)
        self.verify_provisioned()
        self.assertEqual(self.managed_memberships(), managed)

    def test_new_roles_get_required_membership(self):
        self.postgres.execute(PROVISION_SQL)
        self.verify_provisioned()

    def test_existing_postgres_grant_gets_set_and_inherit(self):
        self.managed_roles()
        self.postgres.execute("""
            GRANT vervfy_prod_migrator TO postgres
                WITH ADMIN FALSE, INHERIT FALSE, SET FALSE GRANTED BY postgres
        """)
        self.postgres.execute(PROVISION_SQL)
        self.verify_provisioned()
        self.assertEqual(
            self.postgres.execute("""
            SELECT admin_option, inherit_option, set_option FROM pg_auth_members
            WHERE roleid = 'vervfy_prod_migrator'::regrole
              AND member = 'postgres'::regrole AND grantor = 'postgres'::regrole
        """).fetchone(),
            (False, True, True),
        )

    def test_security_failure_rolls_back_membership_ownership_and_acls(self):
        self.managed_roles()
        self.admin.execute("GRANT vervfy_prod_migrator TO app_runtime")
        before = self.admin.execute(
            "SELECT * FROM pg_auth_members ORDER BY oid"
        ).fetchall()
        with self.assertRaisesRegex(
            psycopg.errors.RaiseException, "app_runtime inherits"
        ):
            self.postgres.execute(PROVISION_SQL)
        self.postgres.execute("ROLLBACK")
        self.assertEqual(
            self.admin.execute("SELECT * FROM pg_auth_members ORDER BY oid").fetchall(),
            before,
        )
        for table in (*TABLES, "users_id_seq"):
            self.assertEqual(
                self.admin.execute(
                    "SELECT relowner::regrole::text, relacl FROM pg_class WHERE oid = %s::regclass",
                    (f"public.{table}",),
                ).fetchone(),
                ("postgres", None),
            )

    def test_existing_lookup_owner_set_edge_is_exactly_allowed(self):
        import importlib.util

        import sqlalchemy as sa

        from scripts.production_migration import _check_role_graph

        spec = importlib.util.spec_from_file_location(
            "migration_0022",
            Path(__file__).resolve().parents[1]
            / "alembic/versions/0022_provider_identity_lookup.py",
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.managed_roles()
        self.postgres.execute("""
            GRANT vervfy_identity_lookup_owner TO postgres
                WITH ADMIN FALSE, INHERIT FALSE, SET TRUE GRANTED BY postgres
        """)
        before = self.managed_memberships()
        self.postgres.execute(PROVISION_SQL)
        self.assertEqual(self.managed_memberships(), before)
        engine = sa.create_engine(
            "postgresql+psycopg://",
            creator=lambda: psycopg.connect(
                host=self.postgres.info.host,
                port=5432,
                dbname="postgres",
                user="vervfy_prod_migrator",
            ),
        )
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            _check_role_graph(connection, "vervfy_prod_migrator")
            # Invoke the exact membership validator imported by 0022, not upgrade().
            migration.assert_role_memberships(
                connection,
                migration.OWNER,
                [
                    ("vervfy_prod_migrator", "postgres", False, False, True),
                ],
            )
        self.postgres.execute("""
            GRANT vervfy_identity_lookup_owner TO postgres
                WITH INHERIT TRUE GRANTED BY postgres
        """)
        with self.assertRaisesRegex(
            psycopg.errors.RaiseException, "Lookup-owner membership graph"
        ):
            self.postgres.execute(PROVISION_SQL)
        self.postgres.execute("ROLLBACK")
        with engine.connect() as connection:
            with self.assertRaisesRegex(RuntimeError, "Unexpected membership graph"):
                _check_role_graph(connection, "vervfy_prod_migrator")
            with self.assertRaisesRegex(RuntimeError, "Unexpected membership graph"):
                migration.assert_role_memberships(
                    connection,
                    migration.OWNER,
                    [
                        ("vervfy_prod_migrator", "postgres", False, False, True),
                    ],
                )
