"""Offline preparation and read-only preflight proof; no hosted project access."""

import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy as sa

from scripts import prepare_storage_rehearsal_baseline as prep
from storage_inventory import plan_digest


@pytest.fixture
def inputs(tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_bytes(b"synthetic offline CA pin")
    config = {
        "purpose": prep.rehearsal.PURPOSE,
        "project_ref": "f" * 20,
        "namespace_id": str(uuid.uuid4()),
        "bucket": "vervfy-rehearsal-offline",
        "start_revision": "0031_cleanup_retry_limits",
        "run_id": str(uuid.uuid4()),
        "ca_sha256": hashlib.sha256(ca.read_bytes()).hexdigest(),
        "history_sha256": prep.rehearsal.history_digest(),
    }
    path = tmp_path / "config.json"
    prep.rehearsal.write_private(path, config)
    return path, config, ca


@pytest.mark.parametrize("baseline", prep.rehearsal.SUPPORTED_START_REVISIONS)
def test_bundle_is_private_pinned_deterministic_and_never_connects(
    inputs, tmp_path, monkeypatch, baseline
):
    path, config, ca = inputs
    config["start_revision"] = baseline
    path.write_text(json.dumps(config))
    never = Mock(
        side_effect=AssertionError("offline preparation attempted a connection")
    )
    monkeypatch.setattr(prep.rehearsal, "engine_for", never)
    # Ambient production settings must never be read or copied into artifacts.
    monkeypatch.setenv("VERVFY_PRODUCTION_DATABASE_URL", "PRIVATE_DO_NOT_COPY")
    output = tmp_path / "bundle"
    digest = prep.prepare(path, plan_digest(config), ca, config["project_ref"], output)
    manifest = prep.rehearsal.read_private(output / "manifest.json")
    assert plan_digest(manifest) == digest
    assert manifest["baseline"] == baseline
    assert manifest["ready_for_hosted_execution"] is False
    assert not any("no hosted" in blocker for blocker in manifest["blockers"])
    assert any("tenant-RLS" in blocker for blocker in manifest["blockers"])
    phases = prep.rehearsal.read_private(output / "03-baseline-phases.json")
    assert "storage_rehearsal_provision.py baseline-0031" in next(
        phase["required"]
        for phase in phases["phases"]
        if phase["phase"] == "1-through-0031"
    )
    assert any(
        phase["phase"] == "2-namespace-and-legacy-ledger" for phase in phases["phases"]
    )
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    for name, entry in manifest["files"].items():
        artifact = output / name
        assert stat.S_IMODE(artifact.stat().st_mode) == 0o600
        data = artifact.read_bytes()
        assert entry == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        assert b"PRIVATE_DO_NOT_COPY" not in data
        assert b"offline-validation-only" not in data
    fixture = prep.rehearsal.read_private(output / "04-fixtures.json")
    assert len(fixture["entries"]) == 9
    assert fixture["total_bytes"] < 1024 * 1024
    assert {e["tenant"] for e in fixture["entries"]} == {None, "a", "b"}
    role_plan = prep.rehearsal.read_private(output / "02-role-requirements.json")
    assert set(role_plan["roles"]) == set(prep.ROLES)
    assert set(role_plan["all_roles_forbid"]) == {
        "superuser",
        "bypassrls",
        "createdb",
        "createrole",
        "replication",
    }
    assert {
        (edge["role"], edge["member"], edge["inherit"], edge["set"], edge["admin"])
        for edge in role_plan["memberships"]
    } == {
        ("vervfy_identity_lookup_owner", prep.rehearsal.LOGIN, False, True, False),
        ("vervfy_identity_lookup", "google_auth_lookup", True, False, False),
        ("vervfy_storage_lifecycle_owner", prep.rehearsal.LOGIN, False, True, False),
        ("vervfy_storage_cleanup", "storage_cleanup_worker", True, False, False),
    }
    assert all(
        edge["member"] == "postgres"
        and edge["admin"]
        and not edge["inherit"]
        and not edge["set"]
        for edge in role_plan["permitted_optional_memberships"]
    )
    for entry in fixture["entries"]:
        assert (
            hashlib.sha256((output / entry["file"]).read_bytes()).hexdigest()
            == entry["sha256"]
        )
        assert "upload_verified" not in entry
        if entry["tenant"]:
            assert "{object_uuid}" in entry["reservation_path_pattern"]
    second = tmp_path / "bundle-second"
    assert (
        prep.prepare(path, plan_digest(config), ca, config["project_ref"], second)
        == digest
    )
    with pytest.raises(FileExistsError):
        prep.prepare(path, plan_digest(config), ca, config["project_ref"], output)
    never.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("project_ref", prep.rehearsal.production.PRODUCTION_PROJECT_REF),
        ("project_ref", prep.rehearsal.production.STAGING_PROJECT_REF),
        ("namespace_id", prep.rehearsal.PRODUCTION_NAMESPACE),
        ("bucket", "songs"),
        ("start_revision", "0034_storage_byte_reservations"),
        ("history_sha256", "0" * 64),
    ],
)
def test_unsafe_approved_configuration_creates_no_output(
    inputs, tmp_path, field, value
):
    path, config, ca = inputs
    config[field] = value
    path.write_text(json.dumps(config))
    with pytest.raises(prep.rehearsal.RehearsalBlocked):
        prep.prepare(
            path, plan_digest(config), ca, config["project_ref"], tmp_path / "unsafe"
        )
    assert not (tmp_path / "unsafe").exists()


