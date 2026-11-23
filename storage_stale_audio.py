"""Digest-approved repair of catalog-confirmed missing legacy audio references."""

from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from storage_inventory import InventoryBlocked, plan_digest
from storage_namespace import NamespaceBinding

REVISION = "0034_storage_byte_reservations"
DETACH_REVISIONS = {"0032_auth_sessions", "0033_cleanup_claims_disabled"}
MAX_AGE = timedelta(minutes=15)
EXPECTED_SIZES = {5_759_110, 30_780_168}
_PATH = re.compile(r"([A-Za-z0-9_-]{1,32})/([A-Za-z0-9_.-]{1,70})")
_HASH = re.compile(r"[0-9a-f]{32}")
_METADATA_HASH = re.compile(r"[0-9a-f]{32}")


def _identity(connection, *, expected_role: str) -> None:
    if connection.dialect.name != "postgresql" or not connection.in_transaction():
        raise InventoryBlocked("An explicit PostgreSQL transaction is required")
    role = connection.exec_driver_sql("""
        SELECT current_user=session_user, rolname, rolsuper OR rolbypassrls
        FROM pg_catalog.pg_roles WHERE rolname=current_user
    """).one()
    if tuple(role) != (True, expected_role, False):
        raise InventoryBlocked(f"Restricted {expected_role} login required")
    if (
        connection.exec_driver_sql("SHOW transaction_isolation").scalar_one()
        != "read committed"
    ):
        raise InventoryBlocked("Stale-audio repair requires READ COMMITTED")
    connection.exec_driver_sql("SET LOCAL lock_timeout='1000ms'")
    connection.exec_driver_sql("SET LOCAL statement_timeout='5000ms'")


def _targets(target_sizes: dict[str, int]) -> None:
    if (
        len(target_sizes) != 2
        or any(_HASH.fullmatch(key) is None for key in target_sizes)
        or set(target_sizes.values()) != EXPECTED_SIZES
    ):
        raise InventoryBlocked(
            "Exactly the two audited path hashes and sizes are required"
        )


def _require_revision(connection, supported: set[str]) -> str:
    revisions = (
        connection.execute(text("SELECT version_num FROM public.alembic_version"))
        .scalars()
        .all()
    )
    if len(revisions) != 1 or revisions[0] not in supported:
        raise InventoryBlocked("Stale-audio repair is not supported at this revision")
    return revisions[0]


@contextmanager
def _owner(connection):
    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
        yield
        connection.exec_driver_sql("RESET ROLE")


def _namespace(
    connection, binding: NamespaceBinding, *, require_cleanup_disabled: bool
) -> None:
    with _owner(connection):
        actual = connection.exec_driver_sql("""
            SELECT namespace_id::text,environment,endpoint,bucket,physical_cleanup_enabled
            FROM vervfy_storage.namespaces WHERE id=1
        """).one_or_none()
        expected = (
            str(binding.namespace_id),
            binding.environment,
            binding.endpoint,
            binding.bucket,
            False,
        )
        if actual is None or tuple(actual) != expected:
            raise InventoryBlocked("Immutable namespace mismatch or cleanup enabled")
        if (
            require_cleanup_disabled
            and connection.execute(
                text("""
            SELECT has_function_privilege(
                'app_runtime','vervfy_storage.claim_next_cleanup()','EXECUTE'
            ) OR has_function_privilege(
                'storage_cleanup_worker','vervfy_storage.claim_next_cleanup()','EXECUTE'
            ) OR has_function_privilege(
                'vervfy_storage_cleanup','vervfy_storage.claim_next_cleanup()','EXECUTE'
            )
        """)
            ).scalar_one()
        ):
            raise InventoryBlocked("Storage cleanup claims must remain disabled")


