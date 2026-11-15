"""Pre-migration Supabase ACL regression using disposable PostgreSQL."""

import unittest
from unittest.mock import patch

import sqlalchemy as sa
import test_staging_migrations as staging
from test_storage_migration_role_validation import MIGRATION

DASHBOARD_PRIVILEGES = (
    "SELECT, INSERT, UPDATE, DELETE, TRUNCATE, "
    "REFERENCES, TRIGGER, MAINTAIN"
)


def _capability_role_oids(conn):
    roles = conn.execute(sa.text("""
        SELECT oid
        FROM pg_catalog.pg_roles
        WHERE rolname IN (
            'vervfy_storage_lifecycle_owner',
            'vervfy_storage_cleanup',
            'storage_cleanup_worker'
        )
        ORDER BY rolname
    """)).scalars().all()
    assert len(roles) == 3
    return roles


def _install_supabase_extension_acl(conn, *, dashboard_privileges=DASHBOARD_PRIVILEGES):
    """Reproduce observed Supabase pg_stat_statements view ACLs."""
    conn.exec_driver_sql("CREATE ROLE dashboard_user NOLOGIN")
    conn.exec_driver_sql("CREATE SCHEMA extensions")
    conn.exec_driver_sql("GRANT USAGE ON SCHEMA extensions TO PUBLIC")

    for name in ("pg_stat_statements", "pg_stat_statements_info"):
        conn.exec_driver_sql(
            f"CREATE VIEW extensions.{name} AS SELECT 1 AS example"
        )
        conn.exec_driver_sql(
            f"GRANT SELECT ON extensions.{name} TO PUBLIC"
        )
        conn.exec_driver_sql(
            f"GRANT {dashboard_privileges} ON extensions.{name} "
            "TO dashboard_user"
        )


def _assert_rejects(conn, role_ids, *, restore_sql=()):
    with unittest.TestCase().assertRaisesRegex(
        RuntimeError,
        "preexisting object privileges",
    ):
        MIGRATION._fresh_privileges(conn, role_ids)
    for statement in restore_sql:
        conn.exec_driver_sql(statement)


class SupabaseACLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original_upgrade = staging.command.upgrade
        cls.checked_before_0029 = False

        def intercepted_upgrade(config, revision, *args, **kwargs):
            if revision != "head":
                return original_upgrade(config, revision, *args, **kwargs)

            original_upgrade(
                config, "0028_webauthn_enrollment", *args, **kwargs
            )

            with staging.StagingPostgresTests.engine.begin() as conn:
                assert conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one() == "0028_webauthn_enrollment"

                _install_supabase_extension_acl(conn)
                roles = _capability_role_oids(conn)

                observed = conn.execute(sa.text("""
                    SELECT c.relname, acl.privilege_type
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n
                      ON n.oid = c.relnamespace
                    CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) acl
                    JOIN pg_catalog.pg_roles r ON r.oid = acl.grantee
                    WHERE n.nspname = 'extensions'
                      AND c.relname IN (
                          'pg_stat_statements',
                          'pg_stat_statements_info'
                      )
                      AND r.rolname = 'dashboard_user'
                    ORDER BY 1, 2
                """)).all()
                assert {
                    privilege for _, privilege in observed
                } == {
                    "SELECT", "INSERT", "UPDATE", "DELETE",
                    "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN",
                }

                public_select = conn.execute(sa.text("""
                    SELECT c.relname
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n
                      ON n.oid = c.relnamespace
                    CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) acl
                    WHERE n.nspname = 'extensions'
                      AND c.relname IN (
                          'pg_stat_statements',
                          'pg_stat_statements_info'
                      )
                      AND acl.grantee = 0
                      AND acl.privilege_type = 'SELECT'
                    ORDER BY 1
                """)).scalars().all()
                assert public_select == [
                    "pg_stat_statements",
                    "pg_stat_statements_info",
                ]

                MIGRATION._fresh_privileges(conn, roles)
                cls.checked_before_0029 = True

            return original_upgrade(
                config, "0031_cleanup_retry_limits", *args, **kwargs
            )

        with patch.object(
            staging.command, "upgrade", intercepted_upgrade
        ):
            staging.StagingPostgresTests.setUpClass()

        cls.engine = staging.StagingPostgresTests.engine

    def test_supabase_acl_accepted_before_migration(self):
        self.assertTrue(self.checked_before_0029)

        with self.engine.connect() as conn:
            revision = conn.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()

            self.assertEqual(
                revision,
                "0031_cleanup_retry_limits",
            )


