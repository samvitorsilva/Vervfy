"""Provision and seed an explicitly approved disposable 0031/0033 rehearsal database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import bcrypt
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from alembic import command

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import prepare_storage_rehearsal_baseline as preparation
from scripts import storage_rehearsal as rehearsal
from scripts import upload_storage_rehearsal_fixtures as fixture_uploader
from storage_namespace import initialize_namespace
from supabase_role_memberships import (
    assert_member_memberships,
    assert_role_memberships,
)

BASELINE_0028 = "0028_webauthn_enrollment"
BASELINE_0031 = "0031_cleanup_retry_limits"
BASELINE_0033 = "0033_cleanup_claims_disabled"
OWNER = "vervfy_storage_lifecycle_owner"
EXECUTOR = "vervfy_storage_cleanup"
WORKER = "storage_cleanup_worker"
IDENTITY_OWNER = "vervfy_identity_lookup_owner"
IDENTITY_EXECUTOR = "vervfy_identity_lookup"
RUNTIME_APPROVAL = "vervfy_rehearsal.approval"
PROVISIONING_APPROVAL = "vervfy_rehearsal.provisioning_approval"
FORBIDDEN_ENV = (
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_BUCKET",
    "VERVFY_STAGING_PROFILE",
)

ROLES = {
    rehearsal.LOGIN: (True, False),
    "app_runtime": (True, True),
    "google_auth_lookup": (True, False),
    IDENTITY_OWNER: (False, False),
    IDENTITY_EXECUTOR: (False, False),
    OWNER: (False, False),
    EXECUTOR: (False, False),
    WORKER: (True, False),
}


def _validate_environment(env):
    if (
        env.get("VERVFY_ENVIRONMENT") != "disposable-storage-rehearsal"
        or any(env.get(name) for name in FORBIDDEN_ENV)
        or any(name.startswith("PG") and value for name, value in env.items())
        or any(
            name.startswith("VERVFY_PRODUCTION_") and value
            for name, value in env.items()
        )
    ):
        raise rehearsal.RehearsalBlocked(
            "Ambient application, provider, PostgreSQL or production settings are forbidden"
        )


def load_profile(config_path, approved_digest, ca_file, confirm_project, *, live):
    env = os.environ
    _validate_environment(env)
    if live:
        profile = rehearsal.load_profile(
            config_path,
            approved_digest,
            {
                "VERVFY_ENVIRONMENT": env["VERVFY_ENVIRONMENT"],
                "VERVFY_REHEARSAL_CA_FILE": str(Path(ca_file).resolve(strict=True)),
                "VERVFY_REHEARSAL_DATABASE_URL": env.get(
                    "VERVFY_REHEARSAL_DATABASE_URL", ""
                ),
                "VERVFY_REHEARSAL_RUNTIME_URL": env.get(
                    "VERVFY_REHEARSAL_RUNTIME_URL", ""
                ),
            },
        )
    else:
        profile = preparation.load_offline_profile(
            config_path, approved_digest, ca_file, confirm_project
        )
    fixture_uploader._assert_disposable_profile(profile)
    if profile.config["project_ref"] != confirm_project:
        raise rehearsal.RehearsalBlocked("Disposable project confirmation mismatch")
    return profile


def dba_url(profile):
    raw = os.environ.get("VERVFY_REHEARSAL_DBA_DATABASE_URL", "").strip()
    try:
        url = make_url(raw)
    except Exception:  # noqa: BLE001 - suppress credential-bearing URL details
        raise rehearsal.RehearsalBlocked(
            "Explicit disposable DBA URL required"
        ) from None
    ca = Path(profile.migration_url.query["sslrootcert"]).resolve(strict=True)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != f"db.{profile.config['project_ref']}.supabase.co"
        or url.port != 5432
        or url.database != "postgres"
        or url.username != "postgres"
        or not url.password
        or dict(url.query) != {"sslmode": "verify-full", "sslrootcert": str(ca)}
        or hashlib.sha256(ca.read_bytes()).hexdigest() != profile.config["ca_sha256"]
    ):
        raise rehearsal.RehearsalBlocked(
            "DBA URL must be direct, project-bound and pinned to the approved CA"
        )
    return url


def _engine_for(url):
    return sa.create_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10, "prepare_threshold": None},
    )


def _transaction_limits(connection):
    connection.exec_driver_sql("SET LOCAL search_path TO public")
    connection.exec_driver_sql("SET LOCAL timezone TO 'UTC'")
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='10000ms'")


def _target_identity(connection, *, expected_user):
    rehearsal.production._verify_client_tls(connection)
    identity = connection.exec_driver_sql(
        "SELECT current_database(),session_user,current_user"
    ).one()
    if tuple(identity) != ("postgres", expected_user, expected_user):
        raise rehearsal.RehearsalBlocked("Database execution identity mismatch")
    version = int(connection.exec_driver_sql("SHOW server_version_num").scalar_one())
    if version < 160000:
        raise rehearsal.RehearsalBlocked("PostgreSQL 16 or newer is required")


def _validate_dba(connection):
    _target_identity(connection, expected_user="postgres")
    capabilities = connection.exec_driver_sql(
        """SELECT rolcanlogin,rolcreaterole,rolbypassrls,rolsuper
        FROM pg_catalog.pg_roles WHERE rolname=current_user"""
    ).one()
    if (
        not capabilities.rolcanlogin
        or not (capabilities.rolsuper or capabilities.rolcreaterole)
        or not (capabilities.rolsuper or capabilities.rolbypassrls)
    ):
        raise rehearsal.RehearsalBlocked(
            "Existing DBA role lacks required bootstrap capabilities"
        )


def _check_fresh_application_schema(connection, profile, *, allow_marker):
    _validate_dba(connection)
    existing = connection.exec_driver_sql(
        """SELECT n.nspname,c.relname,c.relkind
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S')"""
    ).all()
    if existing:
        raise rehearsal.RehearsalBlocked(
            "Fresh disposable public schema required; preserve existing objects"
        )
    if any(
        connection.execute(
            text("SELECT to_regnamespace(:name) IS NOT NULL"), {"name": name}
        ).scalar_one()
        for name in ("vervfy_storage", "vervfy_auth")
    ):
        raise rehearsal.RehearsalBlocked(
            "Existing storage/auth schema found; preserve all objects"
        )
    if connection.exec_driver_sql(
        "SELECT to_regclass('public.alembic_version') IS NOT NULL"
    ).scalar_one():
        raise rehearsal.RehearsalBlocked(
            "Existing migration history found; never stamp or replace it"
        )
    public_owner = connection.exec_driver_sql(
        "SELECT nspowner::regrole::text FROM pg_catalog.pg_namespace WHERE nspname='public'"
    ).scalar_one_or_none()
    if public_owner not in {"postgres", "pg_database_owner", rehearsal.LOGIN}:
        raise rehearsal.RehearsalBlocked("Unexpected public schema owner")
    public_create = connection.exec_driver_sql(
        """SELECT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_namespace AS n
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(n.nspacl,pg_catalog.acldefault('n'::"char",n.nspowner))
            ) AS acl
            WHERE n.nspname='public' AND acl.grantee=0
              AND acl.privilege_type='CREATE'
        )"""
    ).scalar_one()
    if public_create:
        raise rehearsal.RehearsalBlocked(
            "PUBLIC can create in the application schema; review privileges without weakening guards"
        )
    schema_exists = connection.exec_driver_sql(
        "SELECT to_regnamespace('vervfy_rehearsal') IS NOT NULL"
    ).scalar_one()
    if schema_exists and not allow_marker:
        raise rehearsal.RehearsalBlocked(
            "Existing rehearsal schema found; preserve existing objects"
        )
    if schema_exists:
        objects = (
            connection.exec_driver_sql(
                """SELECT c.relname FROM pg_catalog.pg_class AS c
            JOIN pg_catalog.pg_namespace AS n ON n.oid=c.relnamespace
            WHERE n.nspname='vervfy_rehearsal'
              AND c.relkind IN ('r','p','v','m','f','S')"""
            )
            .scalars()
            .all()
        )
        if set(objects) - {"provisioning_approval"}:
            raise rehearsal.RehearsalBlocked(
                "Unexpected rehearsal objects found; preserve all objects"
            )