def _references(connection) -> list[tuple[str, str]]:
    with _owner(connection):
        return connection.execute(
            text("""
            SELECT source,path FROM (
                SELECT 'track_audio'::text AS source,storage_path::text AS path
                FROM public.tracks WHERE storage_path IS NOT NULL
                UNION ALL
                SELECT 'track_cover',cover_path::text FROM public.tracks
                WHERE cover_path IS NOT NULL
                UNION ALL
                SELECT 'artist_photo',storage_path::text FROM public.artist_photos
                WHERE storage_path IS NOT NULL
                UNION ALL
                SELECT 'upload_job',storage_path::text FROM public.upload_jobs
                WHERE storage_path IS NOT NULL
            ) refs ORDER BY path COLLATE "C",source
        """)
        ).all()


def _ledger_paths(connection, hashes: list[str]) -> dict[str, list[str]]:
    with _owner(connection):
        rows = connection.execute(
            text("""
                SELECT path,md5(path) AS path_hash
                FROM vervfy_storage.objects
                WHERE namespace_id=1 AND md5(path)=ANY(:hashes)
            """),
            {"hashes": hashes},
        ).all()
    result: dict[str, list[str]] = {path_hash: [] for path_hash in hashes}
    for path, path_hash in rows:
        result[path_hash].append(path)
    return result


def _ledger_rows(connection, paths: list[str]) -> dict[str, dict | None]:
    has_charge = connection.exec_driver_sql("""
        SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_attribute
            WHERE attrelid='vervfy_storage.objects'::regclass
              AND attname='reserved_bytes' AND attnum > 0 AND NOT attisdropped
        )
    """).scalar_one()
    charge_column = "o.reserved_bytes" if has_charge else "NULL::bigint"
    with _owner(connection):
        rows = (
            connection.execute(
                text(f"""
            SELECT o.id::text,o.path,o.tenant_id,o.kind,o.classification,o.state,
                   o.reservation_token::text,o.upload_verified,{charge_column} AS reserved_bytes,
                   j.state AS cleanup_state,j.claim_token::text,j.lease_until::text
            FROM vervfy_storage.objects o
            LEFT JOIN vervfy_storage.cleanup_jobs j ON j.object_id=o.id
            WHERE o.namespace_id=1 AND o.path=ANY(:paths)
            ORDER BY o.path COLLATE "C"
        """),
                {"paths": paths},
            )
            .mappings()
            .all()
        )
    return {row["path"]: dict(row) for row in rows}


