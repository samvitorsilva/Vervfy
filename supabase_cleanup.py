"""Delete one managed object per request using a Storage-RLS-scoped Auth user."""

from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from urllib.parse import quote, urlsplit

import httpx

from scripts.storage_cleanup_worker import CleanupStorageFailure
from storage_namespace import NamespaceBinding

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_TENANT = r"[A-Za-z0-9_-]{1,32}"
_OBJECT = re.compile(
    rf"v2/{_UUID}/{_TENANT}/"
    rf"(?:audio|track-cover|album-cover|artist-photo|staged-audio)/"
    rf"{_UUID}\.[a-z0-9]{{1,5}}"
)
_REQUEST_DEADLINE_SECONDS = 12


class SupabaseCleanupStorage:
    """Use a dedicated Auth identity; never accept the service-role credential."""

    def __init__(
        self,
        binding: NamespaceBinding,
        *,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        subject: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.binding = binding
        self.api_key = (api_key or os.environ.get("SUPABASE_ANON_KEY", "")).strip()
        self.email = (email or os.environ.get("SUPABASE_CLEANUP_EMAIL", "")).strip()
        self.password = password or os.environ.get("SUPABASE_CLEANUP_PASSWORD", "")
        raw_subject = (subject or os.environ.get("SUPABASE_CLEANUP_SUBJECT", "")).strip()
        try:
            self.subject = str(uuid.UUID(raw_subject))
        except ValueError:
            raise ValueError("A dedicated cleanup Auth subject is required") from None
        try:
            endpoint = urlsplit(self.binding.endpoint)
            valid_endpoint = (
                endpoint.scheme == "https"
                and bool(endpoint.hostname)
                and endpoint.username is None
                and endpoint.password is None
                and not endpoint.path.strip("/")
                and not endpoint.query
                and not endpoint.fragment
            )
        except ValueError:
            valid_endpoint = False
        if (
            not self.api_key
            or not self.email
            or not self.password
            or len(self.password) > 1024
            or not valid_endpoint
            or not isinstance(self.binding.namespace_id, uuid.UUID)
            or self.binding.namespace_id.int == 0
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", self.binding.environment)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", self.binding.bucket)
        ):
            raise ValueError("Incomplete Supabase cleanup identity configuration")
        self.transport = transport
        self._access_token: str | None = None
        self._refresh_at = 0.0

    def _validate_path(self, path: str) -> None:
        expected_prefix = f"v2/{self.binding.namespace_id}/"
        if (
            not isinstance(path, str)
            or not path.startswith(expected_prefix)
            or not _OBJECT.fullmatch(path)
            or "*" in path
            or "\\" in path
            or "\x00" in path
        ):
            raise ValueError("Cleanup path is not one managed object key")

    async def _request(self, path: str) -> None:
        try:
            async with asyncio.timeout(_REQUEST_DEADLINE_SECONDS):
                async with httpx.AsyncClient(
                    base_url=self.binding.endpoint,
                    timeout=httpx.Timeout(connect=3, read=4, write=4, pool=2),
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    token = await self._token(client)
                    response = await client.request(
                        "DELETE",
                        "/storage/v1/object/"
                        + quote(self.binding.bucket, safe=""),
                        headers={
                            "Authorization": "Bearer " + token,
                            "apikey": self.api_key,
                        },
                        json={"prefixes": [path]},
                    )
                    if response.status_code != 200:
                        if response.status_code in {408, 429} or response.status_code >= 500:
                            raise CleanupStorageFailure("storage_unavailable")
                        raise CleanupStorageFailure("storage_rejected")
        except CleanupStorageFailure:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise CleanupStorageFailure("storage_timeout") from None
        except httpx.HTTPError:
            raise CleanupStorageFailure("storage_ambiguous") from None
        except (ValueError, TypeError):
            raise CleanupStorageFailure("storage_unknown") from None

    async def _token(self, client: httpx.AsyncClient) -> str:
        now = time.monotonic()
        if self._access_token and now < self._refresh_at:
            return self._access_token
        response = await client.post(
            "/auth/v1/token?grant_type=password",
            headers={"apikey": self.api_key},
            json={"email": self.email, "password": self.password},
        )
        if response.status_code != 200:
            raise CleanupStorageFailure("storage_rejected")
        try:
            payload = response.json()
            token = payload["access_token"]
            user_id = str(uuid.UUID(payload["user"]["id"]))
            expires_in = payload["expires_in"]
        except (KeyError, TypeError, ValueError):
            raise CleanupStorageFailure("storage_unknown") from None
        if (
            not isinstance(token, str)
            or not token
            or user_id != self.subject
            or type(expires_in) not in (int, float)
            or expires_in <= 0
        ):
            raise CleanupStorageFailure("storage_rejected")
        self._access_token = token
        self._refresh_at = now + max(1, expires_in - 30)
        return token

    def delete_if_present(self, path: str) -> None:
        self._validate_path(path)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._request(path))
            return
        raise RuntimeError("Storage cleanup must run outside an active event loop")
