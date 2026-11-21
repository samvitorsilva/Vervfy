"""Fail-closed, explicitly authorized production Alembic upgrade runner."""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
START_REVISION = "0031_cleanup_retry_limits"
AUTH_SESSIONS_REVISION = "0032_auth_sessions"
CLAIMS_DISABLED_REVISION = "0033_cleanup_claims_disabled"
TARGET_REVISION = "0034_storage_byte_reservations"
SUPPORTED_START_REVISIONS = (
    START_REVISION,
    AUTH_SESSIONS_REVISION,
    CLAIMS_DISABLED_REVISION,
)
PRE_CLAIMS_DISABLED_REVISIONS = (START_REVISION, AUTH_SESSIONS_REVISION)
AUTH_SESSIONS_PRESENT_REVISIONS = (
    AUTH_SESSIONS_REVISION,
    CLAIMS_DISABLED_REVISION,
    TARGET_REVISION,
)
AUTHORIZATION = f"{START_REVISION}..{TARGET_REVISION}"
AUTHORIZATION_TTL = timedelta(minutes=15)
EXPECTED_MIGRATION_COUNT = 34
STAGING_PROJECT_REF = "xgqvwqogdtktgfuubzwk"
PRODUCTION_PROJECT_REF = "llxmskxxchpmeavorusj"
PRODUCTION_MIGRATION_ROLE = "vervfy_prod_migrator"
SESSION_POOLER_HOST = "aws-0-us-east-2.pooler.supabase.com"
PROJECT_REF_PATTERN = re.compile(r"[a-z0-9]{20}\Z")
REQUIRED_TABLES = (
    "users",
    "tracks",
    "favorites",
    "playlists",
    "playlist_tracks",
    "upload_jobs",
    "artist_photos",
    "track_listens",
    "artist_images",
    "track_cover_cache",
)
FORBIDDEN_PG_ENV = (
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGOPTIONS",
    "PGSERVICE",
    "PGSERVICEFILE",
    "PGSSLMODE",
    "PGSSLROOTCERT",
)
MIGRATION_LOCK_ID = 0x564552564659


class MigrationBlocked(RuntimeError):
    """A missing or mismatched prerequisite that must stop the operation."""


@dataclass(frozen=True)
class ProductionTarget:
    url: URL
    project_ref: str
    database: str
    username: str
    connection_mode: str = "direct"
    start_revision: str = START_REVISION


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise MigrationBlocked(f"Required setting {name} is missing")
    return value


def load_target(env: Mapping[str, str] | None = None) -> ProductionTarget:
    values = os.environ if env is None else env
    if values.get("VERVFY_ENVIRONMENT", "").strip().lower() != "production":
        raise MigrationBlocked("VERVFY_ENVIRONMENT must be exactly production")
    for name in ("DATABASE_URL", "MIGRATION_DATABASE_URL"):
        if values.get(name, "").strip():
            raise MigrationBlocked(f"Unset {name}; use only VERVFY_PRODUCTION_DATABASE_URL")
    for name in FORBIDDEN_PG_ENV:
        if values.get(name, "").strip():
            raise MigrationBlocked(f"Unset {name}; libpq overrides are not allowed")

    project_ref = _required(values, "VERVFY_PRODUCTION_PROJECT_REF")
    if (
        PROJECT_REF_PATTERN.fullmatch(project_ref) is None
        or project_ref == STAGING_PROJECT_REF
        or project_ref != PRODUCTION_PROJECT_REF
    ):
        raise MigrationBlocked("Production Supabase project reference is not approved")

    database = _required(values, "VERVFY_PRODUCTION_EXPECTED_DATABASE")
    username = _required(values, "VERVFY_PRODUCTION_EXPECTED_USER")
    connection_mode = values.get("VERVFY_PRODUCTION_CONNECTION_MODE", "direct")
    if connection_mode not in ("direct", "session"):
        raise MigrationBlocked(
            "VERVFY_PRODUCTION_CONNECTION_MODE must be direct or session"
        )
    if database != "postgres":
        raise MigrationBlocked("Expected production database must be postgres")
    if username != PRODUCTION_MIGRATION_ROLE:
        raise MigrationBlocked("Expected production user must be the restricted migration role")

    start_revision = values.get("VERVFY_PRODUCTION_START_REVISION", START_REVISION)
    if start_revision not in SUPPORTED_START_REVISIONS:
        raise MigrationBlocked("Production start revision is not an approved upgrade boundary")

    raw_url = _required(values, "VERVFY_PRODUCTION_DATABASE_URL")
    try:
        url = make_url(raw_url)
    except Exception:  # noqa: BLE001 - fail closed without exposing credentials
        raise MigrationBlocked("VERVFY_PRODUCTION_DATABASE_URL is invalid") from None
    expected_host = (
        f"db.{project_ref}.supabase.co"
        if connection_mode == "direct"
        else SESSION_POOLER_HOST
    )
    expected_url_username = (
        username if connection_mode == "direct" else f"{username}.{project_ref}"
    )
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != expected_host
        or url.port != 5432
        or url.database != database
        or url.username != expected_url_username
        or not url.password
    ):
        endpoint = "direct" if connection_mode == "direct" else "Session Pooler"
        raise MigrationBlocked(
            f"Production URL must match the configured {endpoint} host, database, "
            "port, and migration login"
        )

    ca_file = Path(_required(values, "VERVFY_PRODUCTION_CA_FILE"))
    try:
        resolved_ca = ca_file.resolve(strict=True)
    except OSError:
        raise MigrationBlocked("VERVFY_PRODUCTION_CA_FILE is unavailable") from None
    if not resolved_ca.is_file() or not os.access(resolved_ca, os.R_OK):
        raise MigrationBlocked("VERVFY_PRODUCTION_CA_FILE must be a readable CA bundle")
    query = dict(url.query)
    if (
        set(query) != {"sslmode", "sslrootcert"}
        or query.get("sslmode") != "verify-full"
        or Path(query.get("sslrootcert", "")).resolve() != resolved_ca
    ):
        raise MigrationBlocked(
            "Production URL must set sslmode=verify-full and the configured CA bundle"
        )
    return ProductionTarget(url, project_ref, database, username, connection_mode, start_revision)


