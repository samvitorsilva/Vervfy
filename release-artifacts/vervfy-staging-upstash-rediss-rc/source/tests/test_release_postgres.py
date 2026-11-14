"""Release regressions: synthetic accounts and a private Unix-socket PostgreSQL.

No provider/storage traffic. Full migration chain stops at 0027.
"""

import asyncio
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import sqlalchemy as sa
import test_google_oauth as oauth_tests
import test_staging_migrations as migration_tests
from sqlalchemy.orm import sessionmaker
from test_google_oauth import oauth_config

import auth
import db
import google_oauth
import server
from storage_namespace import NamespaceBinding, initialize_namespace


class ReleasePostgresTests(unittest.TestCase):
    setUpClass = classmethod(migration_tests.StagingPostgresTests.setUpClass.__func__)
    account_snapshot = staticmethod(
        migration_tests.StagingPostgresTests.account_snapshot
    )

    def setUp(self):
        self.runtime = sa.create_engine(self.url.set(username="app_runtime"))
        self.lookup_engine = sa.create_engine(
            self.url.set(username="google_auth_lookup")
        )
        self.addCleanup(self.runtime.dispose)
        self.addCleanup(self.lookup_engine.dispose)
        sessions = sessionmaker(self.runtime, autoflush=False, expire_on_commit=False)
        sa.event.listen(sessions, "after_begin", db.set_database_tenant)
        self.enterContext(patch.object(auth, "SessionLocal", sessions))
        self.enterContext(
            patch.object(
                auth,
                "tenant_session",
                lambda tenant_id: sessions(info={"tenant_id": tenant_id}),
            )
        )
        self.store = auth.UserStore()
        self.identity_service = google_oauth.GoogleOAuthService.__new__(
            google_oauth.GoogleOAuthService
        )
        self.identity_service.identity_engine = self.lookup_engine
        self.binding = NamespaceBinding(
            uuid.UUID("00000000-0000-0000-0000-000000000099"),
            "release-test",
            "https://storage.invalid",
            "synthetic",
        )

    def create_google(self):
        suffix = uuid.uuid4().hex[:12]
        subject = "subject-" + suffix
        return self.store.create_google_user(
            "google-" + suffix, suffix + "@example.invalid", subject
        ), subject

    def test_google_creation_is_atomic_and_unique_under_runtime_rls(self):
        user, subject = self.create_google()
        with self.engine.connect() as c:
            row = c.execute(
                sa.text("SELECT password_hash,email_verified FROM users WHERE id=:id"),
                {"id": user["id"]},
            ).one()
            self.assertEqual(tuple(row), (None, True))
            before = c.exec_driver_sql("SELECT count(*) FROM users").scalar_one()
        with self.assertRaises(ValueError):
            self.store.create_google_user(
                "duplicate-" + uuid.uuid4().hex[:10], None, subject
            )
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql("SELECT count(*) FROM users").scalar_one(), before
            )
            self.assertEqual(
                c.execute(
                    sa.text(
                        "SELECT count(*) FROM provider_identities WHERE user_id=:id"
                    ),
                    {"id": user["id"]},
                ).scalar_one(),
                1,
            )
        with self.runtime.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM provider_identities"
                ).scalar_one(),
                0,
            )

    def test_google_login_callback_uses_postgres_lookup_and_account(self):
        user, subject = self.create_google()
        claims = {
            "iss": google_oauth.GOOGLE_ISSUER,
            "sub": subject,
            "email": "untrusted-profile@example.invalid",
        }
        flow = oauth_tests.CallbackTests._flow(self, claims=claims)
        flow.browser_binding = "browser"
        flow.lookup_identity = self.identity_service.lookup_identity
        request = SimpleNamespace(
            query_params={"state": "one-time-state", "code": "synthetic-code"},
            cookies={oauth_config().browser_cookie_name: "browser"},
            session={},
        )
        with (
            patch.object(server, "google_oauth_config", oauth_config()),
            patch.object(server, "google_oauth_service", flow),
        ):
            result = asyncio.run(server.google_oauth_callback(request))
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.headers["location"], "/")
        self.assertEqual(request.session["user_id"], user["id"])
        self.assertTrue(request.session["sid"])
        self.assertIsNone(
            self.identity_service.lookup_identity(
                {"iss": google_oauth.GOOGLE_ISSUER, "sub": "missing-subject"}
            )
        )

    def test_google_linking_preserves_account_and_fences_duplicate_ownership(self):
        suffix = uuid.uuid4().hex[:10]
        user = self.store.create_user(
            "password-" + suffix, None, "Synthetic-password-123"
        )
        other = self.store.create_user(
            "other-" + suffix, None, "Synthetic-password-456"
        )
        with self.engine.connect() as c:
            before = c.execute(
                sa.text("SELECT password_hash,session_version FROM users WHERE id=:id"),
                {"id": user["id"]},
            ).one()
        subject = "link-" + suffix
        version = self.store.link_google_identity(user["id"], subject)
        self.assertEqual(version, before.session_version + 1)
        self.assertEqual(
            self.identity_service.lookup_identity(
                {"iss": google_oauth.GOOGLE_ISSUER, "sub": subject}
            ),
            user["id"],
        )
        with self.assertRaises(ValueError):
            self.store.link_google_identity(other["id"], subject)
        with self.engine.connect() as c:
            after = c.execute(
                sa.text("SELECT password_hash,session_version FROM users WHERE id=:id"),
                {"id": user["id"]},
            ).one()
            self.assertEqual(after.password_hash, before.password_hash)
            self.assertEqual(
                c.execute(
                    sa.text("SELECT session_version FROM users WHERE id=:id"),
                    {"id": other["id"]},
                ).scalar_one(),
                0,
            )
        self.assertTrue(self.store.account_security(user["id"])["google_linked"])
        google_only, _ = self.create_google()
        with self.assertRaises(ValueError):
            self.store.link_google_identity(google_only["id"], "another-subject")

    def test_namespace_initialization_retry_conflict_and_rollback(self):
        with self.engine.connect() as c:
            c.begin()
            initialize_namespace(c, self.binding)
            initialize_namespace(c, self.binding)
            for field, value in [
                ("namespace_id", uuid.uuid4()),
                ("environment", "other"),
                ("endpoint", "https://other.invalid"),
                ("bucket", "other"),
            ]:
                with (
                    self.subTest(field=field),
                    self.assertRaisesRegex(RuntimeError, "different immutable"),
                ):
                    initialize_namespace(c, replace(self.binding, **{field: value}))
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.namespaces"
                ).scalar_one(),
                1,
            )
            self.assertFalse(
                c.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
            )
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one(),
                "0027_storage_lifecycle",
            )
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM pg_proc WHERE pronamespace='vervfy_storage'::regnamespace AND proname IN ('claim_next_cleanup','complete_cleanup','retry_cleanup')"
                ).scalar_one(),
                0,
            )

    def test_namespace_denied_to_runtime_and_invalid_binding(self):
        with (
            self.runtime.begin() as c,
            self.assertRaisesRegex(RuntimeError, "bootstrap administrator"),
        ):
            initialize_namespace(c, self.binding)
        with self.engine.begin() as c:
            with self.assertRaises(ValueError):
                initialize_namespace(
                    c, replace(self.binding, endpoint="http://storage.invalid")
                )
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.namespaces"
                ).scalar_one(),
                0,
            )

    def test_namespace_revision_fence_and_transaction_rollback(self):
        with self.engine.connect() as c:
            tx = c.begin()
            initialize_namespace(c, self.binding)
            tx.rollback()
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.namespaces"
                ).scalar_one(),
                0,
            )
            c.rollback()
            with c.begin():
                c.exec_driver_sql(
                    "UPDATE alembic_version SET version_num='0026_application_runtime_grants'"
                )
                with self.assertRaisesRegex(RuntimeError, "revision 0027"):
                    initialize_namespace(c, self.binding)
                self.assertEqual(
                    c.exec_driver_sql(
                        "SELECT count(*) FROM vervfy_storage.namespaces"
                    ).scalar_one(),
                    0,
                )
                # Roll back this synthetic revision alteration too.
                c.rollback()

    def test_z_namespace_concurrent_identical_initializers(self):
        def initialize():
            with self.engine.begin() as c:
                return initialize_namespace(c, self.binding)

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(
                list(pool.map(lambda _: initialize(), range(2))),
                [self.binding, self.binding],
            )
        with self.engine.connect() as c:
            self.assertEqual(
                c.exec_driver_sql(
                    "SELECT count(*) FROM vervfy_storage.namespaces"
                ).scalar_one(),
                1,
            )
        # No immutable row cleanup: class teardown drops the disposable cluster.
