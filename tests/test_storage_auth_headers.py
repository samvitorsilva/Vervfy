"""Credential headers on real HTTPX requests; synthetic keys and mock transports only."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

import audio_store
import storage_lifecycle
from scripts import storage_inventory_reconcile as inventory
from scripts import storage_rehearsal as rehearsal
from storage_namespace import NamespaceBinding

KEYS = ["sb_secret_synthetic_storage_test", "eyJhbGciOiJIUzI1NiJ9.synthetic.signature"]
ENDPOINT = "https://storage-headers-test.supabase.co"
BUCKET = "synthetic"


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch):
    audio_store.close_client()
    monkeypatch.setenv("SUPABASE_URL", ENDPOINT)
    monkeypatch.setenv("SUPABASE_BUCKET", BUCKET)
    monkeypatch.delenv("VERVFY_STORAGE_BACKEND", raising=False)
    yield
    audio_store.close_client()


def assert_credentials(request, key):
    assert request.headers.get_list("apikey") == [key]
    if key.startswith("sb_secret_"):
        assert "authorization" not in request.headers
    else:
        assert request.headers.get_list("authorization") == ["Bearer " + key]


@pytest.mark.parametrize("key", KEYS, ids=["modern", "legacy"])
def test_sync_storage_request_uses_correct_headers(monkeypatch, key):
    seen = []

    def provider(request):
        assert_credentials(request, key)
        seen.append(request)
        return httpx.Response(200, json={"public": False})

    monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
    monkeypatch.setattr(audio_store, "_transport", httpx.MockTransport(provider))
    assert audio_store.bucket_is_private()
    assert len(seen) == 1
    assert audio_store._client().follow_redirects is False
    assert audio_store._client().timeout.connect == 10


def test_pooled_client_rotation_never_reuses_old_bearer_header(monkeypatch):
    observed = []

    def provider(request):
        observed.append(request)
        return httpx.Response(200, json={"public": False})

    monkeypatch.setattr(audio_store, "_transport", httpx.MockTransport(provider))
    previous = None
    for key in (KEYS[1], KEYS[0], KEYS[1]):
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
        assert audio_store.bucket_is_private()
        assert_credentials(observed[-1], key)
        current = audio_store._client()
        if previous is not None:
            assert previous.is_closed
            assert current is not previous
        previous = current


@pytest.mark.parametrize("key", KEYS, ids=["modern", "legacy"])
def test_lifecycle_async_request_keeps_binding_timeouts_and_headers(monkeypatch, key):
    seen = []

    def provider(request):
        assert_credentials(request, key)
        assert request.headers["accept-encoding"] == "identity"
        seen.append(request)
        return httpx.Response(200, content=b"synthetic")

    monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
    monkeypatch.setattr(audio_store, "_transport", httpx.MockTransport(provider))
    binding = NamespaceBinding(uuid.uuid4(), "disposable-test", ENDPOINT, BUCKET)

    async def request():
        async with storage_lifecycle._client(binding) as client:
            assert client.follow_redirects is False
            assert client.timeout.connect == 5
            assert client.timeout.read == 10
            assert (
                await client.get("/object/authenticated/synthetic/file.mp3")
            ).status_code == 200

    asyncio.run(request())
    assert len(seen) == 1
    with pytest.raises(audio_store.StorageError, match="settings changed"):
        storage_lifecycle._client(
            NamespaceBinding(
                binding.namespace_id, binding.environment, ENDPOINT, "wrong-bucket"
            )
        )
    assert len(seen) == 1


@pytest.mark.parametrize("key", KEYS, ids=["modern", "legacy"])
@pytest.mark.parametrize("tool", ["inventory", "rehearsal"])
def test_plan_clients_share_header_policy_without_db_or_provider_access(
    monkeypatch, tmp_path, key, tool
):
    # Database/target guards are stubbed solely to reach nested HTTP factories.
    # This tests header wiring, not authorization or database guard correctness.
    seen = []
    binding = NamespaceBinding(uuid.uuid4(), "disposable-test", ENDPOINT, BUCKET)
    before = {
        "namespace": [],
        "objects": [
            {
                "id": str(uuid.uuid4()),
                "path": "legacy/synthetic.mp3",
                "state": "hold",
                "reserved_bytes": None,
            }
        ],
    }

    def provider(request):
        assert request.url.host == "storage-headers-test.supabase.co"
        assert request.method == "GET"
        assert_credentials(request, key)
        seen.append(request)
        if "/bucket/" in request.url.path:
            return httpx.Response(200, json={"id": BUCKET, "public": False})
        return httpx.Response(200, content=b"synthetic", headers={"etag": '"v1"'})

    original_client = httpx.AsyncClient

    def client_factory(**options):
        assert options["follow_redirects"] is False
        assert options["trust_env"] is False
        return original_client(transport=httpx.MockTransport(provider), **options)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    engine = MagicMock()
    output = tmp_path / "plan.json"
    if tool == "inventory":
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
        monkeypatch.setattr(
            inventory.runner,
            "load_target",
            lambda: SimpleNamespace(project_ref="storage-headers-test"),
        )
        monkeypatch.setattr(inventory.runner, "_engine", lambda target: engine)
        monkeypatch.setattr(inventory, "verify_connection", lambda *args: None)
        # Bind the fake observer host; this is never the production endpoint.
        monkeypatch.setattr(inventory, "NamespaceBinding", lambda *args: binding)
        monkeypatch.setattr(inventory, "snapshot", lambda *args: before)
        assert (
            inventory.main(
                [
                    "plan",
                    "--plan-file",
                    str(output),
                    "--confirm-project-ref",
                    "storage-headers-test",
                    "--confirm-uploads-paused",
                ]
            )
            == 0
        )
        assert len(seen) == 2
    else:
        monkeypatch.setenv("VERVFY_REHEARSAL_STORAGE_KEY", key)
        profile = SimpleNamespace(
            config={"project_ref": "storage-headers-test"},
            binding=binding,
            migration_url=None,
        )
        monkeypatch.setattr(rehearsal, "load_profile", lambda *args: profile)
        monkeypatch.setattr(rehearsal, "engine_for", lambda url: engine)
        monkeypatch.setattr(rehearsal, "guard", lambda *args, **kwargs: None)
        monkeypatch.setattr(rehearsal, "snapshot", lambda *args: before)
        expiry = (datetime.now(UTC) + timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assert (
            rehearsal.main(
                [
                    "plan",
                    "--config",
                    str(tmp_path / "unused.json"),
                    "--config-sha256",
                    "synthetic",
                    "--confirm-disposable-project",
                    "storage-headers-test",
                    "--confirm-writers-paused",
                    "--authorization-expires-at",
                    expiry,
                    "--plan-file",
                    str(output),
                ]
            )
            == 0
        )
        assert len(seen) == 3
    assert output.is_file()
    engine.dispose.assert_called_once()


@pytest.mark.parametrize("key", KEYS, ids=["modern", "legacy"])
def test_modern_and_legacy_credentials_stay_out_of_network_errors(monkeypatch, key):
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)

    def failing_provider(request):
        raise httpx.ReadTimeout("provider included " + key)

    monkeypatch.setattr(
        audio_store, "_transport", httpx.MockTransport(failing_provider)
    )
    with pytest.raises(audio_store.StorageError) as error:
        audio_store.bucket_is_private()
    assert key not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("key", KEYS, ids=["modern", "legacy"])
@pytest.mark.parametrize("status", [302, 401])
def test_redirects_and_rejections_never_forward_or_retry_credentials(
    monkeypatch, key, status
):
    seen = []

    def provider(request):
        assert request.url.host == "storage-headers-test.supabase.co"
        assert_credentials(request, key)
        seen.append(request)
        return httpx.Response(
            status,
            headers={"location": "https://other-headers-test.invalid/"},
            content=("private response " + key).encode(),
        )

    monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
    monkeypatch.setattr(audio_store, "_transport", httpx.MockTransport(provider))
    with pytest.raises(audio_store.StorageError) as error:
        audio_store.bucket_is_private()
    assert len(seen) == 1
    assert key not in str(error.value)
