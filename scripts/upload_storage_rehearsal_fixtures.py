"""Upload only the prepared synthetic fixtures to an approved disposable 0031 project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import prepare_storage_rehearsal_baseline as preparation
from scripts import storage_rehearsal as rehearsal
from storage_auth_headers import storage_auth_headers
from storage_inventory import plan_digest

BASELINE = "0031_cleanup_retry_limits"
MAX_FIXTURE_BYTES = 1024 * 1024
NETWORK_DEADLINE_SECONDS = 60
MANAGED_PATH = re.compile(
    r"v2/[0-9a-f-]{36}/[ab]/(?:audio|track-cover|artist-photo|staged-audio)/"
    r"[0-9a-f-]{36}\.(?:wav|jpg)\Z"
)


def load_profile(config_path, approved_digest, ca_file, confirm_project):
    """Load only explicitly named rehearsal credentials; reject ambient app targets."""
    env = os.environ
    forbidden = (
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_BUCKET",
        "VERVFY_STAGING_PROFILE",
    )
    if (
        env.get("VERVFY_ENVIRONMENT") != "disposable-storage-rehearsal"
        or any(env.get(name) for name in forbidden)
        or any(name.startswith("PG") and value for name, value in env.items())
        or any(
            name.startswith("VERVFY_PRODUCTION_") and value
            for name, value in env.items()
        )
    ):
        raise rehearsal.RehearsalBlocked(
            "Ambient application, provider, PostgreSQL or production settings are forbidden"
        )
    key = env.get("VERVFY_REHEARSAL_STORAGE_KEY", "").strip()
    if not key:
        raise rehearsal.RehearsalBlocked(
            "Dedicated disposable-project provider credential required"
        )
    profile_env = {
        "VERVFY_ENVIRONMENT": env["VERVFY_ENVIRONMENT"],
        "VERVFY_REHEARSAL_CA_FILE": str(Path(ca_file).resolve(strict=True)),
        "VERVFY_REHEARSAL_DATABASE_URL": env.get("VERVFY_REHEARSAL_DATABASE_URL", ""),
        "VERVFY_REHEARSAL_RUNTIME_URL": env.get("VERVFY_REHEARSAL_RUNTIME_URL", ""),
    }
    profile = rehearsal.load_profile(config_path, approved_digest, profile_env)
    if profile.config["project_ref"] != confirm_project:
        raise rehearsal.RehearsalBlocked("Disposable project confirmation mismatch")
    return profile, key


def _read_private_artifact(path: Path, *, max_bytes: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > max_bytes
        ):
            raise rehearsal.RehearsalBlocked(
                "Bundle artifacts must be bounded owner-only regular files"
            )
        return source.read(max_bytes + 1)


def load_bundle(bundle_dir, profile, approved_bundle_digest):
    root = Path(bundle_dir)
    if (
        root.is_symlink()
        or not root.is_dir()
        or root.resolve(strict=True) != root
        or root.stat().st_uid != os.getuid()
        or stat.S_IMODE(root.stat().st_mode) != 0o700
    ):
        raise rehearsal.RehearsalBlocked(
            "Bundle directory must be private and owner-only"
        )
    manifest = rehearsal.read_private(root / "manifest.json")
    if (
        plan_digest(manifest) != approved_bundle_digest
        or manifest.get("purpose") != "vervfy-disposable-baseline-review-bundle-v1"
        or manifest.get("project_ref") != profile.config["project_ref"]
        or manifest.get("config_sha256") != profile.digest
        or manifest.get("run_id") != profile.config["run_id"]
        or manifest.get("baseline") not in rehearsal.SUPPORTED_START_REVISIONS
        or manifest.get("ready_for_hosted_execution") is not False
    ):
        raise rehearsal.RehearsalBlocked("Prepared bundle identity or digest mismatch")

    expected_files, expected_entries = preparation.fixture_files(profile)
    if manifest.get("files") is None:
        raise rehearsal.RehearsalBlocked("Prepared bundle file manifest is missing")
    entries = rehearsal.read_private(root / "04-fixtures.json")
    expected_inventory = {
        "entries": expected_entries,
        "total_bytes": sum(item["bytes"] for item in expected_entries),
        "physical_cleanup_enabled": False,
    }
    inventory_bytes = _read_private_artifact(
        root / "04-fixtures.json", max_bytes=MAX_FIXTURE_BYTES
    )
    if entries != expected_inventory or manifest["files"].get("04-fixtures.json") != {
        "bytes": len(inventory_bytes),
        "sha256": hashlib.sha256(inventory_bytes).hexdigest(),
    }:
        raise rehearsal.RehearsalBlocked(
            "Fixture inventory differs from reviewed synthetic data"
        )
    fixture_dir = root / "fixtures"
    if (
        fixture_dir.is_symlink()
        or not fixture_dir.is_dir()
        or fixture_dir.resolve(strict=True) != fixture_dir
        or fixture_dir.stat().st_uid != os.getuid()
        or stat.S_IMODE(fixture_dir.stat().st_mode) != 0o700
    ):
        raise rehearsal.RehearsalBlocked(
            "Fixture directory must be private and owner-only"
        )
    files = {}
    for relative, expected in expected_files.items():
        if len(expected) > MAX_FIXTURE_BYTES:
            raise rehearsal.RehearsalBlocked("Fixture exceeds the bounded upload size")
        artifact = root / relative
        data = _read_private_artifact(artifact, max_bytes=MAX_FIXTURE_BYTES)
        if data != expected:
            raise rehearsal.RehearsalBlocked(
                "Fixture bytes differ from reviewed synthetic data"
            )
        record = manifest["files"].get(relative)
        if record != {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }:
            raise rehearsal.RehearsalBlocked("Fixture manifest digest mismatch")
        files[relative] = data
    managed = [
        entry for entry in expected_entries if entry["classification"] == "managed"
    ]
    if sum(entry["bytes"] for entry in managed) > MAX_FIXTURE_BYTES:
        raise rehearsal.RehearsalBlocked(
            "Managed fixture total exceeds the upload limit"
        )
    return managed, files


def verify_migration_guard(profile, engine_factory):
    _assert_disposable_profile(profile)
    engine = engine_factory(profile.migration_url)
    try:
        with engine.begin() as connection:
            rehearsal.guard(connection, profile, head=BASELINE)
    finally:
        engine.dispose()


def _verify_legacy_ledger(profile, entry, engine_factory):
    engine = engine_factory(profile.migration_url)
    try:
        with engine.begin() as connection:
            rehearsal.guard(connection, profile, head=BASELINE)
            connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
            row = connection.execute(
                text("""SELECT n.namespace_id::text,o.path,o.kind,o.classification,
                    o.state,o.tenant_id,o.reservation_token,o.upload_verified,
                    j.requested_by,j.state,j.attempts,j.claim_token,j.lease_until
                    FROM vervfy_storage.objects AS o
                    JOIN vervfy_storage.namespaces AS n ON n.id=o.namespace_id
                    JOIN vervfy_storage.cleanup_jobs AS j ON j.object_id=o.id
                    WHERE o.path=:path"""),
                {"path": entry["legacy_path"]},
            ).one_or_none()
            expected = (
                str(profile.binding.namespace_id),
                entry["legacy_path"],
                "legacy",
                "legacy",
                "hold",
                None,
                None,
                False,
                None,
                "held",
                0,
                None,
                None,
            )
            if row is None or tuple(row) != expected:
                raise rehearsal.RehearsalBlocked(
                    "Shared legacy object must remain unowned and held"
                )
    finally:
        engine.dispose()


def _verify_legacy_references(connection, entry):
    for actor in entry["references"]:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        rows = connection.execute(
            text("""SELECT id,user_id,storage_path FROM public.tracks
                WHERE storage_path=:path ORDER BY id"""),
            {"path": entry["legacy_path"]},
        ).all()
        if [tuple(row) for row in rows] != [
            (f"legacy-{actor}", actor, entry["legacy_path"])
        ]:
            raise rehearsal.RehearsalBlocked(
                "Shared legacy track reference failed tenant RLS verification"
            )


def _assert_disposable_profile(profile):
    config = profile.config
    reference = config.get("project_ref")
    try:
        config_namespace = uuid.UUID(config.get("namespace_id", ""))
    except (TypeError, ValueError):
        config_namespace = None
    if (
        not isinstance(reference, str)
        or rehearsal.production.PROJECT_REF_PATTERN.fullmatch(reference) is None
        or reference
        in {
            rehearsal.production.PRODUCTION_PROJECT_REF,
            rehearsal.production.STAGING_PROJECT_REF,
        }
        or not isinstance(profile.binding.namespace_id, uuid.UUID)
        or not profile.binding.namespace_id.int
        or config_namespace != profile.binding.namespace_id
        or str(profile.binding.namespace_id) == rehearsal.PRODUCTION_NAMESPACE
    ):
        raise rehearsal.RehearsalBlocked("Production and staging targets are forbidden")
    if (
        config.get("purpose") != rehearsal.PURPOSE
        or plan_digest(config) != profile.digest
        or config.get("start_revision") not in rehearsal.SUPPORTED_START_REVISIONS
        or profile.binding.environment != "disposable-rehearsal"
        or profile.binding.endpoint != f"https://{reference}.supabase.co"
        or profile.binding.bucket != config.get("bucket")
        or re.fullmatch(r"vervfy-rehearsal-[a-z0-9-]{1,50}", profile.binding.bucket)
        is None
    ):
        raise rehearsal.RehearsalBlocked("Disposable profile binding is invalid")
    ca_path = None
    for url, role in (
        (profile.migration_url, rehearsal.LOGIN),
        (profile.runtime_url, "app_runtime"),
    ):
        query = dict(url.query)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host != f"db.{reference}.supabase.co"
            or url.port != 5432
            or url.database != "postgres"
            or url.username != role
            or not url.password
            or set(query) != {"sslmode", "sslrootcert"}
            or query.get("sslmode") != "verify-full"
        ):
            raise rehearsal.RehearsalBlocked(
                "Disposable database URLs must be direct and project-bound"
            )
        current_ca = Path(query["sslrootcert"]).resolve(strict=True)
        if ca_path is not None and current_ca != ca_path:
            raise rehearsal.RehearsalBlocked(
                "Database URLs must use the same pinned CA"
            )
        ca_path = current_ca
    if (
        ca_path is None
        or not ca_path.is_file()
        or hashlib.sha256(ca_path.read_bytes()).hexdigest() != config.get("ca_sha256")
    ):
        raise rehearsal.RehearsalBlocked("Disposable database CA pin mismatch")


def _provider_client(profile, key):
    return httpx.Client(
        base_url=profile.binding.endpoint + "/storage/v1",
        headers={**storage_auth_headers(key), "Accept-Encoding": "identity"},
        timeout=httpx.Timeout(connect=5, read=10, write=10, pool=5),
        follow_redirects=False,
    )


def _check_deadline(deadline):
    if time.monotonic() > deadline:
        raise rehearsal.RehearsalBlocked(
            "Storage request exceeded its bounded deadline"
        )


def _read_bounded_response(response, deadline, limit):
    content = bytearray()
    for chunk in response.iter_bytes():
        _check_deadline(deadline)
        content.extend(chunk)
        if len(content) > limit:
            raise rehearsal.RehearsalBlocked("Storage response exceeded its size limit")
    return bytes(content)


def verify_private_bucket(client, bucket):
    deadline = time.monotonic() + NETWORK_DEADLINE_SECONDS
    with client.stream("GET", "/bucket/" + bucket) as response:
        _check_deadline(deadline)
        if (
            response.status_code != 200
            or response.headers.get("content-encoding", "identity") != "identity"
        ):
            raise rehearsal.RehearsalBlocked("Disposable storage bucket check failed")
        body = _read_bounded_response(response, deadline, 65536)
    try:
        payload = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        raise rehearsal.RehearsalBlocked(
            "Disposable storage bucket check failed"
        ) from None
    if not isinstance(payload, dict) or payload.get("public") is not False:
        raise rehearsal.RehearsalBlocked("Disposable storage bucket must be private")


def upload_verified(client, bucket, path, data, content_type):
    """Create once, then require an exact-length full-byte authenticated readback."""
    deadline = time.monotonic() + NETWORK_DEADLINE_SECONDS
    with client.stream(
        "POST",
        f"/object/{bucket}/{path}",
        content=data,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "x-upsert": "false",
            "Cache-Control": "max-age=31536000",
        },
    ) as response:
        _check_deadline(deadline)
        if not 200 <= response.status_code < 300:
            raise rehearsal.RehearsalBlocked(
                "Create-only fixture upload was not confirmed"
            )
        _read_bounded_response(response, deadline, 65536)
    with client.stream("GET", f"/object/authenticated/{bucket}/{path}") as response:
        _check_deadline(deadline)
        if (
            response.status_code != 200
            or response.headers.get("content-encoding", "identity") != "identity"
        ):
            raise rehearsal.RehearsalBlocked("Fixture readback verification failed")
        digest = hashlib.sha256()
        count = 0
        for chunk in response.iter_bytes():
            _check_deadline(deadline)
            count += len(chunk)
            if count > len(data):
                raise rehearsal.RehearsalBlocked("Fixture readback verification failed")
            digest.update(chunk)
        if count != len(data) or digest.digest() != hashlib.sha256(data).digest():
            raise rehearsal.RehearsalBlocked("Fixture readback verification failed")


def _runtime_preflight(connection, profile):
    rehearsal.production._verify_client_tls(connection)
    connection.exec_driver_sql("SET LOCAL search_path TO public")
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
    identity = connection.exec_driver_sql(
        "SELECT current_database(),session_user,current_user"
    ).one()
    if tuple(identity) != ("postgres", "app_runtime", "app_runtime"):
        raise rehearsal.RehearsalBlocked("Fixture uploader runtime identity mismatch")
    attributes = connection.exec_driver_sql(
        """SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication
        FROM pg_catalog.pg_roles WHERE rolname=current_user"""
    ).one()
    if tuple(attributes) != (True, False, False, False, False, False):
        raise rehearsal.RehearsalBlocked(
            "Fixture uploader runtime role is not restricted"
        )
    connection.execute(
        text(
            "SELECT vervfy_storage.validate_namespace(:id,:environment,:endpoint,:bucket)"
        ),
        {
            "id": profile.binding.namespace_id,
            "environment": profile.binding.environment,
            "endpoint": profile.binding.endpoint,
            "bucket": profile.binding.bucket,
        },
    )


def _reserve(connection, profile, actor, kind, extension):
    connection.execute(
        text("SELECT set_config('app.current_user_id',:actor,true)"),
        {"actor": actor},
    )
    row = connection.execute(
        text("SELECT * FROM vervfy_storage.reserve_object(:kind,:extension)"),
        {"kind": kind, "extension": extension},
    ).one()
    connection.execute(
        text("SELECT vervfy_storage.request_cleanup(:id)"),
        {"id": row.object_id},
    )
    path = row.object_path
    expected_path = (
        f"v2/{profile.binding.namespace_id}/{actor}/{kind}/{row.object_id}.{extension}"
    )
    if path != expected_path or not MANAGED_PATH.fullmatch(path):
        raise rehearsal.RehearsalBlocked(
            "Database returned an unexpected fixture identity"
        )
    return row.object_id, row.upload_token, path


def _advance(engine, actor, object_id, token, state):
    with engine.begin() as connection:
        connection.execute(
            text("SELECT set_config('app.current_user_id',:actor,true)"),
            {"actor": actor},
        )
        connection.execute(
            text("SELECT vervfy_storage.advance_upload(:id,:token,:state)"),
            {"id": object_id, "token": token, "state": state},
        )


def upload_bundle(
    profile,
    bundle,
    bundle_digest,
    key,
    *,
    engine_factory=rehearsal.engine_for,
    client_factory=_provider_client,
):
    _assert_disposable_profile(profile)
    entries, files = load_bundle(bundle, profile, bundle_digest)
    _, expected_entries = preparation.fixture_files(profile)
    legacy_entries = [
        entry for entry in expected_entries if entry["classification"] == "legacy"
    ]
    if len(legacy_entries) != 1:
        raise rehearsal.RehearsalBlocked("Expected exactly one shared legacy fixture")
    legacy_entry = legacy_entries[0]
    legacy_data = files.get(legacy_entry["file"])
    if legacy_data is None:
        raise rehearsal.RehearsalBlocked("Shared legacy fixture bytes are missing")
    _verify_legacy_ledger(profile, legacy_entry, engine_factory)
    runtime = engine_factory(profile.runtime_url)
    client = None
    results = []
    try:
        client = client_factory(profile, key)
        with runtime.begin() as connection:
            _runtime_preflight(connection, profile)
            _verify_legacy_references(connection, legacy_entry)
            for actor in rehearsal.TENANTS:
                connection.execute(
                    text("SELECT set_config('app.current_user_id',:actor,true)"),
                    {"actor": actor},
                )
                count = connection.execute(
                    text(
                        "SELECT count(*) FROM vervfy_storage.objects "
                        "WHERE tenant_id=:actor AND classification='managed'"
                    ),
                    {"actor": actor},
                ).scalar_one()
                if count:
                    raise rehearsal.RehearsalBlocked(
                        "Managed fixture identities already exist; do not retry uploads"
                    )
        verify_private_bucket(client, profile.binding.bucket)
        upload_verified(
            client,
            profile.binding.bucket,
            legacy_entry["legacy_path"],
            legacy_data,
            "audio/wav",
        )
        results.append(
            {
                "asset": legacy_entry["asset"],
                "classification": "legacy",
                "path": legacy_entry["legacy_path"],
                "bytes": len(legacy_data),
                "sha256": hashlib.sha256(legacy_data).hexdigest(),
                "references": legacy_entry["references"],
                "ledger_state": "hold",
                "ledger_upload_verified": False,
            }
        )
        for entry in entries:
            actor = entry["tenant"]
            data = files[entry["file"]]
            kind = entry["kind"]
            extension = entry["file"].rsplit(".", 1)[1]
            content_type = "audio/wav" if extension == "wav" else "image/jpeg"
            with runtime.begin() as connection:
                _runtime_preflight(connection, profile)
                object_id, token, path = _reserve(
                    connection, profile, actor, kind, extension
                )
            try:
                _advance(runtime, actor, object_id, token, "uploading")
                upload_verified(
                    client, profile.binding.bucket, path, data, content_type
                )
                _advance(runtime, actor, object_id, token, "ready")
            except BaseException:
                try:
                    _advance(runtime, actor, object_id, token, "hold")
                except SQLAlchemyError:
                    print(
                        f"WARNING: fixture reservation {object_id} could not be marked held",
                        file=sys.stderr,
                    )
                raise
            results.append(
                {
                    "asset": entry["asset"],
                    "object_id": str(object_id),
                    "path": path,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        with runtime.begin() as connection:
            _runtime_preflight(connection, profile)
            _verify_legacy_references(connection, legacy_entry)
        return results
    finally:
        if client is not None:
            client.close()
        runtime.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--confirm-disposable-project", required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        profile, key = load_profile(
            args.config,
            args.config_sha256,
            args.ca_file,
            args.confirm_disposable_project,
        )
        results = upload_bundle(profile, args.bundle_dir, args.bundle_sha256, key)
        print(json.dumps({"uploaded": results}, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - never echo credentials/provider responses
        print(
            f"BLOCKED: disposable fixture upload ({type(exc).__name__}); no deletion attempted",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
