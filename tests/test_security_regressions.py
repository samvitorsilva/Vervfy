from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import httpx

import audio_store
from auth import SessionStore
from library import track_id_for_bytes


class SessionStoreTests(unittest.TestCase):
    def test_revoked_session_is_not_valid(self) -> None:
        store = SessionStore()
        session_id = store.create("user-a")

        self.assertTrue(store.is_valid(session_id, "user-a"))
        self.assertFalse(store.is_valid(session_id, "user-b"))
        store.revoke(session_id)
        self.assertFalse(store.is_valid(session_id, "user-a"))


class TrackIdentityTests(unittest.TestCase):
    def test_identity_includes_bytes_between_the_old_sample_windows(self) -> None:
        first = b"a" * 65_536 + b"x" + b"b" * 65_536
        second = b"a" * 65_536 + b"y" + b"b" * 65_536

        self.assertNotEqual(track_id_for_bytes(first), track_id_for_bytes(second))


class StorageRangeTests(unittest.TestCase):
    def tearDown(self) -> None:
        audio_store.close_client()

    def test_read_range_slices_streaming_response_when_storage_ignores_range(self) -> None:
        body = bytes(range(256)) * 1024

        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["range"], "bytes=100000-100099")
            return httpx.Response(200, content=body)

        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://project.supabase.co",
                    "SUPABASE_SERVICE_KEY": "test-key",
                    "SUPABASE_BUCKET": "songs",
                },
            ),
            patch.object(audio_store, "_transport", httpx.MockTransport(respond)),
        ):
            self.assertEqual(
                audio_store.read_range("user/track.mp3", 100_000, 100_099),
                body[100_000:100_100],
            )


if __name__ == "__main__":
    unittest.main()
