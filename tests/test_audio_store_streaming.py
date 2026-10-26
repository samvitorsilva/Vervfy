from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import httpx

import audio_store


class AudioStoreStreamingTests(unittest.TestCase):
    def test_upload_sets_long_cache_control(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200)

        audio_store.close_client()
        with (
            patch.object(audio_store, "_transport", httpx.MockTransport(handler)),
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://project.supabase.co",
                    "SUPABASE_SERVICE_KEY": "test-key",
                },
            ),
        ):
            try:
                audio_store.upload("user/track.mp3", b"audio", "audio/mpeg")
            finally:
                audio_store.close_client()

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].headers["cache-control"], "max-age=31536000")

    def test_signed_url_cache_reuses_until_one_minute_before_expiry(self) -> None:
        requests = 0
        clock = [100.0]

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal requests
            requests += 1
            return httpx.Response(
                200,
                json={"signedURL": f"/object/sign/songs/user/track?token={requests}"},
            )

        audio_store.close_client()
        with (
            patch.object(audio_store, "_transport", httpx.MockTransport(handler)),
            patch.object(audio_store.time, "monotonic", side_effect=lambda: clock[0]),
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://project.supabase.co",
                    "SUPABASE_SERVICE_KEY": "test-key",
                },
            ),
        ):
            with audio_store._signed_url_cache_lock:
                audio_store._signed_url_cache.clear()
            try:
                first = audio_store.create_signed_url(
                    "user/track.mp3", expires_in=60 * 60
                )
                reused = audio_store.create_signed_url(
                    "user/track.mp3", expires_in=60 * 60
                )
                clock[0] += 60 * 60 - 60 + 1
                expired = audio_store.create_signed_url(
                    "user/track.mp3", expires_in=60 * 60
                )
            finally:
                audio_store.close_client()
                with audio_store._signed_url_cache_lock:
                    audio_store._signed_url_cache.clear()

        self.assertEqual(first, reused)
        self.assertNotEqual(first, expired)
        self.assertEqual(requests, 2)

    def test_upload_file_streams_chunks_with_content_length(self) -> None:
        payload = b"a" * (150 * 1024)
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200)

        with tempfile.NamedTemporaryFile() as source:
            source.write(payload)
            source.flush()
            audio_store.close_client()
            with (
                patch.object(audio_store, "_transport", httpx.MockTransport(handler)),
                patch.dict(
                    os.environ,
                    {
                        "SUPABASE_URL": "https://project.supabase.co",
                        "SUPABASE_SERVICE_KEY": "test-key",
                    },
                ),
            ):
                try:
                    audio_store.upload_file(
                        "user/track.mp3", source.name, "audio/mpeg"
                    )
                finally:
                    audio_store.close_client()

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].content, payload)
        self.assertEqual(
            requests[0].headers["content-length"],
            str(len(payload)),
        )
        self.assertEqual(requests[0].headers["cache-control"], "max-age=31536000")
        self.assertNotIn("transfer-encoding", requests[0].headers)


if __name__ == "__main__":
    unittest.main()
