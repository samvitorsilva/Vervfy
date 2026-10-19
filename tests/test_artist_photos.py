from __future__ import annotations

from io import BytesIO
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("VERVFY_SECRET_KEY", "test-only-vervfy-session-secret")

import auth
import server


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (48, 48)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (40, 120, 200)).save(output, format=image_format)
    return output.getvalue()


class ArtistPhotoApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(server.app)
        self.user_id = "artist-user-a"
        self.photos: dict[tuple[str, str], dict[str, object]] = {}

        def read_photo(user_id: str, normalized_name: str):
            return self.photos.get((user_id, normalized_name))

        def save_photo(user_id: str, normalized_name: str, jpeg_data: bytes | None, **fields):
            self.photos[(user_id, normalized_name)] = {
                "jpeg_data": jpeg_data,
                **fields,
            }

        def delete_photo(user_id: str, normalized_name: str):
            self.photos.pop((user_id, normalized_name), None)
            return None

        self.read_patch = patch.object(server, "_artist_photo_record", side_effect=read_photo)
        self.save_patch = patch.object(server, "_save_artist_photo", side_effect=save_photo)
        self.delete_patch = patch.object(server, "_delete_artist_photo", side_effect=delete_photo)
        self.read_patch.start()
        self.save_patch.start()
        self.delete_patch.start()
        self.user_override = patch.dict(
            server.app.dependency_overrides,
            {server.require_api_user: lambda: {"id": self.user_id}},
        )
        self.csrf_override = patch.dict(
            server.app.dependency_overrides,
            {auth.verify_api_csrf: lambda: None},
        )
        self.user_override.start()
        self.csrf_override.start()
        self.throttle_patch = patch.object(server.request_throttle, "allow", return_value=True)
        self.throttle_patch.start()

    def tearDown(self) -> None:
        self.throttle_patch.stop()
        self.csrf_override.stop()
        self.user_override.stop()
        self.read_patch.stop()
        self.save_patch.stop()
        self.delete_patch.stop()
        server.app.dependency_overrides.clear()

    def upload(self, payload: bytes, filename: str = "artist.png"):
        return self.client.put(
            "/api/artists/photo",
            data={"name": "Vervfy Test Artist"},
            files={"file": (filename, payload, "image/png")},
        )

    def test_upload_stores_user_photo_in_private_supabase_storage(self) -> None:
        uploaded_objects = []
        with (
            patch.object(server.audio_store, "enabled", return_value=True),
            patch.object(server.audio_store, "upload", side_effect=lambda *args: uploaded_objects.append(args)),
        ):
            response = self.upload(image_bytes())

        self.assertEqual(response.status_code, 200, response.text)
        stored = self.photos[("artist-user-a", "vervfytestartist")]
        self.assertEqual(stored["source"], "user")
        self.assertEqual(stored["jpeg_data"], None)
        self.assertTrue(
            str(stored["storage_path"]).startswith(
                "artist-photos/artist-user-a/vervfytestartist/"
            )
        )
        self.assertTrue(str(stored["storage_path"]).endswith(".jpg"))
        self.assertEqual(len(uploaded_objects), 1)
        self.assertEqual(uploaded_objects[0][2], "image/jpeg")

    def test_storage_photo_is_redirected_directly_to_supabase(self) -> None:
        self.photos[("artist-user-a", "vervfytestartist")] = {
            "source": "user",
            "storage_path": "artist-photos/artist-user-a/vervfytestartist.jpg",
            "jpeg_data": None,
        }
        with patch.object(
            server.audio_store,
            "create_signed_url",
            return_value="https://project.supabase.co/storage/v1/object/sign/songs/photo.jpg?token=x",
        ) as create_signed_url:
            response = self.client.get(
                "/api/artists/photo",
                params={"name": "Vervfy Test Artist"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 307)
        self.assertEqual(
            response.headers["location"],
            "https://project.supabase.co/storage/v1/object/sign/songs/photo.jpg?token=x",
        )
        self.assertEqual(response.headers["cache-control"], "private, max-age=86400")
        create_signed_url.assert_called_once_with(
            "artist-photos/artist-user-a/vervfytestartist.jpg",
            expires_in=7 * 24 * 60 * 60,
        )

    def test_upload_rejects_invalid_format_oversize_and_excessive_pixels(self) -> None:
        invalid = self.upload(b"not an image")
        too_large = self.upload(b"x" * (5 * 1024 * 1024 + 1))
        gif = self.upload(image_bytes("GIF"), "artist.gif")
        too_many_pixels = self.upload(image_bytes("PNG", (4000, 4000)))
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(too_large.status_code, 413)
        self.assertEqual(gif.status_code, 400)
        self.assertEqual(too_many_pixels.status_code, 400)

    def test_photo_routes_require_authentication(self) -> None:
        server.app.dependency_overrides.pop(server.require_api_user)
        uploaded = self.upload(image_bytes())
        fetched = self.client.get(
            "/api/artists/photo", params={"name": "Vervfy Test Artist"}
        )
        removed = self.client.delete(
            "/api/artists/photo", params={"name": "Vervfy Test Artist"}
        )
        self.assertEqual(uploaded.status_code, 401)
        self.assertEqual(fetched.status_code, 401)
        self.assertEqual(removed.status_code, 401)

    def test_photo_mutations_require_csrf(self) -> None:
        server.app.dependency_overrides.pop(auth.verify_api_csrf)
        uploaded = self.upload(image_bytes())
        removed = self.client.delete(
            "/api/artists/photo", params={"name": "Vervfy Test Artist"}
        )
        self.assertEqual(uploaded.status_code, 403)
        self.assertEqual(removed.status_code, 403)

    def test_photo_data_is_isolated_between_users(self) -> None:
        self.photos[("artist-user-a", "vervfytestartist")] = {
            "source": "user",
            "jpeg_data": image_bytes(),
            "storage_path": None,
        }
        self.user_id = "artist-user-b"
        missing = self.client.get(
            "/api/artists/photo", params={"name": "Vervfy Test Artist"}
        )
        self.assertEqual(missing.status_code, 404)

    def test_no_artist_photo_lookup_uses_external_image_services(self) -> None:
        with (
            patch.object(server, "_artist_photo_record", return_value=None),
            patch.object(server.httpx, "Client") as client,
        ):
            self.assertIsNone(server._artist_photo_for_user("user-a", "Unknown Artist"))
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
