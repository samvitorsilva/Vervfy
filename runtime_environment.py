"""Canonical runtime environment names shared by startup and database policy."""

import os
from collections.abc import Mapping


def runtime_environment(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    value = (
        env.get("VERVFY_ENVIRONMENT", "").strip()
        or env.get("ENVIRONMENT", "development").strip()
    ).lower()
    return "production" if value in {"prod", "production"} else value
