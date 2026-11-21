"""Explicitly configured disposable Supabase 0034 rehearsal; never a production entrypoint.

Requires a separately provisioned synthetic project and approval marker. This
workflow never creates roles, weakens RLS, uploads provider bytes, or deletes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from scripts import storage_production_migration as production
from scripts.storage_inventory_reconcile import ReadOnlyObserver
from storage_auth_headers import storage_auth_headers
from storage_inventory import apply_inventory, measure_inventory, plan_digest, snapshot
from storage_namespace import NamespaceBinding

PURPOSE = "vervfy-0034-disposable-rehearsal-v1"
LOGIN = "vervfy_rehearsal_migrator"
TENANTS = ("a", "b")
PRODUCTION_NAMESPACE = "31daf7cc-8563-411f-94c7-944d607d1ef1"


class RehearsalBlocked(RuntimeError):
    pass


def history_digest():
    digest = hashlib.sha256()
    files = sorted((production.ROOT / "alembic/versions").glob("*.py"))
    files += [production.ROOT / "alembic/env.py", production.ROOT / "alembic.ini"]
    for path in files:
        digest.update(path.relative_to(production.ROOT).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 16 * 1024 * 1024
        ):
            raise RehearsalBlocked("Input must be a bounded owner-only regular file")
        return json.load(source)


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(value, out, sort_keys=True, indent=2)


@dataclass(frozen=True)
class Profile:
    config: dict
    digest: str
    migration_url: object
    runtime_url: object

    @property
    def binding(self):
        return NamespaceBinding(
            uuid.UUID(self.config["namespace_id"]),
            "disposable-rehearsal",
            f"https://{self.config['project_ref']}.supabase.co",
            self.config["bucket"],
        )


def load_profile(path, approved_digest, env=None):
    env = os.environ if env is None else env
    # Reject ambiguous inherited production/staging/local execution selectors.
    if env.get("VERVFY_ENVIRONMENT") != "disposable-storage-rehearsal":
        raise RehearsalBlocked(
            "Explicit disposable-storage-rehearsal environment required"
        )
    forbidden = (
        *production.FORBIDDEN_PG_ENV,
        "PGPASSFILE",
        "PGSSLKEY",
        "PGSSLCERT",
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_BUCKET",
        "VERVFY_STAGING_PROFILE",
        "ENVIRONMENT",
    )
    if (
        any(env.get(k) for k in forbidden)
        or any(k.startswith("PG") and v for k, v in env.items())
        or any(k.startswith("VERVFY_PRODUCTION_") and v for k, v in env.items())
    ):
        raise RehearsalBlocked(
            "Inherited database, provider or production overrides are forbidden"
        )
    config = read_private(path)
    keys = {
        "purpose",
        "project_ref",
        "namespace_id",
        "bucket",
        "start_revision",
        "run_id",
        "ca_sha256",
        "history_sha256",
    }
    if (
        set(config) != keys
        or plan_digest(config) != approved_digest
        or config["purpose"] != PURPOSE
    ):
        raise RehearsalBlocked("Configuration digest or purpose mismatch")
    ref = config["project_ref"]
    if (
        not isinstance(ref, str)
        or re.fullmatch(r"[a-z0-9]{20}", ref) is None
        or ref in {production.PRODUCTION_PROJECT_REF, production.STAGING_PROJECT_REF}
    ):
        raise RehearsalBlocked(
            "Project must be explicitly disposable, never production or existing staging"
        )
    namespace = uuid.UUID(config["namespace_id"])
    if not namespace.int or str(namespace) == PRODUCTION_NAMESPACE:
        raise RehearsalBlocked("A separate non-production namespace is required")
    uuid.UUID(config["run_id"])
    if (
        re.fullmatch(r"vervfy-rehearsal-[a-z0-9-]{1,50}", config["bucket"]) is None
        or config["start_revision"] not in production.SUPPORTED_START_REVISIONS
        or config["history_sha256"] != history_digest()
    ):
        raise RehearsalBlocked("Bucket, starting revision or reviewed history mismatch")
    production.validate_migration_chain()
    ca = Path(env.get("VERVFY_REHEARSAL_CA_FILE", "")).resolve(strict=True)
    if (
        not ca.is_file()
        or hashlib.sha256(ca.read_bytes()).hexdigest() != config["ca_sha256"]
    ):
        raise RehearsalBlocked("Pinned CA bundle mismatch")
    urls = []
    for key, role in (
        ("VERVFY_REHEARSAL_DATABASE_URL", LOGIN),
        ("VERVFY_REHEARSAL_RUNTIME_URL", "app_runtime"),
    ):
        url = make_url(env.get(key, ""))
        if (
            url.drivername != "postgresql+psycopg"
            or url.host != f"db.{ref}.supabase.co"
            or url.port != 5432
            or url.database != "postgres"
            or url.username != role
            or not url.password
            or dict(url.query) != {"sslmode": "verify-full", "sslrootcert": str(ca)}
        ):
            raise RehearsalBlocked(
                "Direct project-bound verify-full URL and exact restricted login required"
            )
        urls.append(url)
    return Profile(config, approved_digest, *urls)


def engine_for(url):
    return create_engine(url, poolclass=NullPool, pool_pre_ping=True)


def guard(connection, profile, *, head):
    """Run on the actual operation transaction, preserving every isolation gate."""
    if (
        profile.config["project_ref"]
        in {production.PRODUCTION_PROJECT_REF, production.STAGING_PROJECT_REF}
        or str(profile.binding.namespace_id) == PRODUCTION_NAMESPACE
    ):
        raise RehearsalBlocked(
            "Production targets are forbidden even for internal callers"
        )
    production._verify_client_tls(connection)
    connection.exec_driver_sql("SET LOCAL search_path TO public")
    connection.exec_driver_sql("SET LOCAL timezone TO 'UTC'")
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
    identity = connection.exec_driver_sql(
        "SELECT current_database(),session_user,current_user"
    ).one()
    if tuple(identity) != ("postgres", LOGIN, LOGIN):
        raise RehearsalBlocked("Rehearsal connection identity mismatch")
    if int(connection.exec_driver_sql("SHOW server_version_num").scalar_one()) < 160000:
        raise RehearsalBlocked("PostgreSQL 16 or newer is required")
    attributes = connection.exec_driver_sql("""SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,
        rolreplication,rolcanlogin FROM pg_roles WHERE rolname=current_user""").one()
    if tuple(attributes) != (False, False, False, False, False, True):
        raise RehearsalBlocked("Rehearsal login must be restricted")
    revision = (
        connection.exec_driver_sql("SELECT version_num FROM public.alembic_version")
        .scalars()
        .all()
    )
    if revision != [head]:
        raise RehearsalBlocked("Unexpected rehearsal migration boundary")
    owned = set(
        connection.exec_driver_sql("""SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' AND c.relowner=current_user::regrole""").scalars()
    )
    if not {*production.REQUIRED_TABLES, "alembic_version"} <= owned:
        raise RehearsalBlocked("Rehearsal login must own the migration tables")
    if not all(
        connection.exec_driver_sql("""SELECT
        has_database_privilege(current_user,current_database(),'CONNECT'),
        has_database_privilege(current_user,current_database(),'CREATE'),
        has_schema_privilege(current_user,'public','USAGE'),
        has_schema_privilege(current_user,'public','CREATE')""").one()
    ):
        raise RehearsalBlocked("Required migration ownership capabilities are missing")
    # Separately provisioned project marker; no implicit project bootstrap.
    marker_owner = connection.exec_driver_sql("""SELECT relowner=current_user::regrole FROM pg_class
        WHERE oid='vervfy_rehearsal.approval'::regclass""").scalar_one()
    marker = connection.exec_driver_sql(
        "SELECT project_ref,run_id::text,config_sha256,disposable FROM vervfy_rehearsal.approval"
    ).all()
    if (
        not marker_owner
        or len(marker) != 1
        or tuple(marker[0])
        != (
            profile.config["project_ref"],
            profile.config["run_id"],
            profile.digest,
            True,
        )
    ):
        raise RehearsalBlocked("Disposable project approval marker mismatch")
    if set(connection.exec_driver_sql("SELECT id FROM public.users").scalars()) != set(
        TENANTS
    ):
        raise RehearsalBlocked("Only the two synthetic tenants may exist")
    production._check_role_graph(connection, LOGIN)
    connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
    binding = connection.exec_driver_sql(
        "SELECT namespace_id::text,environment,endpoint,bucket,physical_cleanup_enabled FROM vervfy_storage.namespaces"
    ).all()
    expected = (
        str(profile.binding.namespace_id),
        profile.binding.environment,
        profile.binding.endpoint,
        profile.binding.bucket,
        False,
    )
    connection.exec_driver_sql("RESET ROLE")
    if len(binding) != 1 or tuple(binding[0]) != expected:
        raise RehearsalBlocked("Disposable namespace mismatch or cleanup enabled")
    enforced = connection.exec_driver_sql("""SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class
        WHERE oid IN ('public.tracks'::regclass,'public.favorites'::regclass,'public.playlists'::regclass,
        'public.playlist_tracks'::regclass,'vervfy_storage.namespaces'::regclass,
        'vervfy_storage.objects'::regclass,'vervfy_storage.cleanup_jobs'::regclass)""").all()
    if len(enforced) != 7 or any(not r[1] or not r[2] for r in enforced):
        raise RehearsalBlocked("Forced tenant and storage RLS required")
    claims = connection.exec_driver_sql("""SELECT
        has_function_privilege('vervfy_storage_lifecycle_owner','vervfy_storage.claim_next_cleanup()','EXECUTE'),
        has_function_privilege('vervfy_storage_cleanup','vervfy_storage.claim_next_cleanup()','EXECUTE'),
        has_function_privilege('storage_cleanup_worker','vervfy_storage.claim_next_cleanup()','EXECUTE'),
        has_function_privilege('app_runtime','vervfy_storage.claim_next_cleanup()','EXECUTE')""").one()
    expected_claims = (
        (True, True, True, False)
        if head == production.START_REVISION
        else (True, False, False, False)
    )
    if tuple(claims) != expected_claims:
        raise RehearsalBlocked("Cleanup claim privileges mismatch")
    sessions = connection.exec_driver_sql(
        "SELECT to_regclass('public.auth_sessions') IS NOT NULL"
    ).scalar_one()
    if sessions != (head != production.START_REVISION):
        raise RehearsalBlocked("Session schema does not match the approved boundary")
    if sessions:
        session_access = connection.exec_driver_sql("""SELECT
            has_table_privilege('app_runtime','public.auth_sessions','SELECT'),
            has_table_privilege('app_runtime','public.auth_sessions','INSERT'),
            has_table_privilege('app_runtime','public.auth_sessions','DELETE'),
            has_table_privilege('app_runtime','public.auth_sessions','UPDATE')""").one()
        if tuple(session_access) != (True, True, True, False):
            raise RehearsalBlocked("Session privileges mismatch")
    if head == production.TARGET_REVISION:
        snapshot(
            connection, profile.binding
        )  # Includes quota RLS and disabled-cleanup checks.
        connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
        policy = connection.exec_driver_sql(
            "SELECT tenant_limit_bytes,total_limit_bytes FROM vervfy_storage.quota_policy WHERE id=1"
        ).one()
        connection.exec_driver_sql("RESET ROLE")
        if any(type(v) is not int or v <= 0 for v in policy):
            raise RehearsalBlocked("Positive quota policy required")
        access = connection.exec_driver_sql("""SELECT
          has_function_privilege('app_runtime','vervfy_storage.reserve_sized_object(text,text,bigint,bigint)','EXECUTE'),
          has_function_privilege('app_runtime','vervfy_storage.retained_bytes()','EXECUTE'),
          has_function_privilege('app_runtime','vervfy_storage.reserve_object(text,text)','EXECUTE'),
          has_table_privilege('app_runtime','vervfy_storage.quota_policy','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')""").one()
        if tuple(access) != (True, True, False, False):
            raise RehearsalBlocked("Quota capabilities mismatch")


