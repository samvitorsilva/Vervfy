from __future__ import annotations

from io import BytesIO
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("VERVFY_SECRET_KEY", "test-only-vervfy-session-secret")

import auth
import server


def image_bytes(image_format: str, size: tuple[int, int] = (32, 32)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (40, 120, 200)).save(output, format=image_format)
    return output.getvalue()


class FakeLibrary:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tracks = {
            "owned-track": SimpleNamespace(
                id="owned-track",
                title="Owned track",
                artist="Test artist",
                album="Test album",
                duration=3.0,
                custom_lyrics=None,
                has_cover=False,
                cover_source="placeholder",
            )
        } if user_id == "user-a" else {}

    def get(self, track_id: str):
        return self.tracks.get(track_id)

    def set_user_cover(self, track_id: str, cover_data: bytes):
        track = self.get(track_id)
        if track is None:
            return None
        track.cover_data = cover_data
        track.has_cover = True
        track.cover_source = "user"
        return track

    def remove_user_cover(self, track_id: str):
        track = self.get(track_id)
        if track is None:
            return None
        track.has_cover = False
        track.cover_source = "placeholder"
        return track


class TrackCoverApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(server.app)
        self.user_id = "user-a"
        self.library = FakeLibrary(self.user_id)
        self.library_patch = patch.object(server, "get_library", side_effect=self.library_for_user)
        self.library_patch.start()
        self.user_override = patch.dict(
            server.app.dependency_overrides,
            {server.require_api_user: lambda: {"id": self.user_id}},
        )
        self.user_override.start()
        self.csrf_override = patch.dict(
            server.app.dependency_overrides,
            {auth.verify_api_csrf: lambda: None},
        )
        self.csrf_override.start()
        self.throttle_patch = patch.object(server.request_throttle, "allow", return_value=True)
        self.throttle_patch.start()

    def tearDown(self) -> None:
        self.throttle_patch.stop()
        self.csrf_override.stop()
        self.user_override.stop()
        self.library_patch.stop()
        server.app.dependency_overrides.clear()

    def library_for_user(self, user_id: str) -> FakeLibrary:
        if user_id == "user-a":
            return self.library
        return FakeLibrary(user_id)

    def test_requires_authentication(self) -> None:
        server.app.dependency_overrides.pop(server.require_api_user)
        uploaded = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.png", image_bytes("PNG"), "image/png")},
        )
        removed = self.client.delete("/api/tracks/owned-track/cover")
        self.assertEqual(uploaded.status_code, 401)
        self.assertEqual(removed.status_code, 401)

    def test_requires_csrf(self) -> None:
        server.app.dependency_overrides.pop(auth.verify_api_csrf)
        response = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.png", image_bytes("PNG"), "image/png")},
        )
        self.assertEqual(response.status_code, 403)

    def test_accepts_and_normalizes_valid_image(self) -> None:
        response = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.webp", image_bytes("WEBP", (1800, 1200)), "image/webp")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["cover_source"], "user")
        with Image.open(BytesIO(self.library.get("owned-track").cover_data)) as result:
            self.assertEqual(result.format, "JPEG")
            self.assertEqual(result.size, (1024, 683))
            self.assertEqual(result.getexif(), {})

    def test_rejects_non_image_oversized_and_unsupported_format(self) -> None:
        non_image = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.png", b"not an image", "image/png")},
        )
        oversized = self.client.put(
            "/api/tracks/owned-track/cover",
            files={
                "file": (
                    "large.png",
                    b"x" * (5 * 1024 * 1024 + 1),
                    "image/png",
                )
            },
        )
        gif = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.gif", image_bytes("GIF"), "image/gif")},
        )
        huge_dimensions = self.client.put(
            "/api/tracks/owned-track/cover",
            files={
                "file": (
                    "dimensions.png",
                    image_bytes("PNG", (4000, 4000)),
                    "image/png",
                )
            },
        )
        self.assertEqual(non_image.status_code, 400)
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(gif.status_code, 400)
        self.assertEqual(huge_dimensions.status_code, 400)

    def test_cannot_change_another_users_track_and_delete_reverts(self) -> None:
        response = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.png", image_bytes("PNG"), "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        self.user_id = "user-b"
        denied = self.client.put(
            "/api/tracks/owned-track/cover",
            files={"file": ("cover.png", image_bytes("PNG"), "image/png")},
        )
        self.assertEqual(denied.status_code, 404)
        self.user_id = "user-a"
        removed = self.client.delete("/api/tracks/owned-track/cover")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json()["cover_source"], "placeholder")


if __name__ == "__main__":
    unittest.main()
