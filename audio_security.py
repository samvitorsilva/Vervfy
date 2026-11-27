"""Explicit audio rollout switch with an account-scoped production canary."""
import os

AUDIO_TTL_SECONDS = 900
AUDIO_MIN_VALIDITY_SECONDS = 240
AUDIO_CACHE_CONTROL = "private, no-store, max-age=0, must-revalidate"


def enabled(user_id: str | None = None) -> bool:
    mode = os.environ.get("VERVFY_AUDIO_SECURITY_HARDENING", "0")
    if mode == "0":
        return False
    if mode == "canary":
        accounts = {value.strip() for value in os.environ.get("VERVFY_AUDIO_SECURITY_CANARY_USERS", "").split(",") if value.strip()}
        return bool(user_id and user_id in accounts)
    if mode == "1":
        return True
    raise RuntimeError("Invalid audio security rollout mode")


def upload_cache_control(path: str) -> str:
    # Managed immutable identities carry their kind; do not change artwork policy.
    parts = path.split("/")
    if len(parts) == 5 and parts[0] == "v2" and parts[3] in {"audio", "staged-audio"} and enabled(parts[2]):
        return AUDIO_CACHE_CONTROL
    return "max-age=31536000"
