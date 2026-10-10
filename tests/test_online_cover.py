from __future__ import annotations

import io
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

import online_cover


class FetchCoverTests(unittest.TestCase):
    def test_fetch_cover_with_mock_transport(self) -> None:
        image_buffer = io.BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(image_buffer, format="PNG")
        image_bytes = image_buffer.getvalue()

        def respond(request: httpx.Request) -> httpx.Response:
            if request.url.host == "itunes.apple.com":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "trackName": "guilty conscience",
                                "artistName": "Tate McRae",
                                "artworkUrl100": (
                                    "https://is1-ssl.mzstatic.com/image/thumb/"
                                    "100x100bb.jpg"
                                ),
                            }
                        ]
                    },
                )
            return httpx.Response(200, content=image_bytes)

        with patch.object(online_cover, "_transport", httpx.MockTransport(respond)):
            cover = online_cover.fetch_cover("guilty conscience", "Tate McRae")

        self.assertIsNotNone(cover)
        assert cover is not None
        self.assertEqual(cover.size, (1, 1))

    def test_fetches_cover_for_matching_itunes_result(self) -> None:
        image_buffer = io.BytesIO()
        Image.new("RGB", (2, 2), color="red").save(image_buffer, format="PNG")
        image_bytes = image_buffer.getvalue()
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.host == "itunes.apple.com":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "trackName": "guilty conscience",
                                "artistName": "Tate McRae",
                                "collectionName": "THINK LATER",
                                "trackTimeMillis": 152050,
                                "artworkUrl100": (
                                    "https://is1-ssl.mzstatic.com/image/thumb/cover/"
                                    "100x100bb.jpg"
                                ),
                            }
                        ]
                    },
                )
            return httpx.Response(200, content=image_bytes)

        with patch.object(online_cover, "_transport", httpx.MockTransport(respond)):
            metadata = online_cover.fetch_track_metadata(
                "guilty conscience", "Tate McRae"
            )

        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata.album, "THINK LATER")
        self.assertEqual(metadata.duration, 152.05)
        self.assertIsNotNone(metadata.cover)
        assert metadata.cover is not None
        self.assertEqual(metadata.cover.size, (2, 2))
        self.assertEqual(requests[0].url.host, "itunes.apple.com")
        self.assertEqual(
            requests[0].url.params["term"],
            "Tate McRae guilty conscience",
        )
        self.assertEqual(requests[1].url.host, "is1-ssl.mzstatic.com")
        self.assertIn("600x600bb.jpg", requests[1].url.path)

    def test_returns_none_when_itunes_lookup_fails(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(503, request=request)
        )
        with patch.object(online_cover, "_transport", transport):
            self.assertIsNone(online_cover.fetch_cover("guilty conscience", "Tate McRae"))


if __name__ == "__main__":
    unittest.main()
