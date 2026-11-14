"""Fail-closed connection validation for the approved Supabase staging database."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

STAGING_PROJECT_REF = "xgqvwqogdtktgfuubzwk"
STAGING_POOLER_HOST = "aws-0-us-east-1.pooler.supabase.com"
STAGING_DATABASE = "postgres"
STAGING_PORT = 5432
STAGING_ROLES = {
    "app_runtime": f"app_runtime.{STAGING_PROJECT_REF}",
    "google_auth_lookup": f"google_auth_lookup.{STAGING_PROJECT_REF}",
}
STAGING_CA_PATHS = frozenset(
    {
        "/etc/secrets/prod-ca-2021.crt",
        "/home/sam/Downloads/prod-ca-2021.crt",
    }
)
STAGING_CA_SHA256 = "700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7"


class StagingDatabaseConfigurationError(RuntimeError):
    """Raised when staging DB configuration differs from the approved target."""


def _reject() -> None:
    raise StagingDatabaseConfigurationError(
        "Staging database configuration does not match the approved endpoint"
    )


def _validate_connection_overrides(env: dict[str, str]) -> str:
    if any(key.startswith("PG") and key != "PGSSLROOTCERT" for key in env):
        _reject()
    if any(key in env for key in ("SSL_CERT_FILE", "SSL_CERT_DIR")):
        _reject()

    ca_path = env.get("PGSSLROOTCERT", "")
    if ca_path not in STAGING_CA_PATHS:
        _reject()
    path = Path(ca_path)
    try:
        if path.is_symlink() or not path.is_file():
            _reject()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        _reject()
    if digest != STAGING_CA_SHA256:
        _reject()
    return ca_path


def validate_staging_database_url(
    value: str, role: str, env: dict[str, str] | None = None
) -> str:
    """Validate a runtime URL and CA before an engine can be created."""
    env = os.environ if env is None else env
    expected_user = STAGING_ROLES.get(role)
    if expected_user is None or not isinstance(value, str) or not value:
        _reject()
    if value != value.strip() or any(ord(char) < 32 for char in value):
        _reject()

    try:
        parts = urlsplit(value)
        parsed = make_url(value)
    except (ArgumentError, TypeError, ValueError):
        _reject()
    if parts.fragment or parsed.drivername not in {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
    }:
        _reject()
    if (
        parsed.host != STAGING_POOLER_HOST
        or parsed.port != STAGING_PORT
        or parsed.database != STAGING_DATABASE
        or parsed.username != expected_user
        or not parsed.password
        or dict(parsed.query)
        != {"sslmode": "verify-full", "gssencmode": "disable"}
    ):
        _reject()

    _validate_connection_overrides(env)
    return parsed.set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )
