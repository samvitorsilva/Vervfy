"""Phase 2: disposable PostgreSQL only; never accesses Storage or hosted URLs."""

import importlib.util
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from storage_lifecycle_fixture import (
    initialize_disposable_namespace,
    provision_storage_roles,
)

import audio_store
from alembic import command
from storage_namespace import ManagedStorageBoundary

ROOT = Path(__file__).resolve().parents[1]
OWNER = "vervfy_storage_lifecycle_owner"


class StorageLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getuid() == 0 or not all(shutil.which(x) for x in ("initdb", "pg_ctl")):
            raise unittest.SkipTest("Requires non-root disposable PostgreSQL binaries")
        cls.directory = tempfile.TemporaryDirectory(prefix="vervfy-storage-pg-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
        subprocess.run(
            [
                "initdb",
                "-D",
                str(root / "data"),
                "-A",
                "trust",
                "-U",
                "test_admin",
                "--no-locale",
                "--encoding=UTF8",
            ],
            env=env,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(root / "data"),
                "-l",
                str(root / "postgres.log"),
                "-o",
                f"-k {root} -c listen_addresses='' -c unix_socket_permissions=0700",
                "-w",
                "start",
            ],
            env=env,
            check=True,
            capture_output=True,
        )
        cls.addClassCleanup(
            subprocess.run,
            ["pg_ctl", "-D", str(root / "data"), "-m", "fast", "-w", "stop"],
            env=env,
            check=True,
            capture_output=True,
        )
        cls.url = sa.URL.create(
            "postgresql+psycopg",
            username="test_admin",
            database="postgres",
            query={"host": str(root)},
        )
        cls.admin = sa.create_engine(cls.url)
        cls.addClassCleanup(cls.admin.dispose)
        with cls.admin.begin() as c:
            c.exec_driver_sql(
                "CREATE ROLE migration_owner LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS"
            )
            c.exec_driver_sql("GRANT CREATE ON DATABASE postgres TO migration_owner")
            c.exec_driver_sql("ALTER SCHEMA public OWNER TO migration_owner")
            c.exec_driver_sql("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            for name in ("app_runtime", "google_auth_lookup"):
                c.exec_driver_sql(
                    f"CREATE ROLE {name} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS"
                )
            for name in ("vervfy_identity_lookup_owner", "vervfy_identity_lookup"):
                c.exec_driver_sql(
                    f"CREATE ROLE {name} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS"
                )
            c.exec_driver_sql(
                "GRANT vervfy_identity_lookup_owner TO migration_owner WITH INHERIT FALSE, SET TRUE"
            )
            c.exec_driver_sql(
                "GRANT vervfy_identity_lookup TO google_auth_lookup WITH INHERIT TRUE, SET FALSE, ADMIN FALSE"
            )
            provision_storage_roles(c)
        cls.migration_url = cls.url.set(username="migration_owner").render_as_string(
            hide_password=False
        )
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": cls.migration_url,
                "MIGRATION_DATABASE_URL": cls.migration_url,
            },
        ):
            command.upgrade(
                Config(str(ROOT / "alembic.ini")), "0026_application_runtime_grants"
            )
        with cls.admin.begin() as c:
            c.exec_driver_sql(
                "INSERT INTO users(id,username,username_key,password_hash,created_at) VALUES ('a','synthetic-a','synthetic-a','synthetic-hash',1),('b','synthetic-b','synthetic-b','synthetic-hash',1)"
            )
            c.exec_driver_sql(
                "INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source,storage_path) VALUES ('legacy-a','a','f','t','r','l',1,false,'unknown','legacy/shared.wav'),('legacy-b','b','f','t','r','l',1,false,'unknown','legacy/shared.wav')"
            )
            cls.before = c.exec_driver_sql(
                "SELECT id,user_id,storage_path FROM tracks ORDER BY id"
            ).all()
        with cls.admin.begin() as c:
            c.exec_driver_sql(
                "CREATE ROLE synthetic_unexpected_grantee NOLOGIN NOINHERIT"
            )
            c.exec_driver_sql(
                "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner GRANT ALL ON TABLES TO synthetic_unexpected_grantee"
            )
            c.exec_driver_sql(
                "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
            )
            c.exec_driver_sql(
                "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner GRANT EXECUTE ON FUNCTIONS TO synthetic_unexpected_grantee"
            )
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": cls.migration_url,
                "MIGRATION_DATABASE_URL": cls.migration_url,
            },
        ):
            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        with cls.admin.begin() as c:
            cls.after = c.exec_driver_sql(
                "SELECT id,user_id,storage_path FROM tracks ORDER BY id"
            ).all()
            # Exercise an actual uninitialized database before the explicit test binding.
            count = c.exec_driver_sql(
                "SELECT count(*) FROM vervfy_storage.objects"
            ).scalar_one()
            c.exec_driver_sql("SET LOCAL ROLE app_runtime")
            c.exec_driver_sql("SET LOCAL app.current_user_id='a'")
            c.exec_driver_sql(
                "UPDATE tracks SET title='metadata-only',storage_path=storage_path WHERE id='legacy-a'"
            )
            for sql in (
                "SELECT * FROM vervfy_storage.reserve_object('audio','wav')",
                "SELECT vervfy_storage.validate_namespace('00000000-0000-0000-0000-000000000001','disposable-test','https://vervfy.invalid','synthetic')",
            ):
                with unittest.TestCase().assertRaises(DBAPIError), c.begin_nested():
                    c.exec_driver_sql(sql)
            c.exec_driver_sql("RESET ROLE")
            assert (
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.objects"
                ).scalar_one()
                == count
            )
            assert (
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.namespaces"
                ).scalar_one()
                == 0
            )
            cls.uninitialized_verified = True
            cls.binding = initialize_disposable_namespace(c)
        cls.engines = {
            role: sa.create_engine(
                cls.url.set(username=role), connect_args={"prepare_threshold": None}
            )
            for role in (
                "app_runtime",
                "storage_cleanup_worker",
                "google_auth_lookup",
                "migration_owner",
            )
        }
        for engine in cls.engines.values():
            cls.addClassCleanup(engine.dispose)

    @contextmanager
    def tx(self, role="app_runtime", tenant="a"):
        with self.engines[role].begin() as c:
            c.execute(
                sa.text("SELECT set_config('app.current_user_id',:tenant,true)"),
                {"tenant": tenant},
            )
            c.exec_driver_sql("SET LOCAL statement_timeout='10s'")
            yield c

    def ready(self, tenant="a", kind="audio"):
        with self.tx(tenant=tenant) as c:
            obj = c.execute(
                sa.text("SELECT * FROM vervfy_storage.reserve_object(:kind,'wav')"),
                {"kind": kind},
            ).one()
            for state in ("uploading", "ready"):
                c.execute(
                    sa.text("SELECT vervfy_storage.advance_upload(:id,:token,:state)"),
                    {"id": obj.object_id, "token": obj.upload_token, "state": state},
                )
        return obj

    def attach(self, c, path, tenant="a", ident=None):
        ident = ident or uuid.uuid4().hex
        c.execute(
            sa.text("""INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source,storage_path)
            VALUES(:id,:tenant,'synthetic.wav','t','r','l',1,false,'generated',:path)"""),
            {"id": ident, "tenant": tenant, "path": path},
        )
        return ident

    def request(self, obj):
        with self.tx() as c:
            c.execute(
                sa.text("SELECT vervfy_storage.request_cleanup(:id)"),
                {"id": obj.object_id},
            )

    def retire(self, obj):
        with self.tx("storage_cleanup_worker") as c:
            return c.execute(
                sa.text("SELECT vervfy_storage.retire_candidate(:id)"),
                {"id": obj.object_id},
            ).scalar_one()

    def test_migration_preserves_legacy_paths_and_hard_disables_physical_cleanup(self):
        self.assertEqual(self.before, self.after)
        obj = self.ready()
        self.request(obj)
        with (
            self.tx("storage_cleanup_worker") as c,
            self.assertRaises(DBAPIError),
            c.begin_nested(),
        ):
            c.execute(
                sa.text("SELECT vervfy_storage.claim_cleanup(:id)"),
                {"id": obj.object_id},
            )
        with (
            self.admin.begin() as c,
            self.assertRaises(DBAPIError),
            c.begin_nested(),
        ):
            c.exec_driver_sql(
                "UPDATE vervfy_storage.namespaces SET physical_cleanup_enabled=true"
            )

    def test_allocation_is_immutable_and_tenant_scoped(self):
        first, second = self.ready(), self.ready()
        self.assertNotEqual(first.object_path, second.object_path)
        self.assertIn("/a/audio/", first.object_path)
        with self.tx(tenant="b") as c:
            self.assertEqual(
                c.execute(
                    sa.text(
                        "SELECT count(id) FROM vervfy_storage.objects WHERE id=:id"
                    ),
                    {"id": first.object_id},
                ).scalar_one(),
                0,
            )
            with self.assertRaises(DBAPIError), c.begin_nested():
                self.attach(c, first.object_path, tenant="b")
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.execute(
                    sa.text("SELECT vervfy_storage.advance_upload(:id,:token,'hold')"),
                    {"id": first.object_id, "token": first.upload_token},
                )
        with self.tx() as c:
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.execute(
                    sa.text(
                        "UPDATE vervfy_storage.objects SET state='deleted' WHERE id=:id"
                    ),
                    {"id": first.object_id},
                )
            with self.assertRaises(DBAPIError), c.begin_nested():
                self.attach(c, "unregistered/path.wav")

    def test_object_keys_are_case_sensitive_and_byte_exact(self):
        obj = self.ready()
        with self.tx() as c:
            self.attach(c, obj.object_path)
            with self.assertRaises(DBAPIError), c.begin_nested():
                self.attach(c, obj.object_path.upper())
        with self.admin.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT a.attcollation::regcollation::text FROM pg_attribute a WHERE a.attrelid='vervfy_storage.objects'::regclass AND a.attname='path'"
                ).scalar_one(),
                '"C"',
            )

    def test_no_context_wrong_token_and_uncertain_upload_fail_closed(self):
        with (
            self.tx(tenant="") as c,
            self.assertRaises(DBAPIError),
            c.begin_nested(),
        ):
            c.exec_driver_sql(
                "SELECT * FROM vervfy_storage.reserve_object('audio','wav')"
            )
        with self.tx() as c:
            obj = c.execute(
                sa.text("SELECT * FROM vervfy_storage.reserve_object(:kind,'wav')"),
                {"kind": "audio"},
            ).one()
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.execute(
                    sa.text(
                        "SELECT vervfy_storage.advance_upload(:id,:token,'uploading')"
                    ),
                    {"id": obj.object_id, "token": uuid.uuid4()},
                )
            for state in ("uploading", "hold"):
                c.execute(
                    sa.text("SELECT vervfy_storage.advance_upload(:id,:token,:s)"),
                    {"id": obj.object_id, "token": obj.upload_token, "s": state},
                )
        self.assertFalse(self.retire(obj))
        with (
            self.tx() as c,
            self.assertRaises(DBAPIError),
            c.begin_nested(),
        ):
            self.attach(c, obj.object_path)

    def test_reference_guards_cover_artwork_jobs_and_shared_audio(self):
        audio = self.ready()
        cover = self.ready(kind="album-cover")
        photo = self.ready(kind="artist-photo")
        staged = self.ready(kind="staged-audio")
        with self.tx() as c:
            one = self.attach(c, audio.object_path)
            two = self.attach(c, audio.object_path)
            c.execute(
                sa.text("UPDATE tracks SET cover_path=:p WHERE id IN (:a,:b)"),
                {"p": cover.object_path, "a": one, "b": two},
            )
            c.execute(
                sa.text(
                    "INSERT INTO artist_photos(user_id,normalized_artist_name,storage_path,source) VALUES('a',:name,:p,'user')"
                ),
                {"name": uuid.uuid4().hex, "p": photo.object_path},
            )
            c.execute(
                sa.text(
                    "INSERT INTO upload_jobs(id,user_id,filename,storage_path,status,created_at) VALUES(:id,'a','f',:p,'processing',1)"
                ),
                {"id": uuid.uuid4().hex, "p": staged.object_path},
            )
            c.execute(sa.text("DELETE FROM tracks WHERE id=:id"), {"id": one})
        self.assertFalse(self.retire(audio))
        self.assertFalse(self.retire(cover))
        self.request(photo)
        self.request(staged)
        self.assertFalse(self.retire(photo))
        self.assertFalse(self.retire(staged))
        with self.tx() as c:
            c.execute(sa.text("DELETE FROM tracks WHERE id=:id"), {"id": two})
            c.execute(
                sa.text("DELETE FROM artist_photos WHERE storage_path=:p"),
                {"p": photo.object_path},
            )
            c.execute(
                sa.text(
                    "UPDATE upload_jobs SET storage_path=NULL,status='completed' WHERE storage_path=:p"
                ),
                {"p": staged.object_path},
            )
        for obj in (audio, cover, photo, staged):
            self.assertTrue(self.retire(obj))
        with self.tx() as c, self.assertRaises(DBAPIError), c.begin_nested():
            self.attach(c, audio.object_path)

    def test_reference_removal_and_outbox_roll_back_together(self):
        obj = self.ready()
        with self.tx() as c:
            ident = self.attach(c, obj.object_path)
        with self.tx() as c:
            savepoint = c.begin_nested()
            c.execute(sa.text("DELETE FROM tracks WHERE id=:id"), {"id": ident})
            savepoint.rollback()
        with self.admin.connect() as c:
            self.assertEqual(
                c.execute(
                    sa.text(
                        "SELECT count(*) FROM vervfy_storage.cleanup_jobs WHERE object_id=:id"
                    ),
                    {"id": obj.object_id},
                ).scalar_one(),
                0,
            )
        with self.tx() as c:
            c.execute(sa.text("DELETE FROM tracks WHERE id=:id"), {"id": ident})
        self.assertTrue(self.retire(obj))
        self.assertTrue(self.retire(obj))  # Retry after a fresh connection/transaction.

    def test_account_cascade_preserves_cleanup_obligation(self):
        tenant = uuid.uuid4().hex
        with self.tx() as c:
            c.execute(
                sa.text(
                    "INSERT INTO users(id,username,username_key,password_hash,created_at) VALUES(:t,:t,:t,'synthetic',1)"
                ),
                {"t": tenant},
            )
        obj = self.ready(tenant)
        with self.tx(tenant=tenant) as c:
            self.attach(c, obj.object_path, tenant=tenant)
            c.execute(sa.text("DELETE FROM users WHERE id=:id"), {"id": tenant})
        self.assertTrue(self.retire(obj))
        with self.admin.connect() as c:
            self.assertEqual(
                c.execute(
                    sa.text(
                        "SELECT count(*) FROM vervfy_storage.cleanup_jobs WHERE object_id=:id"
                    ),
                    {"id": obj.object_id},
                ).scalar_one(),
                1,
            )

    def test_global_reference_verification_sees_other_tenant_and_legacy_is_held(self):
        with self.tx() as c:
            c.exec_driver_sql("UPDATE tracks SET storage_path=NULL WHERE id='legacy-a'")
        with self.admin.begin() as c:
            oid = c.exec_driver_sql(
                "SELECT id FROM vervfy_storage.objects WHERE path='legacy/shared.wav'"
            ).scalar_one()
        obj = type("Object", (), {"object_id": oid})()
        self.assertFalse(self.retire(obj))
        # Classify only this synthetic fixture as managed to prove the global
        # verifier independently sees tenant B through FORCE RLS.
        try:
            with self.admin.begin() as c:
                c.execute(
                    sa.text(
                        "UPDATE vervfy_storage.objects SET classification='managed',tenant_id='a',reservation_token=:token,upload_verified=true,state='live' WHERE id=:id"
                    ),
                    {"id": oid, "token": uuid.uuid4()},
                )
            with self.tx() as c:
                self.assertEqual(
                    c.exec_driver_sql(
                        "SELECT count(*) FROM tracks WHERE storage_path='legacy/shared.wav'"
                    ).scalar_one(),
                    0,
                )
            with self.tx("storage_cleanup_worker") as c:
                c.exec_driver_sql(
                    "CREATE TEMP TABLE tracks(storage_path text,cover_path text) ON COMMIT DROP"
                )
                c.exec_driver_sql("SET LOCAL search_path=pg_temp,public")
                self.assertFalse(
                    c.execute(
                        sa.text("SELECT vervfy_storage.retire_candidate(:id)"),
                        {"id": oid},
                    ).scalar_one()
                )
        finally:
            with self.admin.begin() as c:
                c.execute(
                    sa.text(
                        "UPDATE vervfy_storage.objects SET classification='legacy',state='hold' WHERE id=:id"
                    ),
                    {"id": oid},
                )

    def test_function_acls_owner_privileges_and_role_escalation(self):
        for role in ("app_runtime", "storage_cleanup_worker", "google_auth_lookup"):
            with self.tx(role) as c:
                for sql in (
                    f"SET ROLE {OWNER}",
                    "SELECT * FROM vervfy_storage.cleanup_jobs",
                    "SELECT vervfy_storage._has_references('legacy/shared.wav')",
                    "CREATE TABLE vervfy_storage.forbidden(id int)",
                ):
                    with (
                        self.subTest(role=role, sql=sql),
                        self.assertRaises(DBAPIError),
                        c.begin_nested(),
                    ):
                        c.exec_driver_sql(sql)
        with self.tx("migration_owner") as c:
            c.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.exec_driver_sql("SELECT password_hash FROM public.users")
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.exec_driver_sql("UPDATE public.tracks SET title='forbidden'")
        with self.admin.connect() as c:
            rows = c.exec_driver_sql(
                "SELECT p.prosecdef,p.provolatile,p.proconfig,pg_get_userbyid(p.proowner),has_function_privilege('public',p.oid,'EXECUTE') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='vervfy_storage'"
            ).all()
            self.assertEqual(len(rows), 13)
            for secure, volatility, config, owner, public in rows:
                self.assertTrue(secure)
                self.assertEqual(volatility, "v")
                self.assertEqual(owner, OWNER)
                self.assertFalse(public)
                self.assertIn("search_path=pg_catalog, pg_temp", config)

    def test_unsafe_membership_is_rejected_by_migration_preflight(self):
        spec = importlib.util.spec_from_file_location(
            "storage_0027", ROOT / "alembic/versions/0027_storage_lifecycle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.admin.begin() as c:
            c.exec_driver_sql(
                f"GRANT {OWNER} TO app_runtime WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
            )
        try:
            with (
                self.tx("migration_owner") as c,
                self.assertRaises(RuntimeError),
            ):
                module._roles(c)
        finally:
            with self.admin.begin() as c:
                c.exec_driver_sql(f"REVOKE {OWNER} FROM app_runtime")

    def test_preexisting_capability_privileges_are_rejected(self):
        spec = importlib.util.spec_from_file_location(
            "storage_0027_acl", ROOT / "alembic/versions/0027_storage_lifecycle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.admin.begin() as c:
            c.exec_driver_sql(
                "CREATE ROLE synthetic_storage_acl NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS"
            )
            role = c.exec_driver_sql(
                "SELECT 'synthetic_storage_acl'::regrole::oid"
            ).scalar_one()
        try:
            with self.tx("migration_owner") as c:
                module._fresh_privileges(c, (role,))
            with self.admin.begin() as c:
                c.exec_driver_sql(
                    "GRANT SELECT(password_hash) ON public.users TO synthetic_storage_acl"
                )
            with (
                self.tx("migration_owner") as c,
                self.assertRaisesRegex(RuntimeError, "preexisting object privileges"),
            ):
                module._fresh_privileges(c, (role,))
        finally:
            with self.admin.begin() as c:
                c.exec_driver_sql(
                    "REVOKE SELECT(password_hash) ON public.users FROM synthetic_storage_acl"
                )
                c.exec_driver_sql("DROP ROLE synthetic_storage_acl")

    def wait_blocked(self, pid):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with self.admin.connect() as c:
                if c.execute(
                    sa.text("SELECT cardinality(pg_blocking_pids(:pid))>0"),
                    {"pid": pid},
                ).scalar_one():
                    return
            threading.Event().wait(0.01)
        self.fail("Expected actual database lock dependency was not observed")

    def test_concurrent_attachment_wins_then_retirement_observes_reference(self):
        obj = self.ready()
        self.request(obj)
        pids = queue.Queue()

        def retire():
            with self.tx("storage_cleanup_worker") as c:
                pids.put(c.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                return c.execute(
                    sa.text("SELECT vervfy_storage.retire_candidate(:id)"),
                    {"id": obj.object_id},
                ).scalar_one()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.tx() as c:
                self.attach(c, obj.object_path)
                result = pool.submit(retire)
                self.wait_blocked(pids.get(timeout=10))
            self.assertFalse(result.result(timeout=10))

    def test_concurrent_retirement_wins_and_delayed_attachment_is_rejected(self):
        obj = self.ready()
        self.request(obj)
        pids = queue.Queue()

        def attach():
            try:
                with self.tx() as c:
                    pids.put(c.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                    self.attach(c, obj.object_path)
            except DBAPIError as error:
                return error.orig.sqlstate
            return "unexpected-success"

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.tx("storage_cleanup_worker") as c:
                self.assertTrue(
                    c.execute(
                        sa.text("SELECT vervfy_storage.retire_candidate(:id)"),
                        {"id": obj.object_id},
                    ).scalar_one()
                )
                result = pool.submit(attach)
                self.wait_blocked(pids.get(timeout=10))
            self.assertEqual(result.result(timeout=10), "42501")

    def test_uninitialized_namespace_metadata_update_and_allocation(self):
        self.assertTrue(self.uninitialized_verified)

    def test_namespace_is_immutable_and_only_test_initialization_is_available(self):
        with self.admin.begin() as c:
            for statement in (
                "UPDATE vervfy_storage.namespaces SET bucket='different'",
                "UPDATE vervfy_storage.namespaces SET namespace_id=gen_random_uuid()",
                "UPDATE vervfy_storage.namespaces SET environment='other'",
                "UPDATE vervfy_storage.namespaces SET endpoint='https://different.example.test'",
                "DELETE FROM vervfy_storage.namespaces",
                "TRUNCATE vervfy_storage.namespaces CASCADE",
            ):
                with (
                    self.subTest(statement=statement),
                    self.assertRaises(DBAPIError),
                    c.begin_nested(),
                ):
                    c.exec_driver_sql(statement)
        from unittest.mock import Mock

        fake = Mock()
        fake.engine.url = sa.URL.create(
            "postgresql", host="hosted.example.test", username="test_admin"
        )
        with self.assertRaises(RuntimeError):
            initialize_disposable_namespace(fake)
        fake.exec_driver_sql.assert_not_called()

    def test_binding_validation_precedes_any_managed_storage_io(self):
        from dataclasses import replace

        obj = self.ready()
        with (
            self.tx() as c,
            patch.object(
                audio_store,
                "_settings",
                return_value=(self.binding.endpoint, "synthetic", self.binding.bucket),
            ),
            patch.object(audio_store, "upload") as upload,
            patch.object(audio_store, "upload_file") as upload_file,
        ):
            ManagedStorageBoundary(c, self.binding).validate(obj.object_path)
            for field, value in (
                ("namespace_id", uuid.uuid4()),
                ("environment", "other"),
                ("endpoint", "https://other.example.test"),
                ("bucket", "other"),
            ):
                with (
                    self.subTest(field=field),
                    self.assertRaises((DBAPIError, audio_store.StorageError)),
                    c.begin_nested(),
                ):
                    ManagedStorageBoundary(
                        c, replace(self.binding, **{field: value})
                    ).validate(obj.object_path)
            with (
                patch.object(
                    audio_store,
                    "_settings",
                    return_value=("https://wrong.example.test", "synthetic", "wrong"),
                ),
                self.assertRaises(audio_store.StorageError),
            ):
                ManagedStorageBoundary(c, self.binding).validate(obj.object_path)
            for path in (
                "../legacy.wav",
                obj.object_path.replace(
                    str(self.binding.namespace_id), str(uuid.uuid4())
                ),
                obj.object_path.rsplit("/", 1)[0] + "/" + "-" * 36 + ".wav",
                obj.object_path + "?token=synthetic",
            ):
                with (
                    self.subTest(invalid_managed_path=True),
                    self.assertRaises(audio_store.StorageError),
                ):
                    ManagedStorageBoundary(c, self.binding).validate(path)
            upload.assert_not_called()
            upload_file.assert_not_called()

    def test_all_destination_kind_pairs(self):
        objects = {
            kind: self.ready(kind=kind)
            for kind in (
                "audio",
                "track-cover",
                "album-cover",
                "artist-photo",
                "staged-audio",
            )
        }
        destinations = {
            "track_audio": (
                {"audio"},
                "INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source,storage_path) VALUES(:id,'a','f','t','r','l',1,false,'unknown',:p)",
            ),
            "track_cover": (
                {"track-cover", "album-cover"},
                "INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source,cover_path) VALUES(:id,'a','f','t','r','l',1,true,'user',:p)",
            ),
            "artist_photo": (
                {"artist-photo"},
                "INSERT INTO artist_photos(user_id,normalized_artist_name,storage_path,source) VALUES('a',:id,:p,'user')",
            ),
            "upload_job": (
                {"staged-audio"},
                "INSERT INTO upload_jobs(id,user_id,filename,storage_path,status,created_at) VALUES(:id,'a','f',:p,'processing',1)",
            ),
        }
        for destination, (allowed, sql) in destinations.items():
            for kind, obj in objects.items():
                with self.subTest(destination=destination, kind=kind), self.tx() as c:
                    if kind in allowed:
                        c.execute(
                            sa.text(sql), {"id": uuid.uuid4().hex, "p": obj.object_path}
                        )
                    else:
                        with self.assertRaises(DBAPIError), c.begin_nested():
                            c.execute(
                                sa.text(sql),
                                {"id": uuid.uuid4().hex, "p": obj.object_path},
                            )

    def test_malformed_and_foreign_paths_and_ownership_changes(self):
        obj = self.ready()
        with self.tx() as c:
            ident = self.attach(c, obj.object_path)
            bad_paths = (
                "",
                "../secret.wav",
                "x" * 601,
                obj.object_path.replace(
                    str(self.binding.namespace_id), str(uuid.uuid4())
                ),
                obj.object_path + "?token=x",
                obj.object_path.replace("/a/", "/b/"),
            )
            for path in bad_paths:
                with (
                    self.subTest(path_length=len(path)),
                    self.assertRaises(DBAPIError),
                    c.begin_nested(),
                ):
                    self.attach(c, path)
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.execute(
                    sa.text("UPDATE tracks SET user_id='b' WHERE id=:id"), {"id": ident}
                )
        with self.admin.connect() as c:
            self.assertEqual(
                c.execute(
                    sa.text(
                        "SELECT count(*) FROM vervfy_storage.objects WHERE path=ANY(:paths)"
                    ),
                    {"paths": list(bad_paths)},
                ).scalar_one(),
                0,
            )

    def test_catalog_ownership_acl_matrix_and_hostile_defaults_stripped(self):
        with self.admin.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='vervfy_storage'"
                ).scalar_one(),
                "migration_owner",
            )
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT DISTINCT pg_get_userbyid(relowner) FROM pg_class WHERE relnamespace='vervfy_storage'::regnamespace AND relkind='r'"
                )
                .scalars()
                .all(),
                ["migration_owner"],
            )
            roles = (
                "app_runtime",
                "storage_cleanup_worker",
                "google_auth_lookup",
                "synthetic_unexpected_grantee",
            )
            runtime = {
                "reserve_object",
                "advance_upload",
                "request_cleanup",
                "validate_namespace",
            }
            worker = {
                "retire_candidate",
                "claim_cleanup",
                "claim_next_cleanup",
                "complete_cleanup",
                "retry_cleanup",
                "validate_namespace",
            }
            for role in roles:
                rows = c.execute(
                    sa.text(
                        "SELECT proname,has_function_privilege(:role,oid,'EXECUTE') FROM pg_proc WHERE pronamespace='vervfy_storage'::regnamespace"
                    ),
                    {"role": role},
                ).all()
                self.assertEqual(
                    {name for name, allowed in rows if allowed},
                    runtime
                    if role == "app_runtime"
                    else worker
                    if role == "storage_cleanup_worker"
                    else set(),
                )
                self.assertFalse(
                    c.execute(
                        sa.text(
                            "SELECT has_schema_privilege(:role,'vervfy_storage','CREATE')"
                        ),
                        {"role": role},
                    ).scalar_one()
                )
                self.assertEqual(
                    c.execute(
                        sa.text(
                            "SELECT count(*) FROM pg_class WHERE relnamespace='vervfy_storage'::regnamespace AND relkind='r' AND has_table_privilege(:role,oid,'INSERT,UPDATE,DELETE,TRUNCATE')"
                        ),
                        {"role": role},
                    ).scalar_one(),
                    0,
                )
            # The hostile defaults still exist; migration strips only its new objects.
            self.assertGreater(
                c.exec_driver_sql(
                    "SELECT count(*) FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a WHERE a.grantee='synthetic_unexpected_grantee'::regrole"
                ).scalar_one(),
                0,
            )

    def test_preflight_rejects_cross_schema_ownership_routines_grants_and_defaults(
        self,
    ):
        spec = importlib.util.spec_from_file_location(
            "storage_preflight", ROOT / "alembic/versions/0027_storage_lifecycle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.admin.begin() as c:
            c.exec_driver_sql(
                "CREATE ROLE synthetic_capability NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS"
            )
            c.exec_driver_sql("CREATE SCHEMA synthetic_security")
            c.exec_driver_sql(
                "CREATE TABLE synthetic_security.private_data(secret text)"
            )
            c.exec_driver_sql("CREATE SEQUENCE synthetic_security.private_sequence")
            c.exec_driver_sql(
                "CREATE FUNCTION synthetic_security.privileged() RETURNS integer LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'"
            )
            c.exec_driver_sql(
                "REVOKE ALL ON FUNCTION synthetic_security.privileged() FROM PUBLIC"
            )
            oid = c.exec_driver_sql(
                "SELECT 'synthetic_capability'::regrole::oid"
            ).scalar_one()
            module._fresh_privileges(c, [oid])
            cases = (
                "GRANT SELECT(secret) ON synthetic_security.private_data TO synthetic_capability",
                "ALTER TABLE synthetic_security.private_data OWNER TO synthetic_capability",
                "ALTER SCHEMA synthetic_security OWNER TO synthetic_capability",
                "ALTER FUNCTION synthetic_security.privileged() OWNER TO synthetic_capability",
                "GRANT USAGE ON SEQUENCE synthetic_security.private_sequence TO synthetic_capability",
                "GRANT CREATE ON SCHEMA synthetic_security TO synthetic_capability",
                "GRANT USAGE ON SCHEMA synthetic_security TO synthetic_capability; GRANT EXECUTE ON FUNCTION synthetic_security.privileged() TO synthetic_capability",
                "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA synthetic_security GRANT SELECT ON TABLES TO synthetic_capability",
                "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner GRANT EXECUTE ON FUNCTIONS TO PUBLIC",
            )
            for statement in cases:
                savepoint = c.begin_nested()
                try:
                    c.exec_driver_sql(statement)
                    with (
                        self.subTest(statement=statement),
                        self.assertRaises(RuntimeError),
                    ):
                        module._fresh_privileges(c, [oid])
                finally:
                    savepoint.rollback()
            c.exec_driver_sql("DROP SCHEMA synthetic_security CASCADE")
            c.exec_driver_sql("DROP ROLE synthetic_capability")

    def test_unauthorized_function_calls_fail_at_execution(self):
        calls = {
            "app_runtime": (
                "SELECT vervfy_storage.retire_candidate(gen_random_uuid())",
                "SELECT vervfy_storage.claim_cleanup(gen_random_uuid())",
                "SELECT vervfy_storage._queue(gen_random_uuid(),'a')",
            ),
            "storage_cleanup_worker": (
                "SELECT * FROM vervfy_storage.reserve_object('audio','wav')",
                "SELECT vervfy_storage.advance_upload(gen_random_uuid(),gen_random_uuid(),'ready')",
                "SELECT vervfy_storage.request_cleanup(gen_random_uuid())",
            ),
            "google_auth_lookup": (
                "SELECT * FROM vervfy_storage.reserve_object('audio','wav')",
                "SELECT vervfy_storage.validate_namespace(gen_random_uuid(),'x','https://x','x')",
            ),
        }
        for role, statements in calls.items():
            with self.tx(role) as c:
                for statement in statements:
                    with (
                        self.subTest(role=role, statement=statement),
                        self.assertRaises(DBAPIError) as caught,
                        c.begin_nested(),
                    ):
                        c.exec_driver_sql(statement)
                    self.assertEqual(caught.exception.orig.sqlstate, "42501")

    def test_concurrent_multi_object_replacements_preserve_references(self):
        left, right = self.ready(), self.ready()
        old_cover, new_cover = (
            self.ready(kind="track-cover"),
            self.ready(kind="album-cover"),
        )
        with self.tx() as c:
            first = self.attach(c, left.object_path)
            second = self.attach(c, right.object_path)
            c.execute(
                sa.text("UPDATE tracks SET cover_path=:p WHERE id IN (:a,:b)"),
                {"p": old_cover.object_path, "a": first, "b": second},
            )
        pids = queue.Queue()

        def replace_second():
            with self.tx() as c:
                pids.put(c.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                c.execute(
                    sa.text(
                        "UPDATE tracks SET storage_path=:audio,cover_path=:cover WHERE id=:id"
                    ),
                    {
                        "audio": left.object_path,
                        "cover": new_cover.object_path,
                        "id": second,
                    },
                )

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.tx() as c:
                c.execute(
                    sa.text(
                        "UPDATE tracks SET storage_path=:audio,cover_path=:cover WHERE id=:id"
                    ),
                    {
                        "audio": right.object_path,
                        "cover": new_cover.object_path,
                        "id": first,
                    },
                )
                result = pool.submit(replace_second)
                self.wait_blocked(pids.get(timeout=10))
            result.result(timeout=10)
        self.assertFalse(self.retire(left))
        self.assertFalse(self.retire(right))
        self.assertTrue(self.retire(old_cover))
        self.request(new_cover)
        self.assertFalse(self.retire(new_cover))

    def test_indirect_capability_membership_is_rejected(self):
        spec = importlib.util.spec_from_file_location(
            "storage_role_preflight",
            ROOT / "alembic/versions/0027_storage_lifecycle.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.admin.begin() as c:
            c.exec_driver_sql(
                "CREATE ROLE synthetic_indirect_capability NOLOGIN NOINHERIT"
            )
            c.exec_driver_sql(
                "GRANT migration_owner TO synthetic_indirect_capability WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
            )
        try:
            with (
                self.tx("migration_owner") as c,
                self.assertRaisesRegex(RuntimeError, "effective storage capability"),
            ):
                module._roles(c)
        finally:
            with self.admin.begin() as c:
                c.exec_driver_sql(
                    "REVOKE migration_owner FROM synthetic_indirect_capability"
                )
                c.exec_driver_sql("DROP ROLE synthetic_indirect_capability")
