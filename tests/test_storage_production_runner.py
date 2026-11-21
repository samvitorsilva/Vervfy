"""Offline regression tests for the production storage migration runner."""

import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "storage_production_runner",
    ROOT / "scripts/storage_production_migration.py",
)
runner = importlib.util.module_from_spec(SPEC)
import sys

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
