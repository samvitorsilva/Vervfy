"""Offline regression tests for the production storage migration runner."""

import importlib.util
import io
import os
import sys
from contextlib import redirect_stderr
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import storage_production_acl_repair as acl_repair

SPEC = importlib.util.spec_from_file_location(
    "storage_production_runner",
    ROOT / "scripts/storage_production_migration.py",
)
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_missing_production_environment_is_blocked():
    with pytest.raises(runner.MigrationBlocked):
        runner.load_target({})


def test_expired_authorization_is_blocked():
    expiry = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with pytest.raises(runner.MigrationBlocked):
        runner.validate_authorization(expiry)


def test_authorization_more_than_15_minutes_is_blocked():
    expiry = (datetime.now(UTC) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with pytest.raises(runner.MigrationBlocked):
        runner.validate_authorization(expiry)


def test_runner_restores_database_environment_after_upgrade():
    connection = MagicMock()
    connection.begin.return_value.__enter__.return_value = connection
    connection.execute.return_value.scalars.return_value.all.return_value = [
        runner.TARGET_REVISION
    ]

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    target = MagicMock()
    target.url.render_as_string.return_value = (
        "postgresql+psycopg://synthetic:synthetic@localhost/synthetic"
    )

    expiry = (datetime.now(UTC) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    original_database_url = os.environ.get("DATABASE_URL")
    original_migration_url = os.environ.get("MIGRATION_DATABASE_URL")

    with (
        patch.object(runner, "_engine", return_value=engine),
        patch.object(runner, "preflight"),
        patch.object(runner, "validate_migration_chain"),
        patch.object(runner, "_verify_followup_result") as postflight,
        patch("alembic.command.upgrade") as upgrade,
    ):
        runner.run_upgrade(target, expiry)

    upgrade.assert_called_once()
    postflight.assert_called_once_with(connection)

    config = upgrade.call_args.args[0]
    assert config.attributes["connection"] is connection
    assert config.attributes["vervfy_production_migration_runner"] is True

    assert os.environ.get("DATABASE_URL") == original_database_url
    assert os.environ.get("MIGRATION_DATABASE_URL") == original_migration_url
    engine.dispose.assert_called_once()


def test_preflight_failure_prevents_upgrade():
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    target = MagicMock()

    expiry = (datetime.now(UTC) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with (
        patch.object(runner, "_engine", return_value=engine),
        patch.object(
            runner,
            "preflight",
            side_effect=runner.MigrationBlocked("Synthetic preflight failure"),
        ),
        patch("alembic.command.upgrade") as upgrade,
        pytest.raises(runner.MigrationBlocked),
    ):
        runner.run_upgrade(target, expiry)

    upgrade.assert_not_called()
    engine.dispose.assert_called_once()


def test_current_reviewed_migration_chain_reaches_quota_head():
    runner.validate_migration_chain()
    assert runner.TARGET_REVISION == "0034_storage_byte_reservations"
    assert runner.EXPECTED_MIGRATION_COUNT == 34


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("PostgreSQL connection did not negotiate TLS", "TLS_NOT_NEGOTIATED"),
        (
            "VERVFY_PRODUCTION_CA_FILE must be a readable CA bundle",
            "CA_FILE_UNREADABLE",
        ),
        (
            "Connected login does not match the approved migration role",
            "MIGRATOR_IDENTITY_MISMATCH",
        ),
        (
            "Migration login requires database CONNECT/CREATE and public USAGE/CREATE",
            "MIGRATOR_PRIVILEGES_INSUFFICIENT",
        ),
        ("Expected exactly 0032_auth_sessions", "REVISION_MISMATCH"),
        (
            "Internal public-table ACLs do not match the reviewed state",
            "INTERNAL_ACL_DRIFT",
        ),
        (
            "storage_role_graph category=app_runtime_attributes; sensitive details",
            "ROLE_GRAPH_APP_RUNTIME_ATTRIBUTES",
        ),
    ],
)
def test_acl_diagnostics_map_preflight_failures_to_safe_codes(message, expected):
    exc = acl_repair.runner.MigrationBlocked(message)

    assert acl_repair._diagnostic_reason_code(exc) == expected


def test_acl_diagnostics_do_not_return_unrecognized_exception_details():
    exc = acl_repair.runner.MigrationBlocked(
        "postgresql://migrator:synthetic-secret@db.example.invalid"
    )

    assert acl_repair._diagnostic_reason_code(exc) == "PREFLIGHT_REJECTED"


def test_acl_diagnostics_classify_inventory_acl_drift():
    exc = acl_repair.InventoryBlocked(
        "Internal table ACL drift is outside the reviewed repair"
    )

    assert acl_repair._diagnostic_reason_code(exc) == "INTERNAL_ACL_DRIFT"


def test_acl_cli_reports_reason_code_without_exception_details(tmp_path):
    secret_detail = (
        "Connected login does not match the approved migration role; "
        "postgresql://migrator:synthetic-secret@db.example.invalid"
    )
    engine = MagicMock()
    target = SimpleNamespace(
        start_revision=acl_repair.runner.AUTH_SESSIONS_REVISION,
        project_ref=acl_repair.runner.PRODUCTION_PROJECT_REF,
    )
    stderr = io.StringIO()

    with (
        patch.object(acl_repair.runner, "validate_migration_chain"),
        patch.object(acl_repair.runner, "load_target", return_value=target),
        patch.object(acl_repair.runner, "_engine", return_value=engine),
        patch.object(
            acl_repair.runner,
            "preflight",
            side_effect=acl_repair.runner.MigrationBlocked(secret_detail),
        ),
        redirect_stderr(stderr),
    ):
        result = acl_repair.main(
            [
                "plan",
                "--plan-file",
                str(tmp_path / "acl-plan.json"),
                "--confirm-project-ref",
                target.project_ref,
                "--confirm-maintenance-window",
            ]
        )

    assert result == 1
    assert "reason_code=MIGRATOR_IDENTITY_MISMATCH" in stderr.getvalue()
    assert "synthetic-secret" not in stderr.getvalue()
    assert "postgresql://" not in stderr.getvalue()
    assert not (tmp_path / "acl-plan.json").exists()
    engine.dispose.assert_called_once()


def test_production_target_accepts_exact_0032_start_revision(tmp_path):
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("synthetic CA bundle")
    url = URL.create(
        "postgresql+psycopg",
        username=runner.PRODUCTION_MIGRATION_ROLE,
        password="synthetic-only",
        host=f"db.{runner.PRODUCTION_PROJECT_REF}.supabase.co",
        port=5432,
        database="postgres",
        query={"sslmode": "verify-full", "sslrootcert": str(ca_file)},
    )
    target = runner.load_target(
        {
            "VERVFY_ENVIRONMENT": "production",
            "VERVFY_PRODUCTION_PROJECT_REF": runner.PRODUCTION_PROJECT_REF,
            "VERVFY_PRODUCTION_EXPECTED_DATABASE": "postgres",
            "VERVFY_PRODUCTION_EXPECTED_USER": runner.PRODUCTION_MIGRATION_ROLE,
            "VERVFY_PRODUCTION_START_REVISION": runner.AUTH_SESSIONS_REVISION,
            "VERVFY_PRODUCTION_DATABASE_URL": url.render_as_string(hide_password=False),
            "VERVFY_PRODUCTION_CA_FILE": str(ca_file),
        }
    )
    assert target.start_revision == runner.AUTH_SESSIONS_REVISION


def test_boundary_authorization_must_match_configured_start(capsys):
    target = MagicMock(
        project_ref="synthetic", start_revision="0033_cleanup_claims_disabled"
    )
    with (
        patch.object(runner, "load_target", return_value=target),
        patch.object(runner, "run_upgrade") as upgrade,
    ):
        result = runner.main(
            [
                "upgrade",
                "--confirm-project-ref",
                "synthetic",
                "--authorize-production-migration",
                runner.AUTHORIZATION,
                "--authorization-expires-at",
                "2099-01-01T00:00:00Z",
            ]
        )
    assert result == 1
    upgrade.assert_not_called()
    assert "Authorization does not match" in capsys.readouterr().err


def test_0032_boundary_authorization_reaches_guarded_upgrade():
    target = MagicMock(
        project_ref="synthetic", start_revision=runner.AUTH_SESSIONS_REVISION
    )
    authorization = f"{runner.AUTH_SESSIONS_REVISION}..{runner.TARGET_REVISION}"
    expiry = (datetime.now(UTC) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with (
        patch.object(runner, "load_target", return_value=target),
        patch.object(runner, "run_upgrade") as upgrade,
    ):
        result = runner.main(
            [
                "upgrade",
                "--confirm-project-ref",
                "synthetic",
                "--authorize-production-migration",
                authorization,
                "--authorization-expires-at",
                expiry,
            ]
        )
    assert result == 0
    upgrade.assert_called_once_with(target, expiry)
