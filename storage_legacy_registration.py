"""Plan and register referenced pre-lifecycle paths as held, unowned legacy rows."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from storage_inventory import InventoryBlocked, plan_digest
from storage_namespace import NamespaceBinding

SUPPORTED_REVISIONS = {
    "0032_auth_sessions",
    "0033_cleanup_claims_disabled",
}
MAX_AGE = timedelta(minutes=15)
REFERENCE_SOURCES = {
    "track_audio": "audio",
    "track_cover": ("track-cover", "album-cover"),
    "artist_photo": "artist-photo",
    "upload_job": "staged-audio",
}


def _valid_path(path: object) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and len(path) <= 600
        and not path.startswith("/")
        and "\\" not in path
        and not any(ord(char) < 32 or ord(char) == 127 for char in path)
        and all(part not in {"", ".", ".."} for part in path.split("/"))
    )


def snapshot_references(connection, binding: NamespaceBinding) -> dict:
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
        raise InventoryBlocked("Legacy registration requires READ COMMITTED")
    revision = (
        connection.execute(text("SELECT version_num FROM public.alembic_version"))
        .scalars()
        .all()
    )
    if len(revision) != 1 or revision[0] not in SUPPORTED_REVISIONS:
        raise InventoryBlocked("Legacy registration requires revision 0032 or 0033")
    unsupported_0034 = connection.exec_driver_sql("""SELECT
        pg_catalog.to_regclass('vervfy_storage.quota_policy') IS NOT NULL
        OR EXISTS (
            SELECT 1 FROM pg_catalog.pg_attribute
            WHERE attrelid='vervfy_storage.objects'::regclass
              AND attname='reserved_bytes' AND attnum > 0 AND NOT attisdropped
        )""").scalar_one()
    if unsupported_0034:
        raise InventoryBlocked("Legacy registration must precede migration 0034")
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")

    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
        namespace = connection.exec_driver_sql("""SELECT namespace_id::text,
            environment,endpoint,bucket,physical_cleanup_enabled
            FROM vervfy_storage.namespaces WHERE id=1""").one_or_none()
        expected_namespace = (
            str(binding.namespace_id),
            binding.environment,
            binding.endpoint,
            binding.bucket,
            False,
        )
        if namespace is None or tuple(namespace) != expected_namespace:
            raise InventoryBlocked("Immutable namespace mismatch or cleanup enabled")

        reference_rows = connection.execute(
            text("""
            SELECT source, path
            FROM (
                SELECT 'track_audio'::text AS source, t.storage_path::text AS path
                FROM public.tracks t
                WHERE t.storage_path IS NOT NULL
                UNION ALL
                SELECT 'track_cover', t.cover_path::text
                FROM public.tracks t
                WHERE t.cover_path IS NOT NULL
                UNION ALL
                SELECT 'artist_photo', p.storage_path::text
                FROM public.artist_photos p
                WHERE p.storage_path IS NOT NULL
                UNION ALL
                SELECT 'upload_job', j.storage_path::text
                FROM public.upload_jobs j
                WHERE j.storage_path IS NOT NULL
            ) ref_rows
            ORDER BY path COLLATE "C", source
        """)
        ).all()
        object_rows = (
            connection.execute(
                text("""
            SELECT id::text, namespace_id, tenant_id, path, kind, classification,
                   state, reservation_token::text, upload_verified
            FROM vervfy_storage.objects
            WHERE namespace_id=1
            ORDER BY path COLLATE "C"
        """)
            )
            .mappings()
            .all()
        )
        connection.exec_driver_sql("RESET ROLE")

    references: dict[str, dict] = {}
    for source, path in reference_rows:
        if source not in REFERENCE_SOURCES or not _valid_path(path):
            raise InventoryBlocked("Unsafe or unsupported storage reference")
        reference = references.setdefault(path, {"path": path, "sources": []})
        reference["sources"].append(source)
    for reference in references.values():
        reference["sources"] = sorted(set(reference["sources"]))

    objects = [dict(row) for row in object_rows]
    paths = [row["path"] for row in objects]
    if len(paths) != len(set(paths)):
        raise InventoryBlocked("Lifecycle ledger contains duplicate paths")
    result = {
        "namespace": list(expected_namespace),
        "revision": revision[0],
        "references": [references[path] for path in sorted(references)],
        "objects": objects,
    }
    _registration_rows(result, binding.namespace_id)
    return result


def _registration_rows(snapshot: dict, namespace_id: uuid.UUID) -> list[dict]:
    objects = {row["path"]: row for row in snapshot["objects"]}
    registrations = []
    for reference in snapshot["references"]:
        path = reference["path"]
        existing = objects.get(path)
        is_managed_path = path.startswith("v2/")
        if existing is None:
            if is_managed_path:
                raise InventoryBlocked("An unregistered v2 reference cannot be adopted")
            object_id = str(uuid.uuid5(namespace_id, "legacy:" + path))
            if any(row["id"] == object_id for row in snapshot["objects"]):
                raise InventoryBlocked("Deterministic legacy object ID collision")
            registrations.append(
                {
                    "id": object_id,
                    "namespace_id": 1,
                    "tenant_id": None,
                    "path": path,
                    "kind": "legacy",
                    "classification": "legacy",
                    "state": "hold",
                    "reservation_token": None,
                    "upload_verified": False,
                }
            )
            continue

        expected_kinds = {source: kind for source, kind in REFERENCE_SOURCES.items()}
        for source in reference["sources"]:
            expected_kind = expected_kinds[source]
            compatible = (
                existing["kind"] in expected_kind
                if isinstance(expected_kind, tuple)
                else existing["kind"] == expected_kind
            )
            if is_managed_path:
                valid = (
                    existing["classification"] == "managed"
                    and existing["tenant_id"] is not None
                    and existing["state"] in {"ready", "live"}
                    and existing["upload_verified"]
                    and compatible
                )
                if not valid:
                    raise InventoryBlocked(
                        "A managed reference does not match its ledger record"
                    )
            elif (
                existing["classification"] != "legacy"
                or existing["kind"] != "legacy"
                or existing["tenant_id"] is not None
                or existing["state"] != "hold"
            ):
                raise InventoryBlocked(
                    "An existing legacy reference has an unsafe ledger record"
                )
    return sorted(registrations, key=lambda row: row["path"])


def _after_snapshot(before: dict, registrations: list[dict]) -> dict:
    after = copy.deepcopy(before)
    after["objects"].extend(copy.deepcopy(registrations))
    after["objects"].sort(key=lambda row: row["path"])
    return after


def plan_registration(
    connection,
    binding: NamespaceBinding,
    *,
    expected_missing_count: int | None = None,
    now: datetime | None = None,
) -> dict:
    before = snapshot_references(connection, binding)
    registrations = _registration_rows(before, binding.namespace_id)
    if (
        expected_missing_count is not None
        and len(registrations) != expected_missing_count
    ):
        raise InventoryBlocked("Unregistered-reference count differs from approval")
    return {
        "version": 1,
        "planned_at": (now or datetime.now(UTC)).astimezone(UTC).isoformat(),
        "snapshot": before,
        "registrations": registrations,
        "after": _after_snapshot(before, registrations),
    }


def apply_registration(
    connection,
    binding: NamespaceBinding,
    plan: dict,
    approved_digest: str,
    *,
    now: datetime | None = None,
) -> int:
    if plan_digest(plan) != approved_digest:
        raise InventoryBlocked("Plan digest does not match independent approval")
    if (
        set(plan)
        != {
            "version",
            "planned_at",
            "snapshot",
            "registrations",
            "after",
        }
        or type(plan["version"]) is not int
        or plan["version"] != 1
    ):
        raise InventoryBlocked("Unknown legacy registration plan format")
    planned_at = datetime.fromisoformat(plan["planned_at"])
    current_time = now or datetime.now(UTC)
    if (
        planned_at.tzinfo is None
        or not timedelta(0) <= current_time - planned_at <= MAX_AGE
    ):
        raise InventoryBlocked("Legacy registration plan is expired or future dated")
    expected = _registration_rows(plan["snapshot"], binding.namespace_id)
    if plan["registrations"] != expected or plan["after"] != _after_snapshot(
        plan["snapshot"], expected
    ):
        raise InventoryBlocked("Legacy registration plan contents are inconsistent")
    if not connection.in_transaction():
        raise InventoryBlocked("Legacy registration requires an explicit transaction")

    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
        connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")
        connection.exec_driver_sql("""
            LOCK TABLE public.tracks, public.artist_photos, public.upload_jobs,
                       vervfy_storage.objects
            IN SHARE ROW EXCLUSIVE MODE
        """)
        actual = snapshot_references(connection, binding)
        if actual == plan["after"]:
            return 0
        if actual != plan["snapshot"]:
            raise InventoryBlocked("References or ledger changed; create a fresh plan")
        if expected:
            with connection.begin_nested():
                connection.exec_driver_sql(
                    "SET LOCAL ROLE vervfy_storage_lifecycle_owner"
                )
                for row in expected:
                    connection.execute(
                        text("""
                        INSERT INTO vervfy_storage.objects(
                            id, namespace_id, tenant_id, path, kind,
                            classification, state, reservation_token,
                            upload_verified
                        ) VALUES (
                            :id, :namespace_id, :tenant_id, :path, :kind,
                            :classification, :state, :reservation_token,
                            :upload_verified
                        )
                    """),
                        row,
                    )
                connection.exec_driver_sql("RESET ROLE")
            if snapshot_references(connection, binding) != plan["after"]:
                raise InventoryBlocked("Legacy registration postcondition failed")
        return len(expected)