def _quote(connection, identifier):
    return connection.dialect.identifier_preparer.quote(identifier)


def _ensure_roles(connection):
    for role, (login, inherit) in ROLES.items():
        existing = connection.execute(
            text(
                """SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,
                rolcreaterole,rolreplication FROM pg_catalog.pg_roles WHERE rolname=:role"""
            ),
            {"role": role},
        ).first()
        expected = (
            login,
            inherit,
            False,
            False,
            False,
            False,
            False,
        )
        if existing is None:
            login_option = "LOGIN" if login else "NOLOGIN"
            inherit_option = "INHERIT" if inherit else "NOINHERIT"
            connection.exec_driver_sql(
                f"CREATE ROLE {_quote(connection, role)} {login_option} "
                f"{inherit_option} NOSUPERUSER NOBYPASSRLS NOCREATEDB "
                "NOCREATEROLE NOREPLICATION"
            )
        elif tuple(existing) != expected:
            raise rehearsal.RehearsalBlocked(
                f"Existing role {role} has unreviewed attributes; do not alter it"
            )


def _ensure_membership(connection, role, member, inherit, can_set):
    role_sql = _quote(connection, role)
    member_sql = _quote(connection, member)
    row = connection.execute(
        text("""SELECT m.admin_option,m.inherit_option,m.set_option,
            grantor.rolname AS grantor
            FROM pg_catalog.pg_auth_members AS m
            JOIN pg_catalog.pg_roles AS granted ON granted.oid=m.roleid
            JOIN pg_catalog.pg_roles AS granted_to ON granted_to.oid=m.member
            JOIN pg_catalog.pg_roles AS grantor ON grantor.oid=m.grantor
            WHERE granted.rolname=:role AND granted_to.rolname=:member"""),
        {"role": role, "member": member},
    ).first()
    expected = (False, inherit, can_set, "postgres")
    if row is None:
        connection.exec_driver_sql(
            f"GRANT {role_sql} TO {member_sql} WITH ADMIN FALSE, "
            f"INHERIT {'TRUE' if inherit else 'FALSE'}, "
            f"SET {'TRUE' if can_set else 'FALSE'}"
        )
    elif tuple(row) != expected:
        raise rehearsal.RehearsalBlocked(
            f"Existing membership {member} -> {role} has unreviewed options"
        )


