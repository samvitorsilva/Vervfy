"""Mocked provider reads only; never contact hosted storage."""

import asyncio
import hashlib
import io
import os
import threading
import time
import uuid
from contextlib import redirect_stderr
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scripts import storage_inventory_reconcile as inventory_cli
from scripts.storage_inventory_reconcile import ReadOnlyObserver
import storage_inventory as inventory
from storage_inventory import (
    MAX_CONCURRENT_OBSERVATIONS,
    InventoryBlocked,
    measure_inventory,
)
from storage_namespace import NamespaceBinding

BINDING = NamespaceBinding(
    uuid.uuid4(), "disposable-test", "https://vervfy.invalid", "synthetic"
)


def observe(handler, **kwargs):
    return ReadOnlyObserver(
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False
        ),
        BINDING,
        **kwargs,
    )("legacy/a b.mp3")


def test_matching_complete_reads_use_only_authenticated_gets():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "vervfy.invalid"
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(
            200, content=b"synthetic", headers={"etag": '"immutable"'}
        )

    result = observe(handler)
    assert result["bytes"] == 9
    assert result["sha256"] == hashlib.sha256(b"synthetic").hexdigest()
    assert len(requests) == 2


@pytest.mark.parametrize(
    "status,headers,body,reason_code",
    [
        (401, {}, b"denied", "PROVIDER_AUTH_REJECTED"),
        (404, {}, b"not found", "OBJECT_NOT_FOUND"),
        (403, {}, b"denied", "PROVIDER_AUTH_REJECTED"),
        (
            302,
            {"location": "https://elsewhere.invalid"},
            b"",
            "PROVIDER_HTTP_REJECTED",
        ),
        (200, {}, b"bytes", "OBJECT_ETAG_INVALID"),
        (200, {"etag": 'W/"weak"'}, b"bytes", "OBJECT_ETAG_INVALID"),
        (200, {"etag": "unquoted"}, b"bytes", "OBJECT_ETAG_INVALID"),
        (
            200,
            {"etag": '"invalid"tag"'},
            b"bytes",
            "OBJECT_ETAG_INVALID",
        ),
        (200, {"etag": '"v"'}, b"", "OBJECT_READ_INCOMPLETE"),
        (
            200,
            {"etag": '"v"', "content-length": "999"},
            b"bytes",
            "OBJECT_CONTENT_LENGTH_INVALID",
        ),
        (
            200,
            {"etag": '"v"', "content-encoding": "unsupported"},
            b"bytes",
            "OBJECT_CONTENT_ENCODING_INVALID",
        ),
    ],
)
def test_missing_unversioned_empty_redirect_or_partial_results_block(
    status, headers, body, reason_code
):
    requests = 0

    def handler(request):
        nonlocal requests
        requests += 1
        return httpx.Response(status, headers=headers, content=body)

    with pytest.raises(InventoryBlocked) as error:
        observe(handler)
    assert error.value.reason_code == reason_code
    assert requests == 1


@pytest.mark.parametrize("changed", ["bytes", "etag"])
def test_changing_content_or_version_fails_closed(changed):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(
            200,
            content=b"old" if count == 1 or changed == "etag" else b"new",
            headers={"etag": f'"{count if changed == "etag" else 1}"'},
        )

    with pytest.raises(InventoryBlocked):
        observe(handler)


def test_bounds_and_provider_errors_are_redacted():
    with pytest.raises(InventoryBlocked):
        observe(
            lambda request: httpx.Response(
                200, content=b"too large", headers={"etag": '"v"'}
            ),
            max_bytes=2,
        )

    async def slow(request):
        await asyncio.sleep(0.05)
        return httpx.Response(200, content=b"data", headers={"etag": '"v"'})

    with pytest.raises(InventoryBlocked) as error:
        observe(slow, deadline=0.01)
    assert error.value.reason_code == "PROVIDER_DEADLINE_EXCEEDED"

    def handler(request):
        raise httpx.ReadTimeout("PRIVATE CREDENTIALS")

    with patch.object(inventory_cli.random, "uniform", return_value=0):
        with pytest.raises(InventoryBlocked) as error:
            observe(handler)
    assert "PRIVATE" not in str(error.value)
    assert error.value.__suppress_context__
    assert error.value.reason_code == "PROVIDER_RETRY_EXHAUSTED"


@pytest.mark.parametrize(
    "path", ["", "../other/key", "a/../key", "/key", "a//key", "a\\key", "a\x00key"]
)
def test_unsafe_paths_never_reach_provider(path):
    def never(request):
        raise AssertionError("Unsafe path reached provider")

    with pytest.raises(InventoryBlocked):
        ReadOnlyObserver(
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(never)), BINDING
        )(path)


