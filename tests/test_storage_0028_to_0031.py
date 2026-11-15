"""Rehearse the exact production storage migration boundary."""

import unittest
from unittest.mock import patch

import test_staging_migrations as staging


class Storage0028To0031Rehearsal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original_upgrade = staging.command.upgrade
        cls.boundary_verified = False

        def intercepted_upgrade(config, revision, *args, **kwargs):
            if revision != "head":
                return original_upgrade(config, revision, *args, **kwargs)

            # Existing setup has inserted synthetic account data.
            original_upgrade(
                config, "0028_webauthn_enrollment", *args, **kwargs
            )

            with staging.StagingPostgresTests.engine.connect() as conn:
                current = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()

                assert current == "0028_webauthn_enrollment", current
                assert conn.exec_driver_sql(
                    "SELECT to_regnamespace('vervfy_storage')"
                ).scalar_one() is None

            cls.boundary_verified = True

            return original_upgrade(
                config, "0031_cleanup_retry_limits", *args, **kwargs
            )

        with patch.object(staging.command, "upgrade", intercepted_upgrade):
            staging.StagingPostgresTests.setUpClass()

        cls.engine = staging.StagingPostgresTests.engine
        cls.before = staging.StagingPostgresTests.pre_upgrade_snapshot

    def test_exact_boundary_and_preservation(self):
        self.assertTrue(self.boundary_verified)

        with self.engine.connect() as conn:
            revision = conn.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()

            self.assertEqual(revision, "0031_cleanup_retry_limits")
            self.assertEqual(
                staging.StagingPostgresTests.account_snapshot(conn),
                self.before,
            )

            for table in ("namespaces", "objects", "cleanup_jobs"):
                self.assertIsNotNone(
                    conn.exec_driver_sql(
                        "SELECT to_regclass(%s)",
                        (f"vervfy_storage.{table}",),
                    ).scalar_one()
                )


if __name__ == "__main__":
    unittest.main()
