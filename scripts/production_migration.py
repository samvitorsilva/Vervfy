#!/usr/bin/env python3
"""Fail-closed, explicitly authorized production Alembic upgrade runner."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import sys
from typing import Mapping

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, URL, make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
START_REVISION = "0019_track_listens"
TARGET_REVISION = "0028_webauthn_enrollment"
AUTHORIZATION = f"{START_REVISION}..{TARGET_REVISION}"
AUTHORIZATION_TTL = timedelta(minutes=15)
EXPECTED_MIGRATION_COUNT = 28
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

    raw_url = _required(values, "VERVFY_PRODUCTION_DATABASE_URL")
    try:
        url = make_url(raw_url)
    except Exception:
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
    return ProductionTarget(url, project_ref, database, username, connection_mode)


def validate_authorization(expires_at: str, *, now: datetime | None = None) -> None:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", expires_at) is None:
        raise MigrationBlocked("Authorization expiry must be UTC RFC3339 seconds ending in Z")
    try:
        expiry = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise MigrationBlocked("Authorization expiry is not a valid UTC timestamp") from None
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
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
        for newer, older in zip(chain, chain[1:])
    ):
        raise MigrationBlocked("Local Alembic history is not a single linear chain")


def _check_role_graph(connection: Connection, migration_user: str) -> None:
    from supabase_role_memberships import (
        assert_member_memberships,
        assert_role_memberships,
    )

    owner = "vervfy_identity_lookup_owner"
    executor = "vervfy_identity_lookup"
    lookup_login = "google_auth_lookup"
    roles = connection.execute(
        text("""
            SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                   rolcreaterole, rolreplication, rolinherit
            FROM pg_catalog.pg_roles
            WHERE rolname IN (:owner, :executor, :lookup_login)
        """),
        {"owner": owner, "executor": executor, "lookup_login": lookup_login},
    ).all()
    by_name = {row.rolname: row for row in roles}
    for role_name in (owner, executor):
        row = by_name.get(role_name)
        if row is None or any(row[1:]):
            raise MigrationBlocked(f"Restricted NOLOGIN role {role_name} is not ready")
    login = by_name.get(lookup_login)
    if login is None or not login.rolcanlogin or any(login[index] for index in range(2, 8)):
        raise MigrationBlocked(f"Restricted lookup login {lookup_login} is not ready")

    assert_role_memberships(
        connection, owner, [(migration_user, "postgres", False, False, True)]
    )
    assert_member_memberships(connection, owner, [])
    assert_role_memberships(
        connection, executor, [(lookup_login, "postgres", False, True, False)]
    )
    assert_role_memberships(connection, lookup_login, [])
    assert_member_memberships(
        connection, lookup_login, [(executor, "postgres", False, True, False)]
    )
    has_set_membership = connection.execute(
        text("SELECT pg_catalog.pg_has_role(current_user, :owner, 'SET')"),
        {"owner": owner},
    ).scalar_one()
    if not has_set_membership:
        raise MigrationBlocked("Migration login cannot SET ROLE to the lookup owner")

    unexpected_access = connection.execute(
        text("""
            SELECT r.rolname
            FROM pg_catalog.pg_roles r
            WHERE r.oid NOT IN (
                'vervfy_identity_lookup'::regrole,
                'google_auth_lookup'::regrole
            )
              AND NOT r.rolsuper
              AND (
                  pg_catalog.pg_has_role(r.oid, 'vervfy_identity_lookup', 'USAGE')
                  OR pg_catalog.pg_has_role(r.oid, 'vervfy_identity_lookup', 'SET')
              )
            LIMIT 1
        """)
    ).first()
    if unexpected_access:
        raise MigrationBlocked(
            f"Unexpected role can access lookup capability: {unexpected_access.rolname}"
        )


def _verify_client_tls(connection: Connection) -> None:
    """Require negotiated TLS on this SQLAlchemy connection's psycopg socket."""
    # pg_stat_ssl describes the database backend's transport, which may be the
    # pooler-to-database hop. libpq reports the runner's actual transport for
    # both direct and Session Pooler connections. URL sslmode is not evidence.
    try:
        tls = connection.connection.driver_connection.pgconn.ssl_in_use
    except Exception:  # noqa: BLE001 - fail closed without exposing driver details
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
        if revision != [START_REVISION]:
            raise MigrationBlocked(
                f"Expected exactly {START_REVISION}; found a different Alembic revision state"
            )
        unexpected_objects = connection.execute(
            text("""
                SELECT object_name
                FROM (
                    SELECT 'vervfy_auth' AS object_name
                    WHERE pg_catalog.to_regnamespace('vervfy_auth') IS NOT NULL
                    UNION ALL
                    SELECT name
                    FROM unnest(ARRAY[
                        'provider_identities',
                        'webauthn_handles',
                        'webauthn_credentials',
                        'account_action_intents',
                        'account_verification_proofs',
                        'account_recovery_codes',
                        'account_recovery_states',
                        'webauthn_enrollments'
                    ]) AS name
                    WHERE pg_catalog.to_regclass('public.' || name) IS NOT NULL
                ) AS unexpected
            """)
        ).scalars().all()
        if unexpected_objects:
            raise MigrationBlocked(
                "Unexpected objects conflict with the 0019 starting schema: "
                + ", ".join(sorted(unexpected_objects))
            )
        _check_role_graph(connection, current_user)


def _engine(target: ProductionTarget):
    return create_engine(target.url, poolclass=NullPool, pool_pre_ping=True)


def run_check(target: ProductionTarget) -> None:
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            preflight(connection, target)
    finally:
        engine.dispose()


def run_upgrade(target: ProductionTarget, expires_at: str) -> None:
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT pg_catalog.pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            connection.commit()
            preflight(connection, target)
            connection.exec_driver_sql("SET search_path TO public")
            connection.commit()
            validate_authorization(expires_at)

            os.environ["DATABASE_URL"] = target.url.render_as_string(hide_password=False)
            os.environ["MIGRATION_DATABASE_URL"] = target.url.render_as_string(
                hide_password=False
            )
            from alembic import command
            from alembic.config import Config

            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["vervfy_production_migration_runner"] = True
            config.attributes["connection"] = connection
            validate_authorization(expires_at)
            validate_migration_chain()
            command.upgrade(config, TARGET_REVISION)

            with connection.begin():
                final_revision = connection.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalars().all()
                if final_revision != [TARGET_REVISION]:
                    raise MigrationBlocked(
                        "Alembic completed without recording the exact target revision"
                    )
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
                choices=(AUTHORIZATION,),
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
            validate_authorization(args.authorization_expires_at)
            run_upgrade(target, args.authorization_expires_at)
            print(f"Production migration completed at {TARGET_REVISION}")
        else:
            run_check(target)
            print(
                f"Read-only production preflight passed at {START_REVISION}; "
                "no migration was executed"
            )
        return 0
    except MigrationBlocked as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
    except Exception as exc:
        print(
            "FAILED: production migration stopped; "
            f"{type(exc).__name__}; details omitted to protect connection data",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