def test_absolute_deadline_also_interrupts_slow_trickling_body():
    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(0.002)
                yield b"x"

    def handler(request):
        return httpx.Response(200, headers={"etag": '"v"'}, stream=Trickle())

    with pytest.raises(InventoryBlocked, match="deadline") as error:
        observe(handler, deadline=0.01)
    assert error.value.reason_code == "PROVIDER_DEADLINE_EXCEEDED"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_http_statuses_retry_with_a_bounded_attempt_count(status):
    requests = 0

    def handler(request):
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(status)
        return httpx.Response(200, content=b"stable", headers={"etag": '"v"'})

    with patch.object(inventory_cli.random, "uniform", return_value=0):
        result = observe(handler)

    assert result["bytes"] == len(b"stable")
    assert requests == 3


def test_transient_network_error_retries_but_permanent_responses_do_not():
    requests = 0

    def recovers(request):
        nonlocal requests
        requests += 1
        if requests == 1:
            raise httpx.ConnectError("transient")
        return httpx.Response(200, content=b"stable", headers={"etag": '"v"'})

    with patch.object(inventory_cli.random, "uniform", return_value=0):
        observe(recovers)
    assert requests == 3

    for status in (401, 403, 404):
        requests = 0

        def rejects(request):
            nonlocal requests
            requests += 1
            return httpx.Response(status)

        with pytest.raises(InventoryBlocked):
            observe(rejects)
        assert requests == 1


def test_exhausted_transient_http_retries_are_bounded_and_path_free():
    requests = 0

    def unavailable(request):
        nonlocal requests
        requests += 1
        return httpx.Response(503)

    with (
        patch.object(inventory_cli.random, "uniform", return_value=0),
        pytest.raises(InventoryBlocked) as error,
    ):
        observe(unavailable)

    assert requests == inventory_cli.MAX_READ_ATTEMPTS
    assert error.value.reason_code == "PROVIDER_RETRY_EXHAUSTED"
    assert "legacy/a b.mp3" not in str(error.value)


def test_measure_inventory_bounds_concurrency_and_reports_path_free_progress():
    lock = threading.Lock()
    active = 0
    maximum = 0
    progress = []
    completed_at = {}
    rows = [
        {
            "id": str(index),
            "path": f"legacy/{index}",
            "state": "hold",
            "reserved_bytes": None,
        }
        for index in range(5)
    ]

    def callback(path):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.02)
        with lock:
            active -= 1
            completed_at[path.rsplit("/", 1)[-1]] = datetime.now(UTC)
        return {
            "bytes": 1,
            "sha256": hashlib.sha256(path.encode()).hexdigest(),
            "etag": '"stable"',
        }

    plan = measure_inventory(
        {"objects": rows},
        callback,
        max_workers=2,
        progress=lambda completed, total: progress.append((completed, total)),
    )

    assert maximum == 2
    assert progress == [(index, len(rows)) for index in range(1, len(rows) + 1)]
    assert plan["version"] == 2
    assert set(plan) == {"version", "snapshot", "observations"}
    for object_id, evidence in plan["observations"].items():
        measured_at = datetime.fromisoformat(evidence["measured_at"])
        assert measured_at.utcoffset() is not None
        assert measured_at >= completed_at[object_id]



