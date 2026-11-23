"""Plan/apply the reviewed internal-table ACL repair; never changes RLS or data."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import storage_production_migration as runner
from storage_internal_acl import apply_acl_repair, plan_acl_repair
from storage_inventory import InventoryBlocked, plan_digest

ROLE_GRAPH_CATEGORIES = {
    runner.ROLE_GRAPH_CATEGORY_CAPABILITY_ATTRIBUTES,
    runner.ROLE_GRAPH_CATEGORY_APP_RUNTIME_ATTRIBUTES,
    runner.ROLE_GRAPH_CATEGORY_CAPABILITY_MEMBERSHIPS,
    runner.ROLE_GRAPH_CATEGORY_APP_RUNTIME_MEMBERSHIPS,
    runner.ROLE_GRAPH_CATEGORY_STORAGE_MEMBERSHIP_OPTIONS,
    runner.ROLE_GRAPH_CATEGORY_EFFECTIVE_PRIVILEGE_INHERITANCE,
    runner.ROLE_GRAPH_CATEGORY_OWNER_SET_CAPABILITY,
    runner.ROLE_GRAPH_CATEGORY_PREEXISTING_PRIVILEGES,
}

MIGRATION_BLOCK_PREFIXES = (
    (
        "Client-side PostgreSQL TLS verification evidence is unavailable",
        "TLS_EVIDENCE_UNAVAILABLE",
    ),
    ("PostgreSQL connection did not negotiate TLS", "TLS_NOT_NEGOTIATED"),
    ("VERVFY_ENVIRONMENT must be exactly production", "ENVIRONMENT_MISMATCH"),
    ("Required setting ", "REQUIRED_SETTING_MISSING"),
    ("Unset ", "FORBIDDEN_ENVIRONMENT_OVERRIDE"),
    ("VERVFY_PRODUCTION_CA_FILE is unavailable", "CA_FILE_UNAVAILABLE"),
    ("VERVFY_PRODUCTION_CA_FILE must be a readable CA bundle", "CA_FILE_UNREADABLE"),
    ("Production URL must set sslmode=verify-full", "TLS_CA_BINDING_MISMATCH"),
    ("Production URL must match the configured", "DATABASE_ENDPOINT_OR_LOGIN_MISMATCH"),
    ("VERVFY_PRODUCTION_DATABASE_URL is invalid", "DATABASE_URL_INVALID"),
    ("Production Supabase project reference is not approved", "PROJECT_REF_MISMATCH"),
    ("Expected production database must be postgres", "DATABASE_CONFIG_MISMATCH"),
    (
        "Expected production user must be the restricted migration role",
        "MIGRATOR_CONFIG_MISMATCH",
    ),
    (
        "Production start revision is not an approved upgrade boundary",
        "REVISION_CONFIG_MISMATCH",
    ),
    ("Connected database does not match", "DATABASE_IDENTITY_MISMATCH"),
    (
        "Connected login does not match the approved migration role",
        "MIGRATOR_IDENTITY_MISMATCH",
    ),
    ("Production migration search path is not public", "SEARCH_PATH_MISMATCH"),
    (
        "Migration login must be unprivileged and able to log in",
        "MIGRATOR_ROLE_ATTRIBUTES",
    ),
    ("Migration login requires database", "MIGRATOR_PRIVILEGES_INSUFFICIENT"),
    (
        "Migration login must own required application tables",
        "APPLICATION_OWNERSHIP_MISMATCH",
    ),
    ("Migration login must own public.alembic_version", "ALEMBIC_OWNERSHIP_MISMATCH"),
    ("Expected exactly ", "REVISION_MISMATCH"),
    ("PostgreSQL 16 or newer is required", "POSTGRES_VERSION_UNSUPPORTED"),
    ("Existing storage lifecycle schema is missing", "STORAGE_SCHEMA_MISSING"),
    (
        "Migration login must own the storage lifecycle schema and tables",
        "STORAGE_OWNERSHIP_OR_PRIVILEGES",
    ),
    ("Existing production storage namespace does not match", "NAMESPACE_MISMATCH"),
    ("Existing storage lifecycle columns are incomplete", "LIFECYCLE_COLUMNS_MISSING"),
    (
        "auth_sessions does not match the approved starting revision",
        "AUTH_SESSIONS_REVISION_MISMATCH",
    ),
    (
        "auth_sessions must be migration-owned with RLS disabled",
        "AUTH_SESSIONS_OWNER_RLS_MISMATCH",
    ),
    ("Unexpected direct auth_sessions privileges", "AUTH_SESSIONS_ACL_DRIFT"),
    (
        "Unexpected effective auth_sessions privileges",
        "AUTH_SESSIONS_EFFECTIVE_ACL_DRIFT",
    ),
    (
        "Internal public-table ACLs do not match the reviewed state",
        "INTERNAL_ACL_DRIFT",
    ),
    ("Unexpected cleanup-claim privileges", "CLEANUP_CLAIM_PRIVILEGE_DRIFT"),
    ("Project confirmation mismatch", "PROJECT_CONFIRMATION_MISMATCH"),
    (
        "Confirmation does not match the configured production project",
        "PROJECT_CONFIRMATION_MISMATCH",
    ),
)

INVENTORY_BLOCK_PREFIXES = (
    ("Internal table ACL drift is outside the reviewed repair", "INTERNAL_ACL_DRIFT"),
    ("Unexpected column-level internal table grants", "COLUMN_ACL_DRIFT"),
    (
        "Internal tables must be migration-owned with their reviewed RLS state",
        "TABLE_OWNER_RLS_DRIFT",
    ),
    ("Internal ACL check requires revision", "REVISION_MISMATCH"),
    ("ACL repair requires revision", "REVISION_MISMATCH"),
    ("A restricted table-owner login is required", "MIGRATOR_IDENTITY_MISMATCH"),
    ("Project confirmation mismatch", "PROJECT_CONFIRMATION_MISMATCH"),
)


def _diagnostic_reason_code(exc: Exception) -> str:
    """Map known failures to fixed codes; never return exception details."""
    message = str(exc)
    if isinstance(exc, runner.MigrationBlocked):
        if message.startswith("storage_role_graph category="):
            category = message.partition("category=")[2].partition(";")[0]
            if category in ROLE_GRAPH_CATEGORIES:
                return f"ROLE_GRAPH_{category.upper()}"
        for prefix, code in MIGRATION_BLOCK_PREFIXES:
            if message.startswith(prefix):
                return code
        return "PREFLIGHT_REJECTED"
    if isinstance(exc, InventoryBlocked):
        for prefix, code in INVENTORY_BLOCK_PREFIXES:
            if message.startswith(prefix):
                return code
        return "ACL_PLAN_REJECTED"
    return "UNEXPECTED_FAILURE"


def _write_plan(path: Path, plan: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(plan, stream, sort_keys=True, indent=2)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply"))
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--confirm-project-ref", required=True)
    parser.add_argument(
        "--confirm-maintenance-window", action="store_true", required=True
    )
    parser.add_argument("--approved-sha256")
    parser.add_argument("--authorization-expires-at")
    args = parser.parse_args(argv)
    engine = None
    try:
        runner.validate_migration_chain()
        target = runner.load_target()
        if target.start_revision not in {
            runner.AUTH_SESSIONS_REVISION,
            runner.CLAIMS_DISABLED_REVISION,
        }:
            raise InventoryBlocked("ACL repair supports only revision 0032 or 0033")
        if args.confirm_project_ref != target.project_ref:
            raise InventoryBlocked("Project confirmation mismatch")
        if args.operation == "apply":
            if not args.approved_sha256 or not args.authorization_expires_at:
                raise InventoryBlocked(
                    "Apply requires independent plan digest approval and expiry"
                )
            runner.validate_authorization(args.authorization_expires_at)

        engine = runner._engine(target)
        with engine.connect() as connection:
            runner.preflight(connection, target, _for_internal_acl_repair=True)
            if args.operation == "plan":
                with connection.begin():
                    plan = plan_acl_repair(connection)
                _write_plan(args.plan_file, plan)
                print("Read-only ACL plan SHA-256: " + plan_digest(plan))
            else:
                if args.plan_file.stat().st_size > 1024 * 1024:
                    raise InventoryBlocked(
                        "ACL repair plan exceeds the input size bound"
                    )
                plan = json.loads(args.plan_file.read_text())
                runner.validate_authorization(args.authorization_expires_at)
                with connection.begin():
                    changed = apply_acl_repair(
                        connection,
                        plan,
                        args.approved_sha256,
                    )
        if args.operation == "apply":
            runner.run_check(target)
            print(
                "Internal ACL repair verified; "
                f"changed_tables={changed}; no RLS or data changed"
            )
        return 0
    except Exception as exc:  # noqa: BLE001 - redact credential-bearing details
        error_type = (
            "MigrationBlocked"
            if isinstance(exc, runner.MigrationBlocked)
            else "InventoryBlocked"
            if isinstance(exc, InventoryBlocked)
            else "UnexpectedError"
        )
        print(
            "BLOCKED: internal ACL repair stopped "
            f"({error_type}; reason_code={_diagnostic_reason_code(exc)}); "
            "no data or RLS changes authorized",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
