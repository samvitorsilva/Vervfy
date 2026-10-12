from __future__ import annotations

from io import BytesIO
import socket
import struct
import unittest
import wave
from unittest.mock import patch

import httpx

from library import Library


def silent_wav() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(struct.pack("<h", 0) * 800)
    return output.getvalue()


class UploadMetadataTests(unittest.TestCase):
    def test_unarted_upload_uses_filename_tags_and_placeholder_without_network(self) -> None:
        with (
            patch.object(httpx, "Client") as http_client,
            patch.object(httpx, "get") as http_get,
            patch.object(socket.socket, "connect", side_effect=AssertionError("unexpected network access")),
        ):
            metadata = Library("test-user")._read_metadata(
                "Fallback Artist - Fallback Song.wav",
                silent_wav(),
            )

        self.assertIsNotNone(metadata)
        title, artist, album, duration, cover, has_cover = metadata
        self.assertEqual((title, artist, album), ("Fallback Song", "Fallback Artist", "Unknown Album"))
        self.assertGreater(duration, 0)
        self.assertIsNotNone(cover)
        self.assertFalse(has_cover)
        http_client.assert_not_called()
        http_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