def validate_authorization(expires_at: str, *, now: datetime | None = None) -> None:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", expires_at) is None:
        raise MigrationBlocked("Authorization expiry must be UTC RFC3339 seconds ending in Z")
    try:
        expiry = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
    except ValueError:
        raise MigrationBlocked("Authorization expiry is not a valid UTC timestamp") from None
    current = datetime.now(UTC) if now is None else now.astimezone(UTC)
    if expiry <= current or expiry > current + AUTHORIZATION_TTL:
        raise MigrationBlocked("Authorization must be active and expire within 15 minutes")


def validate_migration_chain() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    chain = list(script.walk_revisions())
    if (
        script.get_heads() != [TARGET_REVISION]
        or len(chain) != EXPECTED_MIGRATION_COUNT
        or not chain
        or chain[0].revision != TARGET_REVISION
        or chain[-1].down_revision is not None
        or START_REVISION not in {revision.revision for revision in chain}
    ):
        raise MigrationBlocked(
            "Local Alembic history must be the reviewed linear chain through "
            f"{TARGET_REVISION}"
        )
    if any(
        newer.down_revision != older.revision
        for newer, older in pairwise(chain)
    ):
        raise MigrationBlocked("Local Alembic history is not a single linear chain")


# Safe preflight categories for storage role-graph gaps versus migration 0029.
ROLE_GRAPH_CATEGORY_CAPABILITY_ATTRIBUTES = "capability_attributes"
ROLE_GRAPH_CATEGORY_APP_RUNTIME_ATTRIBUTES = "app_runtime_attributes"
ROLE_GRAPH_CATEGORY_CAPABILITY_MEMBERSHIPS = "capability_memberships"
ROLE_GRAPH_CATEGORY_APP_RUNTIME_MEMBERSHIPS = "app_runtime_memberships"
ROLE_GRAPH_CATEGORY_STORAGE_MEMBERSHIP_OPTIONS = "storage_membership_options"
ROLE_GRAPH_CATEGORY_EFFECTIVE_PRIVILEGE_INHERITANCE = (
    "effective_privilege_inheritance"
)
ROLE_GRAPH_CATEGORY_OWNER_SET_CAPABILITY = "owner_set_capability"
ROLE_GRAPH_CATEGORY_PREEXISTING_PRIVILEGES = "preexisting_privileges"
APP_RUNTIME = "app_runtime"


def _load_storage_lifecycle_migration():
    """Load migration 0029 helpers without importing Alembic side effects."""
    from importlib.util import module_from_spec, spec_from_file_location

    path = ROOT / "alembic/versions/0029_storage_lifecycle.py"
    spec = spec_from_file_location("storage_lifecycle_migration_preflight", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _block_role_graph(category: str, detail: str) -> None:
    """Fail closed with a categorized, credential-free role-graph diagnostic."""
    raise MigrationBlocked(
        f"storage_role_graph category={category}; {detail}"
    )


def _check_app_runtime_attributes(connection: Connection, migration) -> object:
    """Require the reviewed Supabase app_runtime attributes before 0029."""
    row = connection.execute(
        text("""
            SELECT oid, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                   rolcreaterole, rolreplication, rolinherit
            FROM pg_catalog.pg_roles WHERE rolname = :name
        """),
        {"name": APP_RUNTIME},
    ).first()
    try:
        migration._validate_role_attributes(APP_RUNTIME, row, True)
    except RuntimeError:
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_APP_RUNTIME_ATTRIBUTES,
            "app_runtime must be LOGIN INHERIT without elevated privileges",
        )
    return row


def _check_storage_membership_options(
    connection: Connection,
    migration,
    *,
    owner_oid: int,
    executor_oid: int,
    worker_oid: int,
) -> None:
    """Match migration 0029 membership-option rules, including inert postgres ADMIN."""
    migrator_oid = connection.execute(
        text("SELECT current_user::regrole::oid")
    ).scalar_one()
    postgres_oid = connection.execute(
        text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'postgres'")
    ).scalar_one_or_none()
    owner_members = connection.execute(
        text("""
            SELECT member, inherit_option, set_option, admin_option
            FROM pg_catalog.pg_auth_members WHERE roleid = :owner
        """),
        {"owner": owner_oid},
    ).all()
    if not migration._valid_storage_memberships(
        owner_members,
        migrator_oid,
        postgres_oid,
        required_inherit=False,
        required_set=True,
    ):
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_STORAGE_MEMBERSHIP_OPTIONS,
            "owner membership options must allow only migration SET; "
            "postgres may hold ADMIN only",
        )
    executor_members = connection.execute(
        text("""
            SELECT member, inherit_option, set_option, admin_option
            FROM pg_catalog.pg_auth_members WHERE roleid = :executor
        """),
        {"executor": executor_oid},
    ).all()
    if not migration._valid_storage_memberships(
        executor_members,
        worker_oid,
        postgres_oid,
        required_inherit=True,
        required_set=False,
    ):
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_STORAGE_MEMBERSHIP_OPTIONS,
            "executor membership options must allow only worker INHERIT; "
            "postgres may hold ADMIN only",
        )


