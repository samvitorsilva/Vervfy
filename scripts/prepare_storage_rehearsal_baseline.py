"""Prepare a private offline 0031/0033 baseline review bundle; never connect or execute SQL."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from sqlalchemy.engine import URL

from scripts import storage_rehearsal as rehearsal
from storage_inventory import plan_digest

ROLES = {
    rehearsal.LOGIN: {"login": True, "inherit": False},
    "app_runtime": {"login": True, "inherit": True},
    "google_auth_lookup": {"login": True, "inherit": False},
    "vervfy_identity_lookup_owner": {"login": False, "inherit": False},
    "vervfy_identity_lookup": {"login": False, "inherit": False},
    "vervfy_storage_lifecycle_owner": {"login": False, "inherit": False},
    "vervfy_storage_cleanup": {"login": False, "inherit": False},
    "storage_cleanup_worker": {"login": True, "inherit": False},
}


def load_offline_profile(config_path, approved_digest, ca_file, confirm_project):
    """Reuse target/history/CA rules with dummy credentials, never inherited secrets."""
    config = rehearsal.read_private(config_path)
    if config.get("project_ref") != confirm_project:
        raise rehearsal.RehearsalBlocked("Disposable project confirmation mismatch")
    ca = Path(ca_file).resolve(strict=True)
    # These are validation-only URLs: no engine/client is constructed here.
    migration = URL.create(
        "postgresql+psycopg",
        username=rehearsal.LOGIN,
        password="offline-validation-only",
        host=f"db.{confirm_project}.supabase.co",
        port=5432,
        database="postgres",
        query={"sslmode": "verify-full", "sslrootcert": str(ca)},
    )
    env = {
        "VERVFY_ENVIRONMENT": "disposable-storage-rehearsal",
        "VERVFY_REHEARSAL_CA_FILE": str(ca),
        "VERVFY_REHEARSAL_DATABASE_URL": migration.render_as_string(
            hide_password=False
        ),
        "VERVFY_REHEARSAL_RUNTIME_URL": migration.set(
            username="app_runtime"
        ).render_as_string(hide_password=False),
    }
    return rehearsal.load_profile(config_path, approved_digest, env)


def preflight_sql(profile):
    """A read-only DBA check, not a substitute for direct-host/TLS target validation."""
    config = profile.config
    role_values = ",\n".join(
        f"('{name}',{str(v['login']).lower()},{str(v['inherit']).lower()})"
        for name, v in ROLES.items()
    )
    # All interpolated values passed the existing strict profile validator.
    return f"""-- Prepared only. Requires a separately guarded disposable postgres connection.
-- The DBA must first attest this exact project/config in the private marker.
BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';
DO $baseline$
BEGIN
 IF current_database()<>'postgres' OR session_user<>'postgres' OR current_user<>'postgres'
 OR current_setting('server_version_num')::integer<160000
 OR NOT EXISTS(SELECT 1 FROM pg_stat_ssl WHERE pid=pg_backend_pid() AND ssl)
 THEN RAISE EXCEPTION 'Wrong baseline administrator, database, version or TLS'; END IF;
 IF to_regclass('vervfy_rehearsal.provisioning_approval') IS NULL THEN
   RAISE EXCEPTION 'Independent disposable provisioning approval is missing'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_class WHERE oid='vervfy_rehearsal.provisioning_approval'::regclass
               AND relowner='postgres'::regrole)
 THEN RAISE EXCEPTION 'Provisioning approval must be independently DBA-owned'; END IF;
 IF (SELECT count(*) FROM vervfy_rehearsal.provisioning_approval)<>1 OR NOT EXISTS(
   SELECT 1 FROM vervfy_rehearsal.provisioning_approval
   WHERE project_ref='{config["project_ref"]}' AND run_id='{config["run_id"]}'::uuid
   AND config_sha256='{profile.digest}' AND disposable IS TRUE
 ) THEN RAISE EXCEPTION 'Disposable provisioning identity mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S'))
 OR to_regnamespace('vervfy_storage') IS NOT NULL OR to_regnamespace('vervfy_auth') IS NOT NULL
 THEN RAISE EXCEPTION 'Fresh disposable application schema required; preserve existing objects'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=current_user AND rolcreaterole AND rolbypassrls)
 THEN RAISE EXCEPTION 'Required existing DBA bootstrap capability is unavailable'; END IF;
 IF (SELECT count(*) FROM (VALUES
 {role_values}
 ) AS expected(name,canlogin,inherit_role) JOIN pg_roles r ON r.rolname=expected.name
 WHERE r.rolcanlogin=expected.canlogin AND r.rolinherit=expected.inherit_role
 AND NOT(r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication))<>8
 THEN RAISE EXCEPTION 'Preprovision exact restricted roles; never add privilege workarounds'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='public'
               AND nspowner='{rehearsal.LOGIN}'::regrole)
 THEN RAISE EXCEPTION 'Restricted migrator must own the fresh public schema'; END IF;
