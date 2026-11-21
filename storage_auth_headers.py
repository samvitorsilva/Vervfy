"""Server-side Supabase Storage credentials; never interpret opaque keys as JWTs."""


def storage_auth_headers(key: str) -> dict[str, str]:
    """Use opaque secret keys as API keys; preserve legacy bearer authentication."""
    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + key
    return headers
