"""No database imports or connections; exercise the Supabase staging boundary."""
import hashlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import staging_guard as guard


class SupabaseStagingGuardTests(unittest.TestCase):
    def setUp(self):
        self.approval = {
            "hostname": "aws-0-us-east-1.pooler.supabase.com",
            "port": 5432,
            "database": "postgres",
            "resource_id": "xgqvwqogdtktgfuubzwk",
            "ca_file": "/approved/ca.pem",
            "ca_sha256": hashlib.sha256(b"CA").hexdigest(),
        }

    def url(self, role):
        return (
            f"postgresql+psycopg://{role}.{self.approval['resource_id']}:p%40ss"
            f"@{self.approval['hostname']}:{self.approval['port']}/postgres?"
            + urlencode(
                {
                    "sslmode": "verify-full",
                    "sslrootcert": self.approval["ca_file"],
                    "gssencmode": "disable",
                }
            )
        )

    def test_valid_urls_require_pooler_project_ref_and_all_three_roles(self):
        for role in guard.ROLES.values():
            with self.subTest(role=role):
                guard.validate_url(self.url(role), role, self.approval)

    def test_production_and_mismatched_endpoints_are_rejected(self):
        for role in guard.ROLES.values():
            url = self.url(role)
            for value in (
                url.replace(self.approval["hostname"], "aws-0-production.pooler.supabase.com"),
                url.replace(f"{role}.{self.approval['resource_id']}", role),
                url.replace(self.approval["resource_id"], "aaaaaaaaaaaaaaaaaaaa"),
                url.replace("/postgres", "/production"),
                url.replace("verify-full", "require"),
                url + "&host=production.example.test",
                url + "&hostaddr=127.0.0.1",
                url + "&service=production",
                url + "&options=-crole=postgres",
                url + "&sslmode=verify-full",
                url.replace("gssencmode=disable", "gssencmode=prefer"),
                url + "#fragment",
                url + " ",
                url.replace("p%40ss", "p@ss"),
                url.replace("%2Fapproved%2Fca.pem", "%2Fother.pem"),
            ):
                with self.subTest(role=role, value=value), self.assertRaises(RuntimeError):
                    guard.validate_url(value, role, self.approval)

    def test_tls_exceptions_and_incomplete_ca_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "TLS exceptions"):
            guard.tls_mode({**self.approval, "tls_exception": {}})
        for missing in ("ca_file", "ca_sha256"):
            approval = dict(self.approval)
            del approval[missing]
            with self.subTest(missing=missing), self.assertRaises(RuntimeError):
                guard.tls_parameters(approval)

    def test_environment_overrides_are_rejected_before_approval_reads(self):
        for key in (
            "PGHOST",
            "PGHOSTADDR",
            "PGSERVICE",
            "PGOPTIONS",
            "PGPASSWORD",
            "PGSSLMODE",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
        ):
            with (
                self.subTest(key=key),
                patch.object(
                    guard.Path,
                    "read_bytes",
                    side_effect=AssertionError("approval must not be read"),
                ),
                self.assertRaises(RuntimeError),
            ):
                guard.validate({"VERVFY_ENVIRONMENT": "staging", key: "unsafe"})

    def test_missing_approval_and_duplicate_keys_fail_closed(self):
        for env in (
            {},
            {"VERVFY_ENVIRONMENT": "production"},
            {"VERVFY_ENVIRONMENT": "staging"},
        ):
            with self.subTest(env=env), self.assertRaises(RuntimeError):
                guard.validate(env)
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            guard.unique([("hostname", "staging"), ("hostname", "production")])

    def test_alembic_guard_precedes_database_import_and_rejects_revision_override(self):
        source = (guard.ROOT / "alembic/env.py").read_text()
        self.assertLess(source.index("    validate()"), source.index("from db import"))
        with patch.object(guard.sys, "argv", ["staging_guard.py", "upgrade", "head"]):
            with self.assertRaisesRegex(RuntimeError, "invalid operation"):
                guard.main()

    def test_render_staging_api_requires_asgi_lifespan(self):
        proposal = (guard.ROOT / "render.staging.proposal.yaml").read_text()
        self.assertRegex(
            proposal,
            r"(?m)^\s+startCommand: uvicorn server:app .* --lifespan on$",
        )

    def test_complete_approval_manifest_and_artifacts_are_bound_without_connections(self):
        files = [
            "alembic.ini",
            "alembic/env.py",
            "db.py",
            "staging_guard.py",
            "supabase_role_memberships.py",
            "requirements.lock",
            "docs/staging-alembic-preflight.sql",
            "docs/staging-alembic-postflight.sql",
            "docs/staging-migration-default-privileges.sql",
            "docs/staging-namespace-bootstrap-grant.sql",
            "docs/staging-namespace-bootstrap-revoke.sql",
        ]
        files += [
            str(path.relative_to(guard.ROOT))
            for path in (guard.ROOT / "alembic/versions").glob("*.py")
        ]
        digest = lambda content: hashlib.sha256(content).hexdigest()
        manifest_bytes = json.dumps(
            {name: digest((guard.ROOT / name).read_bytes()) for name in files}
        ).encode()
        approval = {
            **self.approval,
            "archive": "/approved/source.tar.gz",
            "archive_sha256": digest(b"archive"),
            "manifest": "/approved/manifest.json",
            "manifest_sha256": digest(manifest_bytes),
        }
        approval_bytes = json.dumps(approval).encode()
        virtual = {
            "/approved/approval.json": approval_bytes,
            "/approved/ca.pem": b"CA",
            "/approved/source.tar.gz": b"archive",
            "/approved/manifest.json": manifest_bytes,
        }
        original_read = guard.Path.read_bytes

        def read(path):
            return virtual[str(path)] if str(path) in virtual else original_read(path)

        env = {
            "VERVFY_ENVIRONMENT": "staging",
            "STAGING_APPROVAL_FILE": "/approved/approval.json",
            "STAGING_APPROVAL_SHA256": digest(approval_bytes),
        }
        env.update(
            {
                key: self.url(role)
                for key, role in guard.ROLES.items()
            }
        )

        with (
            patch.object(guard.Path, "read_bytes", read),
            patch.object(guard.Path, "is_file", return_value=True),
            patch.object(guard.Path, "is_symlink", return_value=False),
            patch.object(
                guard.subprocess, "run", side_effect=AssertionError("no connection")
            ),
        ):
            self.assertEqual(guard.validate(env)[0], approval)
            manifest = json.loads(manifest_bytes)
            for bad_manifest in (
                {key: value for key, value in manifest.items()
                 if key != "alembic/versions/0028_storage_cleanup_leases.py"},
                {**manifest, "alembic/versions/0029_unreviewed.py": digest(b"bad")},
            ):
                virtual["/approved/manifest.json"] = json.dumps(bad_manifest).encode()
                approval["manifest_sha256"] = digest(
                    virtual["/approved/manifest.json"]
                )
                approval_bytes = json.dumps(approval).encode()
                virtual["/approved/approval.json"] = approval_bytes
                env["STAGING_APPROVAL_SHA256"] = digest(approval_bytes)
                with self.assertRaisesRegex(RuntimeError, "manifest file set mismatch"):
                    guard.validate(env)

    def test_preflight_dispatch_uses_verified_pooler_principal_and_tls(self):
        migration_key = "MIGRATION_DATABASE_URL"
        urls = {migration_key: guard.urlsplit(self.url(guard.ROLES[migration_key]))}
        with (
            patch.dict(guard.os.environ, {"VERVFY_ENVIRONMENT": "staging"}, clear=True),
            patch.object(guard, "validate", return_value=(self.approval, urls)),
            patch.object(guard.sys, "argv", ["staging_guard.py", "preflight"]),
            patch.object(guard.subprocess, "run") as run,
        ):
            guard.main()
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["PGHOST"], self.approval["hostname"])
        self.assertEqual(env["PGPORT"], "5432")
        self.assertEqual(env["PGDATABASE"], "postgres")
        self.assertEqual(
            env["PGUSER"],
            f"{guard.ROLES[migration_key]}.{self.approval['resource_id']}",
        )
        self.assertEqual(env["PGSSLMODE"], "verify-full")
        self.assertEqual(env["PGSSLROOTCERT"], self.approval["ca_file"])
        self.assertEqual(env["PGGSSENCMODE"], "disable")


if __name__ == "__main__":
    unittest.main()
