from __future__ import annotations

import asyncio
from io import BytesIO
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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


class MusicBrainzCoverTests(unittest.TestCase):
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