def fingerprints(connection, tables=None):
    """Hash all fields of pre-existing public rows under each tenant's RLS context."""
    connection.exec_driver_sql("SET LOCAL timezone TO 'UTC'")
    if tables is None:
        tables = (
            connection.exec_driver_sql("""SELECT tablename FROM pg_tables WHERE schemaname='public'
            AND tablename<>'alembic_version' ORDER BY tablename""")
            .scalars()
            .all()
        )
    data = {}
    for actor in TENANTS:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        for table in tables:
            quoted = connection.dialect.identifier_preparer.quote(table)
            rows = (
                connection.exec_driver_sql(
                    f"SELECT to_jsonb(t)::text FROM public.{quoted} t"
                )
                .scalars()
                .all()
            )
            data[f"{actor}:{table}"] = sorted(rows)
    connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
    for table in ("objects", "cleanup_jobs", "namespaces"):
        # The only permitted storage-row change during upgrade is the new NULL column.
        rows = (
            connection.exec_driver_sql(
                f"SELECT (to_jsonb(t)-'reserved_bytes')::text FROM vervfy_storage.{table} t"
            )
            .scalars()
            .all()
        )
        data["storage:" + table] = sorted(rows)
    connection.exec_driver_sql("RESET ROLE")
    return {
        "tables": list(tables),
        "digest": plan_digest(data),
        "counts": {k: len(v) for k, v in data.items()},
    }


