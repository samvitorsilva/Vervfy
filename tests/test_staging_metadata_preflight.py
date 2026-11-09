"""Metadata preflight checks use only curated catalog metadata."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

import staging_metadata_preflight as metadata_preflight


def _role(name, login):
    return {
        "name": name,
        "login": login,
        "inherit": False,
        "superuser": False,
        "bypass_rls": False,
        "create_db": False,
        "create_role": False,
        "replication": False,
    }


def _migration_snapshot():
    roles = [
        _role(name, login)
        for name, login in metadata_preflight.ROLE_ATTRIBUTES.items()
    ]
    roles.append(_role(metadata_preflight.BOOTSTRAP_ROLE, True))
    memberships = [
        {
            "granted_role": granted,
            "member_role": member,
            "inherit": inherit,
            "set": set_role,
            "admin": admin,
        }
        for granted, member, inherit, set_role, admin
        in metadata_preflight.EXPECTED_MEMBERSHIPS
    ]
    database_privileges = []
    for role in roles:
        name = role["name"]
        database_privileges.append({
            "name": name,
            "connect": name in {
                metadata_preflight.MIGRATION_ROLE,
                "app_runtime",
                "google_auth_lookup",
            },
            "create": name == metadata_preflight.MIGRATION_ROLE,
            "temporary": False,
        })
    schema_privileges = []
    for role in roles:
        name = role["name"]
        schema_privileges.extend([
            {
                "role": name,
                "schema": "public",
                "usage": name in {
                    metadata_preflight.MIGRATION_ROLE,
                    "app_runtime",
                },
                "create": name == metadata_preflight.MIGRATION_ROLE,
            },
            {"role": name, "schema": "vervfy_auth", "usage": None, "create": None},
            {
                "role": name,
                "schema": "vervfy_storage",
                "usage": None,
                "create": None,
            },
        ])
    return {
        "server_version": "18.6",
        "server_version_num": "180006",
        "database": metadata_preflight.TARGET_DATABASE,
        "session_role": metadata_preflight.MIGRATION_ROLE,
        "effective_role": metadata_preflight.MIGRATION_ROLE,
        "database_owner": metadata_preflight.BOOTSTRAP_ROLE,
        "tls_enabled": True,
        "gen_random_uuid_available": True,
        "roles": roles,
        "memberships": memberships,
        "database_privileges": database_privileges,
        "schema_owners": [
            {"schema": "public", "owner": metadata_preflight.BOOTSTRAP_ROLE},
            {"schema": "vervfy_auth", "owner": None},
            {"schema": "vervfy_storage", "owner": None},
        ],
        "schema_privileges": schema_privileges,
        "public_database_privileges": [],
        "public_schema_privileges": [],
        "alembic_version_exists": False,
        "alembic_revisions": [],
        "auth_schema_exists": False,
        "storage_schema_exists": False,
        "has_non_system_relations": False,
        "relations": [],
        "policies": [],
        "security_definer_functions": [],
        "identity_column_privileges": [],
        "extensions": [{"name": "plpgsql", "version": "1.0", "schema": "pg_catalog"}],
    }


def _bootstrap_snapshot():
    snapshot = _migration_snapshot()
    snapshot.update({
        "session_role": metadata_preflight.BOOTSTRAP_ROLE,
        "effective_role": metadata_preflight.BOOTSTRAP_ROLE,
        "database_owner": metadata_preflight.BOOTSTRAP_ROLE,
        "roles": [{
            **_role(metadata_preflight.BOOTSTRAP_ROLE, True),
            "create_role": True,
        }],
        "memberships": [],
        "database_privileges": [{
            "name": metadata_preflight.BOOTSTRAP_ROLE,
            "connect": True,
            "create": True,
            "temporary": True,
        }],
        "schema_privileges": [{
            "role": metadata_preflight.BOOTSTRAP_ROLE,
            "schema": "public",
            "usage": True,
            "create": True,
        }],
    })
    return snapshot


def _post_migration_snapshot():
    snapshot = _migration_snapshot()
    snapshot.update({
        "alembic_version_exists": True,
        "alembic_revisions": [metadata_preflight.RELEASE_TARGET],
        "auth_schema_exists": True,
        "storage_schema_exists": True,
        "has_non_system_relations": True,
        "schema_owners": [
            {"schema": "public", "owner": metadata_preflight.BOOTSTRAP_ROLE},
            {"schema": "vervfy_auth", "owner": metadata_preflight.MIGRATION_ROLE},
            {"schema": "vervfy_storage", "owner": metadata_preflight.MIGRATION_ROLE},
        ],
    })
    for item in snapshot["schema_privileges"]:
        role = item["role"]
        schema = item["schema"]
        if schema == "public":
            if role in {
                "vervfy_identity_lookup_owner",
                "vervfy_storage_lifecycle_owner",
            }:
                item.update(usage=True, create=False)
        elif schema == "vervfy_auth":
            if role in {
                "vervfy_identity_lookup_owner",
                "vervfy_identity_lookup",
                "google_auth_lookup",
                metadata_preflight.MIGRATION_ROLE,
            }:
                item.update(usage=True, create=role == metadata_preflight.MIGRATION_ROLE)
        elif schema == "vervfy_storage":
            if role in {
                "vervfy_storage_lifecycle_owner",
                "vervfy_storage_cleanup",
                "storage_cleanup_worker",
                "app_runtime",
                metadata_preflight.MIGRATION_ROLE,
            }:
                item.update(
                    usage=True,
                    create=role == metadata_preflight.MIGRATION_ROLE,
                )
    snapshot["relations"] = [
        {
            "schema": schema,
            "name": name,
            "exists": True,
            "owner": metadata_preflight.MIGRATION_ROLE,
            "row_security": True,
            "force_row_security": True,
        }
        for schema, name in sorted(metadata_preflight.TENANT_RELATIONS)
    ]
    snapshot["policies"] = [
        {
            "schema": schema,
            "table": table,
            "name": name,
            "command": command,
            "roles": list(roles),
            "permissive": True,
            "using_present": True,
            "check_present": command != "SELECT",
        }
        for schema, table, name, command, roles
        in metadata_preflight.EXPECTED_POLICIES
    ]
    snapshot["security_definer_functions"] = [
        {
            "schema": schema,
            "name": name,
            "owner": owner,
            "security_definer": True,
            "search_path": "pg_catalog, pg_temp",
            "public_execute": False,
            "explicit_execute_grantees": sorted(metadata_preflight.FUNCTION_GRANTEES[(schema, name)]),
            "unexpected_explicit_execute_grantee_count": 0,
            "effective_execute_roles": sorted(metadata_preflight.FUNCTION_EXECUTORS[(schema, name)]),
        }
        for (schema, name), owner in metadata_preflight.FUNCTION_OWNERS.items()
    ]
    snapshot["identity_column_privileges"] = [
        {
            "role": role,
            "column": column,
            "select": (
                role == "vervfy_identity_lookup_owner"
                and column in {"issuer", "subject", "user_id"}
            ) or role == "app_runtime",
        }
        for role in (
            "vervfy_identity_lookup_owner",
            "google_auth_lookup",
            "app_runtime",
        )
        for column in ("issuer", "subject", "user_id", "created_at")
    ]
    return snapshot


class StagingMetadataEvaluationTests(unittest.TestCase):
    def test_bootstrap_preflight_requires_owner_and_role_creation_authority(self):
        report = metadata_preflight.evaluate_metadata(
            _bootstrap_snapshot(), "bootstrap"
        )
        self.assertEqual(report["status"], "pass")
        snapshot = _bootstrap_snapshot()
        snapshot["roles"][0]["create_role"] = False
        report = metadata_preflight.evaluate_metadata(snapshot, "bootstrap")
        self.assertIn(
            "bootstrap_role_creation_authority",
            {item["check"] for item in report["checks"] if not item["passed"]},
        )
        snapshot = _bootstrap_snapshot()
        snapshot["roles"][0]["create_db"] = True
        report = metadata_preflight.evaluate_metadata(snapshot, "bootstrap")
        self.assertIn(
            "bootstrap_role_restricted_attributes",
            {item["check"] for item in report["checks"] if not item["passed"]},
        )
        snapshot = _bootstrap_snapshot()
        snapshot["roles"][0]["inherit"] = True
        report = metadata_preflight.evaluate_metadata(snapshot, "bootstrap")
        self.assertIn(
            "bootstrap_role_restricted_attributes",
            {item["check"] for item in report["checks"] if not item["passed"]},
        )
        snapshot = _bootstrap_snapshot()
        snapshot["memberships"] = [{
            "granted_role": "OTHER",
            "member_role": metadata_preflight.BOOTSTRAP_ROLE,
            "inherit": True,
            "set": False,
            "admin": False,
        }]
        report = metadata_preflight.evaluate_metadata(snapshot, "bootstrap")
        self.assertIn(
            "bootstrap_role_memberships_absent",
            {item["check"] for item in report["checks"] if not item["passed"]},
        )

    def test_fresh_migration_preflight_passes_expected_role_contract(self):
        report = metadata_preflight.evaluate_metadata(
            _migration_snapshot(), "migration"
        )
        self.assertEqual(report["status"], "pass")

    def test_post_migration_preflight_checks_rls_and_lookup_schema_usage(self):
        report = metadata_preflight.evaluate_metadata(
            _post_migration_snapshot(), "post-migration"
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["required_extensions"], [])

    def test_missing_role_and_wrong_database_fail_closed(self):
        snapshot = _migration_snapshot()
        snapshot["roles"] = [
            role for role in snapshot["roles"] if role["name"] != "google_auth_lookup"
        ]
        snapshot["database_privileges"] = [
            item
            for item in snapshot["database_privileges"]
            if item["name"] != "google_auth_lookup"
        ]
        snapshot["schema_privileges"] = [
            item
            for item in snapshot["schema_privileges"]
            if item["role"] != "google_auth_lookup"
        ]
        snapshot["database"] = "production"
        report = metadata_preflight.evaluate_metadata(snapshot, "migration")
        failures = {
            item["check"] for item in report["checks"] if not item["passed"]
        }
        self.assertIn("database_identity", failures)
        self.assertIn("application_role_attributes", failures)
        self.assertIn("database_role_privileges", failures)

    def test_wrong_postgresql_major_version_fails_closed(self):
        snapshot = _migration_snapshot()
        snapshot["server_version_num"] = "170006"
        report = metadata_preflight.evaluate_metadata(snapshot, "migration")
        failures = {
            item["check"] for item in report["checks"] if not item["passed"]
        }
        self.assertIn("postgresql_major_version", failures)

    def test_lookup_owner_must_have_public_schema_usage_after_migration(self):
        snapshot = _post_migration_snapshot()
        for item in snapshot["schema_privileges"]:
            if (
                item["role"] == "vervfy_identity_lookup_owner"
                and item["schema"] == "public"
            ):
                item["usage"] = False
        report = metadata_preflight.evaluate_metadata(snapshot, "post-migration")
        failures = {
            item["check"] for item in report["checks"] if not item["passed"]
        }
        self.assertIn("identity_lookup_schema_usage", failures)

    def test_unknown_public_schema_owner_fails_closed(self):
        snapshot = _bootstrap_snapshot()
        snapshot["schema_owners"][0]["owner"] = "OTHER"
        report = metadata_preflight.evaluate_metadata(snapshot, "bootstrap")
        failures = {
            item["check"] for item in report["checks"] if not item["passed"]
        }
        self.assertIn("public_schema_owner_known", failures)

    def test_runtime_schema_create_privilege_is_rejected(self):
        snapshot = _migration_snapshot()
        for item in snapshot["schema_privileges"]:
            if item["role"] == "app_runtime" and item["schema"] == "public":
                item["create"] = True
        report = metadata_preflight.evaluate_metadata(snapshot, "migration")
        failures = {
            item["check"] for item in report["checks"] if not item["passed"]
        }
        self.assertIn("public_schema_privileges", failures)

    def test_catalog_permission_errors_are_sanitized(self):
        connection = Mock()
        connection.in_transaction.return_value = False
        connection.exec_driver_sql.side_effect = OperationalError(
            "SELECT ...",
            {},
            Exception("postgresql://staging-user:secret@host/db"),
        )
        with self.assertRaises(metadata_preflight.MetadataPreflightError) as raised:
            metadata_preflight.collect_metadata(connection)
        self.assertNotIn("secret", str(raised.exception))

    def test_existing_transaction_is_rejected(self):
        connection = Mock()
        connection.in_transaction.return_value = True
        with self.assertRaisesRegex(
            metadata_preflight.MetadataPreflightError, "fresh database connection"
        ):
            metadata_preflight.collect_metadata(connection)

    def test_connection_errors_are_sanitized(self):
        engine = Mock()
        engine.connect.side_effect = OperationalError(
            "connect",
            {},
            Exception("postgresql://staging-user:secret@host/db"),
        )
        with (
            patch.object(metadata_preflight, "create_engine", return_value=engine),
            self.assertRaises(metadata_preflight.MetadataPreflightError) as raised,
        ):
            metadata_preflight.run_preflight("validated-url", "bootstrap")
        self.assertNotIn("secret", str(raised.exception))

    def test_report_contains_no_user_rows_or_secret_fields(self):
        report = metadata_preflight.evaluate_metadata(
            _post_migration_snapshot(), "post-migration"
        )
        self.assertNotIn("users", report)
        self.assertNotIn("password", str(report).lower())
        self.assertNotIn("account", str(report).lower())


if __name__ == "__main__":
    unittest.main()
