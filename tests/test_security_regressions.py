from __future__ import annotations

import asyncio
from io import BytesIO
from contextlib import nullcontext
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from starlette.responses import Response
from starlette.requests import Request
from PIL import Image

import audio_store
from auth import SessionStore
from library import track_id_for_bytes
import server


class SessionStoreTests(unittest.TestCase):
    def test_revoked_session_is_not_valid(self) -> None:
        store = SessionStore()
        session_id = store.create("user-a")

        self.assertTrue(store.is_valid(session_id, "user-a"))
        self.assertFalse(store.is_valid(session_id, "user-b"))
        store.revoke(session_id)
        self.assertFalse(store.is_valid(session_id, "user-a"))

    def test_logout_rejects_invalid_csrf_for_an_active_session(self) -> None:
        request = type("Request", (), {"session": {"sid": "active"}, "headers": {}})()
        with patch.object(
            server.auth,
            "verify_csrf",
            side_effect=HTTPException(status_code=403),
        ), self.assertRaises(HTTPException):
            server.logout(request, "stale-token")

    def test_logout_remains_idempotent_without_an_active_session(self) -> None:
        request = type("Request", (), {"session": {}, "headers": {}})()
        response = server.logout(request, "stale-token")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session, {})

    def test_account_deletion_removes_all_user_storage_objects(self) -> None:
        user_id = "storage-cleanup-user"
        session = MagicMock()
        session.scalar = lambda *_args, **_kwargs: user_id
        session.scalars.side_effect = [
            SimpleNamespace(all=lambda: [f"{user_id}/track.mp3"]),
            SimpleNamespace(all=lambda: [f"covers/{user_id}/track.jpg"]),
            SimpleNamespace(all=lambda: [f"artist-photos/{user_id}/artist/photo.jpg"]),
            SimpleNamespace(all=lambda: [f"{user_id}/.staging/upload.mp3"]),
        ]
        request = SimpleNamespace(
            session={"sid": "active"},
            app=SimpleNamespace(state=SimpleNamespace(is_first_account=False)),
        )
        storage_paths = [
            f"{user_id}/track.mp3",
            f"covers/{user_id}/track.jpg",
            f"artist-photos/{user_id}/artist/photo.jpg",
            f"{user_id}/.staging/upload.mp3",
        ]

        with (
            patch.object(server, "tenant_session", return_value=nullcontext(session)),
            patch.object(server, "verify_current_password"),
            patch.object(server.audio_store, "delete_many") as delete_many,
            patch.object(server.user_store, "count", return_value=0),
        ):
            result = server.delete_account(
                server.AccountDeletionRequest(
                    current_password="test-password",
                    confirmation="DELETE",
                ),
                request,
                {"id": user_id},
            )

        self.assertEqual(result, {"ok": True})
        delete_many.assert_called_once_with(storage_paths)


class TrackIdentityTests(unittest.TestCase):
    def test_identity_includes_bytes_between_the_old_sample_windows(self) -> None:
        first = b"a" * 65_536 + b"x" + b"b" * 65_536
        second = b"a" * 65_536 + b"y" + b"b" * 65_536

        self.assertNotEqual(track_id_for_bytes(first), track_id_for_bytes(second))


class StorageRangeTests(unittest.TestCase):
    def tearDown(self) -> None:
        audio_store.close_client()

    def test_bulk_delete_with_no_paths_does_not_require_storage_config(self) -> None:
        with patch.object(audio_store, "_client") as client:
            audio_store.delete_many([])
        client.assert_not_called()

    def test_read_range_slices_streaming_response_when_storage_ignores_range(self) -> None:
        body = bytes(range(256)) * 1024

        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["range"], "bytes=100000-100099")
            return httpx.Response(200, content=body)

        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://project.supabase.co",
                    "SUPABASE_SERVICE_KEY": "test-key",
                    "SUPABASE_BUCKET": "songs",
                },
            ),
            patch.object(audio_store, "_transport", httpx.MockTransport(respond)),
        ):
            self.assertEqual(
                audio_store.read_range("user/track.mp3", 100_000, 100_099),
                body[100_000:100_100],
            )


class ApiResponseCacheTests(unittest.TestCase):
    def test_api_get_responses_are_not_cached_between_account_sessions(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/account/photo",
                "query_string": b"",
                "headers": [],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
                "http_version": "1.1",
            }
        )

        async def call_next(_request):
            return Response(headers={"Cache-Control": "private, max-age=86400"})

        response = asyncio.run(server.add_security_headers(request, call_next))
        self.assertEqual(response.headers["cache-control"], "private, no-store")


class HealthCheckTests(unittest.TestCase):
    def test_public_health_check_is_available_without_database_access(self) -> None:
        response = server.healthz()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"ok")
        self.assertEqual(response.headers["cache-control"], "no-store")


class ProfilePhotoValidationTests(unittest.TestCase):
    def test_rejects_images_exceeding_pixel_limit(self) -> None:
        output = BytesIO()
        Image.new("RGB", (3600, 3600)).save(output, format="JPEG")

        with self.assertRaises(HTTPException) as raised:
            server._validate_profile_photo(output.getvalue())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("dimensions", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
