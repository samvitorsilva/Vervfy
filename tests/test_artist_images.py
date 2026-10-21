from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
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

    def test_track_lookup_matches_artist_and_title_then_uses_album_id(self) -> None:
        calls: list[tuple[str, dict[str, str]]] = []

        def request_json(endpoint: str, params: dict[str, str]) -> dict:
            calls.append((endpoint, params))
            if endpoint == "searchtrack.php":
                return {
                    "track": [
                        {
                            "strArtist": "Yellow Tribute",
                            "strTrack": "Yellow",
                            "idAlbum": "wrong",
                        },
                        {
                            "strArtist": "Coldplay",
                            "strTrack": "Yellow",
                            "idAlbum": "1234",
                        },
                    ]
                }
            return {
                "album": [
                    {
                        "idAlbum": "1234",
                        "strArtist": "Coldplay",
                        "strAlbumThumb": "https://r2.theaudiodb.com/album.jpg",
                    }
                ]
            }

        result = artist_images.fetch_track_cover(
            "Coldplay feat. Guest", "Yellow", "Ignored Album", request_json
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["audiodb_album_id"], "1234")
        self.assertEqual(result["cover_url"], "https://r2.theaudiodb.com/album.jpg")
        self.assertEqual(calls[0], ("searchtrack.php", {"s": "Coldplay", "t": "Yellow"}))
        self.assertEqual(calls[1], ("album.php", {"m": "1234"}))

    def test_track_lookup_falls_back_to_a_matched_artist_and_tagged_album(self) -> None:
        calls: list[tuple[str, dict[str, str]]] = []

        def request_json(endpoint: str, params: dict[str, str]) -> dict:
            calls.append((endpoint, params))
            if endpoint == "searchtrack.php":
                return {"track": None}
            self.assertEqual(params, {"s": "Coldplay", "a": "Parachutes"})
            return {
                "album": [
                    {
                        "idAlbum": "bad",
                        "strArtist": "Coldplay Tribute",
                        "strAlbum": "Parachutes",
                        "strAlbumThumb": "https://r2.theaudiodb.com/wrong.jpg",
                    },
                    {
                        "idAlbum": "2109615",
                        "strArtist": "Coldplay",
                        "strAlbum": "Parachutes",
                        "strAlbumThumb": "https://r2.theaudiodb.com/right.jpg",
                    },
                ]
            }

        result = artist_images.fetch_track_cover(
            "Coldplay", "Yellow", "Parachutes", request_json
        )
        self.assertEqual(
            calls,
            [
                ("searchtrack.php", {"s": "Coldplay", "t": "Yellow"}),
                ("searchtrack.php", {"s": "Coldplay"}),
                ("searchalbum.php", {"s": "Coldplay", "a": "Parachutes"}),
            ],
        )
        self.assertEqual(result["audiodb_album_id"], "2109615")
        self.assertEqual(result["cover_url"], "https://r2.theaudiodb.com/right.jpg")

    def test_empty_title_search_retries_free_artist_track_search(self) -> None:
        calls: list[tuple[str, dict[str, str]]] = []

        def request_json(endpoint: str, params: dict[str, str]) -> dict:
            calls.append((endpoint, params))
            if endpoint == "searchtrack.php" and "t" in params:
                return {"track": None}
            if endpoint == "searchtrack.php":
                return {
                    "track": [
                        {
                            "strArtist": "Coldplay",
                            "strTrack": "Yellow",
                            "idAlbum": "2109615",
                        }
                    ]
                }
            return {
                "album": [
                    {
                        "idAlbum": "2109615",
                        "strArtist": "Coldplay",
                        "strAlbumThumb": "https://r2.theaudiodb.com/cover.jpg",
                    }
                ]
            }

        result = artist_images.fetch_track_cover(
            "Coldplay", "Yellow", "", request_json
        )

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["cover_url"], "https://r2.theaudiodb.com/cover.jpg")
        self.assertEqual(
            calls,
            [
                ("searchtrack.php", {"s": "Coldplay", "t": "Yellow"}),
                ("searchtrack.php", {"s": "Coldplay"}),
                ("album.php", {"m": "2109615"}),
            ],
        )

    def test_track_search_failure_falls_back_without_accepting_wrong_artist(self) -> None:
        def request_json(endpoint: str, params: dict[str, str]) -> dict:
            if endpoint == "searchtrack.php":
                raise httpx.HTTPStatusError(
                    "premium-only title parameter",
                    request=httpx.Request("GET", "https://example.test"),
                    response=httpx.Response(403),
                )
            return {"album": [{"strArtist": "Different Artist", "strAlbumThumb": "https://r2.theaudiodb.com/wrong.jpg"}]}

        result = artist_images.fetch_track_cover(
            "Coldplay", "Yellow", "Parachutes", request_json
        )
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["cover_url"])

    def test_free_artist_search_can_match_the_requested_track(self) -> None:
        calls: list[dict[str, str]] = []

        def request_json(endpoint: str, params: dict[str, str]) -> dict:
            calls.append(params)
            if "t" in params:
                raise httpx.HTTPStatusError(
                    "title search is premium-only",
                    request=httpx.Request("GET", "https://example.test"),
                    response=httpx.Response(403),
                )
            if endpoint == "searchtrack.php":
                return {
                    "track": [
                        {
                            "strArtist": "Coldplay",
                            "strTrack": "Yellow",
                            "idAlbum": "2109615",
                        }
                    ]
                }
            return {
                "album": [
                    {
                        "idAlbum": "2109615",
                        "strArtist": "Coldplay",
                        "strAlbumThumb": "https://r2.theaudiodb.com/thumb.jpg",
                    }
                ]
            }

        result = artist_images.fetch_track_cover(
            "Coldplay", "Yellow", "", request_json
        )
        self.assertEqual(calls, [{"s": "Coldplay", "t": "Yellow"}, {"s": "Coldplay"}, {"m": "2109615"}])
        self.assertEqual(result["cover_url"], "https://r2.theaudiodb.com/thumb.jpg")

    def test_invalid_title_search_retries_free_artist_search(self) -> None:
        calls: list[dict[str, str]] = []

        def request_json(endpoint: str, params: dict[str, str]) -> dict:
            calls.append(params)
            if "t" in params:
                raise httpx.DecodingError(
                    "invalid JSON",
                    request=httpx.Request("GET", "https://example.test"),
                )
            return {"track": None}

        result = artist_images.fetch_track_cover(
            "Coldplay", "Yellow", "", request_json
        )

        self.assertEqual(calls, [{"s": "Coldplay", "t": "Yellow"}, {"s": "Coldplay"}])
        self.assertEqual(result["status"], "not_found")

    def test_invalid_provider_json_is_reported_as_decoding_error(self) -> None:
        request = httpx.Request("GET", "https://example.test/searchtrack.php")
        response = httpx.Response(200, content=b"", request=request)

        with self.assertRaises(httpx.DecodingError):
            artist_images._decode_json_response(response, "searchtrack.php")

    def test_artist_and_title_form_the_global_cache_key(self) -> None:
        first = artist_images.track_cover_cache_key("Beyoncé feat. Guest", "Halo!")
        second = artist_images.track_cover_cache_key("Beyonce", "Halo")
        self.assertEqual(first, second)
        legacy_key = hashlib.sha256(
            "beyonce\0halo".encode("utf-8")
        ).hexdigest()
        self.assertNotEqual(first[0], legacy_key)

    def test_shared_queue_throttles_each_external_request(self) -> None:
        decisions: list[tuple[str, int, int]] = []
        queue = artist_images.TheAudioDBQueue(
            lambda key, limit, window: decisions.append((key, limit, window)) or True
        )
        original_client = httpx.Client
        with (
            patch.object(
                artist_images.httpx,
                "Client",
                side_effect=lambda *args, **kwargs: original_client(
                    *args,
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, json={}, request=request)
                    ),
                    **kwargs,
                ),
            ),
            patch.object(artist_images.time, "sleep"),
        ):
            queue._request_json("searchtrack.php", {"s": "Artist", "t": "Title"})
            queue._request_json("album.php", {"m": "42"})
        self.assertEqual(
            decisions,
            [("theaudiodb:global", 25, 60), ("theaudiodb:global", 25, 60)],
        )


if __name__ == "__main__":
    unittest.main()
