from __future__ import annotations

from io import BytesIO
import os
import time
import unittest
from unittest.mock import patch

import httpx
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

        def save_photo(user_id: str, normalized_name: str, jpeg_data: bytes, **fields):
            self.photos[(user_id, normalized_name)] = {
                "jpeg_data": jpeg_data,
                **fields,
            }

        def delete_photo(user_id: str, normalized_name: str):
            self.photos.pop((user_id, normalized_name), None)

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
        self.commons_flag = patch.dict(os.environ, {"ARTIST_PHOTOS_COMMONS": "0"})
        self.commons_flag.start()
        server._artist_commons_photo_cache.clear()

    def tearDown(self) -> None:
        self.commons_flag.stop()
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

    def test_upload_normalizes_and_strips_exif_then_serves_the_stored_photo(self) -> None:
        output = BytesIO()
        image = Image.new("RGB", (1200, 600), (20, 80, 120))
        exif = Image.Exif()
        exif[270] = "private image metadata"
        image.save(output, format="JPEG", exif=exif)

        uploaded = self.upload(output.getvalue(), "portrait.jpg")
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        stored = self.photos[("artist-user-a", "vervfytestartist")]
        self.assertEqual(stored["source"], "user")
        with Image.open(BytesIO(stored["jpeg_data"])) as result:
            self.assertEqual(result.format, "JPEG")
            self.assertEqual(result.size, (800, 400))
            self.assertEqual(result.getexif(), {})

        fetched = self.client.get("/api/artists/photo", params={"name": "Vervfy Test Artist"})
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.headers["content-type"], "image/jpeg")
        self.assertEqual(fetched.content, stored["jpeg_data"])

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
        fetched = self.client.get("/api/artists/photo", params={"name": "artist"})
        removed = self.client.delete("/api/artists/photo", params={"name": "artist"})
        self.assertEqual(uploaded.status_code, 401)
        self.assertEqual(fetched.status_code, 401)
        self.assertEqual(removed.status_code, 401)

    def test_photo_mutations_require_csrf(self) -> None:
        server.app.dependency_overrides.pop(auth.verify_api_csrf)
        uploaded = self.upload(image_bytes())
        removed = self.client.delete("/api/artists/photo", params={"name": "artist"})
        self.assertEqual(uploaded.status_code, 403)
        self.assertEqual(removed.status_code, 403)

    def test_photo_data_is_isolated_between_users(self) -> None:
        uploaded = self.upload(image_bytes())
        self.assertEqual(uploaded.status_code, 200)
        self.user_id = "artist-user-b"
        missing = self.client.get(
            "/api/artists/photo", params={"name": "Vervfy Test Artist"}
        )
        self.assertEqual(missing.status_code, 404)
        removed = self.client.delete(
            "/api/artists/photo", params={"name": "Vervfy Test Artist"}
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIn(("artist-user-a", "vervfytestartist"), self.photos)


class CommonsArtistPhotoTests(unittest.TestCase):
    image_url = (
        "https://upload.wikimedia.org/wikipedia/commons/a/ab/Vervfy_Test.jpg"
    )

    def setUp(self) -> None:
        server._artist_commons_photo_cache.clear()

    @staticmethod
    def metadata(license_name="CC BY-SA 4.0", license_url=None):
        return {
            "Artist": {"value": "Example Photographer"},
            "Credit": {"value": "Example Photographer / Wikimedia Commons"},
            "LicenseShortName": {"value": license_name},
            "LicenseUrl": {
                "value": license_url
                or "https://creativecommons.org/licenses/by-sa/4.0/"
            },
        }

    def fetch_with_mocked_http(self, metadata):
        original_client = httpx.Client
        image_data = image_bytes("PNG", (1200, 600))
        requested_image_urls: list[str] = []
        api_request_headers: list[str] = []

        def transport_handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "commons.wikimedia.org":
                api_request_headers.append(request.headers.get("user-agent", ""))
                return httpx.Response(
                    200,
                    json={
                        "query": {
                            "pages": [
                                {
                                    "imageinfo": [
                                        {
                                            "url": self.image_url,
                                            "descriptionurl": (
                                                "https://commons.wikimedia.org/wiki/"
                                                "File:Vervfy_Test.jpg"
                                            ),
                                            "extmetadata": metadata,
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    request=request,
                )
            requested_image_urls.append(str(request.url))
            return httpx.Response(200, content=image_data, request=request)

        def make_client(**kwargs):
            return original_client(
                transport=httpx.MockTransport(transport_handler),
                **kwargs,
            )

        with patch.object(server.httpx, "Client", side_effect=make_client):
            photo = server._fetch_commons_artist_photo(
                "Vervfy Test Artist", self.image_url
            )
        return photo, requested_image_urls, api_request_headers

    def test_accepts_cc_by_sa_and_stores_a_resized_jpeg_copy(self) -> None:
        photo, downloads, user_agents = self.fetch_with_mocked_http(self.metadata())
        self.assertIsNotNone(photo)
        assert photo is not None
        self.assertEqual(photo["source"], "commons")
        self.assertEqual(photo["author"], "Example Photographer")
        self.assertEqual(photo["license_name"], "CC BY-SA 4.0")
        self.assertTrue(photo["resized_for_display"])
        self.assertEqual(len(downloads), 1)
        self.assertIn("github.com/samvitorsilva/Vervfy", user_agents[0])
        with Image.open(BytesIO(photo["jpeg_data"])) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (800, 400))

    def test_rejects_nc_nd_fair_use_and_unapproved_licenses(self) -> None:
        cases = (
            ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/"),
            ("CC BY-ND 4.0", "https://creativecommons.org/licenses/by-nd/4.0/"),
            ("Fair use", "https://en.wikipedia.org/wiki/Fair_use"),
        )
        for license_name, license_url in cases:
            with self.subTest(license_name=license_name):
                photo, downloads, _ = self.fetch_with_mocked_http(
                    self.metadata(license_name, license_url)
                )
                self.assertIsNone(photo)
                self.assertEqual(downloads, [])

    def test_rejects_missing_author_credit_or_license_information(self) -> None:
        missing_author = self.metadata()
        del missing_author["Artist"]
        missing_credit = self.metadata()
        del missing_credit["Credit"]
        missing_license = self.metadata()
        del missing_license["LicenseUrl"]
        for metadata in (missing_author, missing_credit, missing_license):
            with self.subTest(metadata=metadata):
                photo, downloads, _ = self.fetch_with_mocked_http(metadata)
                self.assertIsNone(photo)
                self.assertEqual(downloads, [])

    def test_rejects_local_wikipedia_images_without_network_requests(self) -> None:
        with patch.object(server.httpx, "Client") as client:
            photo = server._fetch_commons_artist_photo(
                "Vervfy Test Artist",
                "https://upload.wikimedia.org/wikipedia/en/a/ab/Fair_use.jpg",
            )
        self.assertIsNone(photo)
        client.assert_not_called()

    def test_disabled_flag_makes_no_commons_or_wikipedia_requests(self) -> None:
        with (
            patch.dict(os.environ, {"ARTIST_PHOTOS_COMMONS": "off"}),
            patch.object(server, "_artist_photo_record", return_value=None),
            patch.object(server, "_lookup_artist_profile") as lookup,
            patch.object(server.httpx, "Client") as client,
        ):
            self.assertIsNone(server._artist_photo_for_user("user-a", "Artist"))
        lookup.assert_not_called()
        client.assert_not_called()

    def test_blocklisted_artist_never_uses_or_serves_a_commons_photo(self) -> None:
        commons_photo = {"jpeg_data": b"commons-photo", "source": "commons"}
        with (
            patch.dict(
                os.environ,
                {
                    "ARTIST_PHOTOS_COMMONS": "1",
                    "ARTIST_PHOTOS_COMMONS_BLOCKLIST": "Vervfy Test Artist",
                },
            ),
            patch.object(server, "_artist_photo_record", return_value=commons_photo),
            patch.object(server, "_lookup_artist_profile") as lookup,
        ):
            self.assertIsNone(
                server._artist_photo_for_user("user-a", "Vervfy Test Artist")
            )
        lookup.assert_not_called()

    def test_negative_results_are_cached_for_thirty_days(self) -> None:
        with (
            patch.dict(os.environ, {"ARTIST_PHOTOS_COMMONS": "1"}),
            patch.object(server, "_artist_photo_record", return_value=None),
            patch.object(server, "_lookup_artist_profile", return_value=None) as lookup,
        ):
            self.assertIsNone(server._artist_photo_for_user("user-a", "Unknown Artist"))
            self.assertIsNone(server._artist_photo_for_user("user-b", "Unknown Artist"))
        lookup.assert_called_once()
        expires_at, photo = server._artist_commons_photo_cache["unknownartist"]
        self.assertIsNone(photo)
        self.assertGreater(expires_at, time.monotonic() + 29 * 24 * 60 * 60)

    def test_user_photo_takes_priority_over_cached_commons_photo(self) -> None:
        user_photo = {"jpeg_data": b"user-photo", "source": "user"}
        with (
            patch.dict(os.environ, {"ARTIST_PHOTOS_COMMONS": "1"}),
            patch.object(server, "_artist_photo_record", return_value=user_photo),
            patch.object(server, "_lookup_artist_profile") as lookup,
        ):
            self.assertIs(
                server._artist_photo_for_user("user-a", "Vervfy Test Artist"),
                user_photo,
            )
        lookup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
