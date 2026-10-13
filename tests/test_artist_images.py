from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx

import artist_images


class ArtistImageLookupTests(unittest.TestCase):
    def test_cleans_featured_and_compound_artist_credits(self) -> None:
        self.assertEqual(artist_images.clean_artist_name("  Beyoncé feat. Guest "), "Beyoncé")
        self.assertEqual(artist_images.clean_artist_name("Lead & Guest"), "Lead")
        self.assertEqual(artist_images.clean_artist_name("Lead, Guest"), "Lead")
        self.assertEqual(artist_images.clean_artist_name("Lead x Guest"), "Lead")
        self.assertEqual(artist_images.clean_artist_name("X Ambassadors"), "X Ambassadors")
        self.assertEqual(
            artist_images.artists_from_credit("Lead feat. Guest & Partner"),
            ["Lead", "Guest", "Partner"],
        )

    def test_search_uses_public_key_and_requires_a_normalized_exact_match(self) -> None:
        requested: list[httpx.Request] = []
        original_client = httpx.Client

        def transport_handler(request: httpx.Request) -> httpx.Response:
            requested.append(request)
            return httpx.Response(
                200,
                json={
                    "artists": [
                        {
                            "idArtist": "1",
                            "strArtist": "Beyonce Tribute",
                            "strArtistThumb": "https://www.theaudiodb.com/wrong.jpg",
                        },
                        {
                            "idArtist": "2",
                            "strArtist": "Beyoncé!",
                            "strArtistThumb": (
                                "https://www.theaudiodb.com/images/media/artist/thumb/test.jpg"
                            ),
                            "strArtistFanart": None,
                            "strArtistBanner": (
                                "https://r2.theaudiodb.com/images/media/artist/banner/test.jpg"
                            ),
                        },
                    ]
                },
                request=request,
            )

        with (
            patch.dict("os.environ", {}, clear=False),
            patch.dict("os.environ", {"AUDIODB_API_KEY": "123"}),
            patch.object(
                artist_images.httpx,
                "Client",
                side_effect=lambda *args, **kwargs: original_client(
                    *args,
                    transport=httpx.MockTransport(transport_handler),
                    **kwargs,
                ),
            ),
        ):
            result = artist_images.fetch_artist_image("Beyoncé")

        self.assertEqual(result["audiodb_id"], "2")
        self.assertEqual(result["status"], "found")
        self.assertEqual(
            result["image_url"],
            "https://www.theaudiodb.com/images/media/artist/thumb/test.jpg",
        )
        self.assertEqual(
            result["banner_url"],
            "https://r2.theaudiodb.com/images/media/artist/banner/test.jpg",
        )
        self.assertEqual(requested[0].url.path, "/api/v1/json/123/search.php")
        self.assertEqual(requested[0].url.params["s"], "Beyoncé")

    def test_non_matching_result_is_not_blindly_selected(self) -> None:
        original_client = httpx.Client

        with (
            patch.object(
                artist_images.httpx,
                "Client",
                side_effect=lambda *args, **kwargs: original_client(
                    *args,
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(
                            200,
                            json={
                                "artists": [
                                    {
                                        "idArtist": "1",
                                        "strArtist": "Another Artist",
                                        "strArtistThumb": (
                                            "https://www.theaudiodb.com/wrong.jpg"
                                        ),
                                    }
                                ]
                            },
                            request=request,
                        )
                    ),
                    **kwargs,
                ),
            ),
        ):
            result = artist_images.fetch_artist_image("Unknown Artist")
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["audiodb_id"])
        self.assertIsNone(result["image_url"])

    def test_rejects_non_audiodb_image_hosts(self) -> None:
        self.assertIsNone(
            artist_images._validated_image_url("https://example.com/image.jpg")
        )
        self.assertIsNone(
            artist_images._validated_image_url("http://www.theaudiodb.com/image.jpg")
        )
        self.assertEqual(
            artist_images._validated_image_url(
                "https://r2.theaudiodb.com/image.jpg"
            ),
            "https://r2.theaudiodb.com/image.jpg",
        )

    def test_negative_cache_expires_after_thirty_days(self) -> None:
        now = datetime.now(timezone.utc)
        record = {"status": "not_found", "fetched_at": now - timedelta(days=29)}
        self.assertFalse(artist_images.is_stale(record, now))
        record["fetched_at"] = now - timedelta(days=31)
        self.assertTrue(artist_images.is_stale(record, now))


if __name__ == "__main__":
    unittest.main()
