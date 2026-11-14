import ast
import ssl
import unittest
from pathlib import Path

import redis

from staging_session_guard import validate


ROOT = Path(__file__).resolve().parents[1]
STAGING_HOST = "redis-staging.example.invalid"
SECURE_REDIS_URL = (
    "rediss://default:synthetic-token@redis-staging.example.invalid:6380/0"
)
BASE_STAGING_ENV = {
    "VERVFY_ENVIRONMENT": "staging",
    "GOOGLE_OAUTH_ENABLED": "0",
    "VERVFY_ASYNC_UPLOADS": "0",
    "WEB_CONCURRENCY": "1",
}


class StagingSessionGuardTests(unittest.TestCase):
    def test_staging_without_redis_remains_allowed(self):
        validate(BASE_STAGING_ENV)

    def test_accepts_allowlisted_authenticated_rediss_with_verified_tls(self):
        validate(
            {
                **BASE_STAGING_ENV,
                "VERVFY_STAGING_REDIS_HOST": STAGING_HOST,
                "REDIS_URL": SECURE_REDIS_URL,
            }
        )
        client = redis.Redis.from_url(SECURE_REDIS_URL)
        connection = client.connection_pool.connection_class(
            **client.connection_pool.connection_kwargs
        )
        self.assertEqual(
            connection.cert_reqs,
            ssl.CERT_REQUIRED,
        )
        self.assertIs(connection.check_hostname, True)

    def test_rejects_invalid_or_unverified_redis_urls(self):
        invalid_urls = (
            "",
            "redis://default:synthetic-token@redis-staging.example.invalid:6380/0",
            "rediss://redis-staging.example.invalid:6380/0",
            "rediss://default:synthetic-token@redis-staging.example.invalid/0",
            "rediss://default:synthetic-token@redis-staging.example.invalid:6380/1",
            "rediss://default:synthetic-token@redis-staging.example.invalid:6380/0?ssl_cert_reqs=none",
            "rediss://default:synthetic-token@redis-other.example.invalid:6380/0",
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaisesRegex(
                RuntimeError, "Staging REDIS_URL"
            ):
                validate(
                    {
                        **BASE_STAGING_ENV,
                        "VERVFY_STAGING_REDIS_HOST": STAGING_HOST,
                        "REDIS_URL": url,
                    }
                )

    def test_requires_host_allowlist_for_staging_redis(self):
        with self.assertRaisesRegex(RuntimeError, "hostname allowlist"):
            validate({**BASE_STAGING_ENV, "REDIS_URL": SECURE_REDIS_URL})

    def test_rejects_production_configuration_in_staging(self):
        with self.assertRaisesRegex(RuntimeError, "Production configuration"):
            validate(
                {
                    **BASE_STAGING_ENV,
                    "PRODUCTION_REDIS_URL": SECURE_REDIS_URL,
                }
            )

    def test_rejects_unexpected_environment(self):
        for environment in ("preview", " staging "):
            with self.subTest(environment=environment), self.assertRaisesRegex(
                RuntimeError, "Unexpected VERVFY_ENVIRONMENT"
            ):
                validate({"VERVFY_ENVIRONMENT": environment})

    def test_staging_requires_oauth_uploads_off_and_one_worker(self):
        for key, value in (
            ("GOOGLE_OAUTH_ENABLED", "1"),
            ("VERVFY_ASYNC_UPLOADS", "1"),
            ("WEB_CONCURRENCY", "2"),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(
                RuntimeError, "disabled OAuth/uploads"
            ):
                validate({**BASE_STAGING_ENV, key: value})

    def test_server_invokes_guard_before_application_imports(self):
        tree = ast.parse((ROOT / "server.py").read_text())
        application_imports = [
            node.lineno
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Import)
                and any(alias.name == "audio_store" for alias in node.names)
            )
            or (
                isinstance(node, ast.ImportFrom)
                and node.module == "audio_store"
            )
        ]
        guard_calls = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "validate_staging_sessions"
        ]
        self.assertTrue(guard_calls and application_imports)
        self.assertLess(min(guard_calls), min(application_imports))


if __name__ == "__main__":
    unittest.main()
