import hashlib
import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from scripts import prepare_storage_rehearsal_baseline as preparation
from scripts import storage_rehearsal as rehearsal
from scripts import upload_storage_rehearsal_fixtures as uploader
from storage_inventory import plan_digest
from storage_namespace import NamespaceBinding


def test_upload_is_create_only_and_verifies_full_readback():
    data = b"synthetic fixture bytes"
    requests = []

    def handle(request):
        requests.append(request)
        if request.method == "POST":
            assert request.headers["x-upsert"] == "false"
            assert request.content == data
            return httpx.Response(201)
        return httpx.Response(200, content=data)

    with httpx.Client(
        base_url="https://fixture.invalid/storage/v1",
        transport=httpx.MockTransport(handle),
    ) as client:
        uploader.upload_verified(
            client, "vervfy-rehearsal-test", "v2/fixture/audio.wav", data, "audio/wav"
        )

    assert [request.method for request in requests] == ["POST", "GET"]
    assert requests[1].url.path.endswith(
        "/object/authenticated/vervfy-rehearsal-test/v2/fixture/audio.wav"
    )


@pytest.mark.parametrize(
    ("responses", "expected_methods"),
    [
        ([httpx.Response(409)], ["POST"]),
        ([httpx.Response(201), httpx.Response(200, content=b"wrong")], ["POST", "GET"]),
        (
            [httpx.Response(201), httpx.Response(200, content=b"too much data")],
            ["POST", "GET"],
        ),
    ],
)
def test_upload_refuses_conflicts_and_unverified_readbacks(responses, expected_methods):
    seen = []

    def handle(request):
        seen.append(request.method)
        return responses.pop(0)

    with (
        httpx.Client(
            base_url="https://fixture.invalid/storage/v1",
            transport=httpx.MockTransport(handle),
        ) as client,
        pytest.raises(rehearsal.RehearsalBlocked),
    ):
        uploader.upload_verified(
            client,
            "vervfy-rehearsal-test",
            "v2/fixture/audio.wav",
            b"fixture",
            "audio/wav",
        )

    assert seen == expected_methods


def test_bundle_upload_inventory_is_private_pinned_and_synthetic(tmp_path):
    profile = SimpleNamespace(
        config={
            "project_ref": "d" * 20,
            "run_id": str(uuid.uuid4()),
            "start_revision": "0031_cleanup_retry_limits",
        },
        digest="a" * 64,
        binding=NamespaceBinding(
            uuid.uuid4(),
            "disposable-rehearsal",
            "https://" + "d" * 20 + ".supabase.co",
            "vervfy-rehearsal-fixtures",
        ),
    )
    expected_files, entries = preparation.fixture_files(profile)
    root = tmp_path / "bundle"
    root.mkdir(mode=0o700)
    (root / "fixtures").mkdir(mode=0o700)
    records = {}
    for relative, data in expected_files.items():
        path = root / relative
        path.write_bytes(data)
        path.chmod(0o600)
        records[relative] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    inventory = {
        "entries": entries,
        "total_bytes": sum(item["bytes"] for item in entries),
        "physical_cleanup_enabled": False,
    }
    inventory_bytes = json.dumps(inventory).encode()
    inventory_path = root / "04-fixtures.json"
    inventory_path.write_bytes(inventory_bytes)
    inventory_path.chmod(0o600)
    records["04-fixtures.json"] = {
        "bytes": len(inventory_bytes),
        "sha256": hashlib.sha256(inventory_bytes).hexdigest(),
    }
    manifest = {
        "purpose": "vervfy-disposable-baseline-review-bundle-v1",
        "project_ref": profile.config["project_ref"],
        "config_sha256": profile.digest,
        "run_id": profile.config["run_id"],
        "baseline": profile.config["start_revision"],
        "ready_for_hosted_execution": False,
        "files": records,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    manifest_path.chmod(0o600)

    managed, loaded = uploader.load_bundle(root, profile, plan_digest(manifest))
    assert len(managed) == 8
    assert len(loaded) == 9
    assert all(item["classification"] == "managed" for item in managed)

    (root / "fixtures/a-audio.wav").write_bytes(b"not the approved fixture")
    (root / "fixtures/a-audio.wav").chmod(0o600)
    with pytest.raises(rehearsal.RehearsalBlocked, match="Fixture bytes"):
        uploader.load_bundle(root, profile, plan_digest(manifest))


def test_internal_production_profile_is_rejected_before_engine_construction():
    profile = SimpleNamespace(
        config={
            "project_ref": rehearsal.production.PRODUCTION_PROJECT_REF,
            "start_revision": "0031_cleanup_retry_limits",
        },
        binding=NamespaceBinding(
            uuid.uuid4(),
            "disposable-rehearsal",
            "https://not-production.supabase.co",
            "vervfy-rehearsal-fixtures",
        ),
        migration_url=object(),
    )
    engine_factory = Mock(side_effect=AssertionError("must not connect"))

    with pytest.raises(rehearsal.RehearsalBlocked, match="Production"):
        uploader.verify_migration_guard(profile, engine_factory)

    engine_factory.assert_not_called()
