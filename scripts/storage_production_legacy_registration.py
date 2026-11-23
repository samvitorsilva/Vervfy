"""Plan/apply referenced legacy registration before migration 0034."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import storage_production_migration as runner
from storage_inventory import InventoryBlocked, plan_digest
from storage_legacy_registration import apply_registration, plan_registration
from storage_namespace import NamespaceBinding

MAX_PLAN_BYTES = 16 * 1024 * 1024


def _write_plan(path: Path, plan: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(plan, stream, sort_keys=True, indent=2)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply"))
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--confirm-project-ref", required=True)
    parser.add_argument("--confirm-uploads-paused", action="store_true", required=True)
    parser.add_argument("--expected-unregistered-count", type=int, required=True)
    parser.add_argument("--approved-sha256")
    parser.add_argument("--authorization-expires-at")
    args = parser.parse_args(argv)
    engine = None
    try:
        runner.validate_migration_chain()
        target = runner.load_target()
        if target.start_revision not in {
            runner.AUTH_SESSIONS_REVISION,
            runner.CLAIMS_DISABLED_REVISION,
        }:
            raise InventoryBlocked(
                "Legacy registration supports only revision 0032 or 0033"
            )
        if args.confirm_project_ref != target.project_ref:
            raise InventoryBlocked("Project confirmation mismatch")
        if args.expected_unregistered_count < 0:
            raise InventoryBlocked("Expected path count cannot be negative")
        if args.operation == "apply":
            if not args.approved_sha256 or not args.authorization_expires_at:
                raise InventoryBlocked(
                    "Apply requires independent plan digest approval and expiry"
                )
            runner.validate_authorization(args.authorization_expires_at)

        binding = NamespaceBinding(
            uuid.UUID("31daf7cc-8563-411f-94c7-944d607d1ef1"),
            "production",
            f"https://{target.project_ref}.supabase.co",
            "songs",
        )
        engine = runner._engine(target)
        with engine.connect() as connection:
            runner.preflight(connection, target)
            if args.operation == "plan":
                with connection.begin():
                    plan = plan_registration(
                        connection,
                        binding,
                        expected_missing_count=args.expected_unregistered_count,
                    )
                _write_plan(args.plan_file, plan)
                print(
                    f"Read-only plan: {len(plan['registrations'])} legacy paths; "
                    f"SHA-256: {plan_digest(plan)}"
                )
            else:
                if args.plan_file.stat().st_size > MAX_PLAN_BYTES:
                    raise InventoryBlocked(
                        "Legacy registration plan exceeds the input size bound"
                    )
                plan = json.loads(args.plan_file.read_text())
                if (
                    len(plan.get("registrations", ()))
                    != args.expected_unregistered_count
                ):
                    raise InventoryBlocked("Plan path count differs from approval")
                runner.validate_authorization(args.authorization_expires_at)
                with connection.begin():
                    changed = apply_registration(
                        connection,
                        binding,
                        plan,
                        args.approved_sha256,
                    )
        if args.operation == "apply":
            runner.run_check(target)
            print(
                f"Registered {changed} held, unowned legacy paths; "
                "no provider objects, references, or cleanup jobs changed"
            )
        return 0
    except Exception as exc:  # noqa: BLE001 - redact credential-bearing details
        print(
            f"BLOCKED: legacy registration stopped ({type(exc).__name__}); "
            "no provider writes or deletions authorized",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