def receipt_for(connection, profile):
    guard(connection, profile, head=profile.config["start_revision"])
    connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
    owners = set(
        connection.exec_driver_sql(
            "SELECT DISTINCT tenant_id FROM vervfy_storage.objects WHERE tenant_id IS NOT NULL"
        ).scalars()
    )
    legacy = connection.exec_driver_sql(
        "SELECT count(*) FROM vervfy_storage.objects WHERE classification='legacy'"
    ).scalar_one()
    jobs = connection.exec_driver_sql(
        "SELECT count(*) FROM vervfy_storage.cleanup_jobs"
    ).scalar_one()
    connection.exec_driver_sql("RESET ROLE")
    if owners != set(TENANTS) or not legacy or not jobs:
        raise RehearsalBlocked(
            "A populated two-tenant/legacy/outbox fixture is required"
        )
    return {
        "purpose": PURPOSE,
        "config_sha256": profile.digest,
        "run_id": profile.config["run_id"],
        "baseline": fingerprints(connection),
    }


def validate_receipt(profile, receipt, approved):
    if (
        plan_digest(receipt) != approved
        or receipt.get("purpose") != PURPOSE
        or receipt.get("config_sha256") != profile.digest
        or receipt.get("run_id") != profile.config["run_id"]
    ):
        raise RehearsalBlocked("Baseline receipt approval mismatch")


