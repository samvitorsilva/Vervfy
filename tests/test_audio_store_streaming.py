from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import httpx

import audio_store


class AudioStoreStreamingTests(unittest.TestCase):
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
        self.assertNotIn("transfer-encoding", requests[0].headers)


if __name__ == "__main__":
    unittest.main()
