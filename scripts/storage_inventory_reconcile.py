"""Guarded plan/apply for unknown ledger sizes; never deletes provider objects."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import tempfile
import ssl
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
    MAX_CONCURRENT_OBSERVATIONS,
    InventoryBlocked,
    apply_inventory,
    is_strong_etag,
    measure_inventory,
    plan_digest,
    snapshot,
)
from storage_namespace import NamespaceBinding

MAX_READ_ATTEMPTS = 4
RETRY_BASE_SECONDS = 0.25
RETRY_MAX_SECONDS = 2.0


class ReadOnlyObserver:
    """Two complete matching reads under one absolute network deadline."""

    def __init__(self, client_factory, binding, *, max_bytes=10 * 1024**3, deadline=60):
        if type(max_bytes) is not int or max_bytes <= 0 or not 0 < deadline <= 60:
            raise InventoryBlocked(
                "Positive bounded observation limits required",
                reason_code="OBSERVATION_LIMITS_INVALID",
            )
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
            raise InventoryBlocked(
                "Unsafe inventory object path", reason_code="OBJECT_KEY_UNSAFE"
            )
        try:
            return asyncio.run(self._observe(path))
        except InventoryBlocked:
            raise
        except TimeoutError:
            raise InventoryBlocked(
                "Provider observation exceeded its deadline",
                reason_code="PROVIDER_DEADLINE_EXCEEDED",
            ) from None
        except (httpx.HTTPError, ValueError):
            raise InventoryBlocked(
                "Provider observation failed",
                reason_code="PROVIDER_CONNECTION_ERROR",
            ) from None

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
                    observations.append(await self._read_with_retries(client, url))
                if observations[0] != observations[1]:
                    raise InventoryBlocked(
                        "Object changed during observation",
                        reason_code="OBJECT_CHANGED_DURING_READ",
                    )
                return observations[0]
        finally:
            async with asyncio.timeout(5):
                await client.aclose()

    @staticmethod
    def _is_transient_network_error(error):
        current = error
        while current is not None:
            if isinstance(current, ssl.SSLError):
                return False
            current = current.__cause__ or current.__context__
        return isinstance(
            error,
            (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError),
        )

    async def _read_with_retries(self, client, url):
        for attempt in range(MAX_READ_ATTEMPTS):
            try:
                observation = await self._read_once(client, url)
                if observation is not None:
                    return observation
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            ) as error:
                if not self._is_transient_network_error(error):
                    raise
            if attempt + 1 == MAX_READ_ATTEMPTS:
                raise InventoryBlocked(
                    "Provider retry limit reached",
                    reason_code="PROVIDER_RETRY_EXHAUSTED",
                ) from None
            ceiling = min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2**attempt))
            await asyncio.sleep(random.uniform(0, ceiling))
        raise AssertionError("bounded provider retry loop exhausted unexpectedly")

    async def _read_once(self, client, url):
        count, digest = 0, hashlib.sha256()
        async with client.stream(
            "GET", url, headers={"Accept-Encoding": "identity"}
        ) as response:
            status = response.status_code
            if status == 429 or 500 <= status <= 599:
                return None
            if status in {401, 403}:
                raise InventoryBlocked(
                    "Provider authorization was rejected",
                    reason_code="PROVIDER_AUTH_REJECTED",
                )
            if status == 404:
                raise InventoryBlocked(
                    "Object was not found",
                    reason_code="OBJECT_NOT_FOUND",
                )
            if status != 200:
                raise InventoryBlocked(
                    "Provider rejected the object read",
                    reason_code="PROVIDER_HTTP_REJECTED",
                )
            etag = response.headers.get("etag")
            if not is_strong_etag(etag):
                raise InventoryBlocked(
                    "Object version is invalid",
                    reason_code="OBJECT_ETAG_INVALID",
                )
            if response.headers.get("content-encoding", "identity") != "identity":
                raise InventoryBlocked(
                    "Object content encoding is invalid",
                    reason_code="OBJECT_CONTENT_ENCODING_INVALID",
                )
            async for chunk in response.aiter_bytes():
                count += len(chunk)
                if count > self.max_bytes:
                    raise InventoryBlocked(
                        "Object observation exceeded its size bound",
                        reason_code="OBJECT_SIZE_LIMIT",
                    )
                digest.update(chunk)
            length = response.headers.get("content-length")
            if length is not None and (
                not length.isdecimal() or int(length) != count
            ):
                raise InventoryBlocked(
                    "Object content length is invalid",
                    reason_code="OBJECT_CONTENT_LENGTH_INVALID",
                )
            if not count:
                raise InventoryBlocked(
                    "Complete positive-size object read was not confirmed",
                    reason_code="OBJECT_READ_INCOMPLETE",
                )
            return {"bytes": count, "sha256": digest.hexdigest(), "etag": etag}



def _checkpoint_path(plan_file):
    return plan_file.with_name(plan_file.name + ".checkpoint")


def _load_checkpoint(path, before):
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise InventoryBlocked("Checkpoint is unsafe", reason_code="PLAN_SIZE_LIMIT")
    with path.open("r") as stream:
        checkpoint = json.load(stream)
    if (
        not isinstance(checkpoint, dict)
        or set(checkpoint) != {"snapshot", "observations"}
        or checkpoint["snapshot"] != before
        or not isinstance(checkpoint["observations"], dict)
    ):
        raise InventoryBlocked(
            "Checkpoint snapshot changed", reason_code="LEDGER_SNAPSHOT_CHANGED"
        )
    return checkpoint["observations"]


def _save_checkpoint(path, before, observations):
    # Atomic replacement; never write to the approved plan file.
    fd, temp_name = tempfile.mkstemp(prefix=".inventory-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"snapshot": before, "observations": observations}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def verify_connection(connection, target):
    """Check the actual plan/apply transaction, not a different connection."""
    runner._verify_client_tls(connection)
    identity = connection.exec_driver_sql(
        "SELECT current_database(),session_user,current_user"
    ).one()
    if tuple(identity) != (target.database, target.username, target.username):
        raise InventoryBlocked(
            "Inventory connection identity mismatch",
            reason_code="CONNECTION_IDENTITY_MISMATCH",
        )
    runner._check_role_graph(connection, target.username)
    runner._verify_followup_result(connection, installation=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply"))
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--confirm-project-ref", required=True)
    parser.add_argument("--confirm-uploads-paused", action="store_true", required=True)
    parser.add_argument(
        "--workers",
        type=int,
        choices=range(1, MAX_CONCURRENT_OBSERVATIONS + 1),
        default=MAX_CONCURRENT_OBSERVATIONS,
        help=(
            "maximum concurrent read-only observations "
            f"(1-{MAX_CONCURRENT_OBSERVATIONS}; default: {MAX_CONCURRENT_OBSERVATIONS})"
        ),
    )
    parser.add_argument("--approved-sha256")
    parser.add_argument("--authorization-expires-at")
    args = parser.parse_args(argv)
    engine = None
    try:
        runner.validate_migration_chain()
        target = runner.load_target()
        if args.confirm_project_ref != target.project_ref:
            raise InventoryBlocked(
                "Project confirmation mismatch",
                reason_code="PROJECT_CONFIRMATION_MISMATCH",
            )
        if args.operation == "apply":
            if not args.approved_sha256 or not args.authorization_expires_at:
                raise InventoryBlocked(
                    "Apply requires independent plan digest approval and expiry",
                    reason_code="INDEPENDENT_APPROVAL_REQUIRED",
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
                    "Read-only provider observation credential is required",
                    reason_code="PROVIDER_CREDENTIAL_MISSING",
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

            def report_progress(completed, total):
                print(
                    f"Inventory observations: {completed}/{total}",
                    file=sys.stderr,
                    flush=True,
                )

            checkpoint_path = _checkpoint_path(args.plan_file)
            recovered = _load_checkpoint(checkpoint_path, before)
            observations = dict(recovered)

            def save_observation(object_id, evidence):
                observations[object_id] = evidence
                _save_checkpoint(checkpoint_path, before, observations)

            plan = measure_inventory(
                before,
                ReadOnlyObserver(client_factory, binding),
                max_workers=args.workers,
                progress=report_progress,
                on_observation=save_observation,
                initial_observations=recovered,
            )
            # Publish only a complete, fsynced plan; never overwrite an approved plan.
            fd, temp_name = tempfile.mkstemp(
                prefix=".inventory-plan-", dir=args.plan_file.parent
            )
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w") as out:
                    json.dump(plan, out, sort_keys=True, indent=2)
                    out.flush()
                    os.fsync(out.fileno())
                os.link(temp_name, args.plan_file)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            checkpoint_path.unlink(missing_ok=True)
            print(
                f"Read-only plan covers {len(plan['observations'])} unknown charges; "
                f"SHA-256: {plan_digest(plan)}"
            )
        else:
            if args.plan_file.stat().st_size > 16 * 1024 * 1024:
                raise InventoryBlocked(
                    "Inventory plan exceeds the input size bound",
                    reason_code="PLAN_SIZE_LIMIT",
                )
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
            "BLOCKED: inventory operation failed "
            f"({type(exc).__name__}; reason_code="
            f"{exc.reason_code if isinstance(exc, InventoryBlocked) else 'UNEXPECTED_FAILURE'}); "
            "no deletion authorized",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
