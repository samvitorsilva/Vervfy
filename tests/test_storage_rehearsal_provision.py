import hashlib
import os
import shutil
import socket
import subprocess
import uuid

import pytest
import sqlalchemy as sa

from scripts import storage_rehearsal as rehearsal
from scripts import storage_rehearsal_provision as provision
from storage_inventory import plan_digest


@pytest.fixture
def local_target(tmp_path):
    if os.getuid() == 0 or not all(
        shutil.which(name) for name in ("initdb", "pg_ctl", "openssl")
    ):
        pytest.skip("Requires non-root local PostgreSQL/OpenSSL")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    root = tmp_path / "pg"
    root.mkdir()
    subprocess.run(
        [
            "initdb",
            "-D",
            str(root / "data"),
            "-A",
            "trust",
            "-U",
            "postgres",
            "--no-locale",
            "--encoding=UTF8",
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    cert, key = root / "server.crt", root / "server.key"
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
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    key.chmod(0o600)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (root / "data/postgresql.conf").open("a") as out:
        out.write(f"\nssl=on\nssl_cert_file='{cert}'\nssl_key_file='{key}'\n")
    subprocess.run(
        [
            "pg_ctl",
            "-D",
            str(root / "data"),
            "-l",
            str(root / "log"),
            "-o",
            f"-p {port} -k {root} -c listen_addresses=127.0.0.1",
            "-w",
            "start",
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    admin_url = sa.URL.create(
        "postgresql+psycopg",
        username="postgres",
        host="127.0.0.1",
        port=port,
        database="postgres",
        query={"sslmode": "verify-full", "sslrootcert": str(cert)},
    )
    admin = sa.create_engine(admin_url)
    try:
        yield root, cert, admin_url, admin
    finally:
        admin.dispose()
        subprocess.run(
            ["pg_ctl", "-D", str(root / "data"), "-m", "fast", "-w", "stop"],
            env=env,
            check=True,
            capture_output=True,
        )


def make_profile(cert, configured_revision):
    project_ref = "e" * 20
    config = {
        "purpose": rehearsal.PURPOSE,
        "project_ref": project_ref,
        "namespace_id": str(uuid.uuid4()),
        "bucket": "vervfy-rehearsal-local",
        "start_revision": configured_revision,
        "run_id": str(uuid.uuid4()),
        "ca_sha256": hashlib.sha256(cert.read_bytes()).hexdigest(),
        "history_sha256": rehearsal.history_digest(),
    }
    digest = plan_digest(config)
    query = {"sslmode": "verify-full", "sslrootcert": str(cert)}
    migration_url = sa.URL.create(
        "postgresql+psycopg",
        username=rehearsal.LOGIN,
        password="synthetic-local-test-only",
        host=f"db.{project_ref}.supabase.co",
        port=5432,
        database="postgres",
        query=query,
    )
    runtime_url = migration_url.set(
        username="app_runtime", password="synthetic-local-runtime-only"
    )
    return rehearsal.Profile(config, digest, migration_url, runtime_url)


def test_dba_url_is_project_bound_and_ca_pinned(tmp_path, monkeypatch):
    ca = tmp_path / "ca.pem"
    ca.write_bytes(b"synthetic pinned CA")
    profile = make_profile(ca, provision.BASELINE_0031)
    query = {
        "sslmode": "verify-full",
        "sslrootcert": str(ca),
    }
    valid = sa.URL.create(
        "postgresql+psycopg",
        username="postgres",
        password="synthetic-local-dba-only",
        host=f"db.{profile.config['project_ref']}.supabase.co",
        port=5432,
        database="postgres",
        query=query,
    )
    monkeypatch.setenv(
        "VERVFY_REHEARSAL_DBA_DATABASE_URL",
        valid.render_as_string(hide_password=False),
    )
    assert provision.dba_url(profile) == valid

    for rejected in (
        valid.set(host="db.production.supabase.co"),
        valid.update_query_dict({"sslmode": "require"}),
        valid.set(username="app_runtime"),
    ):
        monkeypatch.setenv(
            "VERVFY_REHEARSAL_DBA_DATABASE_URL",
            rejected.render_as_string(hide_password=False),
        )
        with pytest.raises(rehearsal.RehearsalBlocked):
            provision.dba_url(profile)


@pytest.mark.parametrize(
    "ambient",
    (
        {"DATABASE_URL": "postgresql://production.invalid/postgres"},
        {"PGHOST": "production.invalid"},
        {"SUPABASE_SERVICE_KEY": "synthetic-only"},
    ),
)
def test_ambient_database_and_provider_settings_are_rejected(ambient):
    with pytest.raises(rehearsal.RehearsalBlocked):
        provision._validate_environment(
            {"VERVFY_ENVIRONMENT": "disposable-storage-rehearsal", **ambient}
        )


@pytest.mark.parametrize(
    "configured_revision",
    (provision.BASELINE_0031, provision.BASELINE_0033),
)
def test_local_tls_provisioning_baseline_and_legacy_seed(
    local_target, configured_revision
):
    _root, cert, admin_url, admin = local_target
    profile = make_profile(cert, configured_revision)

    with admin.begin() as connection:
        provision.bootstrap_database(connection, profile)
    with admin.begin() as connection:
        provision.bootstrap_database(connection, profile)
    with admin.connect() as connection:
        roles = connection.execute(
            sa.text("""SELECT rolname,rolcanlogin,rolinherit,rolsuper,
                rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,rolpassword
                FROM pg_catalog.pg_authid
                WHERE rolname IN ('vervfy_rehearsal_migrator','app_runtime',
                    'google_auth_lookup','storage_cleanup_worker')
                ORDER BY rolname""")
        ).all()
        assert len(roles) == 4
        assert all(row.rolpassword is None for row in roles)

    migration = sa.create_engine(admin_url.set(username=rehearsal.LOGIN))
    try:
        with migration.begin() as connection:
            provision.baseline_0031(connection, profile)
        with admin.begin() as connection:
            provision.initialize_disposable_namespace(connection, profile)
            provision.initialize_disposable_namespace(connection, profile)
        with migration.begin() as connection:
            provision.seed_legacy_ledger(connection, profile)
            provision.seed_legacy_ledger(connection, profile)
        with migration.begin() as connection:
            if configured_revision == provision.BASELINE_0031:
                provision.approve_0031(connection, profile)
            else:
                provision.baseline_0033(connection, profile)
        with migration.begin() as connection:
            if configured_revision == provision.BASELINE_0031:
                rehearsal.guard(connection, profile, head=provision.BASELINE_0031)
            else:
                rehearsal.guard(connection, profile, head=provision.BASELINE_0033)
            rls = connection.exec_driver_sql(
                """SELECT relrowsecurity,relforcerowsecurity
                FROM pg_catalog.pg_class WHERE oid='public.tracks'::regclass"""
            ).one()
            assert tuple(rls) == (True, True)
            connection.exec_driver_sql("SET LOCAL ROLE vervfy_storage_lifecycle_owner")
            object_state = connection.exec_driver_sql(
                """SELECT classification,state,tenant_id,reservation_token,
                    upload_verified FROM vervfy_storage.objects"""
            ).one()
            assert tuple(object_state) == ("legacy", "hold", None, None, False)
            job = connection.exec_driver_sql(
                """SELECT state,attempts,claim_token,lease_until
                FROM vervfy_storage.cleanup_jobs"""
            ).one()
            assert tuple(job) == ("held", 0, None, None)
            assert (
                connection.exec_driver_sql(
                    "SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces"
                ).scalar_one()
                is False
            )
            connection.exec_driver_sql("RESET ROLE")
            revision = connection.exec_driver_sql(
                "SELECT version_num FROM public.alembic_version"
            ).scalar_one()
            assert revision == configured_revision
    finally:
        migration.dispose()

    # A rerun against populated history must block without disturbing it.
    with admin.begin() as connection:
        version_before = connection.exec_driver_sql(
            "SELECT version_num FROM public.alembic_version"
        ).scalar_one()
        with pytest.raises(rehearsal.RehearsalBlocked):
            provision.bootstrap_database(connection, profile)
        assert (
            connection.exec_driver_sql(
                "SELECT version_num FROM public.alembic_version"
            ).scalar_one()
            == version_before
        )
