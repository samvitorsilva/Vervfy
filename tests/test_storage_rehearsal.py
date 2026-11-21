"""Disposable workflow: real local TLS/PostgreSQL, fake provider bytes, no hosted access."""

import hashlib
import os
import socket
import subprocess
import unittest
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import sqlalchemy as sa
import test_staging_migrations as fixtures
from sqlalchemy.exc import DBAPIError

from alembic import command
from scripts import storage_rehearsal as work
from storage_inventory import plan_digest, snapshot


class PopulatedRehearsalTests(unittest.TestCase):
    start = "0031_cleanup_retry_limits"
    account_snapshot = staticmethod(fixtures.StagingPostgresTests.account_snapshot)

    @classmethod
    def setUpClass(cls):
        original = command.upgrade

        def baseline(config, revision, *args, **kwargs):
            if revision == "head":
                with cls.engine.begin() as c:
                    for actor, track in (("a", "embedded"), ("b", "track-b")):
                        c.execute(
                            sa.text("SELECT set_config('app.current_user_id',:a,true)"),
                            {"a": actor},
                        )
                        c.execute(
                            sa.text(
                                "UPDATE tracks SET storage_path='legacy/shared.mp3' WHERE id=:id AND user_id=:a"
                            ),
                            {"id": track, "a": actor},
                        )
                revision = cls.start
            return original(config, revision, *args, **kwargs)

        with patch.object(command, "upgrade", baseline):
            fixtures.StagingPostgresTests.setUpClass.__func__(cls)
        cert, key = cls.root / "rehearsal.crt", cls.root / "rehearsal.key"
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
            out.write(f"\nssl=on\nssl_cert_file='{cert}'\nssl_key_file='{key}'\n")
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
        cls.config = {
            "purpose": work.PURPOSE,
            "project_ref": "d" * 20,
            "namespace_id": str(uuid.uuid4()),
            "bucket": "vervfy-rehearsal-synthetic",
            "start_revision": cls.start,
            "run_id": str(uuid.uuid4()),
            "ca_sha256": hashlib.sha256(cert.read_bytes()).hexdigest(),
            "history_sha256": work.history_digest(),
        }
        config_path = cls.root / "profile.json"
        work.write_private(config_path, cls.config)
        cls.config_digest = plan_digest(cls.config)
        fake_migration = sa.URL.create(
            "postgresql+psycopg",
            username=work.LOGIN,
            password="synthetic",
            host="db." + "d" * 20 + ".supabase.co",
            port=5432,
            database="postgres",
            query=cls.url.query,
        )
        cls.env = {
            "VERVFY_ENVIRONMENT": "disposable-storage-rehearsal",
            "VERVFY_REHEARSAL_CA_FILE": str(cert),
            "VERVFY_REHEARSAL_STORAGE_KEY": "synthetic-project-key",
            "VERVFY_REHEARSAL_DATABASE_URL": fake_migration.render_as_string(
                hide_password=False
            ),
            "VERVFY_REHEARSAL_RUNTIME_URL": fake_migration.set(
                username="app_runtime"
            ).render_as_string(hide_password=False),
        }
        cls.profile = work.load_profile(config_path, cls.config_digest, cls.env)
        cls.config_path = config_path
        with cls.engine.begin() as c:
            c.exec_driver_sql(f"ALTER ROLE migration_owner RENAME TO {work.LOGIN}")
            c.exec_driver_sql(f"""UPDATE pg_catalog.pg_auth_members SET grantor='postgres'::regrole
                WHERE roleid IN ('vervfy_storage_lifecycle_owner'::regrole,'vervfy_storage_cleanup'::regrole)
                AND member IN ('{work.LOGIN}'::regrole,'storage_cleanup_worker'::regrole)""")
            c.exec_driver_sql(
                f"CREATE SCHEMA vervfy_rehearsal AUTHORIZATION {work.LOGIN}"
            )
            c.exec_driver_sql(
                "CREATE TABLE vervfy_rehearsal.approval(project_ref text,run_id uuid,config_sha256 text,disposable boolean CHECK(disposable))"
            )
            c.exec_driver_sql(
                f"ALTER TABLE vervfy_rehearsal.approval OWNER TO {work.LOGIN}"
            )
            c.execute(
                sa.text(
                    "INSERT INTO vervfy_rehearsal.approval VALUES (:ref,:run,:digest,true)"
                ),
                {
                    "ref": cls.config["project_ref"],
                    "run": cls.config["run_id"],
                    "digest": cls.config_digest,
                },
            )
            c.execute(
                sa.text(
                    "INSERT INTO vervfy_storage.namespaces VALUES(1,:id,'disposable-rehearsal',:endpoint,:bucket,false)"
                ),
                {
                    "id": cls.profile.binding.namespace_id,
                    "endpoint": cls.profile.binding.endpoint,
                    "bucket": cls.profile.binding.bucket,
                },
            )
            c.execute(
                sa.text(
                    "INSERT INTO vervfy_storage.objects(id,namespace_id,path,kind,classification,state) VALUES(:id,1,'legacy/shared.mp3','legacy','legacy','hold')"
                ),
                {"id": uuid.uuid4()},
            )
        cls.payloads = {"legacy/shared.mp3": b"shared-synthetic"}
        cls.runtime = sa.create_engine(cls.url.set(username="app_runtime"))
        cls.addClassCleanup(cls.runtime.dispose)
        cls.migrator = sa.create_engine(cls.url.set(username=work.LOGIN))
        cls.addClassCleanup(cls.migrator.dispose)
        for actor in work.TENANTS:
            paths = {}
            for kind in ("audio", "track-cover", "artist-photo", "staged-audio"):
                ident, token = uuid.uuid4(), uuid.uuid4()
                path = (
                    f"v2/{cls.profile.binding.namespace_id}/{actor}/{kind}/{ident}.mp3"
                )
                paths[kind] = path
                cls.payloads[path] = b"synthetic-" + actor.encode() + kind.encode()
                with cls.engine.begin() as c:
                    c.execute(
                        sa.text("""INSERT INTO vervfy_storage.objects(id,namespace_id,tenant_id,path,kind,
                        classification,state,reservation_token,upload_verified) VALUES(:id,1,:a,:p,:k,'managed','ready',:token,true)"""),
                        {"id": ident, "a": actor, "p": path, "k": kind, "token": token},
                    )
                    c.execute(
                        sa.text(
                            "INSERT INTO vervfy_storage.cleanup_jobs(object_id,requested_by,state) VALUES(:id,:a,'pending')"
                        ),
                        {"id": ident, "a": actor},
                    )
            with cls.runtime.begin() as c:
                c.execute(
                    sa.text("SELECT set_config('app.current_user_id',:a,true)"),
                    {"a": actor},
                )
                c.execute(
                    sa.text("""INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source,storage_path,cover_path)
                    VALUES(:id,:a,'synthetic.mp3','synthetic','artist','album',1,true,'embedded',:p,:cover)"""),
                    {
                        "id": "synthetic-" + actor,
                        "a": actor,
                        "p": paths["audio"],
                        "cover": paths["track-cover"],
                    },
                )
                c.execute(
                    sa.text("""INSERT INTO artist_photos(user_id,normalized_artist_name,source,storage_path)
                    VALUES(:a,'synthetic','user',:p)"""),
                    {"a": actor, "p": paths["artist-photo"]},
                )
                c.execute(
                    sa.text("""INSERT INTO upload_jobs(id,user_id,filename,storage_path,status,attempts,cover_data,created_at)
                    VALUES(:id,:a,'synthetic.mp3',:p,'pending',0,:cover,1)"""),
                    {
                        "id": "job-" + actor,
                        "a": actor,
                        "p": paths["staged-audio"],
                        "cover": b"durable-original-artwork",
                    },
                )

    def engine_for(self, url):
        # Replace only the network destination with our local TLS fixture.
        # Manifest validation and all SQL/TLS guards still execute unchanged.
        engine = sa.create_engine(self.url.set(username=url.username))
        if not getattr(self, "lose_commit_ack", False):
            return engine

        class LostAcknowledgement:
            @contextmanager
            def begin(self):
                with engine.begin() as connection:
                    yield connection
                raise OSError("synthetic COMMIT acknowledgement lost after commit")

            def dispose(self):
                engine.dispose()

        return LostAcknowledgement()

    def cli(self, operation, **flags):
        args = [
            operation,
            "--config",
            str(self.config_path),
            "--config-sha256",
            self.config_digest,
            "--confirm-disposable-project",
            self.config["project_ref"],
            "--confirm-writers-paused",
            "--authorization-expires-at",
            (datetime.now(UTC) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ]
        for key, value in flags.items():
            args.extend(["--" + key.replace("_", "-"), str(value)])
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(work, "engine_for", self.engine_for),
        ):
            return work.main(args)

    def test_populated_upgrade_rollback_recovery_and_reconciliation(self):
        receipt_path = self.root / "baseline.json"
        self.assertEqual(self.cli("snapshot", receipt_file=receipt_path), 0)
        receipt = work.read_private(receipt_path)
        approved = plan_digest(receipt)
        self.assertEqual(
            self.cli("recover", receipt_file=receipt_path, receipt_sha256=approved), 0
        )
        # An occupied advisory lock must fail before revision checks or DDL.
        with self.engine.begin() as blocker:
            blocker.execute(
                sa.text("SELECT pg_advisory_xact_lock(:id)"),
                {"id": work.production.MIGRATION_LOCK_ID},
            )
            self.assertEqual(
                self.cli(
                    "upgrade",
                    receipt_file=receipt_path,
                    receipt_sha256=approved,
                    authorize_upgrade=f"{self.start}..{work.production.TARGET_REVISION}",
                ),
                1,
            )
        # Inject a rejecting verification, never a successful bypass of a guard.
        original = work.guard

        def reject(connection, profile, *, head):
            original(connection, profile, head=head)
            if head == work.production.TARGET_REVISION:
                raise work.RehearsalBlocked("synthetic postflight rejection")

        with patch.object(work, "guard", reject):
            self.assertEqual(
                self.cli(
                    "upgrade",
                    receipt_file=receipt_path,
                    receipt_sha256=approved,
                    authorize_upgrade=f"{self.start}..{work.production.TARGET_REVISION}",
                ),
                1,
            )
        self.assertEqual(
            self.cli("recover", receipt_file=receipt_path, receipt_sha256=approved), 0
        )
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one(),
                self.start,
            )
            self.assertIsNone(
                c.exec_driver_sql(
                    "SELECT to_regclass('vervfy_storage.quota_policy')"
                ).scalar_one()
            )
        self.lose_commit_ack = True
        self.assertEqual(
            self.cli(
                "upgrade",
                receipt_file=receipt_path,
                receipt_sha256=approved,
                authorize_upgrade=f"{self.start}..{work.production.TARGET_REVISION}",
            ),
            1,
        )
        self.lose_commit_ack = False
        # A reconnect after a potentially lost COMMIT acknowledgement must detect head.
        with self.migrator.begin() as c:
            c.exec_driver_sql("SET TRANSACTION READ ONLY")
            self.assertEqual(work.recover(c, self.profile, receipt), "committed_0034")
        self.assertEqual(self.cli("verify"), 0)
        with self.migrator.begin() as c:
            work.guard(c, self.profile, head=work.production.TARGET_REVISION)
            before = snapshot(c, self.profile.binding)
        self.assertTrue(all(r["reserved_bytes"] is None for r in before["objects"]))

        def provider(request):
            self.assertEqual(request.method, "GET")
            if request.url.path == f"/storage/v1/bucket/{self.profile.binding.bucket}":
                return httpx.Response(
                    200, json={"id": self.profile.binding.bucket, "public": False}
                )
            prefix = f"/storage/v1/object/authenticated/{self.profile.binding.bucket}/"
            self.assertTrue(request.url.path.startswith(prefix))
            data = self.payloads[request.url.path[len(prefix) :]]
            return httpx.Response(
                200,
                content=data,
                headers={"etag": '"' + hashlib.sha256(data).hexdigest() + '"'},
            )

        plan_path = self.root / "inventory.json"
        original_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return original_client(transport=httpx.MockTransport(provider), **kwargs)

        with patch.object(work.httpx, "AsyncClient", client_factory):
            self.assertEqual(self.cli("plan", plan_file=plan_path), 0)
        plan = work.read_private(plan_path)
        self.assertEqual(
            self.cli("apply", plan_file=plan_path, plan_sha256=plan_digest(plan)), 0
        )
        self.assertEqual(
            self.cli("apply", plan_file=plan_path, plan_sha256=plan_digest(plan)), 0
        )
        self.assertEqual(self.cli("verify"), 0)
        with self.migrator.begin() as c:
            self.assertEqual(
                work.fingerprints(c, receipt["baseline"]["tables"]), receipt["baseline"]
            )
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT sum(reserved_bytes) FROM vervfy_storage.objects"
                ).scalar_one(),
                sum(map(len, self.payloads.values())),
            )
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )

        with self.migrator.connect() as c:
            transaction = c.begin()
            c.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            c.exec_driver_sql(
                "UPDATE tracks SET title='changed' WHERE id='synthetic-a' AND user_id='a'"
            )
            with self.assertRaisesRegex(work.RehearsalBlocked, "Recovery data changed"):
                work.recover(c, self.profile, receipt)
            transaction.rollback()
        for mutation in (
            "UPDATE vervfy_rehearsal.approval SET config_sha256='wrong'",
            "ALTER TABLE tracks NO FORCE ROW LEVEL SECURITY",
        ):
            with self.migrator.connect() as c:
                transaction = c.begin()
                c.exec_driver_sql(mutation)
                with self.assertRaises(work.RehearsalBlocked):
                    work.guard(c, self.profile, head=work.production.TARGET_REVISION)
                transaction.rollback()
        # Only this disposable fixture gets a tiny policy to prove the shared cap.
        total = sum(map(len, self.payloads.values()))
        with self.engine.begin() as c:
            c.execute(
                sa.text(
                    "UPDATE vervfy_storage.quota_policy SET tenant_limit_bytes=1000,total_limit_bytes=:n"
                ),
                {"n": total + 1},
            )
        with self.runtime.connect() as c:
            transaction = c.begin()
            c.exec_driver_sql("SELECT set_config('app.current_user_id','a',true)")
            c.exec_driver_sql(
                "SELECT * FROM vervfy_storage.reserve_sized_object('audio','mp3',1,1000)"
            ).one()
            c.exec_driver_sql("SELECT set_config('app.current_user_id','b',true)")
            with self.assertRaises(DBAPIError), c.begin_nested():
                c.exec_driver_sql(
                    "SELECT * FROM vervfy_storage.reserve_sized_object('audio','mp3',1,1000)"
                )
            transaction.rollback()
        with self.engine.begin() as c:
            c.exec_driver_sql(
                "UPDATE vervfy_storage.quota_policy SET tenant_limit_bytes=157286400,total_limit_bytes=10737418240"
            )


class PopulatedFrom0033Tests(PopulatedRehearsalTests):
    start = "0033_cleanup_claims_disabled"
