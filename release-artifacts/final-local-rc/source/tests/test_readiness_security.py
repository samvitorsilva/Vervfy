"""Isolated security regressions; synthetic bytes and local databases only."""
from __future__ import annotations

import asyncio
import os
import traceback
import unittest
import wave
from io import BytesIO
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

import audio_store
import server
from request_limits import RequestSizeLimitMiddleware


class UploadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        self.addCleanup(self.client.close)
        for patcher in (
            patch.dict(server.app.dependency_overrides, {
                server.require_api_user: lambda: {"id": "audit-user"},
                server.auth.verify_api_csrf: lambda: None,
            }),
            patch.object(server.request_throttle, "allow", return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_all_upload_routes_reject_oversized_bodies_before_parsing(self):
        for method, path, limit in (
            ("POST", "/api/library/upload", server.MAX_UPLOAD_BYTES),
            ("POST", "/api/account/photo", server.MAX_PROFILE_PHOTO_BYTES),
            ("PUT", "/api/artists/photo", server.MAX_ARTIST_PHOTO_BYTES),
            ("PUT", "/api/tracks/test/cover", server.MAX_TRACK_COVER_BYTES),
        ):
            with self.subTest(path=path):
                response = self.client.request(method, path, content=b"malformed", headers={
                    "content-type": "multipart/form-data; boundary=audit",
                    "content-length": str(limit + server.MULTIPART_UPLOAD_OVERHEAD_BYTES + 1),
                })
                self.assertEqual(response.status_code, 413)

    def test_async_upload_rejects_invalid_content_before_staging(self):
        with patch.object(server, "async_uploads", True), patch.object(server, "_queue_staged_upload") as queue:
            response = self.client.post("/api/library/upload", files={
                "file": ("song.mp3", b"not audio", "audio/mpeg"),
            })
        self.assertEqual(response.status_code, 400)
        queue.assert_not_called()

    def test_async_upload_rejects_executable_extension_before_staging(self):
        with patch.object(server, "async_uploads", True), patch.object(server, "_queue_staged_upload") as queue:
            response = self.client.post("/api/library/upload", files={
                "file": ("../../app.py", b"print('test')", "audio/mpeg"),
            })
        self.assertEqual(response.status_code, 400)
        queue.assert_not_called()

    def test_audio_upload_rejects_executable_double_extension(self):
        with patch.object(server, "async_uploads", True), patch.object(server, "_queue_staged_upload") as queue:
            response = self.client.post("/api/library/upload", files={
                "file": ("song.php.mp3", b"not audio", "audio/mpeg"),
            })
        self.assertEqual(response.status_code, 400)
        queue.assert_not_called()

    def test_chunked_and_underdeclared_requests_cannot_bypass_parser_limit(self):
        async def check(headers):
            async def chunks():
                yield b'{"padding":"'
                yield b"x" * 128
                yield b'"}'

            with patch.object(RequestSizeLimitMiddleware, "limit_for", return_value=64):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
                    return await client.put("/api/library/state", content=chunks(), headers={
                        "content-type": "application/json", **headers,
                    })

        for headers in ({}, {"content-length": "1"}):
            with self.subTest(headers=headers):
                self.assertEqual(asyncio.run(check(headers)).status_code, 413)

    def test_invalid_content_lengths_are_rejected(self):
        for value, expected in (("-1", 400), ("invalid", 400), ("9" * 5000, 413)):
            with self.subTest(expected=expected):
                response = self.client.post("/api/library/upload", content=b"", headers={"content-length": value})
                self.assertEqual(response.status_code, expected)

    def test_valid_async_audio_uses_safe_filename_and_checks_quota(self):
        output = BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\0\0" * 800)
        with (
            patch.object(server, "async_uploads", True),
            patch.object(server, "_queue_staged_upload") as queue,
            patch.object(server, "_upload_preflight", return_value=("id", 0, 0, False)),
        ):
            response = self.client.post("/api/library/upload", files={
                "file": ("../../music.wav", output.getvalue(), "application/octet-stream"),
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queue.call_args.args[2], "music.wav")
        with (
            patch.object(server, "async_uploads", True),
            patch.object(server, "_queue_staged_upload") as queue,
            patch.object(server, "_upload_preflight", return_value=("id", server.USER_QUOTA_BYTES, 0, False)),
        ):
            response = self.client.post("/api/library/upload", files={
                "file": ("music.wav", output.getvalue(), "audio/wav"),
            })
        self.assertEqual(response.status_code, 413)
        queue.assert_not_called()

    def test_lyrics_gate_requires_authentication(self):
        server.app.dependency_overrides.pop(server.require_api_user)
        self.assertEqual(self.client.get("/api/lyrics/authorize").status_code, 401)

    def test_lyrics_gate_honors_disable_flag_rate_limit_and_outage(self):
        with patch.dict(os.environ, {"LYRICS_PROVIDER_LRCLIB": "0"}):
            self.assertEqual(self.client.get("/api/lyrics/authorize").status_code, 403)
        with patch.dict(os.environ, {"LYRICS_PROVIDER_LRCLIB": "1"}):
            with patch.object(server.request_throttle, "allow", return_value=False):
                response = self.client.get("/api/lyrics/authorize")
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response.headers["retry-after"], "60")
            with patch.object(server.request_throttle, "allow", side_effect=RuntimeError("offline")):
                self.assertEqual(self.client.get("/api/lyrics/authorize").status_code, 503)
            with patch.object(server.request_throttle, "allow", return_value=True) as limiter:
                self.assertEqual(self.client.get("/api/lyrics/authorize").status_code, 204)
                limiter.assert_called_once_with("lyrics:audit-user", 60, 60)


class StorageErrorDisclosureTests(unittest.TestCase):
    def test_provider_error_body_is_not_exposed(self):
        sentinel = "synthetic-private-error-value"
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(403, text=sentinel),
        ), base_url="https://storage.example.test")
        with client, patch.object(audio_store, "_client", return_value=client), self.assertRaises(audio_store.StorageError) as result:
            audio_store.upload("audit/test.mp3", b"test")
        self.assertNotIn(sentinel, str(result.exception))

    def test_network_error_traceback_does_not_expose_credentials(self):
        sentinel = "synthetic-private-key-value"

        @audio_store._wrap_errors
        def failing_request():
            raise httpx.ConnectError(f"failed with {sentinel}")

        with patch.dict(os.environ, {"SUPABASE_SERVICE_KEY": sentinel}):
            try:
                failing_request()
            except audio_store.StorageError:
                formatted = traceback.format_exc()
        self.assertNotIn(sentinel, formatted)


class ProfileContentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        self.addCleanup(self.client.close)
        self.user_override = patch.dict(
            server.app.dependency_overrides,
            {server.require_api_user: lambda: {"id": "profile-audit-user"}},
        )
        self.user_override.start()
        self.addCleanup(self.user_override.stop)
        self.csrf_patch = patch.object(server.auth, "verify_api_csrf")
        self.csrf_patch.start()
        self.addCleanup(self.csrf_patch.stop)
        self.throttle_patch = patch.object(
            server.request_throttle, "allow", return_value=True
        )
        self.throttle_patch.start()
        self.addCleanup(self.throttle_patch.stop)

    def test_profile_photo_rejects_truncated_jpeg_pixel_data(self):
        output = BytesIO()
        Image.new("RGB", (16, 16)).save(output, "JPEG")
        data = output.getvalue()
        self.assertEqual(server._validate_profile_photo(data), "image/jpeg")
        with self.assertRaises(HTTPException) as result:
            server._validate_profile_photo(data[:-2])
        self.assertEqual(result.exception.status_code, 400)

    def test_photo_filename_must_be_allowed_and_match_decoded_content(self):
        png = BytesIO()
        Image.new("RGB", (16, 16)).save(png, "PNG")
        for filename in ("photo.php.png", "photo.jsp", "photo.jpg"):
            with self.subTest(filename=filename):
                with self.assertRaises(HTTPException):
                    expected = server._image_upload_format(
                        filename, server.IMAGE_UPLOAD_FORMATS
                    )
                    server._validate_profile_photo(png.getvalue(), expected)

    def test_profile_route_rejects_dangerous_or_mismatched_filenames(self):
        jpeg = BytesIO()
        Image.new("RGB", (16, 16)).save(jpeg, "JPEG")
        with patch.object(server.user_store, "update_profile_photo") as save:
            for filename in ("photo.php.jpg", "photo.jsp", "photo.png"):
                with self.subTest(filename=filename):
                    response = self.client.post(
                        "/api/account/photo",
                        files={"file": (filename, jpeg.getvalue(), "image/jpeg")},
                    )
                    self.assertEqual(response.status_code, 400)
            save.assert_not_called()

    def test_profile_route_accepts_a_valid_matching_image(self):
        png = BytesIO()
        Image.new("RGB", (16, 16)).save(png, "PNG")
        with patch.object(server.user_store, "update_profile_photo") as save:
            response = self.client.post(
                "/api/account/photo",
                files={"file": ("photo.png", png.getvalue(), "image/png")},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"photo_url": "/api/account/photo"})
        self.assertEqual(save.call_args.args[0], "profile-audit-user")
        self.assertEqual(save.call_args.args[2], "image/png")


if __name__ == "__main__":
    unittest.main()
