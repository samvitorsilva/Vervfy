"""Read-only, sanitized PostgreSQL metadata preflight for isolated staging."""

import json
from pathlib import Path
import re

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parent
QUERY_FILE = ROOT / "docs/staging-db-metadata-preflight.sql"
TARGET_DATABASE = "vervfy_oauth_staging"
RELEASE_TARGET = "0027_storage_lifecycle"
BOOTSTRAP_ROLE = "vervfy_staging_bootstrap"
MIGRATION_ROLE = "vervfy_oauth_staging_user"
PUBLIC_SCHEMA_OWNERS = {BOOTSTRAP_ROLE, "pg_database_owner"}

ROLE_ATTRIBUTES = {
    MIGRATION_ROLE: True,
    "app_runtime": True,
    "google_auth_lookup": True,
    "vervfy_identity_lookup_owner": False,
    "vervfy_identity_lookup": False,
    "vervfy_storage_lifecycle_owner": False,
    "vervfy_storage_cleanup": False,
    "storage_cleanup_worker": True,
}

ROLE_PRIVILEGES = (
    "superuser",
    "bypass_rls",
    "create_db",
    "create_role",
    "replication",
)

EXPECTED_MEMBERSHIPS = {
    ("vervfy_identity_lookup_owner", MIGRATION_ROLE, False, True, False),
    ("vervfy_identity_lookup", "google_auth_lookup", True, False, False),
    ("vervfy_storage_lifecycle_owner", MIGRATION_ROLE, False, True, False),
    ("vervfy_storage_cleanup", "storage_cleanup_worker", True, False, False),
}

TENANT_RELATIONS = {
    ("public", "tracks"),
    ("public", "favorites"),
    ("public", "playlists"),
    ("public", "playlist_tracks"),
    ("public", "upload_jobs"),
    ("public", "artist_photos"),
    ("public", "track_listens"),
    ("public", "provider_identities"),
    ("vervfy_storage", "namespaces"),
    ("vervfy_storage", "objects"),
    ("vervfy_storage", "cleanup_jobs"),
}

EXPECTED_POLICIES = {
    ("public", "tracks", "tracks_tenant_isolation", "ALL", ("PUBLIC",)),
    ("public", "favorites", "favorites_tenant_isolation", "ALL", ("PUBLIC",)),
    ("public", "playlists", "playlists_tenant_isolation", "ALL", ("PUBLIC",)),
    (
        "public",
        "playlist_tracks",
        "playlist_tracks_tenant_isolation",
        "ALL",
        ("PUBLIC",),
    ),
    ("public", "upload_jobs", "upload_jobs_tenant_isolation", "ALL", ("PUBLIC",)),
    ("public", "artist_photos", "artist_photos_tenant_isolation", "ALL", ("PUBLIC",)),
    ("public", "track_listens", "track_listens_tenant_isolation", "ALL", ("PUBLIC",)),
    (
        "public",
        "provider_identities",
        "provider_identities_tenant_isolation",
        "ALL",
        ("PUBLIC",),
    ),
    (
        "public",
        "provider_identities",
        "provider_identity_lookup",
        "SELECT",
        ("vervfy_identity_lookup_owner",),
    ),
    (
        "vervfy_storage",
        "namespaces",
        "storage_owner",
        "ALL",
        ("vervfy_storage_lifecycle_owner",),
    ),
    (
        "vervfy_storage",
        "objects",
        "storage_owner",
        "ALL",
        ("vervfy_storage_lifecycle_owner",),
    ),
    (
        "vervfy_storage",
        "objects",
        "storage_tenant_read",
        "SELECT",
        ("app_runtime",),
    ),
    (
        "vervfy_storage",
        "cleanup_jobs",
        "storage_owner",
        "ALL",
        ("vervfy_storage_lifecycle_owner",),
    ),
}

FUNCTION_OWNERS = {
    ("vervfy_auth", "lookup_provider_identity"): "vervfy_identity_lookup_owner",
    **{
        ("vervfy_storage", name): "vervfy_storage_lifecycle_owner"
        for name in (
            "guard_namespace",
            "validate_namespace",
            "_has_references",
            "_queue",
            "reserve_object",
            "advance_upload",
            "request_cleanup",
            "guard_references",
            "retire_candidate",
            "claim_cleanup",
        )
    },
}