END $baseline$;
COMMIT;
"""


def fixture_files(profile):
    audio = io.BytesIO()
    with wave.open(audio, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(8000)
        target.writeframes(b"\0\0" * 80)
    image = io.BytesIO()
    Image.new("RGB", (2, 2), (16, 25, 29)).save(image, format="JPEG")
    files = {"fixtures/shared.wav": audio.getvalue()}
    entries = [
        {
            "asset": "shared-legacy",
            "tenant": None,
            "kind": "legacy",
            "file": "fixtures/shared.wav",
            "legacy_path": f"legacy/rehearsal-{profile.config['run_id']}/shared.wav",
            "references": ["a", "b"],
            "classification": "legacy",
            "state": "hold",
        }
    ]
    for actor in rehearsal.TENANTS:
        for kind in ("audio", "track-cover", "artist-photo", "staged-audio"):
            extension = "wav" if kind in {"audio", "staged-audio"} else "jpg"
            relative = f"fixtures/{actor}-{kind}.{extension}"
            files[relative] = (
                audio.getvalue() if extension == "wav" else image.getvalue()
            )
            entries.append(
                {
                    "asset": f"{actor}-{kind}",
                    "tenant": actor,
                    "kind": kind,
                    "file": relative,
                    "reservation_path_pattern": f"v2/{profile.binding.namespace_id}/{actor}/{kind}/{{object_uuid}}.{extension}",
                    "classification": "managed",
                    "attach_only_after": "create-only provider upload and verified matching read; no direct verified-flag assignment",
                }
            )
    for entry in entries:
        data = files[entry["file"]]
        entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return files, entries


def prepare(config_path, approved_digest, ca_file, confirm_project, output):
    profile = load_offline_profile(
        config_path, approved_digest, ca_file, confirm_project
    )
    files, entries = fixture_files(profile)
    memberships = [
        {
            "role": role,
            "member": member,
            "grantor": "postgres",
            "admin": False,
            "inherit": inherit,
            "set": can_set,
        }
        for role, member, inherit, can_set in (
            ("vervfy_identity_lookup_owner", rehearsal.LOGIN, False, True),
            ("vervfy_identity_lookup", "google_auth_lookup", True, False),
            ("vervfy_storage_lifecycle_owner", rehearsal.LOGIN, False, True),
            ("vervfy_storage_cleanup", "storage_cleanup_worker", True, False),
        )
    ]
    role_plan = {
        "roles": ROLES,
        "all_roles_forbid": [
            "superuser",
            "bypassrls",
            "createdb",
            "createrole",
            "replication",
        ],
        "memberships": memberships,
        "permitted_optional_memberships": [
            {
                "role": role,
                "member": "postgres",
                "grantor": "postgres",
                "admin": True,
                "inherit": False,
                "set": False,
            }
            for role in (
                "vervfy_storage_lifecycle_owner",
                "vervfy_storage_cleanup",
            )
        ],
        "public_schema_owner": rehearsal.LOGIN,
        "managed_grants": "Preserve only the existing reviewed Supabase-managed exceptions; unchanged migrations remain authoritative",
        "passwords": "Set LOGIN passwords only through the disposable secret-management process; none in this bundle",
    }
    phases = [
        {
            "phase": "0-project-and-roles",
            "required": "Independently validate the disposable project's direct host/TLS/CA, then use storage_rehearsal_provision.py bootstrap to create only the reviewed roles, memberships, fresh-schema prerequisites and private approval marker; run the read-only preflight",
        },
        {
            "phase": "1-through-0031",
            "required": "Use storage_rehearsal_provision.py baseline-0031 to apply unchanged migrations through 0028, seed only synthetic tenants a/b and their shared legacy references under tenant contexts, then apply unchanged 0029-0031 in one transaction; stop on any guard failure and never stamp",
        },
        {
            "phase": "2-namespace-and-legacy-ledger",
            "required": "At exactly 0031, use storage_rehearsal_provision.py initialize-namespace with the DBA, then seed-legacy with the restricted migrator; the legacy object remains unowned, held and upload-unverified",
        },
        {
            "phase": "3-provider-fixtures",
            "required": "Use the create-only uploader for the shared legacy WAV and eight managed assets; it verifies the pre-trigger shared track references independently under each tenant's RLS context. Keep the legacy ledger held and upload-unverified; never fabricate verification values or run cleanup",
        },
        {
            "phase": "4-optional-0033",
            "required": "For a 0033 profile only, use storage_rehearsal_provision.py baseline-0033 after namespace initialization and held legacy registration; this applies unchanged 0032/0033 and verifies the disabled claim permissions",
        },
        {
            "phase": "5-approval-and-snapshot",
            "required": "For a 0031 profile, use storage_rehearsal_provision.py approve-0031 after held legacy registration; then verify the exact baseline and use the existing storage_rehearsal snapshot/recover/upgrade/verify/plan/apply workflow",
        },
    ]
    binding = {
        "namespace_id": str(profile.binding.namespace_id),
        "environment": profile.binding.environment,
        "endpoint": profile.binding.endpoint,
        "bucket": profile.binding.bucket,
        "physical_cleanup_enabled": False,
    }
    payloads = {
        "config.json": json.dumps(profile.config, sort_keys=True, indent=2).encode(),
        "01-preflight.sql": preflight_sql(profile).encode(),
        "02-role-requirements.json": json.dumps(
            role_plan, sort_keys=True, indent=2
        ).encode(),
        "03-baseline-phases.json": json.dumps(
            {
                "baseline": profile.config["start_revision"],
                "binding": binding,
                "phases": phases,
            },
            sort_keys=True,
            indent=2,
        ).encode(),
        "04-fixtures.json": json.dumps(
            {
                "entries": entries,
                "total_bytes": sum(e["bytes"] for e in entries),
                "physical_cleanup_enabled": False,
            },
            sort_keys=True,
            indent=2,
        ).encode(),
        **files,
    }
    manifest = {
        "purpose": "vervfy-disposable-baseline-review-bundle-v1",
        "config_sha256": profile.digest,
        "project_ref": confirm_project,
        "run_id": profile.config["run_id"],
        "baseline": profile.config["start_revision"],
        "ready_for_hosted_execution": False,
        "blockers": [
            "independent review and hosted acceptance of disposable-only bootstrap/baseline/legacy-ledger executor",
            "approved disposable Free-tier project, target credentials, verified CA and provider connectivity",
            "hosted legacy/managed provider upload-readback and tenant-RLS validation",
            "hosted 0031/0033 rehearsal plus backup/restore readiness",
        ],
        "files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in payloads.items()
        },
    }
    output = Path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    (output / "fixtures").mkdir(mode=0o700)
    for name, data in payloads.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as target:
            target.write(data)
    rehearsal.write_private(output / "manifest.json", manifest)
    return plan_digest(manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--confirm-disposable-project", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        digest = prepare(
            args.config,
            args.config_sha256,
            args.ca_file,
            args.confirm_disposable_project,
            args.output_dir,
        )
        print("Offline review bundle SHA-256: " + digest)
        return 0
    except Exception as exc:  # noqa: BLE001 - never echo credentials or filesystem contents
        print(
            f"BLOCKED: offline baseline preparation ({type(exc).__name__}); no database or provider execution",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