def test_digest_or_confirmation_drift_blocks_before_artifacts(inputs, tmp_path):
    path, config, ca = inputs
    for digest, ref in (
        ("0" * 64, config["project_ref"]),
        (plan_digest(config), "e" * 20),
    ):
        with pytest.raises(prep.rehearsal.RehearsalBlocked):
            prep.prepare(path, digest, ca, ref, tmp_path / "unsafe")
    assert not (tmp_path / "unsafe").exists()


@pytest.fixture
def local_preflight_db(tmp_path, inputs):
    if os.getuid() == 0 or not all(
        shutil.which(name) for name in ("initdb", "pg_ctl", "openssl")
    ):
        pytest.skip("Requires non-root local PostgreSQL/OpenSSL")
    # PostgreSQL Unix socket path length is bounded: use a short separate directory.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="vervfy-preflight-") as directory:
        root = Path(directory)
        cert = root / "server.crt"
        key = root / "server.key"
        subprocess.run(
            [
                "initdb",
                "-D",
                str(root / "data"),
                "-A",
                "trust",
                "-U",
                "test_admin",
                "--no-locale",
                "--encoding=UTF8",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-nodes",
                "-newkey",
                "rsa:2048",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=IP:127.0.0.1",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            capture_output=True,
        )
        key.chmod(0o600)
        with (root / "data/postgresql.conf").open("a") as out:
            out.write(f"\nssl=on\nssl_cert_file='{cert}'\nssl_key_file='{key}'\n")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(root / "data"),
                "-l",
                str(root / "log"),
                "-o",
                f"-p {port} -k {root} -c listen_addresses=127.0.0.1 -c unix_socket_permissions=0700",
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
        )
        engine = sa.create_engine(
            sa.URL.create(
                "postgresql+psycopg",
                username="test_admin",
                host="127.0.0.1",
                port=port,
                database="postgres",
                query={"sslmode": "verify-full", "sslrootcert": str(cert)},
            )
        )
        path, config, ca = inputs
        profile = prep.load_offline_profile(
            path, plan_digest(config), ca, config["project_ref"]
        )
        try:
            with engine.begin() as c:
                c.exec_driver_sql("CREATE ROLE postgres LOGIN CREATEROLE BYPASSRLS")
                for role, attributes in prep.ROLES.items():
                    login = "LOGIN" if attributes["login"] else "NOLOGIN"
                    inherit = "INHERIT" if attributes["inherit"] else "NOINHERIT"
                    c.exec_driver_sql(
                        f"CREATE ROLE {role} {login} {inherit} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
                    )
                c.exec_driver_sql(
                    f"ALTER SCHEMA public OWNER TO {prep.rehearsal.LOGIN}"
                )
                c.exec_driver_sql(
                    "CREATE SCHEMA vervfy_rehearsal AUTHORIZATION postgres"
                )
                c.exec_driver_sql(
                    "CREATE TABLE vervfy_rehearsal.provisioning_approval(project_ref text,run_id uuid,config_sha256 text,disposable boolean)"
                )
                c.exec_driver_sql(
                    "ALTER TABLE vervfy_rehearsal.provisioning_approval OWNER TO postgres"
                )
                c.execute(
                    sa.text(
                        "INSERT INTO vervfy_rehearsal.provisioning_approval VALUES(:ref,:id,:digest,true)"
                    ),
                    {
                        "ref": config["project_ref"],
                        "id": config["run_id"],
                        "digest": profile.digest,
                    },
                )
            admin = sa.create_engine(engine.url.set(username="postgres"))
            try:
                yield engine, admin, profile
            finally:
                admin.dispose()
        finally:
            engine.dispose()
            subprocess.run(
                ["pg_ctl", "-D", str(root / "data"), "-m", "fast", "-w", "stop"],
                check=True,
                capture_output=True,
            )