def _verify_role_graph(connection):
    for role, members in (
        (
            IDENTITY_OWNER,
            [(rehearsal.LOGIN, "postgres", False, False, True)],
        ),
        (
            IDENTITY_EXECUTOR,
            [("google_auth_lookup", "postgres", False, True, False)],
        ),
        (OWNER, [(rehearsal.LOGIN, "postgres", False, False, True)]),
        (EXECUTOR, [(WORKER, "postgres", False, True, False)]),
    ):
        assert_role_memberships(connection, role, members)
    for member, grants in (
        (
            rehearsal.LOGIN,
            [
                (IDENTITY_OWNER, "postgres", False, False, True),
                (OWNER, "postgres", False, False, True),
            ],
        ),
        ("google_auth_lookup", [(IDENTITY_EXECUTOR, "postgres", False, True, False)]),
        (WORKER, [(EXECUTOR, "postgres", False, True, False)]),
        ("app_runtime", []),
        (IDENTITY_OWNER, []),
        (IDENTITY_EXECUTOR, []),
        (OWNER, []),
        (EXECUTOR, []),
    ):
        assert_member_memberships(connection, member, grants)


def _provisioning_marker(connection, profile):
    owner = connection.execute(
        text(
            """SELECT c.relkind='r' AND c.relowner='postgres'::regrole
            AND n.nspowner='postgres'::regrole
            FROM pg_catalog.pg_class AS c
            JOIN pg_catalog.pg_namespace AS n ON n.oid=c.relnamespace
            WHERE c.oid=to_regclass(:name) AND n.nspname='vervfy_rehearsal'"""
        ),
        {"name": PROVISIONING_APPROVAL},
    ).scalar_one_or_none()
    if owner is not True:
        raise rehearsal.RehearsalBlocked("DBA-owned provisioning marker is missing")
    columns = connection.execute(
        text("""SELECT a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod)
            FROM pg_catalog.pg_attribute AS a
            WHERE a.attrelid=to_regclass(:name) AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY a.attnum"""),
        {"name": PROVISIONING_APPROVAL},
    ).all()
    if [tuple(row) for row in columns] != [
        ("project_ref", "text"),
        ("run_id", "uuid"),
        ("config_sha256", "text"),
        ("disposable", "boolean"),
    ]:
        raise rehearsal.RehearsalBlocked("Provisioning marker schema mismatch")
    acl = connection.execute(
        text("""SELECT r.rolname,acl.privilege_type,acl.is_grantable
            FROM pg_catalog.pg_class AS c
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(c.relacl,pg_catalog.acldefault('r'::"char",c.relowner))
            ) AS acl
            LEFT JOIN pg_catalog.pg_roles AS r ON r.oid=acl.grantee
            WHERE c.oid=to_regclass(:name) AND acl.grantee<>c.relowner"""),
        {"name": PROVISIONING_APPROVAL},
    ).all()
    if {tuple(row) for row in acl} != {(rehearsal.LOGIN, "SELECT", False)}:
        raise rehearsal.RehearsalBlocked(
            "Provisioning marker must be DBA-owned and read-only to the migrator"
        )
    rows = connection.execute(
        text(
            "SELECT project_ref,run_id::text,config_sha256,disposable "
            f"FROM {PROVISIONING_APPROVAL}"
        )
    ).all()
    expected = (
        profile.config["project_ref"],
        profile.config["run_id"],
        profile.digest,
        True,
    )
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise rehearsal.RehearsalBlocked("Disposable provisioning identity mismatch")


