"""Real runner guards over verified TLS against disposable local PostgreSQL."""

import socket
import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

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
            cls.object_ids_by_tenant = {"a": [], "b": []}
            objects = []
            states = ("ready", "live", "retired", "hold", "deleted", "ready", "live")
            for index, state in enumerate(states):
                object_id = uuid4()
                tenant_id = "a" if index < 2 else "b" if index < 5 else None
                classification = "managed" if tenant_id else "legacy"
                if tenant_id:
                    cls.object_ids_by_tenant[tenant_id].append(str(object_id))
                objects.append(
                    {
                        "id": object_id,
                        "tenant_id": tenant_id,
                        "path": f"runner-fixture/{index}.wav",
                        "kind": "audio" if tenant_id else "legacy",
                        "classification": classification,
                        "state": state,
                        "reservation_token": uuid4() if tenant_id else None,
                        "upload_verified": state in ("ready", "live"),
                    }
                )
            c.exec_driver_sql("SET ROLE vervfy_storage_lifecycle_owner")
            c.execute(
                sa.text("""
                INSERT INTO vervfy_storage.objects(
                    id,namespace_id,tenant_id,path,kind,classification,state,
                    reservation_token,upload_verified
                ) VALUES (
                    :id,1,:tenant_id,:path,:kind,:classification,:state,
                    :reservation_token,:upload_verified
                )
            """),
                objects,
            )
            c.exec_driver_sql("RESET ROLE")
            if cls.start_revision in runner.AUTH_SESSIONS_PRESENT_REVISIONS:
                c.exec_driver_sql("""
                    INSERT INTO public.auth_sessions(id,user_id,created_at,expires_at)
                    VALUES ('runner-session-0032','a',1,4102444800)
                """)
        with cls.engine.connect() as c:
            cls.pre_storage_snapshot = cls.storage_snapshot(c)
            cls.pre_security_snapshot = cls.security_snapshot(c)
            cls.pre_auth_sessions_snapshot = (
                cls.auth_sessions_snapshot(c)
                if cls.start_revision in runner.AUTH_SESSIONS_PRESENT_REVISIONS
                else None
            )

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

    @staticmethod
    def storage_snapshot(connection):
        return connection.exec_driver_sql("""
            SELECT id,namespace_id,tenant_id,path,kind,classification,state,
                   reservation_token,upload_verified
            FROM vervfy_storage.objects ORDER BY path
        """).all()

    @staticmethod
    def security_snapshot(connection):
        relations = connection.exec_driver_sql("""
            SELECT n.nspname,c.relname,c.relowner::regrole::text,
                   c.relrowsecurity,c.relforcerowsecurity
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE (n.nspname='public' AND c.relname IN (
                'users','tracks','favorites','playlists','playlist_tracks',
                'upload_jobs','artist_photos','track_listens','artist_images',
                'track_cover_cache'
            )) OR (n.nspname='vervfy_storage' AND c.relname IN (
                'namespaces','objects','cleanup_jobs'
            ))
            ORDER BY n.nspname,c.relname
        """).all()
        policies = connection.exec_driver_sql("""
            SELECT schemaname,tablename,policyname,permissive,roles::text,
                   cmd,qual,with_check
            FROM pg_catalog.pg_policies
            WHERE (schemaname='public' AND tablename IN (
                'users','tracks','favorites','playlists','playlist_tracks',
                'upload_jobs','artist_photos','track_listens','artist_images',
                'track_cover_cache'
            )) OR (schemaname='vervfy_storage' AND tablename IN (
                'namespaces','objects','cleanup_jobs'
            ))
            ORDER BY schemaname,tablename,policyname
        """).all()
        return relations, policies

    @staticmethod
    def auth_sessions_snapshot(connection):
        return connection.exec_driver_sql("""
            SELECT id,user_id,created_at,expires_at
            FROM public.auth_sessions ORDER BY id
        """).all()

    def assert_preflight_blocks(self, mutation, restoration):
        with self.engine.begin() as c:
            c.exec_driver_sql(mutation)
        try:
            with self.assertRaises(runner.MigrationBlocked):
                runner.run_check(self.target())
        finally:
            with self.engine.begin() as c:
                for statement in (
                    restoration if isinstance(restoration, tuple) else (restoration,)
                ):
                    c.exec_driver_sql(statement)

    def visible_storage_ids(self, tenant_id):
        with self.engine.begin() as c:
            c.exec_driver_sql("SET LOCAL ROLE app_runtime")
            c.execute(
                sa.text("SELECT set_config('app.current_user_id',:user_id,true)"),
                {"user_id": tenant_id},
            )
            return (
                c.exec_driver_sql(
                    "SELECT id::text FROM vervfy_storage.objects ORDER BY id"
                )
                .scalars()
                .all()
            )

    def test_guarded_upgrade_preserves_data_and_rolls_back_on_postflight_rejection(
        self,
    ):
        runner.validate_migration_chain()
        self.assertEqual(len(self.pre_storage_snapshot), 7)
        self.assertEqual(
            self.visible_storage_ids("a"),
            sorted(self.object_ids_by_tenant["a"]),
        )
        self.assertEqual(
            self.visible_storage_ids("b"),
            sorted(self.object_ids_by_tenant["b"]),
        )
        if self.start_revision == runner.AUTH_SESSIONS_REVISION:
            with self.engine.connect() as c:
                self.assertEqual(
                    self.auth_sessions_snapshot(c),
                    [("runner-session-0032", "a", 1.0, 4102444800.0)],
                )
                claims = c.exec_driver_sql("""
                    SELECT
                      has_function_privilege(
                        'vervfy_storage_lifecycle_owner',
                        'vervfy_storage.claim_next_cleanup()','EXECUTE'
                      ),
                      has_function_privilege(
                        'vervfy_storage_cleanup',
                        'vervfy_storage.claim_next_cleanup()','EXECUTE'
                      ),
                      has_function_privilege(
                        'storage_cleanup_worker',
                        'vervfy_storage.claim_next_cleanup()','EXECUTE'
                      ),
                      has_function_privilege(
                        'app_runtime',
                        'vervfy_storage.claim_next_cleanup()','EXECUTE'
                      )
                """).one()
                self.assertEqual(tuple(claims), (True, True, True, False))
            self.assert_preflight_blocks(
                "GRANT UPDATE ON public.auth_sessions TO app_runtime",
                "REVOKE UPDATE ON public.auth_sessions FROM app_runtime",
            )
            self.assert_preflight_blocks(
                "ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE public.auth_sessions DISABLE ROW LEVEL SECURITY",
            )
            self.assert_preflight_blocks(
                "ALTER TABLE public.auth_sessions OWNER TO app_runtime",
                (
                    "ALTER TABLE public.auth_sessions OWNER TO migration_owner",
                    "REVOKE ALL ON public.auth_sessions FROM app_runtime",
                    "GRANT SELECT,INSERT,DELETE ON public.auth_sessions TO app_runtime",
                ),
            )
            self.assert_preflight_blocks(
                "REVOKE EXECUTE ON FUNCTION "
                "vervfy_storage.claim_next_cleanup() "
                "FROM vervfy_storage_cleanup",
                "GRANT EXECUTE ON FUNCTION "
                "vervfy_storage.claim_next_cleanup() "
                "TO vervfy_storage_cleanup",
            )

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
            self.assertEqual(self.storage_snapshot(c), self.pre_storage_snapshot)
            self.assertEqual(self.security_snapshot(c), self.pre_security_snapshot)
            if self.pre_auth_sessions_snapshot is not None:
                self.assertEqual(
                    self.auth_sessions_snapshot(c), self.pre_auth_sessions_snapshot
                )
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
            self.assertEqual(self.storage_snapshot(c), self.pre_storage_snapshot)
            self.assertEqual(self.security_snapshot(c), self.pre_security_snapshot)
            self.assertEqual(
                c.exec_driver_sql("""
                    SELECT count(*) FROM vervfy_storage.objects
                    WHERE reserved_bytes IS NULL
                """).scalar_one(),
                7,
            )
            if self.pre_auth_sessions_snapshot is not None:
                self.assertEqual(
                    self.auth_sessions_snapshot(c), self.pre_auth_sessions_snapshot
                )
            session_security = c.exec_driver_sql("""
                SELECT pg_catalog.pg_get_userbyid(relowner),
                       relrowsecurity,relforcerowsecurity,
                       has_table_privilege('app_runtime','public.auth_sessions','SELECT'),
                       has_table_privilege('app_runtime','public.auth_sessions','INSERT'),
                       has_table_privilege('app_runtime','public.auth_sessions','UPDATE'),
                       has_table_privilege('app_runtime','public.auth_sessions','DELETE')
                FROM pg_catalog.pg_class
                WHERE oid='public.auth_sessions'::regclass
            """).one()
            self.assertEqual(
                tuple(session_security),
                ("migration_owner", False, False, True, True, False, True),
            )
            claims = c.exec_driver_sql("""
                SELECT
                  has_function_privilege(
                    'vervfy_storage_lifecycle_owner',
                    'vervfy_storage.claim_next_cleanup()','EXECUTE'
                  ),
                  has_function_privilege(
                    'vervfy_storage_cleanup',
                    'vervfy_storage.claim_next_cleanup()','EXECUTE'
                  ),
                  has_function_privilege(
                    'storage_cleanup_worker',
                    'vervfy_storage.claim_next_cleanup()','EXECUTE'
                  ),
                  has_function_privilege(
                    'app_runtime',
                    'vervfy_storage.claim_next_cleanup()','EXECUTE'
                  )
            """).one()
            self.assertEqual(tuple(claims), (True, False, False, False))
        self.assertEqual(
            self.visible_storage_ids("a"),
            sorted(self.object_ids_by_tenant["a"]),
        )
        self.assertEqual(
            self.visible_storage_ids("b"),
            sorted(self.object_ids_by_tenant["b"]),
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


class RunnerFrom0032Tests(Runner0034Tests):
    start_revision = runner.AUTH_SESSIONS_REVISION