def run_preflight(engine, sql):
    raw = engine.raw_connection()
    try:
        driver = raw.driver_connection
        driver.autocommit = True
        try:
            driver.execute(sql, prepare=False)
        except Exception:
            driver.execute("ROLLBACK")
            raise
    finally:
        raw.close()


def test_generated_preflight_accepts_only_fresh_attested_tls_database(
    local_preflight_db,
):
    engine, admin, profile = local_preflight_db
    run_preflight(admin, prep.preflight_sql(profile))
    with engine.connect() as c:
        assert (
            c.exec_driver_sql(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
            ).scalar_one()
            == 0
        )
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE public.keep_existing_data(id integer)")
        c.exec_driver_sql("INSERT INTO public.keep_existing_data VALUES(123)")
    with pytest.raises(Exception, match="Fresh disposable application schema required"):
        run_preflight(admin, prep.preflight_sql(profile))
    with engine.connect() as c:
        assert (
            c.exec_driver_sql("SELECT id FROM public.keep_existing_data").scalar_one()
            == 123
        )


def test_generated_preflight_refuses_wrong_marker_without_mutations(local_preflight_db):
    engine, admin, profile = local_preflight_db
    with engine.begin() as c:
        c.exec_driver_sql(
            "UPDATE vervfy_rehearsal.provisioning_approval SET config_sha256='wrong'"
        )
    with pytest.raises(Exception, match="Disposable provisioning identity mismatch"):
        run_preflight(admin, prep.preflight_sql(profile))
    with engine.connect() as c:
        assert (
            c.exec_driver_sql(
                "SELECT config_sha256 FROM vervfy_rehearsal.provisioning_approval"
            ).scalar_one()
            == "wrong"
        )


def test_generated_preflight_rejects_non_dba_owned_approval(local_preflight_db):
    engine, admin, profile = local_preflight_db
    with engine.begin() as c:
        c.exec_driver_sql(
            f"ALTER TABLE vervfy_rehearsal.provisioning_approval OWNER TO {prep.rehearsal.LOGIN}"
        )
    with pytest.raises(Exception, match="independently DBA-owned"):
        run_preflight(admin, prep.preflight_sql(profile))


def test_generated_preflight_never_grants_missing_bootstrap_privilege(
    local_preflight_db,
):
    engine, admin, profile = local_preflight_db
    with engine.begin() as c:
        c.exec_driver_sql("ALTER ROLE postgres NOBYPASSRLS")
    with pytest.raises(Exception, match="bootstrap capability is unavailable"):
        run_preflight(admin, prep.preflight_sql(profile))
    with engine.connect() as c:
        assert (
            c.exec_driver_sql(
                "SELECT rolbypassrls FROM pg_roles WHERE rolname='postgres'"
            ).scalar_one()
            is False
        )