def bootstrap_database(connection, profile):
    """Create only reviewed roles, role edges, markers and schema prerequisites."""
    fixture_uploader._assert_disposable_profile(profile)
    _transaction_limits(connection)
    _check_fresh_application_schema(connection, profile, allow_marker=True)
    _ensure_roles(connection)
    # Schema ownership changes are allowed only when the existing DBA already has
    # authority; do not grant itself membership or elevated attributes to make it work.
    can_reassign = connection.execute(
        text(
            "SELECT rolsuper OR pg_catalog.pg_has_role(current_user,:role,'SET') "
            "FROM pg_catalog.pg_roles WHERE rolname=current_user"
        ),
        {"role": rehearsal.LOGIN},
    ).scalar_one()
    if not can_reassign:
        raise rehearsal.RehearsalBlocked(
            "Existing DBA cannot assign the fresh schema to the restricted migrator"
        )
    for role, member, inherit, can_set in (
        (IDENTITY_OWNER, rehearsal.LOGIN, False, True),
        (IDENTITY_EXECUTOR, "google_auth_lookup", True, False),
        (OWNER, rehearsal.LOGIN, False, True),
        (EXECUTOR, WORKER, True, False),
    ):
        _ensure_membership(connection, role, member, inherit, can_set)
    _verify_role_graph(connection)
    quote = connection.dialect.identifier_preparer.quote
    for role in (
        rehearsal.LOGIN,
        "app_runtime",
        "google_auth_lookup",
        WORKER,
    ):
        connection.exec_driver_sql(
            f"GRANT CONNECT ON DATABASE postgres TO {quote(role)}"
        )
    connection.exec_driver_sql(
        f"GRANT CREATE ON DATABASE postgres TO {quote(rehearsal.LOGIN)}"
    )
    connection.exec_driver_sql(
        f"GRANT USAGE, CREATE ON SCHEMA public TO {quote(rehearsal.LOGIN)}"
    )
    connection.exec_driver_sql(f"ALTER SCHEMA public OWNER TO {quote(rehearsal.LOGIN)}")

    schema_owner = connection.exec_driver_sql(
        "SELECT nspowner='postgres'::regrole FROM pg_catalog.pg_namespace "
        "WHERE nspname='vervfy_rehearsal'"
    ).scalar_one_or_none()
    if schema_owner is None:
        connection.exec_driver_sql(
            "CREATE SCHEMA vervfy_rehearsal AUTHORIZATION postgres"
        )
    elif schema_owner is not True:
        raise rehearsal.RehearsalBlocked(
            "Rehearsal schema is not independently DBA-owned"
        )
    connection.exec_driver_sql(
        f"GRANT USAGE, CREATE ON SCHEMA vervfy_rehearsal TO {quote(rehearsal.LOGIN)}"
    )
    schema_acl = connection.execute(
        text("""SELECT r.rolname,acl.privilege_type,acl.is_grantable
            FROM pg_catalog.pg_namespace AS n
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(n.nspacl,pg_catalog.acldefault('n'::"char",n.nspowner))
            ) AS acl
            LEFT JOIN pg_catalog.pg_roles AS r ON r.oid=acl.grantee
            WHERE n.nspname='vervfy_rehearsal' AND acl.grantee<>n.nspowner""")
    ).all()
    if {tuple(row) for row in schema_acl} != {
        (rehearsal.LOGIN, "USAGE", False),
        (rehearsal.LOGIN, "CREATE", False),
    }:
        raise rehearsal.RehearsalBlocked(
            "Rehearsal schema must be usable and writable only by the migrator"
        )
    marker_exists = connection.exec_driver_sql(
        f"SELECT to_regclass('{PROVISIONING_APPROVAL}') IS NOT NULL"
    ).scalar_one()
    if not marker_exists:
        connection.exec_driver_sql(
            f"""CREATE TABLE {PROVISIONING_APPROVAL} (
                project_ref text NOT NULL,
                run_id uuid NOT NULL,
                config_sha256 text NOT NULL,
                disposable boolean NOT NULL CHECK (disposable)
            )"""
        )
        connection.execute(
            text(
                f"INSERT INTO {PROVISIONING_APPROVAL} "
                "(project_ref,run_id,config_sha256,disposable) "
                "VALUES (:project,:run,:digest,true)"
            ),
            {
                "project": profile.config["project_ref"],
                "run": profile.config["run_id"],
                "digest": profile.digest,
            },
        )
        connection.exec_driver_sql(
            f"REVOKE ALL ON TABLE {PROVISIONING_APPROVAL} FROM PUBLIC"
        )
        connection.exec_driver_sql(
            f"GRANT SELECT ON TABLE {PROVISIONING_APPROVAL} TO {quote(rehearsal.LOGIN)}"
        )
        connection.exec_driver_sql(
            f"ALTER TABLE {PROVISIONING_APPROVAL} OWNER TO postgres"
        )
    _provisioning_marker(connection, profile)
    if not connection.execute(
        text(
            """SELECT has_database_privilege(:role,current_database(),'CREATE')
            AND has_database_privilege(:role,current_database(),'CONNECT')
            AND has_schema_privilege(:role,'public','CREATE')"""
        ),
        {"role": rehearsal.LOGIN},
    ).scalar_one():
        raise rehearsal.RehearsalBlocked(
            "Migration schema capability was not provisioned"
        )


def verify_provisioning(connection, profile):
    _transaction_limits(connection)
    _target_identity(connection, expected_user=rehearsal.LOGIN)
    _provisioning_marker(connection, profile)