def _check_auth_sessions(
    connection: Connection, *, expected_exists: bool
) -> None:
    """Require the reviewed auth-session owner, RLS state, and exact grants."""
    exists = connection.execute(text("""
        SELECT pg_catalog.to_regclass('public.auth_sessions') IS NOT NULL
    """)).scalar_one()
    if exists != expected_exists:
        raise MigrationBlocked("auth_sessions does not match the approved starting revision")
    if not exists:
        return

    relation = connection.execute(text("""
        SELECT pg_catalog.pg_get_userbyid(c.relowner),
               c.relrowsecurity, c.relforcerowsecurity
        FROM pg_catalog.pg_class c
        WHERE c.oid = pg_catalog.to_regclass('public.auth_sessions')
    """)).one_or_none()
    current_user = connection.exec_driver_sql(
        "SELECT current_user"
    ).scalar_one()
    if (
        relation is None
        or relation[0] != current_user
        or relation[1]
        or relation[2]
    ):
        raise MigrationBlocked(
            "auth_sessions must be migration-owned with RLS disabled"
        )

    acl = connection.execute(text("""
        SELECT COALESCE(r.rolname, 'PUBLIC'),
               a.privilege_type,
               a.is_grantable
        FROM pg_catalog.pg_class c
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(c.relacl, pg_catalog.acldefault('r'::"char", c.relowner))
        ) a
        LEFT JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE c.oid = pg_catalog.to_regclass('public.auth_sessions')
          AND a.grantee <> c.relowner
    """)).all()
    actual_acl = {
        (row[0], row[1], bool(row[2]))
        for row in acl
    }
    expected_acl = {
        ("app_runtime", "SELECT", False),
        ("app_runtime", "INSERT", False),
        ("app_runtime", "DELETE", False),
    }
    if actual_acl != expected_acl:
        raise MigrationBlocked("Unexpected direct auth_sessions privileges")

    runtime_privileges = connection.execute(text("""
        SELECT
            has_table_privilege('app_runtime', 'public.auth_sessions', 'SELECT'),
            has_table_privilege('app_runtime', 'public.auth_sessions', 'INSERT'),
            has_table_privilege('app_runtime', 'public.auth_sessions', 'UPDATE'),
            has_table_privilege('app_runtime', 'public.auth_sessions', 'DELETE'),
            has_table_privilege('app_runtime', 'public.auth_sessions', 'TRUNCATE'),
            has_table_privilege('app_runtime', 'public.auth_sessions', 'REFERENCES'),
            has_table_privilege('app_runtime', 'public.auth_sessions', 'TRIGGER')
    """)).one()
    if tuple(runtime_privileges) != (
        True, True, False, True, False, False, False
    ):
        raise MigrationBlocked("Unexpected effective auth_sessions privileges")


def _check_effective_privilege_inheritance(
    connection: Connection,
    *,
    owner_oid: int,
    executor_oid: int,
    worker_oid: int,
    postgres_oid: int | None,
) -> None:
    """Reject unexpected effective USAGE/SET on storage capability roles."""
    unsafe = connection.execute(
        text("""
            SELECT 1 FROM pg_catalog.pg_roles r
            WHERE NOT r.rolsuper
              AND r.oid NOT IN (:owner, current_user::regrole::oid)
              AND (:postgres IS NULL OR r.oid <> :postgres)
              AND (
                  pg_catalog.pg_has_role(r.oid, :owner, 'USAGE')
                  OR pg_catalog.pg_has_role(r.oid, :owner, 'SET')
              )
            UNION ALL
            SELECT 1 FROM pg_catalog.pg_roles r
            WHERE NOT r.rolsuper
              AND r.oid NOT IN (:executor, :worker)
              AND (:postgres IS NULL OR r.oid <> :postgres)
              AND (
                  pg_catalog.pg_has_role(r.oid, :executor, 'USAGE')
                  OR pg_catalog.pg_has_role(r.oid, :executor, 'SET')
              )
            LIMIT 1
        """),
        {
            "owner": owner_oid,
            "executor": executor_oid,
            "worker": worker_oid,
            "postgres": postgres_oid,
        },
    ).first()
    if unsafe:
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_EFFECTIVE_PRIVILEGE_INHERITANCE,
            "unexpected effective USAGE or SET on storage capability roles",
        )


def _check_role_graph(connection: Connection, migration_user: str) -> None:
    """Validate the restricted storage lifecycle role configuration.

    Aligns read-only preflight with migration 0029 `_roles()` checks that were
    previously absent: app_runtime attributes/memberships, migration membership
    options, and effective privilege inheritance — while preserving the existing
    TLS/project/authorization path and grantor-aware Supabase membership asserts.
    """
    from supabase_role_memberships import (
        assert_member_memberships,
        assert_role_memberships,
    )

    migration = _load_storage_lifecycle_migration()
    owner = migration.OWNER
    executor = migration.EXECUTOR
    worker = migration.WORKER

    roles = connection.execute(
        text("""
            SELECT oid, rolname, rolcanlogin, rolsuper, rolbypassrls,
                   rolcreatedb, rolcreaterole, rolreplication, rolinherit
            FROM pg_catalog.pg_roles
            WHERE rolname IN (:owner, :executor, :worker)
        """),
        {"owner": owner, "executor": executor, "worker": worker},
    ).all()

    by_name = {row.rolname: row for row in roles}

    for role_name in (owner, executor):
        role = by_name.get(role_name)
        if role is None or any(
            (
                role.rolcanlogin,
                role.rolsuper,
                role.rolbypassrls,
                role.rolcreatedb,
                role.rolcreaterole,
                role.rolreplication,
                role.rolinherit,
            )
        ):
            _block_role_graph(
                ROLE_GRAPH_CATEGORY_CAPABILITY_ATTRIBUTES,
                f"Restricted storage role {role_name} is not ready",
            )

    login = by_name.get(worker)
    if (
        login is None
        or not login.rolcanlogin
        or any(
            (
                login.rolsuper,
                login.rolbypassrls,
                login.rolcreatedb,
                login.rolcreaterole,
                login.rolreplication,
                login.rolinherit,
            )
        )
    ):
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_CAPABILITY_ATTRIBUTES,
            "Restricted storage cleanup login is not ready",
        )

    _check_app_runtime_attributes(connection, migration)

    try:
        assert_role_memberships(
            connection,
            owner,
            [(migration_user, "postgres", False, False, True)],
        )
        assert_member_memberships(connection, owner, [])

        assert_role_memberships(
            connection,
            executor,
            [(worker, "postgres", False, True, False)],
        )
        # Migration 0029 rejects capability roles that themselves hold memberships.
        assert_member_memberships(connection, executor, [])
        # The only permitted member of the worker role is an inert
        # postgres ADMIN grant (no INHERIT and no SET).
        unexpected_worker_member = connection.execute(
            text("""
                SELECT 1
                FROM pg_catalog.pg_auth_members AS m
                JOIN pg_catalog.pg_roles AS granted
                  ON granted.oid = m.roleid
                JOIN pg_catalog.pg_roles AS member
                  ON member.oid = m.member
                WHERE granted.rolname = :worker
                  AND NOT (
                      member.rolname = 'postgres'
                      AND m.admin_option
                      AND NOT m.inherit_option
                      AND NOT m.set_option
                  )
                LIMIT 1
            """),
            {"worker": worker},
        ).first()
        if unexpected_worker_member:
            raise RuntimeError("Unexpected worker role membership")

        assert_member_memberships(
            connection,
            worker,
            [(executor, "postgres", False, True, False)],
        )
    except RuntimeError:
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_CAPABILITY_MEMBERSHIPS,
            "reviewed capability membership graph is not satisfied",
        )

    try:
        assert_member_memberships(connection, APP_RUNTIME, [])
    except RuntimeError:
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_APP_RUNTIME_MEMBERSHIPS,
            "app_runtime must not hold role memberships before 0029",
        )

    _check_storage_membership_options(
        connection,
        migration,
        owner_oid=by_name[owner].oid,
        executor_oid=by_name[executor].oid,
        worker_oid=by_name[worker].oid,
    )

    can_set_owner = connection.execute(
        text("SELECT pg_catalog.pg_has_role(current_user, :owner, 'SET')"),
        {"owner": owner},
    ).scalar_one()

    if not can_set_owner:
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_OWNER_SET_CAPABILITY,
            "Migration login cannot SET ROLE to storage lifecycle owner",
        )

    _check_effective_privilege_inheritance(
        connection,
        owner_oid=by_name[owner].oid,
        executor_oid=by_name[executor].oid,
        worker_oid=by_name[worker].oid,
        postgres_oid=connection.execute(
            text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres'")
        ).scalar_one_or_none(),
    )

    # Migration 0029's fresh-install scan is not valid after 0029-0031
    # intentionally grant lifecycle table and function capabilities. Validate
    # the exact post-install ACL inventory instead; never revoke existing ACLs.
    try:
        _check_storage_acl_inventory(
            connection, owner=owner, executor=executor, worker=worker
        )
    except RuntimeError:
        _block_role_graph(
            ROLE_GRAPH_CATEGORY_PREEXISTING_PRIVILEGES,
            "storage capability ACL inventory differs from the reviewed "
            "0029-0031 allowlist",
        )