def _track_row(connection, target: dict, *, for_update: bool = False) -> dict:
    connection.execute(
        text("SELECT set_config('app.current_user_id',:user_id,true)"),
        {"user_id": target["user_id"]},
    )
    suffix = " FOR UPDATE" if for_update else ""
    row = (
        connection.execute(
            text(f"""
        SELECT id,user_id,storage_path,size_bytes,audio_data IS NULL AS audio_missing,
               md5((to_jsonb(t)-'storage_path'-'media_version')::text) AS metadata_digest
        FROM public.tracks t WHERE id=:track_id AND user_id=:user_id{suffix}
    """),
            {"track_id": target["track_id"], "user_id": target["user_id"]},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise InventoryBlocked("Target track is unavailable under its tenant")
    return dict(row)


def _path_identity(path: str) -> tuple[str, str]:
    match = _PATH.fullmatch(path)
    if match is None or path.startswith("v2/"):
        raise InventoryBlocked("Only two-component legacy audio paths are supported")
    user_id, leaf = match.groups()
    track_id = re.sub(r"\.[a-z0-9]{1,5}$", "", leaf)
    if not track_id or len(track_id) > 64:
        raise InventoryBlocked("Legacy path cannot be bound to a track identity")
    return user_id, track_id


def _target_snapshot(runtime, migration, target_sizes: dict[str, int]) -> list[dict]:
    refs = _references(migration)
    ledger_paths = _ledger_paths(migration, list(target_sizes))
    selected = []
    for path_hash, expected_size in sorted(target_sizes.items()):
        matches = [
            path
            for source, path in refs
            if source == "track_audio"
            and hashlib.md5(path.encode()).hexdigest() == path_hash
        ]
        if not matches:
            matches = ledger_paths[path_hash]
        if len(matches) != 1:
            raise InventoryBlocked(
                "Each approved hash must identify one audio reference or tombstone"
            )
        path = matches[0]
        if hashlib.md5(path.encode()).hexdigest() != path_hash:
            raise InventoryBlocked("Ledger path identity did not match approval")
        user_id, track_id = _path_identity(path)
        track = _track_row(runtime, {"user_id": user_id, "track_id": track_id})
        if (
            track["storage_path"] not in (path, None)
            or track["size_bytes"] != expected_size
            or not track["audio_missing"]
        ):
            raise InventoryBlocked("Track path, size, or inline-audio state changed")
        sources = [source for source, ref_path in refs if ref_path == path]
        if (track["storage_path"] == path and sources != ["track_audio"]) or (
            track["storage_path"] is None and sources
        ):
            raise InventoryBlocked("A stale audio path is shared or still referenced")
        if hashlib.md5(path.encode()).hexdigest() != path_hash:
            raise InventoryBlocked("Legacy path identity did not match approval")
        selected.append(
            {
                "path_hash": path_hash,
                "path": path,
                "user_id": user_id,
                "track_id": track_id,
                "size_bytes": expected_size,
                "metadata_digest": track["metadata_digest"],
            }
        )
    ledger = _ledger_rows(migration, [item["path"] for item in selected])
    for item in selected:
        item["ledger"] = ledger.get(item["path"])
        _validate_tombstone(item, item["ledger"], allow_uncharged=True)
    return selected


def _validate_tombstone(
    target: dict, row: dict | None, *, allow_uncharged: bool
) -> None:
    if row is None:
        return
    if (
        row["tenant_id"] is not None
        or row["kind"] != "legacy"
        or row["classification"] != "legacy"
        or row["state"] != "hold"
        or row["reservation_token"] is not None
        or row["upload_verified"]
        or row["cleanup_state"] not in (None, "held")
        or row["claim_token"] is not None
        or row["lease_until"] is not None
    ):
        raise InventoryBlocked("Existing ledger row is not a held legacy tombstone")
    charge = row["reserved_bytes"]
    if charge is None and allow_uncharged:
        return
    if type(charge) is not int or charge < target["size_bytes"]:
        raise InventoryBlocked(
            "Tombstone quota charge is below the positive historical size"
        )


def plan_stale_audio_repair(
    runtime_connection,
    migration_connection,
    binding: NamespaceBinding,
    target_sizes: dict[str, int],
    *,
    stage: str,
    confirmed_catalog_absence: bool,
    migration_role: str = "vervfy_prod_migrator",
    now: datetime | None = None,
) -> dict:
    _targets(target_sizes)
    if not confirmed_catalog_absence:
        raise InventoryBlocked("All-bucket absence confirmation is required")
    _identity(runtime_connection, expected_role="app_runtime")
    _identity(migration_connection, expected_role=migration_role)
    if stage not in {"detach", "charge"}:
        raise InventoryBlocked("Unknown stale-audio plan stage")
    supported = DETACH_REVISIONS if stage == "detach" else {REVISION}
    revision = _require_revision(migration_connection, supported)
    _namespace(
        migration_connection,
        binding,
        require_cleanup_disabled=(stage == "charge"),
    )
    targets = _target_snapshot(runtime_connection, migration_connection, target_sizes)
    return {
        "version": 1,
        "stage": stage,
        "planned_at": (now or datetime.now(UTC)).astimezone(UTC).isoformat(),
        "revision": revision,
        "namespace": [
            str(binding.namespace_id),
            binding.environment,
            binding.endpoint,
            binding.bucket,
            False,
        ],
        "catalog_absence_confirmed": True,
        "targets": targets,
    }


def detach_stale_audio_references(
    runtime_connection,
    migration_connection,
    binding: NamespaceBinding,
    plan: dict,
    approved_digest: str,
    *,
    now=None,
    migration_role: str = "vervfy_prod_migrator",
) -> int:
    _validate_plan(plan, approved_digest, stage="detach", now=now)
    _identity(runtime_connection, expected_role="app_runtime")
    _identity(migration_connection, expected_role=migration_role)
    _validate_binding(plan, binding)
    revision = _require_revision(migration_connection, DETACH_REVISIONS)
    if revision != plan["revision"]:
        raise InventoryBlocked("Database revision changed since planning")
    _namespace(migration_connection, binding, require_cleanup_disabled=False)
    _verify_apply_snapshot(runtime_connection, migration_connection, plan)
    changed = 0
    with runtime_connection.begin_nested():
        runtime_connection.exec_driver_sql("""
            LOCK TABLE public.tracks IN ROW EXCLUSIVE MODE
        """)
        for target in plan["targets"]:
            track = _track_row(runtime_connection, target, for_update=True)
            if (
                track["size_bytes"] != target["size_bytes"]
                or not track["audio_missing"]
                or track["metadata_digest"] != target["metadata_digest"]
            ):
                raise InventoryBlocked("Track metadata changed; create a fresh plan")
            if track["storage_path"] is None:
                continue
            if track["storage_path"] != target["path"]:
                raise InventoryBlocked("Track path changed; create a fresh plan")
            result = runtime_connection.execute(
                text("""
                UPDATE public.tracks SET storage_path=NULL
                WHERE id=:track_id AND user_id=:user_id
                  AND storage_path=:path AND size_bytes=:size_bytes
                  AND audio_data IS NULL
            """),
                {
                    "track_id": target["track_id"],
                    "user_id": target["user_id"],
                    "path": target["path"],
                    "size_bytes": target["size_bytes"],
                },
            )
            if result.rowcount != 1:
                raise InventoryBlocked("Track reference was not detached")
            changed += 1
        for target in plan["targets"]:
            track = _track_row(runtime_connection, target)
            if (
                track["storage_path"] is not None
                or track["size_bytes"] != target["size_bytes"]
                or not track["audio_missing"]
                or track["metadata_digest"] != target["metadata_digest"]
            ):
                raise InventoryBlocked("Track postcondition failed")
    return changed


def charge_stale_audio_tombstones(
    runtime_connection,
    migration_connection,
    binding: NamespaceBinding,
    plan: dict,
    approved_digest: str,
    *,
    now=None,
    migration_role: str = "vervfy_prod_migrator",
) -> int:
    _validate_plan(plan, approved_digest, stage="charge", now=now)
    _identity(runtime_connection, expected_role="app_runtime")
    _identity(migration_connection, expected_role=migration_role)
    _require_revision(migration_connection, {REVISION})
    _validate_binding(plan, binding)
    _namespace(migration_connection, binding, require_cleanup_disabled=True)
    _verify_apply_snapshot(runtime_connection, migration_connection, plan)
    with migration_connection.begin_nested():
        with _owner(migration_connection):
            migration_connection.exec_driver_sql("""
                SELECT id FROM vervfy_storage.quota_policy WHERE id=1 FOR UPDATE
            """).one()
            migration_connection.exec_driver_sql("""
                LOCK TABLE vervfy_storage.objects,vervfy_storage.cleanup_jobs
                IN SHARE ROW EXCLUSIVE MODE
            """)
        _identity(migration_connection, expected_role=migration_role)
        rows = _ledger_rows(
            migration_connection, [item["path"] for item in plan["targets"]]
        )
        changed = 0
        with _owner(migration_connection):
            for target in plan["targets"]:
                row = rows.get(target["path"])
                _validate_tombstone(target, row, allow_uncharged=True)
                if row is None:
                    raise InventoryBlocked(
                        "Lifecycle trigger did not create its tombstone"
                    )
                if row["reserved_bytes"] is not None:
                    continue
                result = migration_connection.execute(
                    text("""
                    UPDATE vervfy_storage.objects SET reserved_bytes=:charge
                    WHERE id=:object_id AND reserved_bytes IS NULL
                      AND classification='legacy' AND kind='legacy'
                      AND state='hold' AND tenant_id IS NULL
                """),
                    {"charge": target["size_bytes"], "object_id": row["id"]},
                )
                if result.rowcount != 1:
                    raise InventoryBlocked("Positive tombstone charge was not recorded")
                changed += 1
        verified = _ledger_rows(
            migration_connection, [item["path"] for item in plan["targets"]]
        )
        for target in plan["targets"]:
            _validate_tombstone(
                target, verified.get(target["path"]), allow_uncharged=False
            )
        return changed


def _verify_apply_snapshot(
    runtime_connection, migration_connection, plan: dict
) -> None:
    refs = _references(migration_connection)
    ledger = _ledger_rows(
        migration_connection, [item["path"] for item in plan["targets"]]
    )
    for target in plan["targets"]:
        track = _track_row(runtime_connection, target)
        if (
            track["size_bytes"] != target["size_bytes"]
            or not track["audio_missing"]
            or track["metadata_digest"] != target["metadata_digest"]
        ):
            raise InventoryBlocked("Track metadata changed; create a fresh plan")
        sources = [source for source, path in refs if path == target["path"]]
        if track["storage_path"] == target["path"]:
            if sources != ["track_audio"]:
                raise InventoryBlocked(
                    "Stale path is shared or reference state changed"
                )
            if ledger.get(target["path"]) is not None:
                _validate_tombstone(
                    target, ledger[target["path"]], allow_uncharged=True
                )
        elif track["storage_path"] is None:
            if sources or ledger.get(target["path"]) is None:
                raise InventoryBlocked(
                    "Detached path lacks its held lifecycle tombstone"
                )
            if ledger[target["path"]]["cleanup_state"] != "held":
                raise InventoryBlocked("Detached path cleanup job is not held")
            _validate_tombstone(target, ledger[target["path"]], allow_uncharged=True)
        else:
            raise InventoryBlocked("Track path changed; create a fresh plan")


def _validate_plan(plan: dict, approved_digest: str, *, stage: str, now=None) -> None:
    if plan_digest(plan) != approved_digest:
        raise InventoryBlocked("Plan digest does not match independent approval")
    if (
        set(plan)
        != {
            "version",
            "stage",
            "planned_at",
            "revision",
            "namespace",
            "catalog_absence_confirmed",
            "targets",
        }
        or type(plan["version"]) is not int
        or plan["version"] != 1
        or plan["stage"] != stage
        or (
            plan["revision"] not in DETACH_REVISIONS
            if stage == "detach"
            else plan["revision"] != REVISION
        )
        or plan["catalog_absence_confirmed"] is not True
        or len(plan["targets"]) != 2
        or not isinstance(plan["namespace"], list)
        or len(plan["namespace"]) != 5
        or {target.get("size_bytes") for target in plan["targets"]} != EXPECTED_SIZES
    ):
        raise InventoryBlocked("Unknown or incomplete stale-audio repair plan")
    planned_at = datetime.fromisoformat(plan["planned_at"])
    current_time = now or datetime.now(UTC)
    if (
        planned_at.tzinfo is None
        or not timedelta(0) <= current_time - planned_at <= MAX_AGE
    ):
        raise InventoryBlocked("Stale-audio plan is expired or future dated")
    paths = [target.get("path") for target in plan["targets"]]
    if (
        len(set(paths)) != 2
        or any(not isinstance(path, str) or not path for path in paths)
        or any(
            _HASH.fullmatch(target.get("path_hash", "")) is None
            for target in plan["targets"]
        )
    ):
        raise InventoryBlocked("Malformed stale-audio targets")
    for target in plan["targets"]:
        if (
            set(target)
            != {
                "path_hash",
                "path",
                "user_id",
                "track_id",
                "size_bytes",
                "metadata_digest",
                "ledger",
            }
            or hashlib.md5(target["path"].encode()).hexdigest() != target["path_hash"]
            or _path_identity(target["path"]) != (target["user_id"], target["track_id"])
            or _METADATA_HASH.fullmatch(target["metadata_digest"]) is None
        ):
            raise InventoryBlocked("Malformed or inconsistent stale-audio target")


def _validate_binding(plan: dict, binding: NamespaceBinding) -> None:
    expected = [
        str(binding.namespace_id),
        binding.environment,
        binding.endpoint,
        binding.bucket,
        False,
    ]
    if plan["namespace"] != expected:
        raise InventoryBlocked("Stale-audio plan namespace differs from the target")