def _empty_baseline_preflight(connection, profile):
    verify_provisioning(connection, profile)
    if connection.exec_driver_sql("SELECT current_schema()").scalar_one() != "public":
        raise rehearsal.RehearsalBlocked("Public migration schema is required")
    if (
        connection.exec_driver_sql(
            "SELECT nspowner=current_user::regrole FROM pg_catalog.pg_namespace "
            "WHERE nspname='public'"
        ).scalar_one()
        is not True
    ):
        raise rehearsal.RehearsalBlocked("Restricted migrator must own public schema")
    if not connection.exec_driver_sql(
        "SELECT has_database_privilege(current_user,current_database(),'CREATE')"
    ).scalar_one():
        raise rehearsal.RehearsalBlocked(
            "Migration database CREATE capability is missing"
        )
    if connection.exec_driver_sql(
        """SELECT count(*) FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S')"""
    ).scalar_one():
        raise rehearsal.RehearsalBlocked("Fresh public application schema is required")
    if connection.exec_driver_sql(
        "SELECT to_regnamespace('vervfy_storage') IS NOT NULL "
        "OR to_regnamespace('vervfy_auth') IS NOT NULL"
    ).scalar_one():
        raise rehearsal.RehearsalBlocked(
            "Existing application schema must be preserved"
        )
    if connection.exec_driver_sql(
        "SELECT to_regclass('public.alembic_version') IS NOT NULL"
    ).scalar_one():
        raise rehearsal.RehearsalBlocked(
            "Existing migration history found; never stamp or replace it"
        )
    if tuple(
        connection.exec_driver_sql(
            """SELECT has_database_privilege(current_user,current_database(),'CONNECT'),
        has_schema_privilege(current_user,'public','USAGE'),
        has_schema_privilege(current_user,'public','CREATE')"""
        ).one()
    ) != (True, True, True):
        raise rehearsal.RehearsalBlocked(
            "Required migrator schema privileges are missing"
        )


def _upgrade(connection, profile, target):
    config = Config(str(rehearsal.production.ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": profile.migration_url.render_as_string(hide_password=False),
            "MIGRATION_DATABASE_URL": profile.migration_url.render_as_string(
                hide_password=False
            ),
            "VERVFY_ENVIRONMENT": "disposable-storage-rehearsal",
        },
    ):
        command.upgrade(config, target)


def _synthetic_password_hash():
    return bcrypt.hashpw(os.urandom(32), bcrypt.gensalt(rounds=4)).decode("ascii")


def _seed_accounts_and_legacy_references(connection, profile):
    legacy_path = f"legacy/rehearsal-{profile.config['run_id']}/shared.wav"
    for actor in rehearsal.TENANTS:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        connection.execute(
            text("""INSERT INTO public.users
                (id,username,username_key,password_hash,created_at)
                VALUES (:id,:username,:username,:password_hash,1)"""),
            {
                "id": actor,
                "username": f"rehearsal-{actor}",
                "password_hash": _synthetic_password_hash(),
            },
        )
        connection.execute(
            text("""INSERT INTO public.tracks
                (id,user_id,filename,title,artist,album,duration,has_cover,
                 cover_source,storage_path)
                VALUES (:id,:actor,'shared.wav','Synthetic shared fixture',
                        'Rehearsal','Disposable',0,false,'unknown',:path)"""),
            {"id": f"legacy-{actor}", "actor": actor, "path": legacy_path},
        )
    for actor in rehearsal.TENANTS:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        row = connection.execute(
            text(
                "SELECT count(*) FROM public.tracks "
                "WHERE user_id=:actor AND storage_path=:path"
            ),
            {"actor": actor, "path": legacy_path},
        ).scalar_one()
        if row != 1:
            raise rehearsal.RehearsalBlocked(
                "Tenant-scoped shared legacy reference seeding failed"
            )
    if set(connection.exec_driver_sql("SELECT id FROM public.users").scalars()) != set(
        rehearsal.TENANTS
    ):
        raise rehearsal.RehearsalBlocked("Synthetic tenant identity mismatch")