def upgrade(connection, profile, receipt, *, expires_at):
    """Caller owns the transaction; any postflight failure rolls all DDL back."""
    from alembic.config import Config

    from alembic import command

    production._verify_client_tls(connection)
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:id)"), {"id": production.MIGRATION_LOCK_ID}
    )
    guard(connection, profile, head=profile.config["start_revision"])
    if fingerprints(connection, receipt["baseline"]["tables"]) != receipt["baseline"]:
        raise RehearsalBlocked("Baseline changed before upgrade")
    config = Config(str(production.ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    config.attributes["vervfy_disposable_storage_rehearsal"] = True
    production.validate_authorization(expires_at)
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": str(
                profile.migration_url.render_as_string(hide_password=False)
            ),
            "MIGRATION_DATABASE_URL": str(
                profile.migration_url.render_as_string(hide_password=False)
            ),
            "VERVFY_ENVIRONMENT": "disposable-storage-rehearsal",
        },
    ):
        command.upgrade(config, production.TARGET_REVISION)
    guard(connection, profile, head=production.TARGET_REVISION)
    connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
    policy = connection.exec_driver_sql(
        "SELECT tenant_limit_bytes,total_limit_bytes FROM vervfy_storage.quota_policy WHERE id=1"
    ).one()
    connection.exec_driver_sql("RESET ROLE")
    if tuple(policy) != (157286400, 10737418240):
        raise RehearsalBlocked("Unexpected initial quota policy")
    if fingerprints(connection, receipt["baseline"]["tables"]) != receipt["baseline"]:
        raise RehearsalBlocked("Populated data changed during upgrade")
    connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
    nonnull = connection.exec_driver_sql(
        "SELECT count(*) FROM vervfy_storage.objects WHERE reserved_bytes IS NOT NULL"
    ).scalar_one()
    connection.exec_driver_sql("RESET ROLE")
    if nonnull:
        raise RehearsalBlocked("Migration unexpectedly assigned legacy charges")


def recover(connection, profile, receipt):
    """Resolve commit acknowledgement loss read-only; never retry, stamp or downgrade."""
    head = (
        connection.exec_driver_sql("SELECT version_num FROM public.alembic_version")
        .scalars()
        .all()
    )
    if head not in ([profile.config["start_revision"]], [production.TARGET_REVISION]):
        raise RehearsalBlocked("Recovery found an unexpected revision")
    guard(connection, profile, head=head[0])
    if fingerprints(connection, receipt["baseline"]["tables"]) != receipt["baseline"]:
        raise RehearsalBlocked("Recovery data changed; investigate without retrying")
    return (
        "at_baseline"
        if head[0] == profile.config["start_revision"]
        else "committed_0034"
    )


