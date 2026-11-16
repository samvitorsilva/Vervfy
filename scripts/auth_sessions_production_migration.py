"""Guarded, single-revision production repair for durable login sessions.

Run only after reviewing the SQL migration and taking a database backup.
Never use this to skip the storage-production migration runner.
"""
from __future__ import annotations

import argparse
import os
import sys

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from scripts.storage_production_migration import (
    ROOT,
    MIGRATION_LOCK_ID,
    MigrationBlocked,
    _engine,
    _verify_client_tls,
    load_target,
    validate_authorization,
)

START = "0031_cleanup_retry_limits"
TARGET = "0032_auth_sessions"
AUTHORIZATION = f"{START}..{TARGET}"


def verify_chain() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision(TARGET)
    if revision is None or revision.down_revision != START:
        raise MigrationBlocked("Session migration does not directly follow production revision")
    if script.get_revision(START) is None:
        raise MigrationBlocked("Expected starting revision is absent")


def check(connection, target) -> None:
    _verify_client_tls(connection)
    with connection.begin():
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        connection.exec_driver_sql("SET LOCAL search_path TO public")
        identity = connection.execute(text(
            "SELECT current_database(), session_user, current_user, current_schema()"
        )).one()
        if tuple(identity) != (target.database, target.username, target.username, "public"):
            raise MigrationBlocked("Production database or migration identity mismatch")
        attributes = connection.execute(text("""
            SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                   rolcreaterole, rolreplication
            FROM pg_catalog.pg_roles WHERE rolname = current_user
        """)).one_or_none()
        if attributes is None or attributes[0] is not True or any(attributes[1:]):
            raise MigrationBlocked("Migration login is not a restricted login role")
        revisions = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalars().all()
        if revisions != [START]:
            raise MigrationBlocked("Database is not at the approved starting revision")
        if connection.execute(text(
            "SELECT to_regclass('public.auth_sessions') IS NOT NULL"
        )).scalar_one():
            raise MigrationBlocked("Session table already exists")
        if connection.execute(text(
            "SELECT to_regclass('public.users') IS NOT NULL"
        )).scalar_one() is not True:
            raise MigrationBlocked("Users table is missing")
        if connection.execute(text(
            "SELECT to_regrole('app_runtime') IS NOT NULL"
        )).scalar_one() is not True:
            raise MigrationBlocked("Application runtime role is missing")
        permissions = connection.execute(text("""
            SELECT has_schema_privilege(current_user, 'public', 'CREATE'),
                   has_schema_privilege(current_user, 'public', 'USAGE'),
                   has_table_privilege(current_user, 'public.users', 'REFERENCES'),
                   has_table_privilege(current_user, 'public.alembic_version', 'UPDATE')
        """)).one()
        if not all(permissions):
            raise MigrationBlocked("Migration role lacks required DDL or version permissions")


def verify_after(connection) -> None:
    with connection.begin():
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalars().all()
        if revision != [TARGET]:
            raise MigrationBlocked("Post-migration revision does not match")
        if not connection.execute(text(
            "SELECT to_regclass('public.auth_sessions') IS NOT NULL"
        )).scalar_one():
            raise MigrationBlocked("Session table was not created")
        privileges = connection.execute(text("""
            SELECT has_table_privilege('app_runtime', 'public.auth_sessions', 'SELECT'),
                   has_table_privilege('app_runtime', 'public.auth_sessions', 'INSERT'),
                   has_table_privilege('app_runtime', 'public.auth_sessions', 'DELETE'),
                   has_table_privilege('app_runtime', 'public.auth_sessions', 'UPDATE')
        """)).one()
        if tuple(privileges) != (True, True, True, False):
            raise MigrationBlocked("Unexpected session table privileges")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("check", "upgrade"))
    parser.add_argument("--confirm-project-ref", required=True)
    parser.add_argument("--authorize-production-migration")
    parser.add_argument("--authorization-expires-at")
    args = parser.parse_args(argv)
    try:
        verify_chain()
        target = load_target()
        if args.confirm_project_ref != target.project_ref:
            raise MigrationBlocked("Project confirmation mismatch")
        if args.operation == "upgrade":
            if args.authorize_production_migration != AUTHORIZATION:
                raise MigrationBlocked("Only the 0031..0032 session migration is authorized")
            if not args.authorization_expires_at:
                raise MigrationBlocked("Short-lived authorization expiry required")
            validate_authorization(args.authorization_expires_at)
        engine = _engine(target)
        try:
            with engine.connect() as connection:
                if args.operation == "upgrade":
                    connection.execute(
                        text("SELECT pg_catalog.pg_advisory_lock(:id)"),
                        {"id": MIGRATION_LOCK_ID},
                    )
                    connection.commit()
                check(connection, target)
                if args.operation == "check":
                    print("Read-only session migration preflight passed")
                    return 0
                validate_authorization(args.authorization_expires_at)
                connection.exec_driver_sql("SET search_path TO public")
                connection.commit()
                config = Config(str(ROOT / "alembic.ini"))
                config.attributes["vervfy_production_migration_runner"] = True
                config.attributes["connection"] = connection
                # env.py requires a production runner; no generic Alembic invocation.
                command.upgrade(config, TARGET)
                verify_after(connection)
                print("Production session migration completed and verified")
                return 0
        finally:
            engine.dispose()
    except Exception as exc:
        # Never print exception text: it may include credentials or SQL.
        print(f"BLOCKED/FAILED: {type(exc).__name__}; no credentials displayed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
