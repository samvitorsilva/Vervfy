"""Narrow ACL repair for Vervfy's internal public-schema tables."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, text

from storage_inventory import InventoryBlocked, plan_digest

MAX_AGE = timedelta(minutes=15)
SUPPORTED_REVISIONS = {
    "0032_auth_sessions",
    "0033_cleanup_claims_disabled",
}
ACL_CHECK_REVISIONS = SUPPORTED_REVISIONS | {"0034_storage_byte_reservations"}
TARGETS = {
    "alembic_version": (),
    "artist_images": ("SELECT", "INSERT", "UPDATE"),
    "auth_sessions": ("SELECT", "INSERT", "DELETE"),
    "track_cover_cache": ("SELECT", "INSERT", "UPDATE"),
}
EXPOSED_ROLES = ("anon", "authenticated", "service_role")
PRESERVED_GRANT_ROLES = {
    "artist_images": ("postgres",),
    "track_cover_cache": ("postgres",),
}
APP_BASELINE = {
    "alembic_version": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "artist_images": ("SELECT", "INSERT", "UPDATE"),
    "auth_sessions": ("SELECT", "INSERT", "DELETE"),
    "track_cover_cache": ("SELECT", "INSERT", "UPDATE"),
}


def _full_table_privileges(connection: Connection) -> tuple[str, ...]:
    version = connection.exec_driver_sql("SHOW server_version_num").scalar_one()
    privileges = [
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "TRUNCATE",
        "REFERENCES",
        "TRIGGER",
    ]
    if int(version) >= 170000:
        privileges.append("MAINTAIN")
    return tuple(privileges)


def _canonical_acl(privileges: tuple[str, ...]) -> list[list[object]]:
    return sorted(
        [
            [role, privilege, False]
            for role, grants in (("app_runtime", privileges),)
            for privilege in grants
        ]
    )


def snapshot_acl(
    connection: Connection,
    *,
    allow_reviewed_overgrants: bool = True,
) -> dict:
    if connection.dialect.name != "postgresql" or not connection.in_transaction():
        raise InventoryBlocked("An explicit PostgreSQL transaction is required")
    identity = connection.exec_driver_sql("""SELECT current_user=session_user,
        rolsuper OR rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=current_user""").one()
    if tuple(identity) != (True, False):
        raise InventoryBlocked("A restricted table-owner login is required")
    revision = (
        connection.execute(text("SELECT version_num FROM public.alembic_version"))
        .scalars()
        .all()
    )
    if len(revision) != 1 or revision[0] not in ACL_CHECK_REVISIONS:
        raise InventoryBlocked(
            "Internal ACL check requires revision 0032, 0033, or 0034"
        )

    tables = (
        connection.execute(
            text("""
        SELECT c.relname, pg_catalog.pg_get_userbyid(c.relowner) AS table_owner,
               c.relrowsecurity, c.relforcerowsecurity
        FROM pg_catalog.pg_class c
        WHERE c.oid IN (
            'public.alembic_version'::regclass,
            'public.artist_images'::regclass,
            'public.auth_sessions'::regclass,
            'public.track_cover_cache'::regclass
        )
        ORDER BY c.relname
    """)
        )
        .mappings()
        .all()
    )
    current_user = connection.exec_driver_sql("SELECT current_user").scalar_one()
    if len(tables) != len(TARGETS) or any(
        row["table_owner"] != current_user
        or row["relrowsecurity"]
        or row["relforcerowsecurity"]
        for row in tables
    ):
        raise InventoryBlocked(
            "Internal tables must be migration-owned with their reviewed RLS state"
        )

    acl_rows = connection.execute(
        text("""
        SELECT c.relname, COALESCE(r.rolname, 'PUBLIC') AS grantee,
               a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_class c
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(c.relacl, pg_catalog.acldefault('r'::"char", c.relowner))
        ) a
        LEFT JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE c.oid IN (
            'public.alembic_version'::regclass,
            'public.artist_images'::regclass,
            'public.auth_sessions'::regclass,
            'public.track_cover_cache'::regclass
        )
          AND a.grantee <> c.relowner
        ORDER BY c.relname, grantee, a.privilege_type
    """)
    ).all()
    column_acl = connection.execute(
        text("""
        SELECT c.relname, a.attname
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
        WHERE c.oid IN (
            'public.alembic_version'::regclass,
            'public.artist_images'::regclass,
            'public.auth_sessions'::regclass,
            'public.track_cover_cache'::regclass
        )
          AND a.attnum > 0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
        ORDER BY c.relname, a.attname
    """)
    ).all()
    if column_acl:
        raise InventoryBlocked("Unexpected column-level internal table grants")

    direct_acl = {name: [] for name in TARGETS}
    for row in acl_rows:
        direct_acl[row[0]].append([row[1], row[2], bool(row[3])])
    snapshot = {
        "database": connection.exec_driver_sql(
            "SELECT current_database()"
        ).scalar_one(),
        "revision": revision[0],
        "owner": current_user,
        "tables": {
            row["relname"]: {
                "owner": row["table_owner"],
                "rls": bool(row["relrowsecurity"]),
                "force_rls": bool(row["relforcerowsecurity"]),
                "acl": direct_acl[row["relname"]],
            }
            for row in tables
        },
    }
    _validate_known_acl(
        snapshot,
        _full_table_privileges(connection),
        allow_reviewed_overgrants=allow_reviewed_overgrants,
    )
    return snapshot


def _validate_known_acl(
    snapshot: dict,
    full_privileges: tuple[str, ...],
    *,
    allow_reviewed_overgrants: bool,
) -> None:
    clean = {}
    observed = {}
    for table, app_privileges in TARGETS.items():
        if table == "alembic_version":
            app_privileges = APP_BASELINE[table]
        app_acl = [["app_runtime", privilege, False] for privilege in app_privileges]
        preserved_acl = [
            [role, privilege, False]
            for role in PRESERVED_GRANT_ROLES.get(table, ())
            for privilege in full_privileges
        ]
        clean[table] = sorted(_canonical_acl(TARGETS[table]) + preserved_acl)
        observed[table] = sorted(
            app_acl
            + [
                [role, privilege, False]
                for role in EXPOSED_ROLES
                for privilege in full_privileges
            ]
            + [
                [role, privilege, False]
                for role in PRESERVED_GRANT_ROLES.get(table, ())
                for privilege in full_privileges
            ]
        )

    current = {
        table: sorted(details["acl"]) for table, details in snapshot["tables"].items()
    }
    expected_clean = {table: clean[table] for table in TARGETS}
    allowed = (
        (observed, expected_clean) if allow_reviewed_overgrants else (expected_clean,)
    )
    if current not in allowed:
        raise InventoryBlocked(
            "Internal table ACL drift is outside the reviewed repair"
        )


def check_internal_acls(
    connection: Connection,
    *,
    allow_reviewed_overgrants: bool = False,
) -> None:
    snapshot_acl(
        connection,
        allow_reviewed_overgrants=allow_reviewed_overgrants,
    )
    if not allow_reviewed_overgrants:
        _verify_effective_acl(connection, _full_table_privileges(connection))


def plan_acl_repair(connection: Connection, *, now: datetime | None = None) -> dict:
    before = snapshot_acl(connection)
    if before["revision"] not in SUPPORTED_REVISIONS:
        raise InventoryBlocked("ACL repair requires revision 0032 or 0033")
    full_privileges = _full_table_privileges(connection)
    after = _clean_snapshot(before, full_privileges)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    return {
        "version": 1,
        "planned_at": timestamp,
        "full_table_privileges": list(full_privileges),
        "before": before,
        "after": after,
    }


def _clean_snapshot(before: dict, full_privileges: tuple[str, ...]) -> dict:
    return {
        "database": before["database"],
        "revision": before["revision"],
        "owner": before["owner"],
        "tables": {
            table: {
                **{key: value for key, value in details.items() if key != "acl"},
                "acl": sorted(
                    _canonical_acl(TARGETS[table])
                    + [
                        [role, privilege, False]
                        for role in PRESERVED_GRANT_ROLES.get(table, ())
                        for privilege in full_privileges
                    ]
                ),
            }
            for table, details in before["tables"].items()
        },
    }


def _verify_effective_acl(
    connection: Connection, full_privileges: tuple[str, ...]
) -> None:
    # PostgreSQL superusers report every table privilege from
    # has_table_privilege regardless of direct ACL. The direct snapshot
    # verifies postgres's preserved cache grants separately.
    roles = (*EXPOSED_ROLES, "app_runtime")
    role_values = ", ".join(f"(:role_{index})" for index in range(len(roles)))
    table_values = ", ".join(f"(:table_{index})" for index in range(len(TARGETS)))
    privilege_values = ", ".join(
        f"(:privilege_{index})" for index in range(len(full_privileges))
    )
    params = {
        **{f"role_{index}": role for index, role in enumerate(roles)},
        **{f"table_{index}": table for index, table in enumerate(TARGETS)},
        **{
            f"privilege_{index}": privilege
            for index, privilege in enumerate(full_privileges)
        },
    }
    rows = connection.execute(
        text(f"""
        WITH roles(role_name) AS (VALUES {role_values}),
             tables(table_name) AS (VALUES {table_values}),
             privileges(privilege_name) AS (VALUES {privilege_values})
        SELECT roles.role_name, tables.table_name, privileges.privilege_name,
               has_table_privilege(
                   roles.role_name, 'public.' || tables.table_name,
                   privileges.privilege_name
               ) AS granted
        FROM roles CROSS JOIN tables CROSS JOIN privileges
    """),
        params,
    ).all()
    expected = {
        (role, table, privilege): (
            (role == "app_runtime" and privilege in TARGETS[table])
            or (
                role in PRESERVED_GRANT_ROLES.get(table, ())
                and privilege in full_privileges
            )
        )
        for role in roles
        for table in TARGETS
        for privilege in full_privileges
    }
    if {(row[0], row[1], row[2]): bool(row[3]) for row in rows} != expected:
        raise InventoryBlocked("Internal ACL effective-privilege postcondition failed")


def apply_acl_repair(
    connection: Connection,
    plan: dict,
    approved_digest: str,
    *,
    now: datetime | None = None,
) -> int:
    if plan_digest(plan) != approved_digest:
        raise InventoryBlocked("Plan digest does not match independent approval")
    if (
        set(plan)
        != {
            "version",
            "planned_at",
            "full_table_privileges",
            "before",
            "after",
        }
        or type(plan["version"]) is not int
        or plan["version"] != 1
    ):
        raise InventoryBlocked("Unknown ACL repair plan format")
    planned_at = datetime.fromisoformat(plan["planned_at"])
    current_time = now or datetime.now(UTC)
    if (
        planned_at.tzinfo is None
        or not timedelta(0) <= current_time - planned_at <= MAX_AGE
    ):
        raise InventoryBlocked("ACL repair plan is expired or future dated")
    if not connection.in_transaction():
        raise InventoryBlocked("ACL repair requires an explicit transaction")
    if plan["full_table_privileges"] != list(_full_table_privileges(connection)):
        raise InventoryBlocked("Database privilege model differs from the plan")
    try:
        _validate_known_acl(
            plan["before"],
            _full_table_privileges(connection),
            allow_reviewed_overgrants=True,
        )
    except (KeyError, TypeError):
        raise InventoryBlocked("ACL repair plan snapshot is malformed") from None
    if plan["after"] != _clean_snapshot(
        plan["before"], tuple(plan["full_table_privileges"])
    ):
        raise InventoryBlocked("ACL repair plan postcondition is malformed")

    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
        connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
        connection.exec_driver_sql("""
            LOCK TABLE public.alembic_version, public.artist_images,
                       public.auth_sessions, public.track_cover_cache
            IN ACCESS EXCLUSIVE MODE
        """)
        actual = snapshot_acl(connection)
        if actual == plan["after"]:
            _verify_effective_acl(connection, tuple(plan["full_table_privileges"]))
            return 0
        if actual != plan["before"]:
            raise InventoryBlocked("Internal table ACL changed; create a fresh plan")

        for table, app_privileges in TARGETS.items():
            connection.exec_driver_sql(
                f"REVOKE ALL ON TABLE public.{table} "
                "FROM PUBLIC, anon, authenticated, service_role, app_runtime"
            )
            if app_privileges:
                grants = ", ".join(app_privileges)
                connection.exec_driver_sql(
                    f"GRANT {grants} ON TABLE public.{table} TO app_runtime"
                )

        repaired = snapshot_acl(connection)
        if repaired != plan["after"]:
            raise InventoryBlocked("Internal ACL postcondition failed")
        _verify_effective_acl(connection, tuple(plan["full_table_privileges"]))
        return sum(
            plan["before"]["tables"][table]["acl"]
            != plan["after"]["tables"][table]["acl"]
            for table in TARGETS
        )