def verify_runtime(engine, profile, unknown):
    """Read isolation and denied mutations; all probe reservations roll back."""
    from sqlalchemy.exc import DBAPIError

    results = {}
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            production._verify_client_tls(connection)
            identity = connection.exec_driver_sql(
                "SELECT current_database(),session_user,current_user"
            ).one()
            if tuple(identity) != ("postgres", "app_runtime", "app_runtime"):
                raise RehearsalBlocked("Runtime probe identity mismatch")
            connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
            connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
            for actor in TENANTS:
                connection.execute(
                    text("SELECT set_config('app.current_user_id',:actor,true)"),
                    {"actor": actor},
                )
                visible = (
                    connection.exec_driver_sql(
                        "SELECT DISTINCT user_id FROM public.tracks"
                    )
                    .scalars()
                    .all()
                )
                if visible != [actor]:
                    raise RehearsalBlocked("Populated tenant RLS probe failed")
                if connection.execute(
                    text("SELECT count(*) FROM public.tracks WHERE user_id<>:actor"),
                    {"actor": actor},
                ).scalar_one():
                    raise RehearsalBlocked("Cross-tenant rows were exposed")
                other = "b" if actor == "a" else "a"
                changed = connection.execute(
                    text("UPDATE tracks SET title='forbidden' WHERE user_id=:other"),
                    {"other": other},
                )
                if changed.rowcount:
                    raise RehearsalBlocked("Cross-tenant mutation was permitted")
                try:
                    with connection.begin_nested():
                        connection.execute(
                            text("""INSERT INTO tracks
                            (id,user_id,filename,title,artist,album,duration,has_cover)
                            VALUES('rehearsal-forbidden-insert',:other,'f','t','a','l',0,false)"""),
                            {"other": other},
                        )
                except DBAPIError as exc:
                    if getattr(exc.orig, "sqlstate", None) != "42501":
                        raise
                else:
                    raise RehearsalBlocked("Cross-tenant insertion was permitted")
                leaked = connection.execute(
                    text(
                        "SELECT count(*) FROM vervfy_storage.objects WHERE tenant_id IS DISTINCT FROM :actor"
                    ),
                    {"actor": actor},
                ).scalar_one()
                if leaked:
                    raise RehearsalBlocked("Storage tenant isolation failed")
                for sql in (
                    "UPDATE vervfy_storage.quota_policy SET total_limit_bytes=total_limit_bytes+1",
                    "UPDATE vervfy_storage.objects SET reserved_bytes=1",
                ):
                    try:
                        with connection.begin_nested():
                            connection.exec_driver_sql(sql)
                    except DBAPIError as exc:
                        if getattr(exc.orig, "sqlstate", None) != "42501":
                            raise
                    else:
                        raise RehearsalBlocked(
                            "Runtime unexpectedly mutated accounting"
                        )
                try:
                    with connection.begin_nested():
                        connection.exec_driver_sql(
                            "SELECT * FROM vervfy_storage.reserve_sized_object('audio','mp3',9223372036854775807,9223372036854775807)"
                        )
                except DBAPIError as exc:
                    expected = "55000" if unknown else "54000"
                    if getattr(exc.orig, "sqlstate", None) != expected:
                        raise RehearsalBlocked("Unexpected quota rejection") from None
                else:
                    raise RehearsalBlocked("Oversized allocation bypassed quotas")
                results[actor] = (
                    "unknown_inventory_blocked" if unknown else "quota_enforced"
                )
        finally:
            transaction.rollback()
    return results


