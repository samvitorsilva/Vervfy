"""Guarded plan/apply for unknown ledger sizes; never deletes provider objects."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from scripts import storage_production_migration as runner
from storage_auth_headers import storage_auth_headers
from storage_inventory import (
    InventoryBlocked,
    apply_inventory,
    measure_inventory,
    plan_digest,
    snapshot,
)
from storage_namespace import NamespaceBinding


class ReadOnlyObserver:
    """Two complete matching reads under one absolute network deadline."""

    def __init__(self, client_factory, binding, *, max_bytes=10 * 1024**3, deadline=60):
        if type(max_bytes) is not int or max_bytes <= 0 or not 0 < deadline <= 60:
            raise InventoryBlocked("Positive bounded observation limits required")
        self.client_factory, self.binding = client_factory, binding
        self.max_bytes, self.deadline = max_bytes, deadline

    def __call__(self, path):
        if (
            not isinstance(path, str)
            or len(path) > 600
            or "\\" in path
            or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or any(part in {"", ".", ".."} for part in path.split("/"))
        ):
            raise InventoryBlocked("Unsafe inventory object path")
        try:
            return asyncio.run(self._observe(path))
        except (TimeoutError, httpx.HTTPError, ValueError):
            raise InventoryBlocked("Provider observation failed or timed out") from None

    async def _observe(self, path):
        url = (
            self.binding.endpoint
            + "/storage/v1/object/authenticated/"
            + quote(self.binding.bucket, safe="")
            + "/"
            + quote(path, safe="/")
        )
        client = self.client_factory()
        try:
            async with asyncio.timeout(self.deadline):
                observations = []
                for _ in range(2):
                    count, digest = 0, hashlib.sha256()
                    async with client.stream(
                        "GET", url, headers={"Accept-Encoding": "identity"}
                    ) as response:
                        etag = response.headers.get("etag")
                        if (
                            response.status_code != 200
                            or not etag
                            or etag.startswith("W/")
                            or response.headers.get("content-encoding", "identity")
                            != "identity"
                        ):
                            raise InventoryBlocked(
                                "Object is missing, unversioned, or unreadable"
                            )
                        async for chunk in response.aiter_bytes():
                            count += len(chunk)
                            if count > self.max_bytes:
                                raise InventoryBlocked(
                                    "Object observation exceeded its size bound"
                                )
                            digest.update(chunk)
                        length = response.headers.get("content-length")
                        if not count or (length is not None and int(length) != count):
                            raise InventoryBlocked(
                                "Complete positive-size object read was not confirmed"
                            )
                        observations.append(
                            {"bytes": count, "sha256": digest.hexdigest(), "etag": etag}
                        )
                if observations[0] != observations[1]:
                    raise InventoryBlocked("Object changed during observation")
                return observations[0]
        finally:
            async with asyncio.timeout(5):
                await client.aclose()


def verify_connection(connection, target):
    """Check the actual plan/apply transaction, not a different connection."""
    runner._verify_client_tls(connection)
    identity = connection.exec_driver_sql(
        "SELECT current_database(),session_user,current_user"
    ).one()
    if tuple(identity) != (target.database, target.username, target.username):
        raise InventoryBlocked("Inventory connection identity mismatch")
    runner._check_role_graph(connection, target.username)
    runner._verify_followup_result(connection, installation=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply"))
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--confirm-project-ref", required=True)
    parser.add_argument("--confirm-uploads-paused", action="store_true", required=True)
    parser.add_argument("--approved-sha256")
    parser.add_argument("--authorization-expires-at")
    args = parser.parse_args(argv)
    engine = None
    try:
        runner.validate_migration_chain()
        target = runner.load_target()
        if args.confirm_project_ref != target.project_ref:
            raise InventoryBlocked("Project confirmation mismatch")
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
        if args.operation == "plan":
            key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
            if not key:
                raise InventoryBlocked(
                    "Read-only provider observation credential is required"
                )
            with engine.begin() as c:
                c.exec_driver_sql("SET TRANSACTION READ ONLY")
                verify_connection(c, target)
                before = snapshot(c, binding)

            def client_factory():
                return httpx.AsyncClient(
                    headers=storage_auth_headers(key),
                    timeout=httpx.Timeout(5),
                    follow_redirects=False,
                    trust_env=False,
                )

            plan = measure_inventory(before, ReadOnlyObserver(client_factory, binding))
            fd = os.open(args.plan_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                json.dump(plan, out, sort_keys=True, indent=2)
            print("Read-only plan SHA-256: " + plan_digest(plan))
        else:
            if args.plan_file.stat().st_size > 16 * 1024 * 1024:
                raise InventoryBlocked("Inventory plan exceeds the input size bound")
            plan = json.loads(args.plan_file.read_text())
            with engine.begin() as c:
                verify_connection(c, target)
                runner.validate_authorization(args.authorization_expires_at)
                changed = apply_inventory(
                    c, binding, plan, args.approved_sha256, now=datetime.now(UTC)
                )
            print(
                f"Reconciled {changed} unknown ledger charges; physical cleanup remains disabled"
            )
        return 0
    except Exception as exc:  # noqa: BLE001 - redact credential-bearing provider/database details
        print(
            f"BLOCKED: inventory operation failed ({type(exc).__name__}); no deletion authorized",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
