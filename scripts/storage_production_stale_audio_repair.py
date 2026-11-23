"""Detach two audited missing audio references and retain quota as held tombstones."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from scripts import storage_production_migration as runner
from storage_internal_acl import check_internal_acls
from storage_inventory import InventoryBlocked, plan_digest
from storage_namespace import NamespaceBinding
from storage_stale_audio import (
    charge_stale_audio_tombstones,
    detach_stale_audio_references,
    plan_stale_audio_repair,
)

MAX_PLAN_BYTES = 1024 * 1024
TARGET_PATTERN = re.compile(r"([0-9a-f]{32}):([1-9][0-9]*)\Z")


def _write_plan(path: Path, plan: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(plan, stream, sort_keys=True, indent=2)


def _target_sizes(values: list[str]) -> dict[str, int]:
    result = {}
    for value in values:
        match = TARGET_PATTERN.fullmatch(value)
        if match is None:
            raise InventoryBlocked(
                "Each target must be an MD5 path hash and positive byte count"
            )
        path_hash, size = match.groups()
        if path_hash in result:
            raise InventoryBlocked("Duplicate stale-audio path hash")
        result[path_hash] = int(size)
    return result


def _runtime_engine(target):
    raw = os.environ.get("VERVFY_PRODUCTION_RUNTIME_DATABASE_URL", "").strip()
    if not raw:
        raise InventoryBlocked("VERVFY_PRODUCTION_RUNTIME_DATABASE_URL is required")
    try:
        url = runner.make_url(raw)
    except Exception:  # noqa: BLE001 - avoid exposing credential-bearing details
        raise InventoryBlocked("Runtime database URL is invalid") from None
    expected_user = (
        "app_runtime"
        if target.connection_mode == "direct"
        else f"app_runtime.{target.project_ref}"
    )
    if (
        url.drivername != target.url.drivername
        or url.host != target.url.host
        or url.port != target.url.port
        or url.database != target.database
        or url.username != expected_user
        or not url.password
        or dict(url.query) != dict(target.url.query)
    ):
        raise InventoryBlocked(
            "Runtime URL must use the approved project endpoint, TLS settings, and app_runtime login"
        )
    return create_engine(url, poolclass=NullPool, pool_pre_ping=True)


def _strict_checks(connection, runtime=None) -> None:
    runner._verify_client_tls(connection)
    if runtime is not None:
        runner._verify_client_tls(runtime)
    runner._check_auth_sessions(connection, expected_exists=True)
    check_internal_acls(connection)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply"))
    parser.add_argument("--stage", choices=("detach", "charge"), required=True)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--confirm-project-ref", required=True)
    parser.add_argument("--target", action="append", required=True, metavar="MD5:BYTES")
    parser.add_argument(
        "--confirm-storage-writers-paused", action="store_true", required=True
    )
    parser.add_argument(
        "--confirm-no-alternative-copies", action="store_true", required=True
    )
    parser.add_argument("--approved-sha256")
    parser.add_argument("--authorization-expires-at")
    args = parser.parse_args(argv)
    migration_engine = runtime_engine = None
    detached = False
    try:
        runner.validate_migration_chain()
        target = runner.load_target()
        if args.confirm_project_ref != target.project_ref:
            raise InventoryBlocked("Project confirmation mismatch")
        sizes = _target_sizes(args.target)
        runtime_engine = _runtime_engine(target)
        migration_engine = runner._engine(target)
        binding = NamespaceBinding(
            uuid.UUID("31daf7cc-8563-411f-94c7-944d607d1ef1"),
            "production",
            f"https://{target.project_ref}.supabase.co",
            "songs",
        )
        if args.operation == "plan":
            with (
                runtime_engine.connect() as runtime,
                migration_engine.connect() as migration,
                runtime.begin(),
                migration.begin(),
            ):
                _strict_checks(migration, runtime)
                plan = plan_stale_audio_repair(
                    runtime,
                    migration,
                    binding,
                    sizes,
                    stage=args.stage,
                    confirmed_catalog_absence=args.confirm_no_alternative_copies,
                )
            _write_plan(args.plan_file, plan)
            print(
                f"Read-only stale-audio plan for {len(plan['targets'])} tracks; "
                f"SHA-256: {plan_digest(plan)}"
            )
        else:
            if not args.approved_sha256 or not args.authorization_expires_at:
                raise InventoryBlocked("Apply requires digest approval and expiry")
            runner.validate_authorization(args.authorization_expires_at)
            if args.plan_file.stat().st_size > MAX_PLAN_BYTES:
                raise InventoryBlocked("Stale-audio plan exceeds the input size bound")
            plan = json.loads(args.plan_file.read_text())
            if {
                item["path_hash"]: item["size_bytes"] for item in plan["targets"]
            } != sizes:
                raise InventoryBlocked(
                    "Plan targets differ from the approved path hashes and sizes"
                )
            if plan.get("stage") != args.stage:
                raise InventoryBlocked(
                    "Plan stage differs from the requested operation"
                )
            if args.stage == "detach":
                with (
                    runtime_engine.connect() as runtime,
                    migration_engine.connect() as migration,
                    runtime.begin(),
                    migration.begin(),
                ):
                    _strict_checks(migration, runtime)
                    detached_count = detach_stale_audio_references(
                        runtime,
                        migration,
                        binding,
                        plan,
                        args.approved_sha256,
                    )
                detached = True
                print(
                    f"Detached {detached_count} stale references; held tombstones await "
                    "the separately approved 0034 migration and positive quota charge"
                )
            else:
                detached = True
                with (
                    runtime_engine.begin() as runtime,
                    migration_engine.connect() as migration,
                    migration.begin(),
                ):
                    _strict_checks(migration, runtime)
                    charged_count = charge_stale_audio_tombstones(
                        runtime,
                        migration,
                        binding,
                        plan,
                        args.approved_sha256,
                    )
                print(
                    f"Positively charged {charged_count} held tombstones from historical "
                    "track sizes; no files or track records deleted"
                )
        return 0
    except Exception as exc:  # noqa: BLE001 - redact credential-bearing details
        prefix = "PARTIAL" if detached else "BLOCKED"
        print(
            f"{prefix}: stale-audio repair stopped ({type(exc).__name__}); "
            "if detached, quota remains fail-closed until the approved plan is retried",
            file=sys.stderr,
        )
        return 1
    finally:
        if migration_engine is not None:
            migration_engine.dispose()
        if runtime_engine is not None:
            runtime_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
