"""Validate staging runtime settings before application imports or connections."""
import os
import re
from urllib.parse import urlsplit


_RUNTIME_ENVIRONMENTS = {
    "development",
    "dev",
    "test",
    "local",
    "local-test",
    "staging",
    "production",
    "prod",
}


def _validate_staging_redis(env):
    raw = env.get("REDIS_URL")
    if raw is None:
        return
    expected_host = env.get("VERVFY_STAGING_REDIS_HOST")
    if not isinstance(expected_host, str) or not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", expected_host
    ) or ".." in expected_host:
        raise RuntimeError("Staging requires an explicit Redis hostname allowlist")
    if not isinstance(raw, str) or not raw or any(
        char.isspace() or ord(char) < 32 for char in raw
    ):
        raise RuntimeError("Staging REDIS_URL is invalid")
    try:
        url = urlsplit(raw)
        port = url.port
    except ValueError:
        raise RuntimeError("Staging REDIS_URL is malformed") from None
    if not (
        url.scheme == "rediss"
        and url.hostname
        and url.hostname.lower() == expected_host.lower()
        and port is not None
        and 1 <= port <= 65535
        and url.username
        and url.password
        and url.path in ("", "/0")
        and not url.query
        and not url.fragment
    ):
        raise RuntimeError(
            "Staging REDIS_URL must match the authenticated rediss endpoint "
            "without TLS overrides"
        )


def validate(env=None):
    env = os.environ if env is None else env
    environment = (
        env.get("VERVFY_ENVIRONMENT")
        or env.get("ENVIRONMENT", "development")
    ).lower()
    if environment not in _RUNTIME_ENVIRONMENTS:
        raise RuntimeError("Unexpected VERVFY_ENVIRONMENT")
    if environment != "staging":
        return
    if any(re.search(r"(?:^|_)(?:PROD|PRODUCTION)(?:_|$)", key) for key in env):
        raise RuntimeError("Production configuration is forbidden in staging")
    if (
        env.get("GOOGLE_OAUTH_ENABLED") != "0"
        or env.get("VERVFY_ASYNC_UPLOADS") != "0"
        or env.get("WEB_CONCURRENCY", "1") != "1"
    ):
        raise RuntimeError(
            "Staging requires disabled OAuth/uploads and one worker"
        )
    _validate_staging_redis(env)
