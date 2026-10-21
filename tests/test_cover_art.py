from __future__ import annotations

import asyncio
from io import BytesIO
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from PIL import Image

import cover_art


def _jpeg_bytes(color=(20, 40, 60), size=(64, 64)) -> bytes:
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


class NormalizeTitleTests(unittest.TestCase):
    def test_strips_feat_single_official_video_and_underscores(self) -> None:
        self.assertEqual(
            cover_art.normalize_title(
                "Just_Keep_Watching (feat. Someone) - Single (Official Video)"
            ),
            "just keep watching",
        )

    def test_clean_title_preserves_case(self) -> None:
        self.assertEqual(
            cover_art.clean_title("Miles & Miles (ft. AJ)"),
            "Miles & Miles",
        )

    def test_strips_release_suffix_before_normalizing(self) -> None:
        self.assertEqual(
            cover_art.normalize_title("Track - Single (Official Video)"),
            "track",
        )


class UploadedCoverTests(unittest.TestCase):
    def test_accepts_png_and_returns_jpeg(self) -> None:
        png = BytesIO()
        Image.new("RGB", (32, 32), (1, 2, 3)).save(png, format="PNG")
        result = cover_art.uploaded_cover(png.getvalue())
        self.assertIsNotNone(result)
        with Image.open(BytesIO(result)) as image:
            self.assertEqual(image.format, "JPEG")

    def test_rejects_oversized_payload(self) -> None:
        with self.assertRaises(ValueError):
            cover_art.uploaded_cover(b"x" * (5 * 1024 * 1024 + 1))


class EmbeddedCoverTests(unittest.TestCase):
    def test_extracts_and_normalizes_embedded_picture(self) -> None:
        image = Image.new("RGB", (40, 30), (10, 20, 30))
        with patch.object(cover_art, "_extract_cover", return_value=image) as extract:
            result = cover_art.embedded_cover("/tmp/track.mp3")

        self.assertIsNotNone(result)
        extract.assert_called_once_with("/tmp/track.mp3", ".mp3")
        with Image.open(BytesIO(result)) as normalized:
            self.assertEqual(normalized.format, "JPEG")
            self.assertEqual(normalized.size, (40, 30))


class AudioDBCoverTests(unittest.TestCase):
    def test_returns_existing_audio_db_lookup_url(self) -> None:
        with patch.object(
            cover_art,
            "fetch_track_cover",
            return_value={
                "status": "found",
                "cover_url": "https://r2.theaudiodb.com/cover.jpg",
            },
        ) as fetch:
            result = cover_art.audiodb_cover("Artist", "Song", "Album")

        self.assertEqual(result, "https://r2.theaudiodb.com/cover.jpg")
        fetch.assert_called_once_with("Artist", "Song", "Album")


class MusicBrainzCoverTests(unittest.TestCase):
    def test_retries_a_musicbrainz_503_once(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            if request.url.host == "musicbrainz.org":
                attempts += 1
                if attempts == 1:
                    return httpx.Response(503)
                return httpx.Response(
                    200,
                    json={
                        "recordings": [
                            {
                                "title": "Song",
                                "artist-credit": [{"name": "Artist"}],
                                "release-group": {"id": "retry-release"},
                            }
                        ]
                    },
                )
            return httpx.Response(200)

        original_client = httpx.AsyncClient
        transport = httpx.MockTransport(handler)
        with (
            patch.dict("os.environ", {"MB_CONTACT_EMAIL": "ops@vervfy.test"}),
            patch.object(
                cover_art.httpx,
                "AsyncClient",
                side_effect=lambda **kwargs: original_client(
                    transport=transport, **kwargs
                ),
            ),
            patch.object(cover_art, "_wait_for_musicbrainz_slot", new=AsyncMock()),
        ):
            url = asyncio.run(cover_art.musicbrainz_cover("Artist", "Song"))

        self.assertEqual(attempts, 2)
        self.assertEqual(
            url,
            "https://coverartarchive.org/release-group/retry-release/front-500",
        )

    def test_picks_release_group_and_returns_caa_url(self) -> None:
        search_payload = {
            "recordings": [
                {
                    "title": "Just Keep Watching",
                    "artist-credit": [{"name": "Tate McRae"}],
                    "releases": [
                        {
                            "status": "Official",
                            "release-group": {
                                "id": "bcaf4c17-e1c3-4c47-a691-c243a0753ac0",
                                "primary-type": "Album",
                                "secondary-types": ["Soundtrack"],
                            },
                        }
                    ],
                }
            ]
        }

        class FakeResponse:
            def __init__(self, status_code=200, payload=None, url="https://example.test"):
                self.status_code = status_code
                self._payload = payload
                self.url = url
                self.headers = {"content-type": "application/json"}

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self):
                self.calls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, params=None):
                self.calls.append(("GET", url, params))
                return FakeResponse(payload=search_payload)

            async def head(self, url):
                self.calls.append(("HEAD", url, None))
                return FakeResponse(status_code=200, url=url)

            def stream(self, method, url):
                raise AssertionError("stream should not be used when HEAD succeeds")

        fake = FakeClient()
        with (
            patch.dict("os.environ", {"MB_CONTACT_EMAIL": "ops@vervfy.test"}),
            patch.object(cover_art, "_musicbrainz_client", return_value=fake),
            patch.object(cover_art, "_wait_for_musicbrainz_slot", new=AsyncMock()),
        ):
            url = asyncio.run(cover_art.musicbrainz_cover("Tate McRae", "Just Keep Watching"))

        self.assertEqual(
            url,
            "https://coverartarchive.org/release-group/"
            "bcaf4c17-e1c3-4c47-a691-c243a0753ac0/front-500",
        )
        self.assertEqual(fake.calls[0][0], "GET")
        self.assertEqual(fake.calls[1][0], "HEAD")

    def test_http_requests_use_mock_transport_and_musicbrainz_user_agent(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.host == "musicbrainz.org":
                return httpx.Response(
                    200,
                    json={
                        "recordings": [
                            {
                                "title": "Miles & Miles",
                                "artist-credit": [{"name": "AJ Vitanza"}],
                                "release-group": {"id": "release-group-id"},
                            }
                        ]
                    },
                )
            return httpx.Response(200, headers={"content-type": "image/jpeg"})

        original_client = httpx.AsyncClient
        transport = httpx.MockTransport(handler)
        with (
            patch.dict("os.environ", {"MB_CONTACT_EMAIL": "ops@vervfy.test"}),
            patch.object(
                cover_art.httpx,
                "AsyncClient",
                side_effect=lambda **kwargs: original_client(
                    transport=transport, **kwargs
                ),
            ),
            patch.object(cover_art, "_wait_for_musicbrainz_slot", new=AsyncMock()),
        ):
            url = asyncio.run(cover_art.musicbrainz_cover("AJ Vitanza", "Miles_Miles"))

        self.assertEqual(
            url,
            "https://coverartarchive.org/release-group/release-group-id/front-500",
        )
        self.assertEqual(len(requests), 2)
        self.assertIn("Vervfy/1.0 (ops@vervfy.test)", requests[0].headers["user-agent"])
        self.assertEqual(requests[0].url.params["limit"], "5")

    def test_404_from_cover_art_archive_is_a_miss(self) -> None:
        class FakeResponse:
            def __init__(self, status_code=200, payload=None):
                self.status_code = status_code
                self._payload = payload
                self.url = "https://coverartarchive.org/missing"
                self.headers = {}

            def raise_for_status(self) -> None:
                if self.status_code >= 400 and self.status_code != 404:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, params=None):
                return FakeResponse(
                    payload={
                        "recordings": [
                            {
                                "title": "X",
                                "artist-credit": [{"name": "Y"}],
                                "releases": [
                                    {
                                        "release-group": {
                                            "id": "11111111-1111-1111-1111-111111111111",
                                            "primary-type": "Single",
                                        }
                                    }
                                ],
                            }
                        ]
                    }
                )

            async def head(self, url):
                return FakeResponse(status_code=404)

        with (
            patch.dict("os.environ", {"MB_CONTACT_EMAIL": "ops@vervfy.test"}),
            patch.object(cover_art, "_musicbrainz_client", return_value=FakeClient()),
            patch.object(cover_art, "_wait_for_musicbrainz_slot", new=AsyncMock()),
        ):
            url = asyncio.run(cover_art.musicbrainz_cover("Y", "X"))
        self.assertIsNone(url)


class CoverResolutionScheduleTests(unittest.TestCase):
    class BackgroundTasks:
        def __init__(self) -> None:
            self.tasks = []

        def add_task(self, *args, **kwargs) -> None:
            self.tasks.append((args, kwargs))

    def test_cooldown_skips_a_repeat_attempt(self) -> None:
        tasks = self.BackgroundTasks()
        library = MagicMock()
        library.claim_cover_resolution.side_effect = [True, False]
        key = ("cooldown-user", "cooldown-track")

        with patch("library.Library", return_value=library):
            try:
                self.assertTrue(
                    cover_art.schedule_cover_resolution(
                        tasks, *key
                    )
                )
                with cover_art._lookup_pending_lock:
                    cover_art._lookup_pending.discard(key)
                self.assertFalse(
                    cover_art.schedule_cover_resolution(
                        tasks, *key
                    )
                )
            finally:
                with cover_art._lookup_pending_lock:
                    cover_art._lookup_pending.discard(key)

        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(library.claim_cover_resolution.call_count, 2)

    def test_force_bypasses_the_persisted_cooldown(self) -> None:
        tasks = self.BackgroundTasks()
        library = MagicMock()
        library.claim_cover_resolution.return_value = True
        key = ("force-user", "force-track")

        with patch("library.Library", return_value=library):
            try:
                self.assertTrue(
                    cover_art.schedule_cover_resolution(
                        tasks, *key, force=True
                    )
                )
            finally:
                with cover_art._lookup_pending_lock:
                    cover_art._lookup_pending.discard(key)

        library.claim_cover_resolution.assert_called_once_with(
            key[1], force=True
        )
        self.assertEqual(len(tasks.tasks), 1)


class ResolveCoverChainTests(unittest.TestCase):
    def test_first_hit_wins_and_logs_each_step(self) -> None:
        track = MagicMock(
            id="track-1",
            title="Song",
            artist="Artist",
            album="Album",
            cover_source="generated",
            has_cover=False,
        )
        library = MagicMock()
        library.get.return_value = track
        library.set_resolved_cover.return_value = True
        library.embedded_cover.return_value = None

        async def mb(artist, title):
            return "https://coverartarchive.org/release-group/abc/front-500"

        with (
            patch("library.Library", return_value=library),
            patch.object(cover_art, "uploaded_cover", return_value=None),
            patch.object(
                cover_art,
                "audiodb_cover",
                side_effect=AssertionError("audiodb should not run after musicbrainz hit"),
            ),
            self.assertLogs("vervfy.cover_art", level="INFO") as logs,
        ):
            asyncio.run(
                cover_art.resolve_cover(
                    "user-1",
                    "track-1",
                    lookup_musicbrainz=mb,
                )
            )

        library.set_resolved_cover.assert_called_once_with(
            "track-1",
            "musicbrainz",
            None,
            "https://coverartarchive.org/release-group/abc/front-500",
        )
        messages = "\n".join(logs.output)
        self.assertIn("step=upload result=miss", messages)
        self.assertIn("step=embedded result=miss", messages)
        self.assertIn("step=musicbrainz result=hit", messages)

    def test_uploaded_cover_wins_before_embedded_or_network_lookup(self) -> None:
        track = MagicMock(
            id="track-upload",
            title="Song",
            artist="Artist",
            album="Album",
            cover_source="generated",
            has_cover=False,
        )
        library = MagicMock()
        library.get.return_value = track
        jpeg = _jpeg_bytes()

        with (
            patch("library.Library", return_value=library),
            patch.object(cover_art, "uploaded_cover", return_value=jpeg),
            patch.object(
                cover_art,
                "embedded_cover",
                side_effect=AssertionError("embedded step must not run"),
            ),
        ):
            asyncio.run(
                cover_art.resolve_cover(
                    "user-1",
                    "track-upload",
                    uploaded_data=jpeg,
                )
            )

        library.set_resolved_cover.assert_called_once_with(
            "track-upload", "upload", jpeg, None
        )

    def test_generated_step_creates_a_jpeg(self) -> None:
        with Image.open(BytesIO(cover_art.generated_cover("Generated song"))) as image:
            self.assertEqual(image.format, "JPEG")

    def test_audiodb_step_runs_after_musicbrainz_miss(self) -> None:
        track = MagicMock(
            id="track-2",
            title="Song",
            artist="Artist",
            album="Album",
            cover_source="generated",
            has_cover=False,
        )
        library = MagicMock()
        library.get.return_value = track

        with (
            patch("library.Library", return_value=library),
            patch.object(cover_art, "uploaded_cover", return_value=None),
            patch.object(cover_art, "embedded_cover", return_value=None),
        ):
            asyncio.run(
                cover_art.resolve_cover(
                    "user-1",
                    "track-2",
                    audio_path="/tmp/missing.mp3",
                    lookup_musicbrainz=AsyncMock(return_value=None),
                    lookup_audiodb=lambda a, t, al: "https://r2.theaudiodb.com/x.jpg",
                )
            )

        library.set_resolved_cover.assert_called_once_with(
            "track-2",
            "audiodb",
            None,
            "https://r2.theaudiodb.com/x.jpg",
        )

    def test_generated_fallback_stores_image(self) -> None:
        track = MagicMock(
            id="track-3",
            title="Song",
            artist="Artist",
            album="Album",
            cover_source=None,
            has_cover=False,
        )
        library = MagicMock()
        library.get.return_value = track
        jpeg = _jpeg_bytes()

        with (
            patch("library.Library", return_value=library),
            patch.object(cover_art, "uploaded_cover", return_value=None),
            patch.object(cover_art, "embedded_cover", return_value=None),
            patch.object(cover_art, "generated_cover", return_value=jpeg),
        ):
            asyncio.run(
                cover_art.resolve_cover(
                    "user-1",
                    "track-3",
                    audio_path="/tmp/missing.mp3",
                    lookup_musicbrainz=AsyncMock(return_value=None),
                    lookup_audiodb=lambda *args: None,
                )
            )

        library.set_resolved_cover.assert_called_once_with(
            "track-3",
            "generated",
            jpeg,
            None,
        )


if __name__ == "__main__":
    unittest.main()