FUNCTION_EXECUTORS = {
    ("vervfy_auth", "lookup_provider_identity"): {
        "vervfy_identity_lookup_owner",
        "vervfy_identity_lookup",
        "google_auth_lookup",
    },
    ("vervfy_storage", "guard_namespace"): {"vervfy_storage_lifecycle_owner"},
    ("vervfy_storage", "validate_namespace"): {
        "vervfy_storage_lifecycle_owner",
        "app_runtime",
        "vervfy_storage_cleanup",
        "storage_cleanup_worker",
    },
    ("vervfy_storage", "_has_references"): {"vervfy_storage_lifecycle_owner"},
    ("vervfy_storage", "_queue"): {"vervfy_storage_lifecycle_owner"},
    ("vervfy_storage", "reserve_object"): {
        "vervfy_storage_lifecycle_owner",
        "app_runtime",
    },
    ("vervfy_storage", "advance_upload"): {
        "vervfy_storage_lifecycle_owner",
        "app_runtime",
    },
    ("vervfy_storage", "request_cleanup"): {
        "vervfy_storage_lifecycle_owner",
        "app_runtime",
    },
    ("vervfy_storage", "guard_references"): {"vervfy_storage_lifecycle_owner"},
    ("vervfy_storage", "retire_candidate"): {
        "vervfy_storage_lifecycle_owner",
        "vervfy_storage_cleanup",
        "storage_cleanup_worker",
    },
    ("vervfy_storage", "claim_cleanup"): {
        "vervfy_storage_lifecycle_owner",
        "vervfy_storage_cleanup",
        "storage_cleanup_worker",
    },
}

FUNCTION_GRANTEES = {
    ("vervfy_auth", "lookup_provider_identity"): {"vervfy_identity_lookup"},
    ("vervfy_storage", "guard_namespace"): set(),
    ("vervfy_storage", "validate_namespace"): {
        "app_runtime",
        "vervfy_storage_cleanup",
    },
    ("vervfy_storage", "_has_references"): set(),
    ("vervfy_storage", "_queue"): set(),
    ("vervfy_storage", "reserve_object"): {"app_runtime"},
    ("vervfy_storage", "advance_upload"): {"app_runtime"},
    ("vervfy_storage", "request_cleanup"): {"app_runtime"},
    ("vervfy_storage", "guard_references"): set(),
    ("vervfy_storage", "retire_candidate"): {"vervfy_storage_cleanup"},
    ("vervfy_storage", "claim_cleanup"): {"vervfy_storage_cleanup"},
}


class MetadataPreflightError(RuntimeError):
    """A sanitized preflight failure; never includes driver diagnostics."""


def collect_metadata(connection: Connection) -> dict:
    """Read the fixed metadata query and revision value in one read-only txn."""
    if connection.in_transaction():
        raise MetadataPreflightError(
            "Metadata preflight requires a fresh database connection"
        )

    try:
        connection.exec_driver_sql("BEGIN TRANSACTION READ ONLY")
        query = QUERY_FILE.read_text(encoding="utf-8")
        statement = re.sub(r"--[^\n]*", "", query).strip()
        if not re.fullmatch(r"SELECT\b[\s\S]*;\s*", statement, re.IGNORECASE):
            raise MetadataPreflightError("Metadata preflight query is not read-only")
        result = connection.exec_driver_sql(query).scalar_one()
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise MetadataPreflightError("Metadata preflight returned an invalid report")

        if result.get("alembic_version_exists") is True:
            result["alembic_revisions"] = connection.exec_driver_sql(
                "SELECT version_num FROM public.alembic_version ORDER BY version_num"
            ).scalars().all()
        else:
            result["alembic_revisions"] = []
        connection.rollback()
        return result
    except MetadataPreflightError:
        raise
    except SQLAlchemyError as exc:
        cause = getattr(exc, "orig", None)
        sqlstate = getattr(cause, "sqlstate", None) or getattr(
            getattr(cause, "diag", None), "sqlstate", None
        )
        raise MetadataPreflightError(
            "Metadata preflight could not read required catalog metadata; "
            "query and connection diagnostics were suppressed"
            + (f" (SQLSTATE {sqlstate})" if sqlstate else "")
            + f" ({type(exc).__name__})"
        ) from None
    except (OSError, ValueError, TypeError) as exc:
        raise MetadataPreflightError(
            "Metadata preflight could not read required catalog metadata; "
            "query and connection diagnostics were suppressed"
            f" ({type(exc).__name__})"
        ) from None


def _role_map(metadata):
    return {
        role.get("name"): role
        for role in metadata.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }


def _database_privilege_map(metadata):
    return {
        item.get("name"): item
        for item in metadata.get("database_privileges", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _schema_privilege_map(metadata):
    return {
        (item.get("role"), item.get("schema")): item
        for item in metadata.get("schema_privileges", [])
        if isinstance(item, dict)
    }


def evaluate_metadata(metadata: dict, phase: str) -> dict:
    """Return sanitized PASS/FAIL checks for the selected staging phase."""
    if phase not in {"bootstrap", "migration", "post-migration"}:
        raise MetadataPreflightError("Unknown metadata preflight phase")

    report = {
        "phase": phase,
        "database": metadata.get("database"),
        "session_role": metadata.get("session_role"),
        "effective_role": metadata.get("effective_role"),
        "server_version": metadata.get("server_version"),
        "server_version_num": metadata.get("server_version_num"),
        "tls_enabled": metadata.get("tls_enabled"),
        "database_owner": metadata.get("database_owner"),
        "roles": metadata.get("roles", []),
        "memberships": metadata.get("memberships", []),
        "database_privileges": metadata.get("database_privileges", []),
        "schema_owners": metadata.get("schema_owners", []),
        "schema_privileges": metadata.get("schema_privileges", []),
        "public_database_privileges": metadata.get(
            "public_database_privileges", []
        ),
        "public_schema_privileges": metadata.get("public_schema_privileges", []),
        "relations": metadata.get("relations", []),
        "policies": metadata.get("policies", []),
        "security_definer_functions": metadata.get("security_definer_functions", []),
        "identity_column_privileges": metadata.get("identity_column_privileges", []),
        "extensions": metadata.get("extensions", []),
        "required_extensions": [],
        "alembic_version_exists": metadata.get("alembic_version_exists"),
        "alembic_revisions": metadata.get("alembic_revisions", []),
        "has_non_system_relations": metadata.get("has_non_system_relations"),
        "auth_schema_exists": metadata.get("auth_schema_exists"),
        "storage_schema_exists": metadata.get("storage_schema_exists"),
        "gen_random_uuid_available": metadata.get("gen_random_uuid_available"),
        "checks": [],
    }

    def check(name, passed):
        report["checks"].append({"check": name, "passed": passed is True})

    try:
        postgres_major = int(metadata.get("server_version_num", "")) // 10000
    except (TypeError, ValueError):
        postgres_major = None

    roles = _role_map(metadata)
    db_privileges = _database_privilege_map(metadata)
    schema_privileges = _schema_privilege_map(metadata)
    check("database_identity", metadata.get("database") == TARGET_DATABASE)
    check(
        "postgresql_major_version",
        postgres_major == 18,
    )
    check("tls_required", metadata.get("tls_enabled") is True)
    check(
        "gen_random_uuid_available",
        metadata.get("gen_random_uuid_available") is True,
    )

    expected_user = BOOTSTRAP_ROLE if phase == "bootstrap" else MIGRATION_ROLE
    check(
        "connection_identity",
        metadata.get("session_role") == expected_user
        and metadata.get("effective_role") == expected_user,
    )
    current_role = roles.get(expected_user, {})
    check(
        "current_role_not_elevated",
        current_role.get("superuser") is False
        and current_role.get("bypass_rls") is False,
    )

    if phase == "bootstrap":
        current_db = db_privileges.get(expected_user, {})
        public_schema = schema_privileges.get((expected_user, "public"), {})
        check("bootstrap_role_creation_authority", current_role.get("create_role") is True)
        check(
            "bootstrap_role_restricted_attributes",
            current_role.get("login") is True
            and current_role.get("inherit") is False
            and current_role.get("create_db") is False
            and current_role.get("replication") is False,
        )
        check(
            "bootstrap_role_memberships_absent",
            all(
                item.get("granted_role") != BOOTSTRAP_ROLE
                and item.get("member_role") != BOOTSTRAP_ROLE
                for item in metadata.get("memberships", [])
            ),
        )
        check("bootstrap_database_owner", metadata.get("database_owner") == expected_user)
        check(
            "bootstrap_database_privileges",
            current_db.get("connect") is True and current_db.get("create") is True,
        )
        check(
            "bootstrap_public_schema_privileges",
            public_schema.get("usage") is True and public_schema.get("create") is True,
        )
        check(
            "application_roles_absent",
            all(name not in roles for name in ROLE_ATTRIBUTES),
        )
        check(
            "fresh_database",
            metadata.get("has_non_system_relations") is False
            and metadata.get("alembic_version_exists") is False
            and metadata.get("auth_schema_exists") is False
            and metadata.get("storage_schema_exists") is False,
        )
        schemas = {
            item.get("schema"): item.get("owner")
            for item in metadata.get("schema_owners", [])
            if isinstance(item, dict)
        }
        check(
            "public_schema_owner_known",
            schemas.get("public") in PUBLIC_SCHEMA_OWNERS,
        )
    else:
        check(
            "application_role_attributes",
            all(
                name in roles
                and roles[name].get("login") is login
                and roles[name].get("inherit") is False
                and all(roles[name].get(key) is False for key in ROLE_PRIVILEGES)
                for name, login in ROLE_ATTRIBUTES.items()
            ),
        )
        actual_memberships = {
            (
                item.get("granted_role"),
                item.get("member_role"),
                item.get("inherit"),
                item.get("set"),
                item.get("admin"),
            )
            for item in metadata.get("memberships", [])
            if item.get("granted_role") in ROLE_ATTRIBUTES
            or item.get("member_role") in ROLE_ATTRIBUTES
        }
        check("exact_capability_memberships", actual_memberships == EXPECTED_MEMBERSHIPS)
        expected_db_privileges = {
            MIGRATION_ROLE: (True, True, False),
            "app_runtime": (True, False, False),
            "google_auth_lookup": (True, False, False),
            "storage_cleanup_worker": (False, False, False),
            "vervfy_identity_lookup_owner": (False, False, False),
            "vervfy_identity_lookup": (False, False, False),
            "vervfy_storage_lifecycle_owner": (False, False, False),
            "vervfy_storage_cleanup": (False, False, False),
        }
        check(
            "database_role_privileges",
            all(
                (
                    db_privileges.get(name, {}).get("connect"),
                    db_privileges.get(name, {}).get("create"),
                    db_privileges.get(name, {}).get("temporary"),
                )
                == expected
                for name, expected in expected_db_privileges.items()
            ),
        )
        migration_schema = schema_privileges.get((MIGRATION_ROLE, "public"), {})
        runtime_schema = schema_privileges.get(("app_runtime", "public"), {})
        lookup_schema = schema_privileges.get(("google_auth_lookup", "public"), {})
        check(
            "public_schema_privileges",
            migration_schema.get("usage") is True
            and migration_schema.get("create") is True
            and runtime_schema.get("usage") is True
            and runtime_schema.get("create") is False
            and lookup_schema.get("usage") is False
            and lookup_schema.get("create") is False,
        )

        if phase == "migration":
            check(
                "fresh_database",
                metadata.get("has_non_system_relations") is False
                and metadata.get("alembic_version_exists") is False
                and metadata.get("auth_schema_exists") is False
                and metadata.get("storage_schema_exists") is False,
            )
            schemas = {
                item.get("schema"): item.get("owner")
                for item in metadata.get("schema_owners", [])
                if isinstance(item, dict)
            }
            check(
                "public_schema_owner_known",
                schemas.get("public") in PUBLIC_SCHEMA_OWNERS,
            )
            check(
                "public_acl_restricted",
                metadata.get("public_database_privileges") == []
                and metadata.get("public_schema_privileges") == [],
            )
        else:
            check(
                "pinned_migration_revision",
                metadata.get("alembic_revisions") == [RELEASE_TARGET],
            )
            schema_owners = {
                item.get("schema"): item.get("owner")
                for item in metadata.get("schema_owners", [])
                if isinstance(item, dict)
            }
            check(
                "application_schema_ownership",
                schema_owners.get("vervfy_auth") == MIGRATION_ROLE
                and schema_owners.get("vervfy_storage") == MIGRATION_ROLE
                and schema_owners.get("public") in PUBLIC_SCHEMA_OWNERS,
            )
            relations = {
                (item.get("schema"), item.get("name")): item
                for item in metadata.get("relations", [])
                if isinstance(item, dict)
            }
            check(
                "forced_rls_relations",
                all(
                    (item := relations.get(key)) is not None
                    and item.get("owner") == MIGRATION_ROLE
                    and item.get("row_security") is True
                    and item.get("force_row_security") is True
                    for key in TENANT_RELATIONS
                ),
            )
            actual_policies = {
                (
                    item.get("schema"),
                    item.get("table"),
                    item.get("name"),
                    item.get("command"),
                    tuple(sorted(item.get("roles", []))),
                )
                for item in metadata.get("policies", [])
            }
            policy_rows = {
                (
                    item.get("schema"),
                    item.get("table"),
                    item.get("name"),
                    item.get("command"),
                    tuple(sorted(item.get("roles", []))),
                ): item
                for item in metadata.get("policies", [])
            }
            check(
                "rls_policy_metadata",
                actual_policies == EXPECTED_POLICIES
                and all(
                    item.get("permissive") is True
                    and item.get("using_present") is True
                    and item.get("check_present") is (key[3] != "SELECT")
                    for key, item in policy_rows.items()
                ),
            )
            _check_function_contracts(metadata, check)
            _check_identity_lookup_privileges(metadata, schema_privileges, check)

    report["status"] = (
        "pass" if all(item["passed"] for item in report["checks"]) else "fail"
    )
    return report


def _check_function_contracts(metadata, check):
    functions = {
        (item.get("schema"), item.get("name")): item
        for item in metadata.get("security_definer_functions", [])
        if isinstance(item, dict)
    }
    check("security_definer_function_set", set(functions) == set(FUNCTION_OWNERS))
    check(
        "security_definer_owners_and_search_paths",
        all(
            functions.get(key, {}).get("owner") == owner
            and functions.get(key, {}).get("security_definer") is True
            and functions.get(key, {}).get("search_path") == "pg_catalog, pg_temp"
            for key, owner in FUNCTION_OWNERS.items()
        ),
    )
    check(
        "security_definer_execution_grants",
        all(
            functions.get(key, {}).get("public_execute") is False
            and set(functions.get(key, {}).get("effective_execute_roles", []))
            == FUNCTION_EXECUTORS[key]
            and set(
                functions.get(key, {}).get("explicit_execute_grantees", [])
            )
            == FUNCTION_GRANTEES[key]
            and functions.get(key, {}).get(
                "unexpected_explicit_execute_grantee_count"
            )
            == 0
            for key in FUNCTION_OWNERS
        ),
    )
    check(
        "security_definer_explicit_grantees",
        all(
            set(
                functions.get(key, {}).get("explicit_execute_grantees", [])
            )
            == FUNCTION_GRANTEES[key]
            for key in FUNCTION_OWNERS
        ),
    )


def _check_identity_lookup_privileges(metadata, schema_privileges, check):
    auth_schema = schema_privileges.get(("vervfy_identity_lookup", "vervfy_auth"), {})
    google_auth = schema_privileges.get(("google_auth_lookup", "vervfy_auth"), {})
    owner_public = schema_privileges.get(
        ("vervfy_identity_lookup_owner", "public"), {}
    )
    lookup_public = schema_privileges.get(("google_auth_lookup", "public"), {})
    check(
        "identity_lookup_schema_usage",
        owner_public.get("usage") is True
        and owner_public.get("create") is False
        and auth_schema.get("usage") is True
        and google_auth.get("usage") is True
        and google_auth.get("create") is False
        and lookup_public.get("usage") is False,
    )
    columns = {
        (item.get("role"), item.get("column")): item.get("select")
        for item in metadata.get("identity_column_privileges", [])
    }
    all_columns = {
        item.get("column")
        for item in metadata.get("identity_column_privileges", [])
    }
    owner_select = {
        column
        for column in all_columns
        if columns.get(("vervfy_identity_lookup_owner", column)) is True
    }
    google_select = any(
        columns.get(("google_auth_lookup", column)) is True for column in all_columns
    )
    check(
        "identity_lookup_column_grants",
        owner_select == {"issuer", "subject", "user_id"} and not google_select,
    )


def run_preflight(database_url: str, phase: str) -> dict:
    """Open one bounded, non-logging connection and return safe metadata only."""
    if phase not in {"bootstrap", "migration", "post-migration"}:
        raise MetadataPreflightError("Unknown metadata preflight phase")
    try:
        engine = create_engine(
            database_url,
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=15000",
            },
            echo=False,
            hide_parameters=True,
            poolclass=NullPool,
        )
    except SQLAlchemyError:
        raise MetadataPreflightError(
            "Metadata preflight could not initialize a database connection"
        ) from None

    try:
        with engine.connect() as connection:
            metadata = collect_metadata(connection)
    except MetadataPreflightError:
        raise
    except SQLAlchemyError as exc:
        cause = getattr(exc, "orig", None)
        sqlstate = getattr(cause, "sqlstate", None) or getattr(
            getattr(cause, "diag", None), "sqlstate", None
        )
        raise MetadataPreflightError(
            "Metadata preflight could not connect to the approved database; "
            "connection diagnostics were suppressed"
            + (f" (SQLSTATE {sqlstate})" if sqlstate else "")
        ) from None
    finally:
        engine.dispose()
    return evaluate_metadata(metadata, phase)
