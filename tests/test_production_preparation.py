"""Disposable PostgreSQL rehearsal for production ACL and legacy preparation."""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import test_staging_migrations as fixtures
from alembic.config import Config
from sqlalchemy.exc import DBAPIError

from alembic import command
from scripts import storage_production_migration as runner
from storage_internal_acl import (
    _full_table_privileges,
    apply_acl_repair,
    check_internal_acls,
    plan_acl_repair,
)
from storage_inventory import (
    InventoryBlocked,
    apply_inventory,
    measure_inventory,
    plan_digest,
    snapshot,
)
from storage_legacy_registration import (
    _registration_rows,
    _valid_path,
    apply_registration,
    plan_registration,
)
from storage_namespace import NamespaceBinding
from storage_stale_audio import (
    charge_stale_audio_tombstones,
    detach_stale_audio_references,
    plan_stale_audio_repair,
)


class ProductionPreparationTests(unittest.TestCase):
    account_snapshot = staticmethod(fixtures.StagingPostgresTests.account_snapshot)

    @classmethod
    def setUpClass(cls):
        original_upgrade = command.upgrade

        def pre_0034_upgrade(config, revision, *args, **kwargs):
            if revision != "head":
                return original_upgrade(config, revision, *args, **kwargs)
            original_upgrade(config, "0028_webauthn_enrollment", *args, **kwargs)
            with cls.engine.begin() as connection:
                connection.exec_driver_sql("""
                    UPDATE public.tracks
                    SET storage_path='legacy/shared.wav',
                        cover_path='legacy/covers/a.jpg'
                    WHERE id='embedded'
                """)
                connection.exec_driver_sql("""
                    UPDATE public.tracks
                    SET storage_path='legacy/shared.wav'
                    WHERE id='track-b'
                """)
                connection.exec_driver_sql("""
                    UPDATE public.tracks
                    SET storage_path='legacy/already-registered.wav'
                    WHERE id='placeholder'
                """)
                connection.exec_driver_sql("""
                    INSERT INTO public.artist_photos(
                        user_id,normalized_artist_name,jpeg_data,source,storage_path
                    ) VALUES ('b','legacy-fixture',decode('ffd8ffd9','hex'),
                              'user','legacy/photos/b.jpg')
                """)
            return original_upgrade(
                config, "0033_cleanup_claims_disabled", *args, **kwargs
            )

        with patch.object(command, "upgrade", pre_0034_upgrade):
            fixtures.StagingPostgresTests.setUpClass.__func__(cls)

        cls.migrator = sa.create_engine(cls.url.set(username="migration_owner"))
        cls.addClassCleanup(cls.migrator.dispose)
        cls.binding = NamespaceBinding(
            uuid.UUID("31daf7cc-8563-411f-94c7-944d607d1ef1"),
            "production",
            "https://llxmskxxchpmeavorusj.supabase.co",
            "songs",
        )
        cls._seed_namespace_ledger_and_acl_drift()

    @classmethod
    def _seed_namespace_ledger_and_acl_drift(cls):
        with cls.engine.begin() as connection:
            for role in ("anon", "authenticated", "service_role"):
                connection.exec_driver_sql(f"CREATE ROLE {role} NOLOGIN")
            connection.exec_driver_sql("""
                INSERT INTO vervfy_storage.namespaces VALUES
                (1,'31daf7cc-8563-411f-94c7-944d607d1ef1','production',
                 'https://llxmskxxchpmeavorusj.supabase.co','songs',false)
            """)
            rows = [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": None,
                    "path": "legacy/already-registered.wav",
                    "kind": "legacy",
                    "classification": "legacy",
                    "state": "hold",
                    "reservation_token": None,
                    "upload_verified": False,
                },
                {
                    "id": uuid.uuid4(),
                    "tenant_id": None,
                    "path": "legacy/existing-held.wav",
                    "kind": "legacy",
                    "classification": "legacy",
                    "state": "hold",
                    "reservation_token": None,
                    "upload_verified": False,
                },
            ]
            for index in range(6):
                object_id = uuid.uuid4()
                rows.append(
                    {
                        "id": object_id,
                        "tenant_id": "a",
                        "path": (
                            f"v2/{cls.binding.namespace_id}/a/audio/{object_id}.wav"
                        ),
                        "kind": "audio",
                        "classification": "managed",
                        "state": "ready",
                        "reservation_token": uuid.uuid4(),
                        "upload_verified": True,
                    }
                )
            connection.exec_driver_sql("SET ROLE vervfy_storage_lifecycle_owner")
            connection.execute(
                sa.text("""
                INSERT INTO vervfy_storage.objects(
                    id,namespace_id,tenant_id,path,kind,classification,state,
                    reservation_token,upload_verified
                ) VALUES (
                    :id,1,:tenant_id,:path,:kind,:classification,:state,
                    :reservation_token,:upload_verified
                )
            """),
                rows,
            )
            connection.execute(
                sa.text("""
                    INSERT INTO vervfy_storage.cleanup_jobs(
                        object_id,requested_by,state
                    ) VALUES (:object_id,'legacy','held')
                """),
                {"object_id": rows[1]["id"]},
            )
            connection.exec_driver_sql("RESET ROLE")

            full = ", ".join(_full_table_privileges(connection))
            for table in (
                "alembic_version",
                "artist_images",
                "auth_sessions",
                "track_cover_cache",
            ):
                for role in ("anon", "authenticated", "service_role"):
                    connection.exec_driver_sql(
                        f"GRANT {full} ON public.{table} TO {role}"
                    )
            for table in ("artist_images", "track_cover_cache"):
                connection.exec_driver_sql(
                    f"GRANT {full} ON public.{table} TO postgres"
                )
            connection.exec_driver_sql(
                "GRANT SELECT,INSERT,UPDATE,DELETE "
                "ON public.alembic_version TO app_runtime"
            )
            connection.exec_driver_sql("""
                INSERT INTO public.auth_sessions(id,user_id,created_at,expires_at)
                VALUES ('preparation-session','a',1,4102444800)
            """)

        with cls.engine.connect() as connection:
            cls.prepared_security_state = cls._security_snapshot(connection)

    @staticmethod
    def _security_snapshot(connection):
        return (
            connection.exec_driver_sql("""
                SELECT n.nspname,c.relname,c.relrowsecurity,c.relforcerowsecurity
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public'
                  AND c.relname IN ('tracks','artist_photos','upload_jobs')
                ORDER BY c.relname
            """).all(),
            connection.exec_driver_sql("""
                SELECT tablename,policyname,roles::text,cmd,qual,with_check
                FROM pg_catalog.pg_policies
                WHERE schemaname='public'
                  AND tablename IN ('tracks','artist_photos','upload_jobs')
                ORDER BY tablename,policyname
            """).all(),
        )

    def test_acl_registration_and_0034_reconciliation(self):
        with self.migrator.begin() as connection:
            with self.assertRaisesRegex(
                runner.MigrationBlocked, "Unexpected direct auth_sessions"
            ):
                runner._check_auth_sessions(connection, expected_exists=True)
            runner._check_auth_sessions(
                connection,
                expected_exists=True,
                allow_reviewed_overgrants=True,
            )
            with self.assertRaisesRegex(
                InventoryBlocked, "outside the reviewed repair"
            ):
                check_internal_acls(connection)
            check_internal_acls(connection, allow_reviewed_overgrants=True)
            with connection.begin_nested() as nested:
                connection.exec_driver_sql(
                    "ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY"
                )
                with self.assertRaisesRegex(InventoryBlocked, "reviewed RLS state"):
                    plan_acl_repair(connection)
                nested.rollback()

            acl_plan = plan_acl_repair(connection)
            with self.assertRaisesRegex(InventoryBlocked, "digest"):
                apply_acl_repair(connection, acl_plan, "0" * 64)
            self.assertEqual(
                apply_acl_repair(connection, acl_plan, plan_digest(acl_plan)),
                4,
            )
            self.assertEqual(
                apply_acl_repair(connection, acl_plan, plan_digest(acl_plan)),
                0,
            )
            runner._check_auth_sessions(connection, expected_exists=True)
            check_internal_acls(connection)

        with self.engine.connect() as connection:
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.objects"
                ).scalar_one(),
                8,
            )
        self._seed_stale_audio()
        self._detach_stale_audio_pre_0034()

        with self.migrator.begin() as connection:
            registration_plan = plan_registration(
                connection, self.binding, expected_missing_count=3
            )
            self.assertEqual(len(registration_plan["snapshot"]["objects"]), 10)
            self.assertEqual(len(registration_plan["registrations"]), 3)
            with self.assertRaisesRegex(InventoryBlocked, "digest"):
                apply_registration(
                    connection, self.binding, registration_plan, "0" * 64
                )

        with self.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE FUNCTION public.reject_registration_test() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.path='legacy/photos/b.jpg' THEN
                        RAISE EXCEPTION 'synthetic registration rejection';
                    END IF;
                    RETURN NEW;
                END $$
            """)
            connection.exec_driver_sql("""
                CREATE TRIGGER reject_registration_test
                BEFORE INSERT ON vervfy_storage.objects
                FOR EACH ROW EXECUTE FUNCTION public.reject_registration_test()
            """)
        try:
            with self.migrator.begin() as connection:
                with self.assertRaisesRegex(DBAPIError, "synthetic registration"):
                    apply_registration(
                        connection,
                        self.binding,
                        registration_plan,
                        plan_digest(registration_plan),
                    )
                self.assertEqual(
                    connection.exec_driver_sql("SELECT current_user").scalar_one(),
                    "migration_owner",
                )
            with self.engine.connect() as connection:
                self.assertEqual(
                    connection.exec_driver_sql(
                        "SELECT count(*) FROM vervfy_storage.objects"
                    ).scalar_one(),
                    10,
                )
        finally:
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "DROP TRIGGER reject_registration_test ON vervfy_storage.objects"
                )
                connection.exec_driver_sql(
                    "DROP FUNCTION public.reject_registration_test()"
                )

        with self.migrator.begin() as connection:
            self.assertEqual(
                apply_registration(
                    connection,
                    self.binding,
                    registration_plan,
                    plan_digest(registration_plan),
                ),
                3,
            )
        with self.migrator.begin() as connection:
            self.assertEqual(
                apply_registration(
                    connection,
                    self.binding,
                    registration_plan,
                    plan_digest(registration_plan),
                ),
                0,
            )
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.objects"
                ).scalar_one(),
                13,
            )
            after_objects = (
                connection.exec_driver_sql("""
                SELECT id::text,namespace_id,tenant_id,path,kind,classification,state,
                       reservation_token::text,upload_verified
                FROM vervfy_storage.objects
                ORDER BY path COLLATE "C"
            """)
                .mappings()
                .all()
            )
            after_by_path = {row["path"]: dict(row) for row in after_objects}
            for existing in registration_plan["snapshot"]["objects"]:
                self.assertEqual(after_by_path[existing["path"]], existing)
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.cleanup_jobs"
                ).scalar_one(),
                3,
            )
            new_rows = connection.exec_driver_sql("""
                SELECT tenant_id,kind,classification,state,reservation_token,
                       upload_verified
                FROM vervfy_storage.objects
                WHERE path IN (
                    'legacy/shared.wav','legacy/covers/a.jpg','legacy/photos/b.jpg'
                )
                ORDER BY path
            """).all()
            self.assertEqual(
                new_rows,
                [(None, "legacy", "legacy", "hold", None, False)] * 3,
            )
            self.assertEqual(
                self._security_snapshot(connection),
                self.prepared_security_state,
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT id FROM public.auth_sessions
                    WHERE id='preparation-session'
                """).scalar_one(),
                "preparation-session",
            )
            for role in ("anon", "authenticated", "service_role"):
                self.assertFalse(
                    connection.exec_driver_sql(
                        f"SELECT has_table_privilege('{role}',"
                        "'public.auth_sessions','SELECT')"
                    ).scalar_one()
                )
            self.assertTrue(
                connection.exec_driver_sql("""
                    SELECT has_table_privilege(
                        'app_runtime','public.auth_sessions','SELECT,INSERT,DELETE'
                    )
                """).scalar_one()
            )

        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": self.migration_url,
                "MIGRATION_DATABASE_URL": self.migration_url,
            },
        ):
            command.upgrade(
                Config(str(ROOT / "alembic.ini")),
                "0034_storage_byte_reservations",
            )

        self._charge_stale_audio_post_0034()
        with self.migrator.begin() as connection:
            before = snapshot(connection, self.binding)
            self.assertEqual(len(before["objects"]), 13)
            self.assertEqual(
                sum(row["reserved_bytes"] is None for row in before["objects"]), 11
            )
        size_plan = measure_inventory(
            before,
            lambda path: {
                "bytes": len(path.encode("utf-8")) + 100,
                "sha256": hashlib.sha256(path.encode("utf-8")).hexdigest(),
                "etag": '"synthetic-stable-version"',
            },
        )
        with self.migrator.begin() as connection:
            self.assertEqual(
                apply_inventory(
                    connection,
                    self.binding,
                    size_plan,
                    plan_digest(size_plan),
                ),
                11,
            )
        with self.migrator.begin() as connection:
            self.assertEqual(
                apply_inventory(
                    connection,
                    self.binding,
                    size_plan,
                    plan_digest(size_plan),
                ),
                0,
            )
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.objects "
                    "WHERE reserved_bytes IS NULL"
                ).scalar_one(),
                0,
            )
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.objects"
                ).scalar_one(),
                13,
            )
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.cleanup_jobs"
                ).scalar_one(),
                3,
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT o.path,o.reserved_bytes,j.state
                    FROM vervfy_storage.objects o
                    JOIN vervfy_storage.cleanup_jobs j ON j.object_id=o.id
                    WHERE position('stale-audio-' IN o.path)>0
                    ORDER BY o.path
                """).all(),
                [
                    ("a/stale-audio-a.mp3", 30780168, "held"),
                    ("b/stale-audio-b.wav", 5759110, "held"),
                ],
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT title,artist,album,duration,size_bytes,storage_path
                    FROM public.tracks
                    WHERE left(id,12)='stale-audio-' ORDER BY id
                """).all(),
                [
                    ("Preserve A", "Artist A", "Album A", 123.5, 30780168, None),
                    ("Preserve B", "Artist B", "Album B", 234.5, 5759110, None),
                ],
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT playlist_id,track_id,position
                    FROM public.playlist_tracks
                    WHERE left(track_id,12)='stale-audio-' ORDER BY track_id
                """).all(),
                [
                    ("playlist-a", "stale-audio-a", 1),
                    ("playlist-b", "stale-audio-b", 1),
                ],
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT id,user_id,track_id,played_at FROM public.track_listens
                    WHERE left(track_id,12)='stale-audio-' ORDER BY track_id
                """).all(),
                [
                    ("stale-audio-history-a", "a", "stale-audio-a", 10.0),
                    ("stale-audio-history-b", "b", "stale-audio-b", 20.0),
                ],
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT id FROM public.auth_sessions
                    WHERE id='preparation-session'
                """).scalar_one(),
                "preparation-session",
            )
            self.assertEqual(
                self._security_snapshot(connection),
                self.prepared_security_state,
            )

    def _seed_stale_audio(self):
        sizes = {
            "a/stale-audio-a.mp3": 30_780_168,
            "b/stale-audio-b.wav": 5_759_110,
        }
        self.stale_audio_target_sizes = {
            hashlib.md5(path.encode()).hexdigest(): size for path, size in sizes.items()
        }
        with self.engine.begin() as connection:
            connection.exec_driver_sql("SET session_replication_role=replica")
            connection.execute(
                sa.text("""
                    INSERT INTO public.tracks(
                        id,user_id,filename,title,artist,album,duration,has_cover,
                        cover_source,audio_data,storage_path,size_bytes
                    ) VALUES
                        ('stale-audio-a','a','stale-a.mp3','Preserve A','Artist A',
                         'Album A',123.5,false,'unknown',NULL,
                         'a/stale-audio-a.mp3',30780168),
                        ('stale-audio-b','b','stale-b.wav','Preserve B','Artist B',
                         'Album B',234.5,false,'unknown',NULL,
                         'b/stale-audio-b.wav',5759110)
                """)
            )
            connection.exec_driver_sql("SET session_replication_role=origin")
            connection.exec_driver_sql("""
                INSERT INTO public.playlist_tracks(playlist_id,track_id,position)
                VALUES ('playlist-a','stale-audio-a',1),
                       ('playlist-b','stale-audio-b',1)
            """)
            connection.exec_driver_sql("""
                INSERT INTO public.track_listens(id,user_id,track_id,played_at)
                VALUES ('stale-audio-history-a','a','stale-audio-a',10),
                       ('stale-audio-history-b','b','stale-audio-b',20)
            """)

    def _stale_audio_plan(self, stage):
        runtime = sa.create_engine(self.url.set(username="app_runtime"))
        with (
            runtime.connect() as runtime_connection,
            self.migrator.connect() as migration,
            runtime_connection.begin(),
            migration.begin(),
        ):
            plan = plan_stale_audio_repair(
                runtime_connection,
                migration,
                self.binding,
                self.stale_audio_target_sizes,
                stage=stage,
                confirmed_catalog_absence=True,
                migration_role="migration_owner",
            )
        runtime.dispose()
        return plan, plan_digest(plan)

    def _detach_stale_audio_pre_0034(self):
        plan, digest = self._stale_audio_plan("detach")
        runtime = sa.create_engine(self.url.set(username="app_runtime"))
        self.addCleanup(runtime.dispose)
        with (
            runtime.connect() as runtime_connection,
            self.migrator.connect() as migration,
            runtime_connection.begin(),
            migration.begin(),
            self.assertRaisesRegex(InventoryBlocked, "digest"),
        ):
            detach_stale_audio_references(
                runtime_connection,
                migration,
                self.binding,
                plan,
                "0" * 64,
                migration_role="migration_owner",
            )
        failing_track_id = max(plan["targets"], key=lambda item: item["path_hash"])[
            "track_id"
        ]
        with self.engine.begin() as connection:
            connection.exec_driver_sql(f"""
                CREATE FUNCTION public.reject_stale_detach() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF OLD.id = '{failing_track_id}' AND NEW.storage_path IS NULL THEN
                        RAISE EXCEPTION 'synthetic stale detach rejection';
                    END IF;
                    RETURN NEW;
                END $$
            """)
            connection.exec_driver_sql("""
                CREATE TRIGGER reject_stale_detach
                BEFORE UPDATE OF storage_path ON public.tracks
                FOR EACH ROW EXECUTE FUNCTION public.reject_stale_detach()
            """)
        try:
            with (
                self.assertRaisesRegex(DBAPIError, "synthetic stale detach rejection"),
                runtime.connect() as runtime_connection,
                self.migrator.connect() as migration,
                runtime_connection.begin(),
                migration.begin(),
            ):
                detach_stale_audio_references(
                    runtime_connection,
                    migration,
                    self.binding,
                    plan,
                    digest,
                    migration_role="migration_owner",
                )
        finally:
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "DROP TRIGGER reject_stale_detach ON public.tracks"
                )
                connection.exec_driver_sql("DROP FUNCTION public.reject_stale_detach()")
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT count(*) FROM public.tracks
                    WHERE left(id,12)='stale-audio-' AND storage_path IS NOT NULL
                """).scalar_one(),
                2,
            )
            self.assertEqual(
                connection.exec_driver_sql("""
                    SELECT count(*) FROM vervfy_storage.objects
                    WHERE position('stale-audio-' IN path)>0
                """).scalar_one(),
                0,
            )
        with (
            runtime.connect() as runtime_connection,
            self.migrator.connect() as migration,
            runtime_connection.begin(),
            migration.begin(),
        ):
            self.assertEqual(
                detach_stale_audio_references(
                    runtime_connection,
                    migration,
                    self.binding,
                    plan,
                    digest,
                    migration_role="migration_owner",
                ),
                2,
            )
        with (
            runtime.connect() as runtime_connection,
            self.migrator.connect() as migration,
            runtime_connection.begin(),
            migration.begin(),
        ):
            self.assertEqual(
                detach_stale_audio_references(
                    runtime_connection,
                    migration,
                    self.binding,
                    plan,
                    digest,
                    migration_role="migration_owner",
                ),
                0,
            )

    def _charge_stale_audio_post_0034(self):
        plan, digest = self._stale_audio_plan("charge")
        runtime = sa.create_engine(self.url.set(username="app_runtime"))
        self.addCleanup(runtime.dispose)
        with (
            runtime.connect() as runtime_connection,
            self.migrator.connect() as migration,
            runtime_connection.begin(),
            migration.begin(),
        ):
            self.assertEqual(
                charge_stale_audio_tombstones(
                    runtime_connection,
                    migration,
                    self.binding,
                    plan,
                    digest,
                    migration_role="migration_owner",
                ),
                2,
            )
        with (
            runtime.connect() as runtime_connection,
            self.migrator.connect() as migration,
            runtime_connection.begin(),
            migration.begin(),
        ):
            self.assertEqual(
                charge_stale_audio_tombstones(
                    runtime_connection,
                    migration,
                    self.binding,
                    plan,
                    digest,
                    migration_role="migration_owner",
                ),
                0,
            )


class LegacyRegistrationGuardTests(unittest.TestCase):
    def test_rejects_unregistered_managed_paths_and_unsafe_paths(self):
        binding_id = uuid.uuid4()
        snapshot = {
            "references": [
                {"path": "v2/unregistered/path.wav", "sources": ["track_audio"]}
            ],
            "objects": [],
        }
        with self.assertRaisesRegex(InventoryBlocked, "v2 reference"):
            _registration_rows(snapshot, binding_id)
        for path in ("../escape.wav", "/rooted.wav", "a//b.wav", "a\\b.wav"):
            with self.subTest(path=path):
                self.assertFalse(_valid_path(path))


if __name__ == "__main__":
    unittest.main()
