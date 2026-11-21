"""Fail before engine construction for unsafe disposable rehearsal configuration."""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy.engine import URL, make_url

from scripts import storage_rehearsal as work
from storage_inventory import plan_digest


@pytest.fixture
def configuration(tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_bytes(b"synthetic CA pin; no network")
    config = {
        "purpose": work.PURPOSE,
        "project_ref": "e" * 20,
        "namespace_id": str(uuid.uuid4()),
        "bucket": "vervfy-rehearsal-unit",
        "start_revision": work.production.START_REVISION,
        "run_id": str(uuid.uuid4()),
        "ca_sha256": hashlib.sha256(ca.read_bytes()).hexdigest(),
        "history_sha256": work.history_digest(),
    }
    url = URL.create(
        "postgresql+psycopg",
        username=work.LOGIN,
        password="synthetic",
        host="db." + "e" * 20 + ".supabase.co",
        port=5432,
        database="postgres",
        query={"sslmode": "verify-full", "sslrootcert": str(ca)},
    )
    env = {
        "VERVFY_ENVIRONMENT": "disposable-storage-rehearsal",
        "VERVFY_REHEARSAL_CA_FILE": str(ca),
        "VERVFY_REHEARSAL_DATABASE_URL": url.render_as_string(hide_password=False),
        "VERVFY_REHEARSAL_RUNTIME_URL": url.set(
            username="app_runtime"
        ).render_as_string(hide_password=False),
    }
    path = tmp_path / "profile.json"
    return path, config, env


def save(path, config):
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return plan_digest(config)


def test_exact_private_profile_is_accepted_without_connecting(configuration):
    path, config, env = configuration
    digest = save(path, config)
    assert (
        work.load_profile(path, digest, env).binding.environment
        == "disposable-rehearsal"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("project_ref", work.production.PRODUCTION_PROJECT_REF),
        ("project_ref", work.production.STAGING_PROJECT_REF),
        ("namespace_id", work.PRODUCTION_NAMESPACE),
        ("namespace_id", str(uuid.UUID(int=0))),
        ("bucket", "songs"),
        ("purpose", "production"),
        ("start_revision", "0032_auth_sessions"),
        ("history_sha256", "0" * 64),
        ("ca_sha256", "0" * 64),
    ],
)
def test_even_digest_approved_unsafe_targets_are_rejected(configuration, field, value):
    path, config, env = configuration
    config[field] = value
    digest = save(path, config)
    with pytest.raises(work.RehearsalBlocked):
        work.load_profile(path, digest, env)


@pytest.mark.parametrize(
    "key,value",
    [
        ("VERVFY_ENVIRONMENT", "production"),
        ("ENVIRONMENT", "prod"),
        ("DATABASE_URL", "postgres://private"),
        ("MIGRATION_DATABASE_URL", "postgres://private"),
        ("PGHOST", "private"),
        ("PGHOSTADDR", "127.0.0.1"),
        ("PGPASSFILE", "/tmp/passwords"),
        ("SUPABASE_URL", "https://private"),
        ("SUPABASE_SERVICE_KEY", "PRIVATE_SECRET"),
        ("VERVFY_PRODUCTION_PROJECT_REF", work.production.PRODUCTION_PROJECT_REF),
        ("VERVFY_STAGING_PROFILE", "local-disposable"),
    ],
)
def test_inherited_overrides_fail_before_network(configuration, key, value):
    path, config, env = configuration
    env[key] = value
    digest = save(path, config)
    with pytest.raises(work.RehearsalBlocked):
        work.load_profile(path, digest, env)


@pytest.mark.parametrize("change", ["host", "role", "tls", "extra", "runtime"])
def test_url_mismatch_cannot_route_to_production_or_privileged_login(
    configuration, change
):
    path, config, env = configuration
    digest = save(path, config)
    url = make_url(env["VERVFY_REHEARSAL_DATABASE_URL"])
    if change == "host":
        url = url.set(host=f"db.{work.production.PRODUCTION_PROJECT_REF}.supabase.co")
    if change == "role":
        url = url.set(username="postgres")
    if change == "tls":
        url = url.update_query_dict({"sslmode": "require"})
    if change == "extra":
        url = url.update_query_dict({"hostaddr": "127.0.0.1"})
    if change == "runtime":
        env["VERVFY_REHEARSAL_RUNTIME_URL"] = url.set(
            username="postgres"
        ).render_as_string(hide_password=False)
    else:
        env["VERVFY_REHEARSAL_DATABASE_URL"] = url.render_as_string(hide_password=False)
    with pytest.raises(work.RehearsalBlocked):
        work.load_profile(path, digest, env)


def test_changed_insecure_or_symlink_profile_is_not_accepted(configuration, tmp_path):
    path, config, env = configuration
    digest = save(path, config)
    with pytest.raises(work.RehearsalBlocked):
        work.load_profile(path, "0" * 64, env)
    path.chmod(0o644)
    with pytest.raises(work.RehearsalBlocked):
        work.load_profile(path, digest, env)
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(OSError):
        work.load_profile(link, digest, env)


def test_cli_production_target_is_rejected_before_engine_and_redacts(
    configuration, monkeypatch, capsys
):
    path, config, env = configuration
    config["project_ref"] = work.production.PRODUCTION_PROJECT_REF
    digest = save(path, config)
    monkeypatch.setattr(
        work, "engine_for", Mock(side_effect=AssertionError("network attempted"))
    )
    for key in list(__import__("os").environ):
        monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    expiry = (datetime.now(UTC) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert (
        work.main(
            [
                "snapshot",
                "--config",
                str(path),
                "--config-sha256",
                digest,
                "--confirm-disposable-project",
                config["project_ref"],
                "--confirm-writers-paused",
                "--authorization-expires-at",
                expiry,
                "--receipt-file",
                str(path.parent / "receipt.json"),
            ]
        )
        == 1
    )
    work.engine_for.assert_not_called()
    assert "synthetic" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "metadata",
    [
        {"id": "vervfy-rehearsal-unit", "public": True},
        {"id": "songs", "public": False},
        {},
    ],
)
def test_provider_bucket_must_match_and_be_private(configuration, metadata):
    path, config, env = configuration
    profile = work.load_profile(path, save(path, config), env)

    def handler(request):
        assert request.method == "GET"
        assert request.url.host == "e" * 20 + ".supabase.co"
        return httpx.Response(200, json=metadata)

    with pytest.raises(work.RehearsalBlocked):
        work.verify_bucket(
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            profile.binding,
        )
