"""Ops-only reconciliation of unknown ledger sizes from approved byte evidence.

No provider writes, ownership adoption, charge reduction, or deletion. All
storage writers must be paused through plan collection, review, and commit.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from storage_namespace import NamespaceBinding

REVISION = "0034_storage_byte_reservations"
MAX_AGE = timedelta(minutes=15)


class InventoryBlocked(RuntimeError):
    pass


def plan_digest(plan: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


@contextmanager
def _owner(connection):
    # SQL errors roll back role selection with the savepoint, too.
    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
        yield
        connection.exec_driver_sql("RESET ROLE")


def snapshot(connection, binding: NamespaceBinding) -> dict:
    """Read via the existing restricted lifecycle-owner capability; no grants."""
    if connection.dialect.name != "postgresql" or not connection.in_transaction():
        raise InventoryBlocked("An explicit PostgreSQL transaction is required")
    role = connection.exec_driver_sql("""SELECT current_user=session_user,
        pg_has_role(current_user,'vervfy_storage_lifecycle_owner','SET'),
        rolsuper OR rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=current_user""").one()
    if tuple(role) != (True, True, False):
        raise InventoryBlocked(
            "A restricted migration login with SET owner capability is required"
        )
    if (
        connection.exec_driver_sql("SHOW transaction_isolation").scalar_one()
        != "read committed"
    ):
        raise InventoryBlocked("Inventory requires READ COMMITTED")
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
    if connection.execute(
        text("SELECT version_num FROM public.alembic_version")
    ).scalars().all() != [REVISION]:
        raise InventoryBlocked("Inventory requires exactly migration 0034")
    with _owner(connection):
        actual = connection.exec_driver_sql("""SELECT namespace_id::text,environment,endpoint,bucket,
            physical_cleanup_enabled FROM vervfy_storage.namespaces WHERE id=1""").one()
        expected = (
            str(binding.namespace_id),
            binding.environment,
            binding.endpoint,
            binding.bucket,
            False,
        )
        if tuple(actual) != expected:
            raise InventoryBlocked("Immutable namespace mismatch or cleanup enabled")
        unsafe = connection.exec_driver_sql("""SELECT count(*) FROM pg_catalog.pg_class
            WHERE oid IN ('vervfy_storage.namespaces'::regclass,'vervfy_storage.objects'::regclass,
              'vervfy_storage.cleanup_jobs'::regclass,'vervfy_storage.quota_policy'::regclass)
            AND NOT (relrowsecurity AND relforcerowsecurity)""").scalar_one()
        claims = connection.exec_driver_sql("""SELECT
            has_function_privilege('app_runtime','vervfy_storage.claim_next_cleanup()','EXECUTE') OR
            has_function_privilege('storage_cleanup_worker','vervfy_storage.claim_next_cleanup()','EXECUTE') OR
            has_function_privilege('vervfy_storage_cleanup','vervfy_storage.claim_next_cleanup()','EXECUTE')
        """).scalar_one()
        if unsafe or claims:
            raise InventoryBlocked("RLS or cleanup-claim guards are not intact")
        rows = (
            connection.exec_driver_sql("""SELECT id::text,namespace_id,tenant_id,path,kind,
            classification,state,reservation_token::text,upload_verified,created_at::text,reserved_bytes
            FROM vervfy_storage.objects ORDER BY path COLLATE "C"
        """)
            .mappings()
            .all()
        )
        return {"namespace": list(expected), "objects": [dict(row) for row in rows]}


def measure_inventory(before: dict, observe, *, now=None) -> dict:
    """No SQL transaction during I/O. Observe must finish two matching full reads."""
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    observations = {}
    for row in before["objects"]:
        if row["reserved_bytes"] is not None:
            continue
        if row["state"] in {"reserved", "uploading", "deleting"}:
            raise InventoryBlocked(
                "An unknown-size object still has an active operation"
            )
        measurement = observe(row["path"])
        if (
            set(measurement) != {"bytes", "sha256", "etag"}
            or type(measurement["bytes"]) is not int
            or not 0 < measurement["bytes"] <= 2**63 - 1
            or not isinstance(measurement["sha256"], str)
            or len(measurement["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in measurement["sha256"])
            or not isinstance(measurement["etag"], str)
            or not measurement["etag"]
            or measurement["etag"].startswith("W/")
        ):
            raise InventoryBlocked("Complete positive-size byte evidence is required")
        observations[row["id"]] = measurement
    return {
        "version": 1,
        "measured_at": timestamp,
        "snapshot": before,
        "observations": observations,
    }


def apply_inventory(
    connection, binding: NamespaceBinding, plan: dict, approved_digest: str, *, now=None
) -> int:
    """Fill only NULL charges atomically. Exact replay is harmless, never a refund."""
    if plan_digest(plan) != approved_digest:
        raise InventoryBlocked("Plan digest does not match independent approval")
    if (
        set(plan) != {"version", "measured_at", "snapshot", "observations"}
        or type(plan["version"]) is not int
        or plan["version"] != 1
    ):
        raise InventoryBlocked("Unknown inventory plan format")
    measured = datetime.fromisoformat(plan["measured_at"])
    current = now or datetime.now(UTC)
    if measured.tzinfo is None or not timedelta(0) <= current - measured <= MAX_AGE:
        raise InventoryBlocked("Inventory evidence is expired or future dated")
    observations = plan["observations"]
    unknown = [r for r in plan["snapshot"]["objects"] if r["reserved_bytes"] is None]
    if set(observations) != {r["id"] for r in unknown}:
        raise InventoryBlocked("Inventory must cover exactly all unknown ledger rows")
    by_path = {r["path"]: observations[r["id"]] for r in unknown}
    measure_inventory(plan["snapshot"], by_path.__getitem__, now=measured)
    with connection.begin_nested():
        snapshot(connection, binding)
        # Same quota-policy serialization order as reserve_sized_object().
        with _owner(connection):
            connection.exec_driver_sql(
                "SELECT id FROM vervfy_storage.quota_policy WHERE id=1 FOR UPDATE"
            ).one()
            connection.exec_driver_sql(
                "LOCK TABLE vervfy_storage.objects IN SHARE ROW EXCLUSIVE MODE"
            )
        actual = snapshot(connection, binding)
        original = plan["snapshot"]
        if actual != original:
            completed = json.loads(json.dumps(original))
            for row in completed["objects"]:
                if row["id"] in observations:
                    row["reserved_bytes"] = observations[row["id"]]["bytes"]
            if actual == completed:
                return 0
            raise InventoryBlocked(
                "Ledger changed since measurement; collect a fresh plan"
            )
        with _owner(connection):
            for object_id, evidence in observations.items():
                changed = connection.execute(
                    text("""UPDATE vervfy_storage.objects SET reserved_bytes=:bytes
                    WHERE id=:id AND reserved_bytes IS NULL"""),
                    {"id": object_id, "bytes": evidence["bytes"]},
                )
                if changed.rowcount != 1:
                    raise InventoryBlocked("Unknown-size charge was not confirmed")
        return len(observations)
