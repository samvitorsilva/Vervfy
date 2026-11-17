"""Fail-closed tests for the narrowly scoped auth session migration runner."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts import auth_sessions_production_migration as runner


class SessionMigrationRunnerTests(unittest.TestCase):
    def test_migration_target_is_only_session_revision(self):
        self.assertEqual(runner.START, "0031_cleanup_retry_limits")
        self.assertEqual(runner.TARGET, "0032_auth_sessions")
        self.assertEqual(runner.AUTHORIZATION, "0031_cleanup_retry_limits..0032_auth_sessions")

    def test_actual_repository_migration_dependency(self):
        runner.verify_chain()

    def test_rejects_wrong_migration_parent(self):
        script = MagicMock()
        script.get_revision.side_effect = lambda revision: (
            SimpleNamespace(down_revision="wrong") if revision == runner.TARGET
            else SimpleNamespace(revision=runner.START)
        )
        with patch.object(runner.ScriptDirectory, "from_config", return_value=script):
            with self.assertRaisesRegex(runner.MigrationBlocked, "directly follow"):
                runner.verify_chain()

    def test_rejects_wrong_project_before_connection(self):
        target = SimpleNamespace(project_ref="approved")
        with (
            patch.object(runner, "verify_chain"),
            patch.object(runner, "load_target", return_value=target),
            patch.object(runner, "_engine") as engine,
        ):
            code = runner.main(["check", "--confirm-project-ref", "wrong"])
        self.assertEqual(code, 1)
        engine.assert_not_called()

    def test_rejects_unapproved_migration_range_before_connection(self):
        target = SimpleNamespace(project_ref="approved")
        with (
            patch.object(runner, "verify_chain"),
            patch.object(runner, "load_target", return_value=target),
            patch.object(runner, "_engine") as engine,
        ):
            code = runner.main([
                "upgrade", "--confirm-project-ref", "approved",
                "--authorize-production-migration",
                "0031_cleanup_retry_limits..0033_cleanup_claims_disabled",
                "--authorization-expires-at", "2099-01-01T00:00:00Z",
            ])
        self.assertEqual(code, 1)
        engine.assert_not_called()

    def test_rejects_missing_authorization_expiry(self):
        target = SimpleNamespace(project_ref="approved")
        with (
            patch.object(runner, "verify_chain"),
            patch.object(runner, "load_target", return_value=target),
            patch.object(runner, "_engine") as engine,
        ):
            code = runner.main([
                "upgrade", "--confirm-project-ref", "approved",
                "--authorize-production-migration", runner.AUTHORIZATION,
            ])
        self.assertEqual(code, 1)
        engine.assert_not_called()

    def test_rejects_expired_authorization_before_connection(self):
        target = SimpleNamespace(project_ref="approved")
        with (
            patch.object(runner, "verify_chain"),
            patch.object(runner, "load_target", return_value=target),
            patch.object(runner, "_engine") as engine,
        ):
            code = runner.main([
                "upgrade", "--confirm-project-ref", "approved",
                "--authorize-production-migration", runner.AUTHORIZATION,
                "--authorization-expires-at", "2000-01-01T00:00:00Z",
            ])
        self.assertEqual(code, 1)
        engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