class UnauthorizedPrivilegeTests(unittest.TestCase):
    """Unrelated grants and inherited privileges must remain rejected."""

    @classmethod
    def setUpClass(cls):
        original_upgrade = staging.command.upgrade
        cls.rejection_cases = []

        def intercepted_upgrade(config, revision, *args, **kwargs):
            if revision != "head":
                return original_upgrade(config, revision, *args, **kwargs)

            original_upgrade(
                config, "0028_webauthn_enrollment", *args, **kwargs
            )

            with staging.StagingPostgresTests.engine.begin() as conn:
                assert conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one() == "0028_webauthn_enrollment"

                _install_supabase_extension_acl(conn)
                roles = _capability_role_oids(conn)
                MIGRATION._fresh_privileges(conn, roles)

                cleanup_oid = conn.execute(sa.text("""
                    SELECT oid FROM pg_catalog.pg_roles
                    WHERE rolname = 'vervfy_storage_cleanup'
                """)).scalar_one()

                # Unrelated application-table grant.
                conn.exec_driver_sql(
                    "GRANT SELECT ON public.users "
                    "TO vervfy_storage_cleanup"
                )
                _assert_rejects(
                    conn,
                    [cleanup_oid],
                    restore_sql=(
                        (
                            "REVOKE SELECT ON public.users "
                            "FROM vervfy_storage_cleanup"
                        ),
                    ),
                )
                cls.rejection_cases.append("unrelated_table_grant")

                # Unrelated named grantee on the allowed views.
                conn.exec_driver_sql(
                    "CREATE ROLE unrelated_reader NOLOGIN"
                )
                conn.exec_driver_sql(
                    "GRANT SELECT ON extensions.pg_stat_statements "
                    "TO unrelated_reader"
                )
                _assert_rejects(
                    conn,
                    roles,
                    restore_sql=(
                        (
                            "REVOKE SELECT ON "
                            "extensions.pg_stat_statements "
                            "FROM unrelated_reader"
                        ),
                    ),
                )
                cls.rejection_cases.append("unrelated_view_grantee")

                # PUBLIC privilege beyond SELECT is not the reviewed exception.
                conn.exec_driver_sql(
                    "GRANT INSERT ON extensions.pg_stat_statements "
                    "TO PUBLIC"
                )
                _assert_rejects(
                    conn,
                    roles,
                    restore_sql=(
                        (
                            "REVOKE INSERT ON "
                            "extensions.pg_stat_statements "
                            "FROM PUBLIC"
                        ),
                    ),
                )
                cls.rejection_cases.append("public_non_select")

                # Inherited dashboard_user membership must fail closed.
                conn.exec_driver_sql(
                    "GRANT dashboard_user TO vervfy_storage_cleanup "
                    "WITH INHERIT TRUE, SET FALSE, ADMIN FALSE"
                )
                _assert_rejects(
                    conn,
                    [cleanup_oid],
                    restore_sql=(
                        (
                            "REVOKE dashboard_user "
                            "FROM vervfy_storage_cleanup"
                        ),
                    ),
                )
                cls.rejection_cases.append("inherited_dashboard_user")

                # SET-capable membership is also unsafe for the exception.
                conn.exec_driver_sql(
                    "GRANT dashboard_user TO storage_cleanup_worker "
                    "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
                )
                worker_oid = conn.execute(sa.text("""
                    SELECT oid FROM pg_catalog.pg_roles
                    WHERE rolname = 'storage_cleanup_worker'
                """)).scalar_one()
                _assert_rejects(
                    conn,
                    [worker_oid],
                    restore_sql=(
                        (
                            "REVOKE dashboard_user "
                            "FROM storage_cleanup_worker"
                        ),
                    ),
                )
                cls.rejection_cases.append("set_dashboard_user")

                # Baseline exception remains valid after cleanup.
                MIGRATION._fresh_privileges(conn, roles)

            return original_upgrade(
                config, "0031_cleanup_retry_limits", *args, **kwargs
            )

        with patch.object(
            staging.command, "upgrade", intercepted_upgrade
        ):
            staging.StagingPostgresTests.setUpClass()

    def test_unauthorized_and_inherited_privileges_are_rejected(self):
        self.assertEqual(
            self.rejection_cases,
            [
                "unrelated_table_grant",
                "unrelated_view_grantee",
                "public_non_select",
                "inherited_dashboard_user",
                "set_dashboard_user",
            ],
        )


if __name__ == "__main__":
    unittest.main()