def _check_storage_acl_inventory(
    connection: Connection,
    *,
    owner: str,
    executor: str,
    worker: str,
) -> None:
    """Accept reviewed lifecycle ACLs for the installed revision; reject drift.

    This is intentionally a post-install inventory, not migration 0029's
    fresh-role check. Existing grants on the lifecycle tables and functions
    are required for the application to operate and must not be revoked.
    """
    rows = connection.execute(text("""
        SELECT r.rolname AS role_name, 'SCHEMA' AS object_type,
               n.nspname::text AS object_name, a.privilege_type,
               a.is_grantable
        FROM pg_catalog.pg_namespace n
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(n.nspacl, pg_catalog.acldefault('n'::"char", n.nspowner))
        ) a
        JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE r.rolname IN (:owner, :executor, :worker)

        UNION ALL

        SELECT r.rolname, 'TABLE', n.nspname::text || '.' || c.relname::text,
               a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                c.relacl,
                pg_catalog.acldefault(
                    CASE WHEN c.relkind = 'S' THEN 's'::"char" ELSE 'r'::"char" END,
                    c.relowner
                )
            )
        ) a
        JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE c.relkind IN ('r','p','v','m','f','S')
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND r.rolname IN (:owner, :executor, :worker)

        UNION ALL

        SELECT r.rolname, 'COLUMN',
               n.nspname::text || '.' || c.relname::text || '.' || att.attname::text,
               a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute att ON att.attrelid = c.oid
        CROSS JOIN LATERAL pg_catalog.aclexplode(att.attacl) a
        JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE att.attnum > 0 AND NOT att.attisdropped
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND r.rolname IN (:owner, :executor, :worker)

        UNION ALL

        SELECT r.rolname, 'FUNCTION',
               n.nspname::text || '.' || p.proname::text || '(' ||
                   pg_catalog.pg_get_function_identity_arguments(p.oid) || ')',
               a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(p.proacl, pg_catalog.acldefault('f'::"char", p.proowner))
        ) a
        JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE n.nspname = 'vervfy_storage'
          AND r.rolname IN (:owner, :executor, :worker)
    """), {"owner": owner, "executor": executor, "worker": worker}).all()

    # Recognize only the exact reviewed quota migration, not arbitrary future
    # schemas. This inventory is read-only and never creates or restores grants.
    quota_aware = connection.execute(
        text("SELECT version_num FROM public.alembic_version")
    ).scalars().all() == ["0034_storage_byte_reservations"]

    actual = {
        (row.role_name, row.object_type, row.object_name,
         row.privilege_type, bool(row.is_grantable))
        for row in rows
    }

    allowed = set()
    for object_name in ("vervfy_storage", "public"):
        allowed.add((owner, "SCHEMA", object_name, "USAGE", False))
    allowed.add((executor, "SCHEMA", "vervfy_storage", "USAGE", False))

    for table, privileges in {
        "vervfy_storage.namespaces": ("SELECT",),
        "vervfy_storage.objects": ("SELECT", "INSERT", "UPDATE"),
        "vervfy_storage.cleanup_jobs": ("SELECT", "INSERT", "UPDATE"),
    }.items():
        for privilege in privileges:
            allowed.add((owner, "TABLE", table, privilege, False))

    if quota_aware:
        for privilege in ("SELECT", "UPDATE"):
            allowed.add((owner, "TABLE", "vervfy_storage.quota_policy", privilege, False))

    for table, column in (
        ("public.users", "id"),
        ("public.tracks", "storage_path"),
        ("public.tracks", "cover_path"),
        ("public.artist_photos", "storage_path"),
        ("public.upload_jobs", "storage_path"),
    ):
        allowed.add((owner, "COLUMN", f"{table}.{column}", "SELECT", False))

    lifecycle_functions = (
        "guard_namespace()",
        "validate_namespace(p_id uuid, p_environment text, p_endpoint text, p_bucket text)",
        "_has_references(p_path text)",
        "_queue(p_object uuid, p_actor text)",
        "reserve_object(p_kind text, p_extension text)",
        "advance_upload(p_object uuid, p_token uuid, p_next text)",
        "request_cleanup(p_object uuid)",
        "guard_references()",
        "retire_candidate(p_object uuid)",
        "claim_cleanup(p_object uuid)",
        "claim_next_cleanup()",
        "complete_cleanup(p_object uuid, p_token uuid)",
        "retry_cleanup(p_object uuid, p_token uuid, p_error_code text)",
    )
    if quota_aware:
        lifecycle_functions += (
            "reserve_sized_object(p_kind text, p_extension text, p_bytes bigint, p_limit bigint)",
            "retained_bytes()",
        )
    for signature in lifecycle_functions:
        allowed.add((
            owner, "FUNCTION", f"vervfy_storage.{signature}", "EXECUTE", False
        ))

    executor_functions = (
        "claim_cleanup(p_object uuid)",
        "claim_next_cleanup()",
        "complete_cleanup(p_object uuid, p_token uuid)",
        "retire_candidate(p_object uuid)",
        "retry_cleanup(p_object uuid, p_token uuid, p_error_code text)",
        "validate_namespace(p_id uuid, p_environment text, p_endpoint text, p_bucket text)",
    )
    for signature in executor_functions:
        allowed.add((
            executor, "FUNCTION", f"vervfy_storage.{signature}", "EXECUTE", False
        ))

    # Also inspect effective privileges, not just direct ACL entries. This
    # catches PUBLIC grants and privileges inherited through an unexpected role.
    effective_relations = connection.execute(text("""
        SELECT r.rolname AS role_name,
               n.nspname || '.' || c.relname AS object_name,
               privilege.privilege_type
        FROM pg_catalog.pg_roles r
        CROSS JOIN pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN (VALUES
            ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'),
            ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')
        ) AS privilege(privilege_type)
        WHERE r.rolname IN (:owner, :executor, :worker)
          AND c.relkind IN ('r','p','v','m','f')
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND pg_catalog.has_table_privilege(
              r.oid, c.oid, privilege.privilege_type
          )
    """), {"owner": owner, "executor": executor, "worker": worker}).all()

    effective_allowed = set()
    for table, privileges in {
        "vervfy_storage.namespaces": ("SELECT",),
        "vervfy_storage.objects": ("SELECT", "INSERT", "UPDATE"),
        "vervfy_storage.cleanup_jobs": ("SELECT", "INSERT", "UPDATE"),
        "public.users": ("SELECT",),
        "public.tracks": ("SELECT",),
        "public.artist_photos": ("SELECT",),
        "public.upload_jobs": ("SELECT",),
        "extensions.pg_stat_statements": ("SELECT",),
        "extensions.pg_stat_statements_info": ("SELECT",),
    }.items():
        for privilege in privileges:
            effective_allowed.add((owner, table, privilege))
    for role in (executor, worker):
        for view in (
            "extensions.pg_stat_statements",
            "extensions.pg_stat_statements_info",
        ):
            effective_allowed.add((role, view, "SELECT"))

    if quota_aware:
        for privilege in ("SELECT", "UPDATE"):
            effective_allowed.add((owner, "vervfy_storage.quota_policy", privilege))

    unexpected_effective = {
        (row.role_name, row.object_name, row.privilege_type)
        for row in effective_relations
    } - effective_allowed
    if unexpected_effective:
        raise RuntimeError(
            "Unexpected effective storage capability relation privileges: "
            + "; ".join(
                f"{role} {name} {privilege}"
                for role, name, privilege in sorted(unexpected_effective)[:3]
            )
        )

    effective_columns = connection.execute(text("""
        SELECT r.rolname AS role_name,
               n.nspname || '.' || c.relname || '.' || att.attname AS object_name,
               privilege.privilege_type
        FROM pg_catalog.pg_roles r
        CROSS JOIN pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute att ON att.attrelid = c.oid
        CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('REFERENCES'))
            AS privilege(privilege_type)
        WHERE r.rolname IN (:owner, :executor, :worker)
          AND att.attnum > 0 AND NOT att.attisdropped
          AND n.nspname = 'public'
          AND pg_catalog.has_column_privilege(
              r.oid, c.oid, att.attnum, privilege.privilege_type
          )
    """), {"owner": owner, "executor": executor, "worker": worker}).all()

    expected_columns = {
        (owner, "public.users.id", "SELECT"),
        (owner, "public.tracks.storage_path", "SELECT"),
        (owner, "public.tracks.cover_path", "SELECT"),
        (owner, "public.artist_photos.storage_path", "SELECT"),
        (owner, "public.upload_jobs.storage_path", "SELECT"),
    }
    unexpected_columns = {
        (row.role_name, row.object_name, row.privilege_type)
        for row in effective_columns
    } - expected_columns
    if unexpected_columns:
        raise RuntimeError(
            "Unexpected effective storage capability column privileges: "
            + "; ".join(
                f"{role} {name} {privilege}"
                for role, name, privilege in sorted(unexpected_columns)[:3]
            )
        )

    effective_sequences = connection.execute(text("""
        SELECT r.rolname AS role_name,
               n.nspname || '.' || c.relname AS object_name,
               privilege.privilege_type
        FROM pg_catalog.pg_roles r
        CROSS JOIN pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN (VALUES ('USAGE'), ('SELECT'), ('UPDATE'))
            AS privilege(privilege_type)
        WHERE r.rolname IN (:owner, :executor, :worker)
          AND c.relkind = 'S'
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND pg_catalog.has_sequence_privilege(
              r.oid, c.oid, privilege.privilege_type
          )
    """), {"owner": owner, "executor": executor, "worker": worker}).all()
    if effective_sequences:
        raise RuntimeError("Storage capability roles have unexpected sequence privileges")

    effective_functions = connection.execute(text("""
        SELECT r.rolname AS role_name,
               n.nspname::text || '.' || p.proname::text || '(' ||
                   pg_catalog.pg_get_function_identity_arguments(p.oid) || ')' AS object_name
        FROM pg_catalog.pg_roles r
        CROSS JOIN pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE r.rolname IN (:owner, :executor, :worker)
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND pg_catalog.has_function_privilege(r.oid, p.oid, 'EXECUTE')
    """), {"owner": owner, "executor": executor, "worker": worker}).all()

    expected_function_access = {
        (owner, "vervfy_storage." + signature)
        for signature in lifecycle_functions
    } | {
        (role, "vervfy_storage." + signature)
        for role in (executor, worker)
        for signature in executor_functions
    }
    actual_function_access = {
        (row.role_name, row.object_name) for row in effective_functions
    }
    unexpected_function_access = actual_function_access - expected_function_access
    if unexpected_function_access:
        raise RuntimeError(
            "Unexpected effective storage capability function privileges: "
            + "; ".join(
                f"{role} {name}"
                for role, name in sorted(unexpected_function_access)[:3]
            )
        )

    unsafe_schema_create = connection.execute(text("""
        SELECT r.rolname, n.nspname
        FROM pg_catalog.pg_roles r
        CROSS JOIN pg_catalog.pg_namespace n
        WHERE r.rolname IN (:owner, :executor, :worker)
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND pg_catalog.has_schema_privilege(r.oid, n.oid, 'CREATE')
        LIMIT 1
    """), {"owner": owner, "executor": executor, "worker": worker}).first()
    if unsafe_schema_create:
        raise RuntimeError("Storage capability roles have unexpected schema CREATE access")

    unexpected = actual - allowed
    if unexpected:
        sample = sorted(unexpected)
        raise RuntimeError(
            "Unexpected direct storage capability ACL entries:" + chr(10)
            + chr(10).join(
                repr((role, kind, name, privilege, grantable))
                for role, kind, name, privilege, grantable in sample
            )
        )

    ownership = connection.execute(text("""
        SELECT r.rolname AS role_name, 'SCHEMA' AS object_type,
               n.nspname::text AS object_name
        FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid = n.nspowner
        WHERE r.rolname IN (:owner, :executor, :worker)
        UNION ALL
        SELECT r.rolname, 'TABLE', n.nspname::text || '.' || c.relname::text
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
        WHERE c.relkind IN ('r','p','v','m','f','S')
          AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND r.rolname IN (:owner, :executor, :worker)
        UNION ALL
        SELECT r.rolname, 'FUNCTION',
               n.nspname::text || '.' || p.proname::text || '(' ||
                   pg_catalog.pg_get_function_identity_arguments(p.oid) || ')'
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_catalog.pg_roles r ON r.oid = p.proowner
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND r.rolname IN (:owner, :executor, :worker)
    """), {"owner": owner, "executor": executor, "worker": worker}).all()

    expected_owned_functions = {
        "vervfy_storage." + signature for signature in lifecycle_functions
    }
    unexpected_ownership = [
        (row.role_name, row.object_type, row.object_name)
        for row in ownership
        if not (
            row.role_name == owner
            and row.object_type == "FUNCTION"
            and row.object_name in expected_owned_functions
        )
    ]
    if unexpected_ownership:
        raise RuntimeError("Storage capability role unexpectedly owns database objects")

    defaults = connection.execute(text("""
        SELECT DISTINCT r.rolname
        FROM pg_catalog.pg_default_acl d
        CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
        JOIN pg_catalog.pg_roles r
          ON r.oid = d.defaclrole OR r.oid = a.grantee
        WHERE r.rolname IN (:owner, :executor, :worker) OR a.grantee = 0
    """), {"owner": owner, "executor": executor, "worker": worker}).scalars().all()
    if defaults:
        raise RuntimeError("Storage capability roles have unexpected default ACLs")


