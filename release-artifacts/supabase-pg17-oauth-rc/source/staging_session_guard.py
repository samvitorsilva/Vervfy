"""Validate temporary staging before application imports or connections."""
import os


def validate(env=None):
    env = os.environ if env is None else env
    if env.get("VERVFY_ENVIRONMENT", "").strip().lower() != "staging":
        return
    if ("REDIS_URL" in env or env.get("GOOGLE_OAUTH_ENABLED") != "0"
            or env.get("VERVFY_ASYNC_UPLOADS") != "0"
            or env.get("WEB_CONCURRENCY", "1") != "1"):
        raise RuntimeError("Temporary staging requires absent Redis, disabled OAuth/uploads and one worker")