def _verify_0031(connection, profile):
    revision = (
        connection.exec_driver_sql("SELECT version_num FROM public.alembic_version")
        .scalars()
        .all()
    )
    if revision != [BASELINE_0031]:
        raise rehearsal.RehearsalBlocked("Baseline did not stop at exact 0031")
    for table in (
        "tracks",
        "artist_photos",
        "upload_jobs",
        "vervfy_storage.namespaces",
        "vervfy_storage.objects",
        "vervfy_storage.cleanup_jobs",
    ):
        row = connection.execute(
            text("""SELECT relrowsecurity,relforcerowsecurity
                FROM pg_catalog.pg_class WHERE oid=to_regclass(:name)"""),
            {"name": table},
        ).one_or_none()
        if row is None or tuple(row) != (True, True):
            raise rehearsal.RehearsalBlocked(
                f"Row-level security is not forced on {table}"
            )
    connection.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
    try:
        namespace_rows = connection.exec_driver_sql(
            "SELECT count(*) FROM vervfy_storage.namespaces"
        ).scalar_one()
        object_rows = connection.exec_driver_sql(
            "SELECT count(*) FROM vervfy_storage.objects"
        ).scalar_one()
        job_rows = connection.exec_driver_sql(
            "SELECT count(*) FROM vervfy_storage.cleanup_jobs"
        ).scalar_one()
    finally:
        connection.exec_driver_sql("RESET ROLE")
    if namespace_rows or object_rows or job_rows:
        raise rehearsal.RehearsalBlocked(
            "0031 baseline must stop before namespace and object seeding"
        )
    legacy_path = f"legacy/rehearsal-{profile.config['run_id']}/shared.wav"
    for actor in rehearsal.TENANTS:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        if (
            connection.execute(
                text(
                    "SELECT count(*) FROM public.tracks "
                    "WHERE user_id=:actor AND storage_path=:path"
                ),
                {"actor": actor, "path": legacy_path},
            ).scalar_one()
            != 1
        ):
            raise rehearsal.RehearsalBlocked(
                "Shared legacy reference changed during migration"
            )
    claims = connection.exec_driver_sql(
        """SELECT
        has_function_privilege('vervfy_storage_lifecycle_owner',
            'vervfy_storage.claim_next_cleanup()','EXECUTE'),
        has_function_privilege('vervfy_storage_cleanup',
            'vervfy_storage.claim_next_cleanup()','EXECUTE'),
        has_function_privilege('storage_cleanup_worker',
            'vervfy_storage.claim_next_cleanup()','EXECUTE'),
        has_function_privilege('app_runtime',
            'vervfy_storage.claim_next_cleanup()','EXECUTE')"""
    ).one()
    if tuple(claims) != (True, True, True, False):
        raise rehearsal.RehearsalBlocked("Unexpected 0031 cleanup claim permissions")


def baseline_0031(connection, profile):
    """Migrate empty schema to 0028, seed only tenants/refs, then migrate through 0031."""
    fixture_uploader._assert_disposable_profile(profile)
    if (
        profile.config["start_revision"]
        not in rehearsal.production.SUPPORTED_START_REVISIONS
    ):
        raise rehearsal.RehearsalBlocked("Unsupported rehearsal baseline")
    _transaction_limits(connection)
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": rehearsal.production.MIGRATION_LOCK_ID},
    )
    _empty_baseline_preflight(connection, profile)
    _upgrade(connection, profile, BASELINE_0028)
    if (
        connection.exec_driver_sql(
            "SELECT version_num FROM public.alembic_version"
        ).scalar_one()
        != BASELINE_0028
    ):
        raise rehearsal.RehearsalBlocked("Migrations did not stop at exact 0028")
    _seed_accounts_and_legacy_references(connection, profile)
    _upgrade(connection, profile, BASELINE_0031)
    _verify_0031(connection, profile)


def _check_migration_head(connection, expected):
    head = (
        connection.exec_driver_sql("SELECT version_num FROM public.alembic_version")
        .scalars()
        .all()
    )
    if head != [expected]:
        raise rehearsal.RehearsalBlocked(
            f"Expected exact migration revision {expected}"
        )


def initialize_disposable_namespace(connection, profile):
    fixture_uploader._assert_disposable_profile(profile)
    _transaction_limits(connection)
    _validate_dba(connection)
    _provisioning_marker(connection, profile)
    _check_migration_head(connection, BASELINE_0031)
    if set(connection.exec_driver_sql("SELECT id FROM public.users").scalars()) != set(
        rehearsal.TENANTS
    ):
        raise rehearsal.RehearsalBlocked("Only the two synthetic tenants may exist")
    _verify_synthetic_legacy_references(connection, profile)
    initialize_namespace(connection, profile.binding)
    binding = connection.exec_driver_sql(
        "SELECT namespace_id::text,environment,endpoint,bucket,physical_cleanup_enabled "
        "FROM vervfy_storage.namespaces"
    ).all()
    expected = (
        str(profile.binding.namespace_id),
        profile.binding.environment,
        profile.binding.endpoint,
        profile.binding.bucket,
        False,
    )
    if len(binding) != 1 or tuple(binding[0]) != expected:
        raise rehearsal.RehearsalBlocked("Disposable namespace postflight mismatch")


def _runtime_approval(connection, profile):
    owner = connection.execute(
        text(
            """SELECT c.relkind='r' AND c.relowner=current_user::regrole
            FROM pg_catalog.pg_class AS c
            WHERE c.oid=to_regclass(:name)"""
        ),
        {"name": RUNTIME_APPROVAL},
    ).scalar_one_or_none()
    if owner is None:
        connection.exec_driver_sql(
            f"""CREATE TABLE {RUNTIME_APPROVAL} (
                project_ref text NOT NULL,
                run_id uuid NOT NULL,
                config_sha256 text NOT NULL,
                disposable boolean NOT NULL CHECK (disposable)
            )"""
        )
        connection.execute(
            text(
                f"INSERT INTO {RUNTIME_APPROVAL} "
                "(project_ref,run_id,config_sha256,disposable) "
                "VALUES (:project,:run,:digest,true)"
            ),
            {
                "project": profile.config["project_ref"],
                "run": profile.config["run_id"],
                "digest": profile.digest,
            },
        )
        owner = True
    elif owner is not True:
        raise rehearsal.RehearsalBlocked("Runtime approval marker owner mismatch")
    columns = connection.execute(
        text("""SELECT a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod)
            FROM pg_catalog.pg_attribute AS a
            WHERE a.attrelid=to_regclass(:name) AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY a.attnum"""),
        {"name": RUNTIME_APPROVAL},
    ).all()
    if [tuple(row) for row in columns] != [
        ("project_ref", "text"),
        ("run_id", "uuid"),
        ("config_sha256", "text"),
        ("disposable", "boolean"),
    ]:
        raise rehearsal.RehearsalBlocked("Runtime approval marker schema mismatch")
    acl = connection.execute(
        text("""SELECT r.rolname,acl.privilege_type,acl.is_grantable
            FROM pg_catalog.pg_class AS c
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(c.relacl,pg_catalog.acldefault('r'::"char",c.relowner))
            ) AS acl
            LEFT JOIN pg_catalog.pg_roles AS r ON r.oid=acl.grantee
            WHERE c.oid=to_regclass(:name) AND acl.grantee<>c.relowner"""),
        {"name": RUNTIME_APPROVAL},
    ).all()
    if acl:
        raise rehearsal.RehearsalBlocked(
            "Runtime approval marker must not grant access beyond its owner"
        )
    rows = connection.execute(
        text(
            f"SELECT project_ref,run_id::text,config_sha256,disposable "
            f"FROM {RUNTIME_APPROVAL}"
        )
    ).all()
    expected = (
        profile.config["project_ref"],
        profile.config["run_id"],
        profile.digest,
        True,
    )
    if rows and (len(rows) != 1 or tuple(rows[0]) != expected):
        raise rehearsal.RehearsalBlocked("Runtime approval marker mismatch")
    if not rows:
        connection.execute(
            text(
                f"INSERT INTO {RUNTIME_APPROVAL} "
                "(project_ref,run_id,config_sha256,disposable) "
                "VALUES (:project,:run,:digest,true)"
            ),
            {
                "project": profile.config["project_ref"],
                "run": profile.config["run_id"],
                "digest": profile.digest,
            },
        )


def _verify_synthetic_legacy_references(connection, profile):
    legacy_path = f"legacy/rehearsal-{profile.config['run_id']}/shared.wav"
    for actor in rehearsal.TENANTS:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        if (
            connection.execute(
                text(
                    "SELECT count(*) FROM public.tracks "
                    "WHERE user_id=:actor AND storage_path=:path"
                ),
                {"actor": actor, "path": legacy_path},
            ).scalar_one()
            != 1
        ):
            raise rehearsal.RehearsalBlocked(
                "Expected tenant-scoped synthetic legacy reference is missing"
            )


def seed_legacy_ledger(connection, profile):
    """Register the two pre-trigger references as one held, unowned legacy object."""
    fixture_uploader._assert_disposable_profile(profile)
    _transaction_limits(connection)
    verify_provisioning(connection, profile)
    _check_migration_head(connection, BASELINE_0031)
    _runtime_approval(connection, profile)
    rehearsal.guard(connection, profile, head=BASELINE_0031)
    _verify_synthetic_legacy_references(connection, profile)
    connection.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
    try:
        path = f"legacy/rehearsal-{profile.config['run_id']}/shared.wav"
        existing = connection.execute(
            text("""SELECT id::text,namespace_id,tenant_id,path,kind,
                classification,state,reservation_token,upload_verified
                FROM vervfy_storage.objects WHERE path=:path"""),
            {"path": path},
        ).first()
        if existing is None:
            object_id = uuid.uuid4()
            connection.execute(
                text("""INSERT INTO vervfy_storage.objects
                    (id,namespace_id,path,kind,classification,state)
                    VALUES (:id,1,:path,'legacy','legacy','hold')"""),
                {"id": object_id, "path": path},
            )
        else:
            object_id = uuid.UUID(existing.id)
            if tuple(existing[1:]) != (
                1,
                None,
                path,
                "legacy",
                "legacy",
                "hold",
                None,
                False,
            ):
                raise rehearsal.RehearsalBlocked(
                    "Existing legacy ledger row differs; preserve it"
                )
        job = connection.execute(
            text("""SELECT requested_by,state,attempts,claim_token,lease_until
                FROM vervfy_storage.cleanup_jobs WHERE object_id=:id"""),
            {"id": object_id},
        ).first()
        if job is None:
            connection.execute(
                text("""INSERT INTO vervfy_storage.cleanup_jobs
                    (object_id,requested_by,state) VALUES (:id,NULL,'held')"""),
                {"id": object_id},
            )
        elif tuple(job) != (None, "held", 0, None, None):
            raise rehearsal.RehearsalBlocked(
                "Existing legacy cleanup obligation differs; preserve it"
            )
    finally:
        connection.exec_driver_sql("RESET ROLE")
    _verify_synthetic_legacy_references(connection, profile)
    connection.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
    try:
        result = connection.execute(
            text("""SELECT o.classification,o.state,o.tenant_id,o.reservation_token,
                o.upload_verified,j.state,j.attempts,j.claim_token,j.lease_until
                FROM vervfy_storage.objects AS o
                JOIN vervfy_storage.cleanup_jobs AS j ON j.object_id=o.id
                WHERE o.path=:path"""),
            {"path": path},
        ).one_or_none()
        if result is None or tuple(result) != (
            "legacy",
            "hold",
            None,
            None,
            False,
            "held",
            0,
            None,
            None,
        ):
            raise rehearsal.RehearsalBlocked(
                "Legacy fixture was not safely registered as held"
            )
    finally:
        connection.exec_driver_sql("RESET ROLE")


