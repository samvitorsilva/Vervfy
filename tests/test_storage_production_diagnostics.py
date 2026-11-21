"""Regression tests for sanitized production migration failures."""

import contextlib
import io
import unittest
from unittest.mock import patch

from scripts import storage_production_migration as runner


class ProductionDiagnosticsTests(unittest.TestCase):
    def test_upgrade_failure_reports_stage_without_secret(self):
        secret = "DO_NOT_PRINT_THIS_DATABASE_PASSWORD"
        error = RuntimeError(secret)
        error.add_note("vervfy_migration_stage=alembic_upgrade")

        stderr = io.StringIO()

        with (
            patch.object(runner, "validate_migration_chain"),
            patch.object(runner, "load_target") as load_target,
            patch.object(runner, "validate_authorization"),
            patch.object(runner, "run_upgrade", side_effect=error),
            contextlib.redirect_stderr(stderr),
        ):
            load_target.return_value.project_ref = "test-project"
            load_target.return_value.start_revision = runner.START_REVISION

            result = runner.main(
                [
                    "upgrade",
                    "--confirm-project-ref",
                    "test-project",
                    "--authorize-production-migration",
                    runner.AUTHORIZATION,
                    "--authorization-expires-at",
                    "2099-01-01T00:00:00Z",
                ]
            )

        output = stderr.getvalue()

        self.assertEqual(result, 1)
        self.assertIn("stage=alembic_upgrade", output)
        self.assertIn("error_type=RuntimeError", output)
        self.assertIn("sqlstate=unavailable", output)
        self.assertNotIn(secret, output)

    def test_unknown_stage_is_not_printed(self):
        error = RuntimeError("sensitive error")
        error.add_note("vervfy_migration_stage=SECRET_VALUE")

        stderr = io.StringIO()

        with (
            patch.object(runner, "validate_migration_chain"),
            patch.object(runner, "load_target") as load_target,
            patch.object(runner, "validate_authorization"),
            patch.object(runner, "run_upgrade", side_effect=error),
            contextlib.redirect_stderr(stderr),
        ):
            load_target.return_value.project_ref = "test-project"
            load_target.return_value.start_revision = runner.START_REVISION

            result = runner.main(
                [
                    "upgrade",
                    "--confirm-project-ref",
                    "test-project",
                    "--authorize-production-migration",
                    runner.AUTHORIZATION,
                    "--authorization-expires-at",
                    "2099-01-01T00:00:00Z",
                ]
            )

        output = stderr.getvalue()

        self.assertEqual(result, 1)
        self.assertIn("stage=unavailable", output)
        self.assertNotIn("SECRET_VALUE", output)


if __name__ == "__main__":
    unittest.main()
