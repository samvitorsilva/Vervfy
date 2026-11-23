"""Ops-only reconciliation of unknown ledger sizes from approved byte evidence.

No provider writes, ownership adoption, charge reduction, or deletion. All
storage writers must be paused through plan collection, review, and commit.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from storage_namespace import NamespaceBinding

REVISION = "0034_storage_byte_reservations"
MAX_AGE = timedelta(minutes=15)
PLAN_VERSION = 2
MAX_CONCURRENT_OBSERVATIONS = 16
INVENTORY_REASON_CODES = frozenset(
    {
        "INVENTORY_BLOCKED",
        "PROVIDER_EVIDENCE_INVALID",
        "EVIDENCE_TIMESTAMP_INVALID",
        "EVIDENCE_TIMEZONE_MISSING",
        "TRANSACTION_REQUIRED",
        "ROLE_CAPABILITY_REQUIRED",
        "ISOLATION_MISMATCH",
        "REVISION_MISMATCH",
        "NAMESPACE_GUARD_MISMATCH",
        "SECURITY_GUARD_DRIFT",
        "CONCURRENCY_OUT_OF_BOUNDS",
        "ACTIVE_UNKNOWN_OBJECT",
        "EVIDENCE_STALE_OR_FUTURE",
        "PLAN_FORMAT_INVALID",
        "APPROVAL_DIGEST_INVALID",
        "PLAN_DIGEST_INVALID",
        "APPROVAL_DIGEST_MISMATCH",
        "APPLY_TIMEZONE_MISSING",
        "SNAPSHOT_FORMAT_INVALID",
        "OBSERVATION_COVERAGE_MISMATCH",
        "LEDGER_SNAPSHOT_CHANGED",
        "CHARGE_UPDATE_UNCONFIRMED",
        "OBSERVATION_LIMITS_INVALID",
        "OBJECT_KEY_UNSAFE",
        "PROVIDER_TIMEOUT_OR_ERROR",
        "OBJECT_MISSING_OR_UNREADABLE",
        "OBJECT_SIZE_LIMIT",
        "OBJECT_READ_INCOMPLETE",
        "OBJECT_CHANGED_DURING_READ",
        "CONNECTION_IDENTITY_MISMATCH",
        "PROJECT_CONFIRMATION_MISMATCH",
        "INDEPENDENT_APPROVAL_REQUIRED",
        "PROVIDER_CREDENTIAL_MISSING",
        "PLAN_SIZE_LIMIT",
        "PROVIDER_RETRY_EXHAUSTED",
        "PROVIDER_DEADLINE_EXCEEDED",
        "PROVIDER_CONNECTION_ERROR",
        "PROVIDER_AUTH_REJECTED",
        "OBJECT_NOT_FOUND",
        "PROVIDER_HTTP_REJECTED",
        "OBJECT_ETAG_INVALID",
        "OBJECT_CONTENT_ENCODING_INVALID",
        "OBJECT_CONTENT_LENGTH_INVALID",
    }
)


class InventoryBlocked(RuntimeError):
    def __init__(self, message: str, *, reason_code="INVENTORY_BLOCKED"):
        super().__init__(message)
        self.reason_code = (
            reason_code
            if isinstance(reason_code, str) and reason_code in INVENTORY_REASON_CODES
            else "INVENTORY_BLOCKED"
        )


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


def is_strong_etag(etag) -> bool:
    return (
        isinstance(etag, str)
        and len(etag) >= 2
        and etag[0] == '"'
        and etag[-1] == '"'
        and all(
            ord(char) == 0x21 or 0x23 <= ord(char) <= 0x7E or 0x80 <= ord(char) <= 0xFF
            for char in etag[1:-1]
        )
    )


def _validate_measurement(measurement: dict) -> None:
    if (
        not isinstance(measurement, dict)
        or set(measurement) != {"bytes", "sha256", "etag", "measured_at"}
        or type(measurement["bytes"]) is not int
        or not 0 < measurement["bytes"] <= 2**63 - 1
        or not isinstance(measurement["sha256"], str)
        or len(measurement["sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in measurement["sha256"])
        or not is_strong_etag(measurement["etag"])
        or not isinstance(measurement["measured_at"], str)
    ):
        raise InventoryBlocked(
            "Complete positive-size byte evidence is required",
            reason_code="PROVIDER_EVIDENCE_INVALID",
        )
    try:
        measured = datetime.fromisoformat(measurement["measured_at"])
    except ValueError:
        raise InventoryBlocked(
            "Inventory evidence timestamp is invalid",
            reason_code="EVIDENCE_TIMESTAMP_INVALID",
        ) from None
    if measured.tzinfo is None or measured.utcoffset() is None:
        raise InventoryBlocked(
            "Inventory evidence timestamp must include a timezone",
            reason_code="EVIDENCE_TIMEZONE_MISSING",
        )


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
        raise InventoryBlocked(
            "An explicit PostgreSQL transaction is required",
            reason_code="TRANSACTION_REQUIRED",
        )
    role = connection.exec_driver_sql("""SELECT current_user=session_user,
        pg_has_role(current_user,'vervfy_storage_lifecycle_owner','SET'),
        rolsuper OR rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=current_user""").one()
    if tuple(role) != (True, True, False):
        raise InventoryBlocked(
            "A restricted migration login with SET owner capability is required",
            reason_code="ROLE_CAPABILITY_REQUIRED",
        )
    if (
        connection.exec_driver_sql("SHOW transaction_isolation").scalar_one()
        != "read committed"
    ):
        raise InventoryBlocked(
            "Inventory requires READ COMMITTED",
            reason_code="ISOLATION_MISMATCH",
        )
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
    if connection.execute(
        text("SELECT version_num FROM public.alembic_version")
    ).scalars().all() != [REVISION]:
        raise InventoryBlocked(
            "Inventory requires exactly migration 0034",
            reason_code="REVISION_MISMATCH",
        )
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
            raise InventoryBlocked(
                "Immutable namespace mismatch or cleanup enabled",
                reason_code="NAMESPACE_GUARD_MISMATCH",
            )
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
            raise InventoryBlocked(
                "RLS or cleanup-claim guards are not intact",
                reason_code="SECURITY_GUARD_DRIFT",
            )
        rows = (
            connection.exec_driver_sql("""SELECT id::text,namespace_id,tenant_id,path,kind,
            classification,state,reservation_token::text,upload_verified,created_at::text,reserved_bytes
            FROM vervfy_storage.objects ORDER BY path COLLATE "C"
        """)
            .mappings()
            .all()
        )
        return {"namespace": list(expected), "objects": [dict(row) for row in rows]}


def measure_inventory(
    before: dict,
    observe,
    *,
    max_workers=MAX_CONCURRENT_OBSERVATIONS,
    progress=None,
) -> dict:
    """Observe unknown rows concurrently, without holding a SQL transaction."""
    if (
        type(max_workers) is not int
        or not 1 <= max_workers <= MAX_CONCURRENT_OBSERVATIONS
    ):
        raise InventoryBlocked(
            "Inventory observation concurrency is out of bounds",
            reason_code="CONCURRENCY_OUT_OF_BOUNDS",
        )
    unknown = [row for row in before["objects"] if row["reserved_bytes"] is None]
    if any(row["state"] in {"reserved", "uploading", "deleting"} for row in unknown):
        raise InventoryBlocked(
            "An unknown-size object still has an active operation",
            reason_code="ACTIVE_UNKNOWN_OBJECT",
        )

    def observe_one(row):
        measurement = observe(row["path"])
        if not isinstance(measurement, dict) or set(measurement) != {
            "bytes",
            "sha256",
            "etag",
        }:
            raise InventoryBlocked(
                "Complete positive-size byte evidence is required",
                reason_code="PROVIDER_EVIDENCE_INVALID",
            )
        evidence = {**measurement, "measured_at": datetime.now(UTC).isoformat()}
        _validate_measurement(evidence)
        return row["id"], evidence

    observations = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(observe_one, row): row for row in unknown}
        try:
            for completed, future in enumerate(as_completed(futures), start=1):
                object_id, evidence = future.result()
                observations[object_id] = evidence
                if progress is not None:
                    progress(completed, len(unknown))
        except Exception:
            for future in futures:
                future.cancel()
            raise
    _validate_freshness(observations, datetime.now(UTC))
    return {
        "version": PLAN_VERSION,
        "snapshot": before,
        "observations": observations,
    }


def _validate_freshness(observations, current):
    current = current.astimezone(UTC)
    for evidence in observations.values():
        measured = datetime.fromisoformat(evidence["measured_at"]).astimezone(UTC)
        age = current - measured
        if not timedelta(0) <= age < MAX_AGE:
            raise InventoryBlocked(
                "Inventory evidence is expired or future dated",
                reason_code="EVIDENCE_STALE_OR_FUTURE",
            )


def apply_inventory(
    connection, binding: NamespaceBinding, plan: dict, approved_digest: str, *, now=None
) -> int:
    """Fill only NULL charges atomically. Exact replay is harmless, never a refund."""
    if not isinstance(plan, dict):
        raise InventoryBlocked(
            "Unknown inventory plan format", reason_code="PLAN_FORMAT_INVALID"
        )
    if (
        set(plan) != {"version", "snapshot", "observations"}
        or type(plan["version"]) is not int
        or plan["version"] != PLAN_VERSION
        or not isinstance(plan["snapshot"], dict)
        or not isinstance(plan["observations"], dict)
    ):
        raise InventoryBlocked(
            "Unknown inventory plan format", reason_code="PLAN_FORMAT_INVALID"
        )
    if (
        not isinstance(approved_digest, str)
        or len(approved_digest) != 64
        or any(c not in "0123456789abcdef" for c in approved_digest)
    ):
        raise InventoryBlocked(
            "Plan digest does not match independent approval",
            reason_code="APPROVAL_DIGEST_INVALID",
        )
    try:
        actual_digest = plan_digest(plan)
    except (TypeError, ValueError):
        raise InventoryBlocked(
            "Inventory plan cannot be digested", reason_code="PLAN_DIGEST_INVALID"
        ) from None
    if not hmac.compare_digest(actual_digest, approved_digest):
        raise InventoryBlocked(
            "Plan digest does not match independent approval",
            reason_code="APPROVAL_DIGEST_MISMATCH",
        )
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise InventoryBlocked(
            "Apply time must include a timezone",
            reason_code="APPLY_TIMEZONE_MISSING",
        )
    snapshot_plan = plan["snapshot"]
    if (
        set(snapshot_plan) != {"namespace", "objects"}
        or not isinstance(snapshot_plan["namespace"], list)
        or not isinstance(snapshot_plan["objects"], list)
        or any(
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or "reserved_bytes" not in row
            for row in snapshot_plan["objects"]
        )
    ):
        raise InventoryBlocked(
            "Inventory snapshot format is invalid",
            reason_code="SNAPSHOT_FORMAT_INVALID",
        )
    observations = plan["observations"]
    unknown = [r for r in snapshot_plan["objects"] if r["reserved_bytes"] is None]
    if set(observations) != {r["id"] for r in unknown}:
        raise InventoryBlocked(
            "Inventory must cover exactly all unknown ledger rows",
            reason_code="OBSERVATION_COVERAGE_MISMATCH",
        )
    for evidence in observations.values():
        _validate_measurement(evidence)
    _validate_freshness(observations, current)
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
        _validate_freshness(observations, now if now is not None else datetime.now(UTC))
        original = snapshot_plan
        if actual != original:
            completed = json.loads(json.dumps(original))
            for row in completed["objects"]:
                if row["id"] in observations:
                    row["reserved_bytes"] = observations[row["id"]]["bytes"]
            if actual == completed:
                return 0
            raise InventoryBlocked(
                "Ledger changed since measurement; collect a fresh plan",
                reason_code="LEDGER_SNAPSHOT_CHANGED",
            )
        with _owner(connection):
            for object_id, evidence in observations.items():
                changed = connection.execute(
                    text("""UPDATE vervfy_storage.objects SET reserved_bytes=:bytes
                    WHERE id=:id AND reserved_bytes IS NULL"""),
                    {"id": object_id, "bytes": evidence["bytes"]},
                )
                if changed.rowcount != 1:
                    raise InventoryBlocked(
                        "Unknown-size charge was not confirmed",
                        reason_code="CHARGE_UPDATE_UNCONFIRMED",
                    )
        return len(observations)