def _verify_client_tls(connection: Connection) -> None:
    """Require negotiated TLS on this SQLAlchemy connection's psycopg socket."""
    # pg_stat_ssl describes the database backend's transport, which may be the
    # pooler-to-database hop. libpq reports the runner's actual transport for
    # both direct and Session Pooler connections. URL sslmode is not evidence.
    try:
        tls = connection.connection.driver_connection.pgconn.ssl_in_use
    except Exception:  # noqa: BLE001 - fail closed without exposing credentials  # noqa: BLE001 - fail closed without exposing driver details
        raise MigrationBlocked(
            "Client-side PostgreSQL TLS verification evidence is unavailable"
        ) from None
    if tls is False:
        raise MigrationBlocked("PostgreSQL connection did not negotiate TLS")
    if tls is not True:
        raise MigrationBlocked(
            "Client-side PostgreSQL TLS verification evidence is unavailable"
        )


def preflight(connection: Connection, target: ProductionTarget) -> None:
    _verify_client_tls(connection)
    with connection.begin():
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        connection.exec_driver_sql("SET LOCAL search_path TO public")
        identity = connection.execute(
            text("""
                SELECT current_database(), session_user, current_user,
                       current_schema(), current_setting('server_version_num')::integer
            """)
        ).one()
        db_name, session_user, current_user, schema, version_num = identity
        if db_name != target.database:
            raise MigrationBlocked("Connected database does not match the approved target")
        if session_user != target.username or current_user != target.username:
            raise MigrationBlocked("Connected login does not match the approved migration role")
        if schema != "public":
            raise MigrationBlocked("Production migration search path is not public")
        if version_num < 160000:
            raise MigrationBlocked("PostgreSQL 16 or newer is required for membership checks")

        principal = connection.execute(
            text("""
                SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole,
                       rolreplication, rolcanlogin
                FROM pg_catalog.pg_roles WHERE rolname = current_user
            """)
        ).one_or_none()
        if principal is None or any(principal[:5]) or not principal.rolcanlogin:
            raise MigrationBlocked("Migration login must be unprivileged and able to log in")

        privileges = connection.execute(
            text("""
                SELECT has_database_privilege(current_user, current_database(), 'CONNECT'),
                       has_database_privilege(current_user, current_database(), 'CREATE'),
                       has_schema_privilege(current_user, 'public', 'USAGE'),
                       has_schema_privilege(current_user, 'public', 'CREATE')
            """)
        ).one()
        if not all(privileges):
            raise MigrationBlocked(
                "Migration login requires database CONNECT/CREATE and public USAGE/CREATE"
            )

        owned = set(
            connection.execute(
                text("""
                    SELECT c.relname
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind IN ('r', 'p')
                      AND pg_catalog.pg_get_userbyid(c.relowner) = current_user
                """)
            ).scalars()
        )
        missing_ownership = sorted(set(REQUIRED_TABLES) - owned)
        if missing_ownership:
            raise MigrationBlocked(
                "Migration login must own required application tables: "
                + ", ".join(missing_ownership)
            )
        version_owner = connection.execute(
            text("""
                SELECT pg_catalog.pg_get_userbyid(c.relowner)
                FROM pg_catalog.pg_class c
                WHERE c.oid = 'public.alembic_version'::regclass
            """)
        ).scalar_one_or_none()
        if version_owner != current_user:
            raise MigrationBlocked("Migration login must own public.alembic_version")
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalars().all()
        if target.start_revision not in SUPPORTED_START_REVISIONS or revision != [target.start_revision]:
            raise MigrationBlocked(
                f"Expected exactly {target.start_revision}; found a different Alembic revision state"
            )
        # Verify the complete restricted storage role graph before
        # exercising the lifecycle owner's read capability.
        _check_role_graph(connection, current_user)

        # Verify the existing production storage namespace.
        schema_exists = connection.execute(
            text("SELECT pg_catalog.to_regnamespace('vervfy_storage') IS NOT NULL")
        ).scalar_one()

        if not schema_exists:
            raise MigrationBlocked("Existing storage lifecycle schema is missing")

        storage_schema = connection.execute(text("""
            SELECT pg_catalog.pg_get_userbyid(nspowner),
                   has_schema_privilege(current_user, 'vervfy_storage', 'USAGE'),
                   has_schema_privilege(current_user, 'vervfy_storage', 'CREATE')
            FROM pg_catalog.pg_namespace
            WHERE nspname = 'vervfy_storage'
        """)).one_or_none()
        storage_table_owners = set(connection.execute(text("""
            SELECT c.relname
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'vervfy_storage'
              AND c.relname IN ('namespaces', 'objects', 'cleanup_jobs')
              AND c.relkind IN ('r', 'p')
              AND pg_catalog.pg_get_userbyid(c.relowner) = current_user
        """)).scalars())
        if (
            storage_schema is None
            or storage_schema[0] != current_user
            or not storage_schema[1]
            or not storage_schema[2]
            or storage_table_owners != {"namespaces", "objects", "cleanup_jobs"}
        ):
            raise MigrationBlocked(
                "Migration login must own the storage lifecycle schema and tables"
            )

        # Read the namespace using its restricted lifecycle-owner capability.
        connection.exec_driver_sql(
            "SET LOCAL ROLE vervfy_storage_lifecycle_owner"
        )
        namespace_rows = connection.execute(text("""
            SELECT namespace_id::text, environment, endpoint,
                   bucket, physical_cleanup_enabled
            FROM vervfy_storage.namespaces
            WHERE id = 1
        """)).all()
        connection.exec_driver_sql("RESET ROLE")

        expected_namespace = (
            "31daf7cc-8563-411f-94c7-944d607d1ef1",
            "production",
            "https://llxmskxxchpmeavorusj.supabase.co",
            "songs",
            False,
        )

        if len(namespace_rows) != 1 or tuple(namespace_rows[0]) != expected_namespace:
            raise MigrationBlocked(
                "Existing production storage namespace does not match "
                "the approved configuration"
            )

        # The storage lifecycle columns must already exist at revision 0031.
        existing_columns = {
            (row.table_name, row.column_name)
            for row in connection.execute(text("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND (
                      (table_name = 'tracks' AND column_name = 'media_version')
                      OR (table_name = 'artist_photos' AND column_name = 'media_version')
                      OR (table_name = 'upload_jobs' AND column_name = 'processing_token')
                  )
            """)).all()
        }

        expected_columns = {
            ("tracks", "media_version"),
            ("artist_photos", "media_version"),
            ("upload_jobs", "processing_token"),
        }

        if not expected_columns.issubset(existing_columns):
            raise MigrationBlocked(
                "Existing storage lifecycle columns are incomplete"
            )

        # 0032 creates auth_sessions; 0033 preserves its reviewed grants.
        _check_auth_sessions(
            connection,
            expected_exists=target.start_revision in AUTH_SESSIONS_PRESENT_REVISIONS,
        )

        # Confirm the expected pre-0033 cleanup permissions.
        cleanup_privileges = connection.execute(text("""
            SELECT
                has_function_privilege(
                    'vervfy_storage_lifecycle_owner',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                ),
                has_function_privilege(
                    'vervfy_storage_cleanup',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                ),
                has_function_privilege(
                    'storage_cleanup_worker',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                ),
                has_function_privilege(
                    'app_runtime',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                )
        """)).one()

        expected_claims = (
            (True, True, True, False)
            if target.start_revision in PRE_CLAIMS_DISABLED_REVISIONS
            else (True, False, False, False)
        )
        if tuple(cleanup_privileges) != expected_claims:
            raise MigrationBlocked(
                "Unexpected cleanup-claim privileges at the approved starting revision"
            )



def _engine(target: ProductionTarget):
    return create_engine(target.url, poolclass=NullPool, pool_pre_ping=True)


def run_check(target: ProductionTarget) -> None:
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            preflight(connection, target)
    finally:
        engine.dispose()


def _verify_followup_result(connection: Connection, *, installation: bool = True) -> None:
    """Verify the quota-aware head without enabling cleanup or changing data."""
    with (connection.begin_nested() if connection.in_transaction() else connection.begin()):
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalars().all()

        if revision != [TARGET_REVISION]:
            raise MigrationBlocked("Post-migration revision verification failed")

        _check_auth_sessions(connection, expected_exists=True)

        cleanup_privileges = connection.execute(text("""
            SELECT
                has_function_privilege(
                    'vervfy_storage_lifecycle_owner',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                ),
                has_function_privilege(
                    'vervfy_storage_cleanup',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                ),
                has_function_privilege(
                    'storage_cleanup_worker',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                ),
                has_function_privilege(
                    'app_runtime',
                    'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
                )
        """)).one()

        if tuple(cleanup_privileges) != (True, False, False, False):
            raise MigrationBlocked(
                "Unexpected effective cleanup-claim privileges after 0033"
            )

        # Verify the immutable namespace using its restricted owner role.
        connection.exec_driver_sql(
            "SET LOCAL ROLE vervfy_storage_lifecycle_owner"
        )

        namespace = connection.execute(text("""
            SELECT namespace_id::text, environment, endpoint,
                   bucket, physical_cleanup_enabled
            FROM vervfy_storage.namespaces
            WHERE id = 1
        """)).all()

        connection.exec_driver_sql("RESET ROLE")

        expected = (
            "31daf7cc-8563-411f-94c7-944d607d1ef1",
            "production",
            "https://llxmskxxchpmeavorusj.supabase.co",
            "songs",
            False,
        )

        if len(namespace) != 1 or tuple(namespace[0]) != expected:
            raise MigrationBlocked(
                "Production storage namespace changed unexpectedly"
            )
        connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
        policy = connection.exec_driver_sql(
            "SELECT tenant_limit_bytes,total_limit_bytes FROM vervfy_storage.quota_policy WHERE id=1"
        ).one()
        connection.exec_driver_sql("RESET ROLE")
        if ((installation and tuple(policy) != (157286400, 10737418240))
            or any(type(value) is not int or value <= 0 for value in policy)):
            raise MigrationBlocked("Unexpected quota policy after 0034")

        quota_access = connection.execute(text("""
            SELECT
              has_function_privilege('app_runtime', 'vervfy_storage.reserve_sized_object(text,text,bigint,bigint)', 'EXECUTE'),
              has_function_privilege('app_runtime', 'vervfy_storage.retained_bytes()', 'EXECUTE'),
              has_function_privilege('app_runtime', 'vervfy_storage.reserve_object(text,text)', 'EXECUTE'),
              has_table_privilege('app_runtime', 'vervfy_storage.quota_policy', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),
              (SELECT relrowsecurity AND relforcerowsecurity FROM pg_catalog.pg_class
               WHERE oid='vervfy_storage.quota_policy'::regclass)
        """)).one()
        if tuple(quota_access) != (True, True, False, False, True):
            raise MigrationBlocked("Unexpected quota RLS or runtime privileges after 0034")
        _check_storage_acl_inventory(
            connection, owner="vervfy_storage_lifecycle_owner",
            executor="vervfy_storage_cleanup", worker="storage_cleanup_worker",
        )



def run_upgrade(target: ProductionTarget, expires_at: str) -> None:
    engine = _engine(target)
    stage = "connection"
    try:
        with engine.connect() as connection:
            stage = "advisory_lock"
            connection.execute(
                text("SELECT pg_catalog.pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            connection.commit()

            stage = "preflight"
            preflight(connection, target)
            stage = "session_setup"
            connection.exec_driver_sql("SET search_path TO public")
            connection.commit()
            stage = "authorization"
            validate_authorization(expires_at)

            from unittest.mock import patch

            from alembic.config import Config

            from alembic import command

            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["vervfy_production_migration_runner"] = True
            config.attributes["connection"] = connection

            validate_authorization(expires_at)
            stage = "migration_chain"
            validate_migration_chain()

            stage = "alembic_upgrade"
            # Postflight failures roll back the entire upgrade, including DDL.
            with (
                patch.dict(os.environ, {"DATABASE_URL": target.url.render_as_string(hide_password=False)}),
                connection.begin(),
            ):
                command.upgrade(config, TARGET_REVISION)
                stage = "post_migration_verification"
                _verify_followup_result(connection)
    except Exception as exc:
        exc.add_note(f"vervfy_migration_stage={stage}")
        raise
    finally:
        engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("check", "upgrade"):
        subparser = subparsers.add_parser(operation)
        subparser.add_argument("--confirm-project-ref", required=True)
        if operation == "upgrade":
            subparser.add_argument(
                "--authorize-production-migration",
                required=True,
                choices=tuple(f"{start}..{TARGET_REVISION}" for start in SUPPORTED_START_REVISIONS),
            )
            subparser.add_argument(
                "--authorization-expires-at",
                required=True,
                help="UTC RFC3339 expiry; must be within 15 minutes",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        validate_migration_chain()
        target = load_target()
        if args.confirm_project_ref != target.project_ref:
            raise MigrationBlocked("Confirmation does not match the configured production project")
        if args.operation == "upgrade":
            if args.authorize_production_migration != f"{target.start_revision}..{TARGET_REVISION}":
                raise MigrationBlocked("Authorization does not match the configured upgrade boundary")
            validate_authorization(args.authorization_expires_at)
            run_upgrade(target, args.authorization_expires_at)
            print(f"Production migration completed at {TARGET_REVISION}")
        else:
            run_check(target)
            print(
                f"Read-only production preflight passed at {target.start_revision}; "
                "no migration was executed"
            )
        return 0
    except MigrationBlocked as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - redact unexpected errors
        sqlstate = None
        current = exc
        visited = set()

        while current is not None and id(current) not in visited:
            visited.add(id(current))
            candidate = getattr(current, "sqlstate", None)
            if not isinstance(candidate, str):
                candidate = getattr(current, "pgcode", None)

            if (
                isinstance(candidate, str)
                and len(candidate) == 5
                and candidate.isascii()
                and candidate.isalnum()
            ):
                sqlstate = candidate
                break

            current = (
                getattr(current, "orig", None)
                or getattr(current, "__cause__", None)
                or getattr(current, "__context__", None)
            )

        allowed_stages = {
            "connection",
            "advisory_lock",
            "preflight",
            "session_setup",
            "authorization",
            "migration_chain",
            "alembic_upgrade",
            "final_revision",
        }
        stage = "unavailable"
        for note in getattr(exc, "__notes__", ()):
            if note.startswith("vervfy_migration_stage="):
                candidate = note.removeprefix("vervfy_migration_stage=")
                if candidate in allowed_stages:
                    stage = candidate

        print(
            "FAILED: production migration stopped; "
            f"stage={stage}; "
            f"error_type={type(exc).__name__}; "
            f"sqlstate={sqlstate or 'unavailable'}; "
            "details omitted to protect connection data",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
