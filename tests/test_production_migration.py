from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from sqlalchemy.engine import URL

from scripts.production_migration import (
    AUTHORIZATION_TTL,
    MigrationBlocked,
    PRODUCTION_PROJECT_REF,
    START_REVISION,
    TARGET_REVISION,
    REQUIRED_TABLES,
    ProductionTarget,
    load_target,
    preflight,
    validate_authorization,
    validate_migration_chain,
)


class ProductionTargetTests(unittest.TestCase):
    def setUp(self):
        self.ca_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.ca_dir.cleanup)
        self.ca = Path(self.ca_dir.name) / "ca.pem"
        self.ca.write_text("test CA bundle\n")
        self.env = {
            "VERVFY_ENVIRONMENT": "production",
            "VERVFY_PRODUCTION_PROJECT_REF": PRODUCTION_PROJECT_REF,
            "VERVFY_PRODUCTION_EXPECTED_DATABASE": "postgres",
            "VERVFY_PRODUCTION_EXPECTED_USER": "vervfy_prod_migrator",
            "VERVFY_PRODUCTION_CA_FILE": str(self.ca),
            "VERVFY_PRODUCTION_DATABASE_URL": URL.create(
                "postgresql+psycopg",
                username="vervfy_prod_migrator",
                password="placeholder-secret",
                host=f"db.{PRODUCTION_PROJECT_REF}.supabase.co",
                port=5432,
                database="postgres",
                query={
                    "sslmode": "verify-full",
                    "sslrootcert": str(self.ca.resolve()),
                },
            ).render_as_string(hide_password=False),
        }

    def test_accepts_exact_direct_production_target_with_verify_full(self):
        target = load_target(self.env)
        self.assertEqual(target.project_ref, self.env["VERVFY_PRODUCTION_PROJECT_REF"])
        self.assertEqual(
            target.url.host, f"db.{PRODUCTION_PROJECT_REF}.supabase.co"
        )
        self.assertEqual(target.url.query["sslmode"], "verify-full")
        self.assertEqual(target.connection_mode, "direct")

    def test_accepts_exact_project_session_pooler_username(self):
        self.env["VERVFY_PRODUCTION_CONNECTION_MODE"] = "session"
        self.env["VERVFY_PRODUCTION_DATABASE_URL"] = URL.create(
            "postgresql+psycopg",
            username=f"vervfy_prod_migrator.{PRODUCTION_PROJECT_REF}",
            password="placeholder-secret",
            host="aws-0-us-east-2.pooler.supabase.com",
            port=5432,
            database="postgres",
            query={
                "sslmode": "verify-full",
                "sslrootcert": str(self.ca.resolve()),
            },
        ).render_as_string(hide_password=False)

        target = load_target(self.env)
        self.assertEqual(target.connection_mode, "session")
        self.assertEqual(
            target.url.username,
            f"vervfy_prod_migrator.{PRODUCTION_PROJECT_REF}",
        )
        self.assertEqual(target.username, "vervfy_prod_migrator")

    def test_rejects_staging_project_even_if_url_matches(self):
        self.env["VERVFY_PRODUCTION_PROJECT_REF"] = "xgqvwqogdtktgfuubzwk"
        self.env["VERVFY_PRODUCTION_DATABASE_URL"] = self.env[
            "VERVFY_PRODUCTION_DATABASE_URL"
        ].replace(
            f"db.{PRODUCTION_PROJECT_REF}.supabase.co",
            "db.xgqvwqogdtktgfuubzwk.supabase.co",
        )
        with self.assertRaisesRegex(MigrationBlocked, "project reference"):
            load_target(self.env)

    def test_rejects_host_or_role_mismatch(self):
        self.env["VERVFY_PRODUCTION_DATABASE_URL"] = self.env[
            "VERVFY_PRODUCTION_DATABASE_URL"
        ].replace("vervfy_prod_migrator", "app_runtime")
        with self.assertRaisesRegex(MigrationBlocked, "must match"):
            load_target(self.env)

    def test_rejects_session_pooler_identity_mode_and_endpoint_mismatches(self):
        valid_url = URL.create(
            "postgresql+psycopg",
            username=f"vervfy_prod_migrator.{PRODUCTION_PROJECT_REF}",
            password="placeholder-secret",
            host="aws-0-us-east-2.pooler.supabase.com",
            port=5432,
            database="postgres",
            query={
                "sslmode": "verify-full",
                "sslrootcert": str(self.ca.resolve()),
            },
        )
        self.env["VERVFY_PRODUCTION_CONNECTION_MODE"] = "session"
        cases = (
            ("unqualified login", valid_url.set(username="vervfy_prod_migrator")),
            (
                "wrong project-qualified login",
                valid_url.set(username="vervfy_prod_migrator.otherprojectref"),
            ),
            ("wrong project ref", None),
            ("wrong pooler host", valid_url.set(host="aws-0-us-west-1.pooler.supabase.com")),
            ("transaction-pooling port", valid_url.set(port=6543)),
            ("wrong database", valid_url.set(database="other")),
            (
                "unverified TLS",
                valid_url.set(query={"sslmode": "require", "sslrootcert": str(self.ca)}),
            ),
        )
        for label, url in cases:
            with self.subTest(label=label):
                if label == "wrong project ref":
                    env = {
                        **self.env,
                        "VERVFY_PRODUCTION_PROJECT_REF": "abcdefghijklmnopqrst",
                    }
                else:
                    env = {
                        **self.env,
                        "VERVFY_PRODUCTION_DATABASE_URL": url.render_as_string(
                            hide_password=False
                        ),
                    }
                with self.assertRaises(MigrationBlocked):
                    load_target(env)

    def test_pooler_requires_explicit_session_mode(self):
        self.env["VERVFY_PRODUCTION_DATABASE_URL"] = URL.create(
            "postgresql+psycopg",
            username=f"vervfy_prod_migrator.{PRODUCTION_PROJECT_REF}",
            password="placeholder-secret",
            host="aws-0-us-east-2.pooler.supabase.com",
            port=5432,
            database="postgres",
            query={
                "sslmode": "verify-full",
                "sslrootcert": str(self.ca.resolve()),
            },
        ).render_as_string(hide_password=False)
        with self.assertRaisesRegex(MigrationBlocked, "direct host"):
            load_target(self.env)

    def test_rejects_unapproved_role_and_connection_mode(self):
        for name, value in (
            ("VERVFY_PRODUCTION_EXPECTED_USER", "postgres"),
            ("VERVFY_PRODUCTION_CONNECTION_MODE", "transaction"),
        ):
            with self.subTest(name=name):
                with self.assertRaises(MigrationBlocked):
                    load_target({**self.env, name: value})

    def test_rejects_non_verifying_tls(self):
        self.env["VERVFY_PRODUCTION_DATABASE_URL"] = self.env[
            "VERVFY_PRODUCTION_DATABASE_URL"
        ].replace("verify-full", "require")
        with self.assertRaisesRegex(MigrationBlocked, "sslmode=verify-full"):
            load_target(self.env)

    def test_rejects_database_url_fallback_and_libpq_overrides(self):
        for name in ("DATABASE_URL", "PGHOST"):
            with self.subTest(name=name):
                with self.assertRaises(MigrationBlocked):
                    load_target({**self.env, name: "unexpected"})


class ProductionTLSPreflightTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.pgconn = SimpleNamespace(ssl_in_use=True)
        self.connection.connection = SimpleNamespace(
            driver_connection=SimpleNamespace(pgconn=self.pgconn)
        )
        self.target = ProductionTarget(
            url=URL.create(
                "postgresql+psycopg",
                query={"sslmode": "verify-full", "sslrootcert": "/test/ca.pem"},
            ),
            project_ref=PRODUCTION_PROJECT_REF,
            database="postgres",
            username="vervfy_prod_migrator",
        )

    def test_client_tls_passes_direct_and_session_preflight_without_server_ssl(self):
        for mode in ("direct", "session"):
            with self.subTest(mode=mode):
                self.connection.reset_mock()
                identity = MagicMock()
                identity.one.return_value = (
                    "postgres", self.target.username, self.target.username,
                    "public", 170000,
                )
                principal = MagicMock()
                role = MagicMock()
                role.__getitem__.return_value = (False,) * 5
                role.rolcanlogin = True
                principal.one_or_none.return_value = role
                privileges = MagicMock()
                privileges.one.return_value = (True,) * 4
                owned = MagicMock()
                owned.scalars.return_value = iter(REQUIRED_TABLES)
                version_owner = MagicMock()
                version_owner.scalar_one_or_none.return_value = self.target.username
                revision = MagicMock()
                revision.scalars.return_value.all.return_value = [START_REVISION]
                unexpected = MagicMock()
                unexpected.scalars.return_value.all.return_value = []
                self.connection.execute.side_effect = [
                    identity, principal, privileges, owned, version_owner,
                    revision, unexpected,
                ]
                target = ProductionTarget(
                    self.target.url, self.target.project_ref,
                    self.target.database, self.target.username, mode,
                )
                with patch("scripts.production_migration._check_role_graph") as graph:
                    preflight(self.connection, target)
                graph.assert_called_once_with(self.connection, target.username)
                for call in self.connection.execute.call_args_list:
                    self.assertNotIn("pg_stat_ssl", str(call.args[0]))

    def test_absent_tls_blocks_even_with_verify_full_configured(self):
        self.pgconn.ssl_in_use = False
        with self.assertRaisesRegex(MigrationBlocked, "did not negotiate TLS"):
            preflight(self.connection, self.target)
        self.connection.begin.assert_not_called()
        self.connection.execute.assert_not_called()

    def test_missing_or_ambiguous_tls_evidence_blocks(self):
        for pgconn in (
            SimpleNamespace(), None,
            *(SimpleNamespace(ssl_in_use=value) for value in (None, 1, "true")),
        ):
            with self.subTest(pgconn=pgconn):
                self.connection.connection.driver_connection.pgconn = pgconn
                with self.assertRaisesRegex(MigrationBlocked, "evidence is unavailable"):
                    preflight(self.connection, self.target)
        self.connection.begin.assert_not_called()
        self.connection.execute.assert_not_called()

    def test_unreadable_tls_evidence_blocks_without_exposing_driver_error(self):
        pgconn = MagicMock()
        type(pgconn).ssl_in_use = PropertyMock(
            side_effect=RuntimeError("sensitive connection details")
        )
        self.connection.connection.driver_connection.pgconn = pgconn
        with self.assertRaisesRegex(MigrationBlocked, "evidence is unavailable") as error:
            preflight(self.connection, self.target)
        self.assertNotIn("sensitive", str(error.exception))
        self.connection.execute.assert_not_called()


class ProductionAuthorizationTests(unittest.TestCase):
    def test_requires_exact_short_lived_future_expiry(self):
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        expiry = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        validate_authorization(expiry, now=now)
        for invalid in (
            (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            (now + AUTHORIZATION_TTL + timedelta(seconds=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "2026-11-12T12:10:00+00:00",
            "not-a-time",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(MigrationBlocked):
                    validate_authorization(invalid, now=now)

    def test_operation_is_pinned_to_requested_revisions(self):
        self.assertEqual(
            f"{START_REVISION}..{TARGET_REVISION}",
            "0019_track_listens..0028_webauthn_enrollment",
        )
        validate_migration_chain()