@pytest.mark.parametrize(
    "reason",
    [
        "PROVIDER_DEADLINE_EXCEEDED",
        "PROVIDER_RETRY_EXHAUSTED",
        "PROVIDER_CONNECTION_ERROR",
    ],
)
def test_inventory_retries_one_transient_observation_without_partial_evidence(reason):
    calls = 0

    def flaky(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InventoryBlocked("temporary failure", reason_code=reason)
        return {
            "bytes": 3,
            "sha256": hashlib.sha256(b"abc").hexdigest(),
            "etag": '"stable"',
        }

    rows = [{"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None}]
    plan = measure_inventory({"objects": rows}, flaky, max_workers=1)
    assert calls == 2
    assert plan["observations"]["1"]["bytes"] == 3


def test_inventory_never_retries_permanent_or_repeated_failure():
    rows = [{"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None}]
    for reason, expected_calls in (
        ("OBJECT_NOT_FOUND", 1),
        ("PROVIDER_DEADLINE_EXCEEDED", 2),
    ):
        calls = 0

        def fails(path):
            nonlocal calls
            calls += 1
            raise InventoryBlocked("failed", reason_code=reason)

        with pytest.raises(InventoryBlocked) as error:
            measure_inventory({"objects": rows}, fails, max_workers=1)
        assert error.value.reason_code == reason
        assert calls == expected_calls



def test_inventory_emits_only_complete_verified_observations_before_failure():
    checkpoints = []
    rows = [
        {"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None},
        {"id": "2", "path": "legacy/2", "state": "hold", "reserved_bytes": None},
    ]

    def callback(path):
        if path.endswith("/2"):
            raise InventoryBlocked("missing", reason_code="OBJECT_NOT_FOUND")
        return {
            "bytes": 3,
            "sha256": hashlib.sha256(b"abc").hexdigest(),
            "etag": '"stable"',
        }

    with pytest.raises(InventoryBlocked) as error:
        measure_inventory(
            {"objects": rows},
            callback,
            max_workers=1,
            on_observation=lambda object_id, evidence: checkpoints.append(
                (object_id, evidence)
            ),
        )
    assert error.value.reason_code == "OBJECT_NOT_FOUND"
    assert len(checkpoints) == 1
    assert checkpoints[0][0] == "1"
    assert checkpoints[0][1]["bytes"] == 3
    assert "measured_at" in checkpoints[0][1]



def test_checkpoint_round_trip_and_reuses_only_fresh_matching_evidence(tmp_path):
    path = tmp_path / "inventory.json.checkpoint"
    rows = [{"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None}]
    before = {"objects": rows}
    evidence = {
        "bytes": 3,
        "sha256": hashlib.sha256(b"abc").hexdigest(),
        "etag": '"stable"',
        "measured_at": datetime.now(UTC).isoformat(),
    }
    inventory_cli._save_checkpoint(path, before, {"1": evidence})
    assert inventory_cli._load_checkpoint(path, before) == {"1": evidence}
    plan = measure_inventory(
        before,
        lambda path: pytest.fail("Fresh evidence must not be re-read"),
        initial_observations={"1": evidence},
    )
    assert plan["observations"]["1"] == evidence
    with pytest.raises(InventoryBlocked, match="snapshot"):
        inventory_cli._load_checkpoint(path, {"objects": []})


def test_stale_checkpoint_evidence_fails_closed():
    rows = [{"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None}]
    evidence = {
        "bytes": 3,
        "sha256": hashlib.sha256(b"abc").hexdigest(),
        "etag": '"stable"',
        "measured_at": (datetime.now(UTC) - timedelta(minutes=16)).isoformat(),
    }
    calls = []

    def fresh_read(path):
        calls.append(path)
        return {
            "bytes": 4,
            "sha256": hashlib.sha256(b"new!").hexdigest(),
            "etag": '"new"',
        }

    plan = measure_inventory(
        {"objects": rows}, fresh_read, initial_observations={"1": evidence}
    )
    assert calls == ["legacy/1"]
    assert plan["observations"]["1"]["bytes"] == 4
    assert plan["observations"]["1"]["sha256"] != evidence["sha256"]



def test_future_checkpoint_evidence_blocks_without_provider_reads():
    rows = [{"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None}]
    evidence = {
        "bytes": 3,
        "sha256": hashlib.sha256(b"abc").hexdigest(),
        "etag": '"stable"',
        "measured_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
    }
    with pytest.raises(InventoryBlocked) as error:
        measure_inventory(
            {"objects": rows},
            lambda path: pytest.fail("Future evidence must fail closed"),
            initial_observations={"1": evidence},
        )
    assert error.value.reason_code == "EVIDENCE_STALE_OR_FUTURE"


def test_measure_inventory_rejects_unbounded_concurrency():
    with pytest.raises(InventoryBlocked) as error:
        measure_inventory(
            {"objects": []},
            lambda path: None,
            max_workers=MAX_CONCURRENT_OBSERVATIONS + 1,
        )
    assert error.value.reason_code == "CONCURRENCY_OUT_OF_BOUNDS"


def test_measure_inventory_rejects_evidence_stale_before_plan_completion(monkeypatch):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    calls = 0

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            nonlocal calls
            calls += 1
            return base if calls == 1 else base + timedelta(minutes=16)

    monkeypatch.setattr(inventory, "datetime", Clock)
    rows = [
        {"id": "1", "path": "legacy/1", "state": "hold", "reserved_bytes": None}
    ]

    with pytest.raises(InventoryBlocked) as error:
        measure_inventory(
            {"objects": rows},
            lambda path: {
                "bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
                "etag": '"stable"',
            },
        )

    assert error.value.reason_code == "EVIDENCE_STALE_OR_FUTURE"


@pytest.mark.parametrize(
    "worker_args,expected_workers",
    [([], MAX_CONCURRENT_OBSERVATIONS), (["--workers", "4"], 4)],
)
def test_cli_configures_bounded_observation_workers(
    tmp_path, monkeypatch, worker_args, expected_workers
):
    target = SimpleNamespace(project_ref="synthetic-project")
    engine = MagicMock()
    before = {"objects": []}
    measured = {}

    def fake_measure_inventory(snapshot, observer, **kwargs):
        measured.update(kwargs)
        return {"observations": {}}

    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "synthetic-only")
    with (
        patch.object(inventory_cli.runner, "validate_migration_chain"),
        patch.object(inventory_cli.runner, "load_target", return_value=target),
        patch.object(inventory_cli.runner, "_engine", return_value=engine),
        patch.object(inventory_cli, "verify_connection"),
        patch.object(inventory_cli, "snapshot", return_value=before),
        patch.object(
            inventory_cli, "measure_inventory", side_effect=fake_measure_inventory
        ),
        patch.object(inventory_cli, "plan_digest", return_value="synthetic-digest"),
    ):
        result = inventory_cli.main(
            [
                "plan",
                "--plan-file",
                str(tmp_path / "inventory-plan.json"),
                "--confirm-project-ref",
                target.project_ref,
                "--confirm-uploads-paused",
                *worker_args,
            ]
        )

    assert result == 0
    assert measured["max_workers"] == expected_workers
    engine.dispose.assert_called_once()



def test_cli_does_not_overwrite_existing_plan(tmp_path, monkeypatch):
    target = SimpleNamespace(project_ref="synthetic-project")
    engine = MagicMock()
    before = {"objects": []}
    plan_file = tmp_path / "inventory-plan.json"
    plan_file.write_text("approved existing plan")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "synthetic-only")
    with (
        patch.object(inventory_cli.runner, "validate_migration_chain"),
        patch.object(inventory_cli.runner, "load_target", return_value=target),
        patch.object(inventory_cli.runner, "_engine", return_value=engine),
        patch.object(inventory_cli, "verify_connection"),
        patch.object(inventory_cli, "snapshot", return_value=before),
        patch.object(
            inventory_cli,
            "measure_inventory",
            return_value={"version": 2, "snapshot": before, "observations": {}},
        ),
    ):
        result = inventory_cli.main(
            [
                "plan",
                "--plan-file",
                str(plan_file),
                "--confirm-project-ref",
                target.project_ref,
                "--confirm-uploads-paused",
            ]
        )
    assert result == 1
    assert plan_file.read_text() == "approved existing plan"
    assert not list(tmp_path.glob(".inventory-plan-*"))


def test_checkpoint_write_failure_keeps_last_complete_file(tmp_path):
    path = tmp_path / "inventory.json.checkpoint"
    before = {"objects": []}
    inventory_cli._save_checkpoint(path, before, {})
    original = path.read_bytes()
    with patch.object(inventory_cli.os, "replace", side_effect=OSError("interrupted")):
        with pytest.raises(OSError):
            inventory_cli._save_checkpoint(path, before, {"x": {}})
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".inventory-*"))


@pytest.mark.parametrize("workers", ["0", str(MAX_CONCURRENT_OBSERVATIONS + 1)])
def test_cli_rejects_observation_workers_out_of_bounds(workers, tmp_path):
    with pytest.raises(SystemExit) as error:
        inventory_cli.main(
            [
                "plan",
                "--plan-file",
                str(tmp_path / "inventory-plan.json"),
                "--confirm-project-ref",
                "synthetic-project",
                "--confirm-uploads-paused",
                "--workers",
                workers,
            ]
        )
    assert error.value.code == 2


def test_unknown_reason_codes_cannot_expose_exception_details():
    error = InventoryBlocked("private path", reason_code="private/path")

    assert error.reason_code == "INVENTORY_BLOCKED"


def test_cli_reports_fixed_reason_code_without_exception_details(tmp_path, monkeypatch):
    target = SimpleNamespace(project_ref="synthetic-project")
    engine = MagicMock()
    stderr = io.StringIO()

    with (
        patch.object(inventory_cli.runner, "validate_migration_chain"),
        patch.object(inventory_cli.runner, "load_target", return_value=target),
        patch.object(inventory_cli.runner, "_engine", return_value=engine),
        patch.object(inventory_cli, "verify_connection"),
        patch.object(
            inventory_cli,
            "snapshot",
            side_effect=InventoryBlocked(
                "private object path and credential",
                reason_code="REVISION_MISMATCH",
            ),
        ),
        patch.dict(os.environ, {"SUPABASE_SERVICE_KEY": "synthetic-only"}),
        redirect_stderr(stderr),
    ):
        result = inventory_cli.main(
            [
                "plan",
                "--plan-file",
                str(tmp_path / "inventory-plan.json"),
                "--confirm-project-ref",
                target.project_ref,
                "--confirm-uploads-paused",
            ]
        )

    assert result == 1
    assert "reason_code=REVISION_MISMATCH" in stderr.getvalue()
    assert "private object path" not in stderr.getvalue()
    assert "credential" not in stderr.getvalue()
    assert not (tmp_path / "inventory-plan.json").exists()
    engine.dispose.assert_called_once()
