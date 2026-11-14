from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.engine import make_url

import staging_database_guard as guard

PROJECT_USER = "app_runtime.xgqvwqogdtktgfuubzwk"
HOST = "aws-0-us-east-1.pooler.supabase.com"


class StagingDatabaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.ca_path = Path(self.tempdir.name) / "approved-ca.crt"
        self.ca_bytes = b"test-only CA fixture"
        self.ca_path.write_bytes(self.ca_bytes)
        self.ca_paths_patch = patch.object(
            guard, "STAGING_CA_PATHS", frozenset({str(self.ca_path)})
        )
        self.ca_digest_patch = patch.object(
            guard,
            "STAGING_CA_SHA256",
            hashlib.sha256(self.ca_bytes).hexdigest(),
        )
        self.ca_paths_patch.start()
        self.ca_digest_patch.start()
        self.addCleanup(self.ca_paths_patch.stop)
        self.addCleanup(self.ca_digest_patch.stop)

    def environment(self):
        return {"PGSSLROOTCERT": str(self.ca_path)}

    def url(self, **overrides):
        parts = {
            "user": PROJECT_USER,
            "password": "test-only-password",
            "host": HOST,
            "port": "5432",
            "database": "postgres",
            "query": "sslmode=verify-full&gssencmode=disable",
        }
        parts.update(overrides)
        return (
            f"postgresql+psycopg://{parts['user']}:{parts['password']}"
            f"@{parts['host']}:{parts['port']}/{parts['database']}?"
            f"{parts['query']}"
        )

    def test_approved_endpoint_and_ca_are_accepted(self):
        result = guard.validate_staging_database_url(
            self.url(), "app_runtime", self.environment()
        )
        self.assertEqual(make_url(result), make_url(self.url()))

    def test_google_lookup_role_is_bound_to_the_same_staging_project(self):
        url = self.url(
            user="google_auth_lookup.xgqvwqogdtktgfuubzwk"
        )
        result = guard.validate_staging_database_url(
            url, "google_auth_lookup", self.environment()
        )
        self.assertEqual(make_url(result), make_url(url))

    def test_production_and_mismatched_target_urls_are_rejected(self):
        invalid_urls = (
            self.url(host="prod.example.com"),
            self.url(database="production"),
            self.url(user="postgres.xgqvwqogdtktgfuubzwk"),
            self.url(user="google_auth_lookup.xgqvwqogdtktgfuubzwk"),
            self.url(password=""),
            self.url(port=""),
            self.url(query="sslmode=require"),
            self.url(query="sslmode=verify-ca"),
            self.url(query="sslmode=verify-full&gssencmode=prefer"),
            self.url(query="sslmode=verify-full&sslmode=require"),
            self.url(query="sslmode=verify-full&sslrootcert=/tmp/other.crt"),
        )
        for value in invalid_urls:
            with self.subTest(url=value.split("@")[-1]), self.assertRaises(
                guard.StagingDatabaseConfigurationError
            ) as raised:
                guard.validate_staging_database_url(
                    value, "app_runtime", self.environment()
                )
            self.assertNotIn("test-only-password", str(raised.exception))

    def test_ambiguous_or_unapproved_libpq_overrides_are_rejected(self):
        for key, value in (
            ("PGHOST", HOST),
            ("PGPASSWORD", "override"),
            ("PGSSLMODE", "require"),
            ("PGOPTIONS", "-c sslmode=require"),
            ("SSL_CERT_FILE", str(self.ca_path)),
        ):
            env = {**self.environment(), key: value}
            with self.subTest(key=key), self.assertRaises(
                guard.StagingDatabaseConfigurationError
            ):
                guard.validate_staging_database_url(
                    self.url(), "app_runtime", env
                )

    def test_missing_or_changed_ca_is_rejected(self):
        with self.assertRaises(guard.StagingDatabaseConfigurationError):
            guard.validate_staging_database_url(
                self.url(), "app_runtime", {}
            )

        self.ca_path.write_bytes(b"changed CA")
        with self.assertRaises(guard.StagingDatabaseConfigurationError):
            guard.validate_staging_database_url(
                self.url(), "app_runtime", self.environment()
            )

    def test_invalid_staging_url_fails_before_engine_creation_on_import(self):
        source_root = Path(__file__).resolve().parents[1]
        script = """
from staging_database_guard import StagingDatabaseConfigurationError
from unittest.mock import patch
with patch("sqlalchemy.create_engine") as create_engine:
    try:
        import db
    except StagingDatabaseConfigurationError:
        assert not create_engine.called
    else:
        raise AssertionError("invalid staging database URL was accepted")
"""
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("PG")
            and key not in {"SSL_CERT_FILE", "SSL_CERT_DIR"}
        }
        env.update(
            {
                "PYTHONPATH": str(source_root),
                "VERVFY_ENVIRONMENT": "staging",
                "DATABASE_URL": self.url(host="production.example.com"),
                "PGSSLROOTCERT": "/etc/secrets/prod-ca-2021.crt",
            }
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
