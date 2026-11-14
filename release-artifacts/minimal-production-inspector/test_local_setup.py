"""Disposable Unix-socket PostgreSQL only. No environment database credentials."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROLE = "vervfy_prod_inspector"


class InspectorSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getuid() == 0:
            raise RuntimeError(
                "Run as non-root: local cluster required, never a hosted fallback"
            )
        cls.tmp = tempfile.TemporaryDirectory(prefix="vervfy-inspector-pg-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        for command in ("initdb", "pg_ctl", "psql"):
            if not shutil.which(command, path=cls.env["PATH"]):
                raise RuntimeError(
                    "Local PostgreSQL tools required; no remote fallback"
                )
        subprocess.run(
            [
                "initdb",
                "-D",
                str(cls.root / "data"),
                "-A",
                "trust",
                "-U",
                "fixture_admin",
                "--no-locale",
                "--encoding=UTF8",
            ],
            env=cls.env,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(cls.root / "data"),
                "-l",
                str(cls.root / "postgres.log"),
                "-o",
                f"-k {cls.root} -c listen_addresses='' -c unix_socket_permissions=0700",
                "-w",
                "start",
            ],
            env=cls.env,
            check=True,
            capture_output=True,
        )
        cls.addClassCleanup(
            subprocess.run,
            ["pg_ctl", "-D", str(cls.root / "data"), "-m", "fast", "-w", "stop"],
            env=cls.env,
            check=True,
            capture_output=True,
        )
        cls.execute("CREATE ROLE fixture_provisioner LOGIN CREATEROLE NOINHERIT")
        cls.execute(
            "GRANT CONNECT ON DATABASE postgres TO fixture_provisioner WITH GRANT OPTION"
        )

    @classmethod
    def execute(cls, sql=None, *, file=None, role="fixture_admin", check=True):
        cmd = [
            "psql",
            "-X",
            "--no-password",
            "-h",
            str(cls.root),
            "-U",
            role,
            "-d",
            "postgres",
            "--set=ON_ERROR_STOP=1",
            "--set=VERBOSITY=terse",
            "-At",
        ]
        if file:
            cmd += ["--file", str(file)]
        else:
            cmd += ["--command", sql]
        result = subprocess.run(
            cmd, env=cls.env, text=True, capture_output=True, check=False
        )
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result

    def setUp(self):
        if self.exists():
            self.execute(f"DROP OWNED BY {ROLE}; DROP ROLE {ROLE}")
        self.execute("""DROP SCHEMA public CASCADE;
            CREATE SCHEMA public AUTHORIZATION fixture_provisioner;
            REVOKE ALL ON SCHEMA public FROM PUBLIC;
            REVOKE ALL ON DATABASE postgres FROM PUBLIC;
            REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
            SET ROLE fixture_provisioner;
            CREATE TABLE public.alembic_version(version_num varchar(32) NOT NULL, extra_metadata text);
            INSERT INTO public.alembic_version VALUES ('0020_playlist_last_played','synthetic-not-permitted');
            CREATE TABLE public.users(id text, email text);
            INSERT INTO public.users VALUES ('synthetic-id','synthetic@example.invalid');
            CREATE SEQUENCE public.user_sequence;
            RESET ROLE;
        """)
        # Controlled success fixture only. These are NOT production instructions:
        # remove default PUBLIC LOB execution in this disposable database.
        self.execute("""DO $fixture$ DECLARE fixture_proc record; BEGIN
            FOR fixture_proc IN SELECT p.oid::regprocedure AS signature FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='pg_catalog' AND p.proname IN
            ('lo_create','lo_creat','lo_from_bytea','lo_import','lo_put','lo_unlink','lowrite','lo_truncate','lo_truncate64')
            LOOP EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC',fixture_proc.signature); END LOOP;
            END $fixture$;""")

    def exists(self):
        return (
            self.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='vervfy_prod_inspector')"
            ).stdout.strip()
            == "t"
        )

    def create(self, **kwargs):
        return self.execute(file=ROOT / "10-create-inspector.sql", **kwargs)

    def rejected(self, message):
        result = self.create(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertFalse(
            self.exists(), "Failure must roll back CREATE ROLE and every grant"
        )

    def test_readonly_absence_check_preserves_database(self):
        self.assertFalse(self.exists())
        result = self.execute(file=ROOT / "00-confirm-absence.sql")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.exists())

    def test_success_authentication_catalog_and_revision_column_only(self):
        self.create()
        self.assertTrue(self.exists())
        self.assertEqual(
            self.execute(
                "SELECT version_num FROM ONLY public.alembic_version", role=ROLE
            ).stdout.strip(),
            "0020_playlist_last_played",
        )
        self.assertGreater(
            int(
                self.execute(
                    "SELECT count(*) FROM pg_catalog.pg_class", role=ROLE
                ).stdout.strip()
            ),
            0,
        )
        self.assertEqual(
            self.execute(
                "SHOW default_transaction_read_only", role=ROLE
            ).stdout.strip(),
            "on",
        )
        self.execute(file=ROOT / "20-inspector-readonly.sql", role=ROLE)
        for sql in (
            "SELECT * FROM public.users",
            "SELECT extra_metadata FROM public.alembic_version",
            "SET default_transaction_read_only=off; INSERT INTO public.users VALUES ('x','local-only')",
            "SET default_transaction_read_only=off; UPDATE public.alembic_version SET version_num='0027_storage_lifecycle'",
            "SET default_transaction_read_only=off; CREATE TABLE public.forbidden(id int)",
            "SET default_transaction_read_only=off; CREATE ROLE forbidden_role",
            "SET ROLE fixture_provisioner",
            "SELECT nextval('public.user_sequence')",
            "SET default_transaction_read_only=off; SELECT pg_catalog.lo_create(0)",
        ):
            with self.subTest(sql=sql):
                self.assertNotEqual(
                    self.execute(sql, role=ROLE, check=False).returncode, 0
                )
        self.assertEqual(
            self.execute(
                "SELECT count(*) FROM pg_auth_members WHERE member='vervfy_prod_inspector'::regrole OR roleid='vervfy_prod_inspector'::regrole"
            ).stdout.strip(),
            "0",
        )
        self.assertEqual(
            self.execute(
                "SELECT rolpassword IS NULL FROM pg_authid WHERE rolname='vervfy_prod_inspector'"
            ).stdout.strip(),
            "t",
        )

    def test_supabase_style_public_temp_causes_atomic_refusal(self):
        self.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        self.rejected("database CREATE/TEMP")
        self.assertEqual(
            self.execute(
                "SELECT has_database_privilege('fixture_provisioner','postgres','TEMP')"
            ).stdout.strip(),
            "t",
        )

    def test_other_database_public_connect_causes_atomic_refusal(self):
        self.execute("GRANT CONNECT ON DATABASE template1 TO PUBLIC")
        self.rejected("access to another database")

    def test_public_large_object_execution_causes_atomic_refusal(self):
        self.execute("GRANT EXECUTE ON FUNCTION pg_catalog.lo_create(oid) TO PUBLIC")
        self.rejected("large-object write routine")

    def test_public_user_record_read_causes_atomic_refusal(self):
        self.execute("GRANT SELECT ON public.users TO PUBLIC")
        self.rejected("access to non-release records")

    def test_public_write_causes_atomic_refusal(self):
        self.execute("GRANT INSERT ON public.users TO PUBLIC")
        self.rejected("access to non-release records")

    def test_public_callable_function_causes_atomic_refusal(self):
        self.execute("""GRANT USAGE ON SCHEMA public TO PUBLIC;
          CREATE FUNCTION public.fixture_reader() RETURNS text LANGUAGE sql AS
          $$ SELECT 'synthetic-only'::text $$""")
        self.rejected("large-object write routine")

    def test_missing_revision_table_rolls_back_without_creating_table(self):
        self.execute("DROP TABLE public.alembic_version")
        self.rejected("revision metadata missing")
        self.assertEqual(
            self.execute(
                "SELECT to_regclass('public.alembic_version') IS NULL"
            ).stdout.strip(),
            "t",
        )

    def test_existing_role_is_preserved(self):
        self.create()
        before = self.execute(
            "SELECT oid,rolcanlogin,rolinherit,rolconnlimit FROM pg_roles WHERE rolname='vervfy_prod_inspector'"
        ).stdout
        result = self.create(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(
            self.execute(
                "SELECT oid,rolcanlogin,rolinherit,rolconnlimit FROM pg_roles WHERE rolname='vervfy_prod_inspector'"
            ).stdout,
            before,
        )

    def test_non_superuser_creator_automatic_admin_edge_is_not_ignored(self):
        result = self.create(role="fixture_provisioner", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("membership conflicts", result.stderr)
        self.assertFalse(self.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