def approve_0031(connection, profile):
    """Create the runtime review marker only after exact 0031 guards pass."""
    fixture_uploader._assert_disposable_profile(profile)
    if profile.config["start_revision"] != BASELINE_0031:
        raise rehearsal.RehearsalBlocked("0031 approval requires a 0031 profile")
    _transaction_limits(connection)
    verify_provisioning(connection, profile)
    _check_migration_head(connection, BASELINE_0031)
    _runtime_approval(connection, profile)
    rehearsal.guard(connection, profile, head=BASELINE_0031)
    _verify_registered_legacy(connection, profile)


def _verify_registered_legacy(connection, profile):
    connection.exec_driver_sql(f"SET LOCAL ROLE {OWNER}")
    try:
        path = f"legacy/rehearsal-{profile.config['run_id']}/shared.wav"
        row = connection.execute(
            text("""SELECT o.classification,o.state,o.tenant_id,o.reservation_token,
                o.upload_verified,j.state,j.attempts,j.claim_token,j.lease_until
                FROM vervfy_storage.objects AS o
                JOIN vervfy_storage.cleanup_jobs AS j ON j.object_id=o.id
                WHERE o.path=:path"""),
            {"path": path},
        ).one_or_none()
        if row is None or tuple(row) != (
            "legacy",
            "hold",
            None,
            None,
            False,
            "held",
            0,
            None,
            None,
        ):
            raise rehearsal.RehearsalBlocked(
                "Held legacy fixture registration is required"
            )
    finally:
        connection.exec_driver_sql("RESET ROLE")


def baseline_0033(connection, profile):
    """Apply unchanged 0032/0033 only after the prepared 0031 state is approved."""
    fixture_uploader._assert_disposable_profile(profile)
    if profile.config["start_revision"] != BASELINE_0033:
        raise rehearsal.RehearsalBlocked("0033 executor requires a 0033 profile")
    _transaction_limits(connection)
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": rehearsal.production.MIGRATION_LOCK_ID},
    )
    verify_provisioning(connection, profile)
    _check_migration_head(connection, BASELINE_0031)
    _runtime_approval(connection, profile)
    rehearsal.guard(connection, profile, head=BASELINE_0031)
    _verify_registered_legacy(connection, profile)
    _upgrade(connection, profile, BASELINE_0033)
    rehearsal.guard(connection, profile, head=BASELINE_0033)


@contextmanager
def _migration_connection(profile):
    fixture_uploader._assert_disposable_profile(profile)
    engine = _engine_for(profile.migration_url)
    try:
        with engine.begin() as connection:
            yield connection
    finally:
        engine.dispose()


def _run_admin(profile, callback):
    url = dba_url(profile)
    engine = _engine_for(url)
    try:
        with engine.begin() as connection:
            return callback(connection, profile)
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "bootstrap",
            "baseline-0031",
            "initialize-namespace",
            "seed-legacy",
            "approve-0031",
            "baseline-0033",
        ),
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--confirm-disposable-project", required=True)
    args = parser.parse_args(argv)
    try:
        _validate_environment(os.environ)
        profile = load_profile(
            args.config,
            args.config_sha256,
            args.ca_file,
            args.confirm_disposable_project,
            live=args.operation
            in {"baseline-0031", "seed-legacy", "approve-0031", "baseline-0033"},
        )
        if args.operation == "bootstrap":
            _run_admin(profile, bootstrap_database)
            result = {"provisioned": "restricted_roles_and_marker"}
        elif args.operation == "initialize-namespace":
            _run_admin(profile, initialize_disposable_namespace)
            result = {
                "namespace_initialized": True,
                "physical_cleanup_enabled": False,
            }
        else:
            functions = {
                "baseline-0031": baseline_0031,
                "seed-legacy": seed_legacy_ledger,
                "approve-0031": approve_0031,
                "baseline-0033": baseline_0033,
            }
            with _migration_connection(profile) as connection:
                functions[args.operation](connection, profile)
            result = {"operation": args.operation}
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - suppress SQL/URL/password details
        print(
            f"BLOCKED: disposable rehearsal provisioning ({type(exc).__name__}); "
            "no downgrade or deletion attempted",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