def verify_bucket(client_factory, binding):
    """Read only the pinned bucket metadata under bounded I/O."""

    async def read():
        client = client_factory()
        try:
            async with asyncio.timeout(60):
                from urllib.parse import quote

                url = (
                    binding.endpoint
                    + "/storage/v1/bucket/"
                    + quote(binding.bucket, safe="")
                )
                data = bytearray()
                async with client.stream(
                    "GET", url, headers={"Accept-Encoding": "identity"}
                ) as response:
                    if (
                        response.status_code != 200
                        or response.headers.get("content-encoding", "identity")
                        != "identity"
                    ):
                        raise RehearsalBlocked("Disposable bucket metadata unavailable")
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 65536:
                            raise RehearsalBlocked("Bucket metadata exceeds bound")
                metadata = json.loads(data)
                if (
                    not isinstance(metadata, dict)
                    or metadata.get("public") is not False
                    or metadata.get("id") != binding.bucket
                ):
                    raise RehearsalBlocked(
                        "Expected a private, exact disposable bucket"
                    )
        finally:
            async with asyncio.timeout(5):
                await client.aclose()

    asyncio.run(read())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=("snapshot", "upgrade", "recover", "verify", "plan", "apply"),
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--confirm-disposable-project", required=True)
    parser.add_argument("--authorization-expires-at", required=True)
    parser.add_argument("--confirm-writers-paused", action="store_true", required=True)
    parser.add_argument("--receipt-file", type=Path)
    parser.add_argument("--receipt-sha256")
    parser.add_argument("--authorize-upgrade")
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--plan-sha256")
    args = parser.parse_args(argv)
    engine = None
    try:
        profile = load_profile(args.config, args.config_sha256)
        if args.confirm_disposable_project != profile.config["project_ref"]:
            raise RehearsalBlocked("Disposable project confirmation mismatch")
        production.validate_authorization(args.authorization_expires_at)
        receipt = None
        if args.operation in {"upgrade", "recover"}:
            if not args.receipt_file or not args.receipt_sha256:
                raise RehearsalBlocked("Approved pre-upgrade receipt required")
            receipt = read_private(args.receipt_file)
            validate_receipt(profile, receipt, args.receipt_sha256)
        if (
            args.operation == "upgrade"
            and args.authorize_upgrade
            != f"{profile.config['start_revision']}..{production.TARGET_REVISION}"
        ):
            raise RehearsalBlocked("Exact upgrade-boundary authorization required")
        if args.operation in {"snapshot", "plan", "apply"}:
            if args.operation == "snapshot" and not args.receipt_file:
                raise RehearsalBlocked("Exclusive receipt output path required")
            if args.operation in {"plan", "apply"} and not args.plan_file:
                raise RehearsalBlocked("Private plan path required")
            if args.operation == "apply" and not args.plan_sha256:
                raise RehearsalBlocked("Independently approved plan digest required")
        engine = engine_for(profile.migration_url)
        with engine.begin() as connection:
            if args.operation not in {"upgrade", "apply"}:
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            production.validate_authorization(args.authorization_expires_at)
            if args.operation == "snapshot":
                receipt = receipt_for(connection, profile)
                write_private(args.receipt_file, receipt)
                result = {"baseline_sha256": plan_digest(receipt)}
            elif args.operation == "upgrade":
                upgrade(
                    connection,
                    profile,
                    receipt,
                    expires_at=args.authorization_expires_at,
                )
                result = {"revision": production.TARGET_REVISION}
            elif args.operation == "recover":
                result = {"recovery": recover(connection, profile, receipt)}
            else:
                guard(connection, profile, head=production.TARGET_REVISION)
                before = snapshot(connection, profile.binding)
                if args.operation == "apply":
                    plan = read_private(args.plan_file)
                    result = {
                        "charges_filled": apply_inventory(
                            connection, profile.binding, plan, args.plan_sha256
                        )
                    }
                else:
                    result = {
                        "unknown_rows": sum(
                            r["reserved_bytes"] is None for r in before["objects"]
                        )
                    }
            if args.operation in {"upgrade", "apply"}:
                production.validate_authorization(args.authorization_expires_at)
        if args.operation == "verify":
            runtime = engine_for(profile.runtime_url)
            try:
                result["tenants"] = verify_runtime(
                    runtime, profile, bool(result["unknown_rows"])
                )
            finally:
                runtime.dispose()
        if args.operation == "plan":
            key = os.environ.get("VERVFY_REHEARSAL_STORAGE_KEY", "").strip()
            if not key:
                raise RehearsalBlocked(
                    "Dedicated disposable-project provider credential required"
                )

            def client_factory():
                return httpx.AsyncClient(
                    headers=storage_auth_headers(key),
                    follow_redirects=False,
                    trust_env=False,
                    timeout=httpx.Timeout(5),
                )

            verify_bucket(client_factory, profile.binding)
            plan = measure_inventory(
                before, ReadOnlyObserver(client_factory, profile.binding)
            )
            production.validate_authorization(args.authorization_expires_at)
            write_private(args.plan_file, plan)
            result = {"plan_sha256": plan_digest(plan)}
        # Print successful upgrade only after the outer transaction has committed.
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - suppress SQL/provider/credential details
        print(
            f"BLOCKED: disposable rehearsal ({type(exc).__name__}); inspect via read-only recovery, never blindly retry",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
