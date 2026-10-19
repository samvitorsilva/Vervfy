from __future__ import annotations

import os
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

os.environ.setdefault("VERVFY_SECRET_KEY", "test-only-vervfy-session-secret")

import auth
import library
import server


class FakeLibrary:
    def __init__(self, storage_path: str | None) -> None:
        self.info = SimpleNamespace(
            filename="test.mp3",
            size_bytes=1234,
            storage_path=storage_path,
        )
        self.track = SimpleNamespace(
            id="track-id",
            title="Test track",
            artist="Test artist",
            album="Test album",
            duration=12,
            custom_lyrics=None,
            has_cover=False,
            cover_source="placeholder",
            cover_url=None,
            audio_data=b"must not be serialized",
        )
        self.migration_path = "user-a/track-id.mp3"
        self.ensure_calls = 0

    def audio_info(self, track_id: str):
        return self.info if track_id == "track-id" else None

    def list_tracks(self):
        return [self.track]

    def ensure_audio_storage(self, track_id: str) -> str:
        self.ensure_calls += 1
        self.info.storage_path = self.migration_path
        return self.migration_path


class TrackAudioRedirectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(server.app)
        self.library = FakeLibrary("user-a/track-id.mp3")
        self.library_patch = patch.object(
            server, "get_library", return_value=self.library
        )
        self.library_patch.start()
        self.user_override = patch.dict(
            server.app.dependency_overrides,
            {server.require_api_user: lambda: {"id": "user-a"}},
        )
        self.user_override.start()

    def tearDown(self) -> None:
        self.user_override.stop()
        self.library_patch.stop()
        server.app.dependency_overrides.clear()

    def test_storage_track_redirects_without_proxying_range_bytes(self) -> None:
        with patch.object(
            server.audio_store,
            "create_signed_url",
            return_value="https://project.supabase.co/storage/v1/object/sign/songs/audio?token=x",
        ) as create_signed_url, patch.object(
            self.library, "ensure_audio_storage"
        ) as ensure_audio_storage:
            response = self.client.get(
                "/api/tracks/track-id/stream",
                headers={"Range": "bytes=100-199"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["location"],
            "https://project.supabase.co/storage/v1/object/sign/songs/audio?token=x",
        )
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        create_signed_url.assert_called_once_with("user-a/track-id.mp3")
        ensure_audio_storage.assert_not_called()

    def test_legacy_track_is_lazily_migrated_before_redirect(self) -> None:
        self.library.info.storage_path = None
        with patch.object(
            server.audio_store,
            "create_signed_url",
            return_value="https://project.supabase.co/storage/v1/object/sign/songs/audio?token=x",
        ) as create_signed_url, patch.object(
            server.audio_store, "upload"
        ) as upload:
            response = self.client.get(
                "/api/tracks/track-id/stream", follow_redirects=False
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.library.ensure_calls, 1)
        upload.assert_not_called()
        create_signed_url.assert_called_once_with("user-a/track-id.mp3")

    def test_stream_requires_authentication(self) -> None:
        server.app.dependency_overrides.pop(server.require_api_user)
        response = self.client.get("/api/tracks/track-id/stream")
        self.assertEqual(response.status_code, 401)

    def test_track_list_does_not_serialize_audio_and_is_private_cached(self) -> None:
        response = self.client.get("/api/tracks")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "private, max-age=60")
        self.assertNotIn("audio_data", response.text)
        self.assertNotIn("must not be serialized", response.text)


class LazyAudioMigrationTests(unittest.TestCase):
    def test_uploads_legacy_audio_then_saves_stable_path(self) -> None:
        first_session = MagicMock()
        first_session.execute.return_value.one_or_none.return_value = (
            "song.mp3",
            None,
        )
        first_session.scalar.return_value = b"audio bytes"
        second_session = MagicMock()
        second_session.execute.return_value.rowcount = 1

        with (
            patch.object(
                library,
                "tenant_session",
                side_effect=[
                    nullcontext(first_session),
                    nullcontext(second_session),
                ],
            ),
            patch.object(library.audio_store, "upload") as upload,
        ):
            path = library.Library("user-a").ensure_audio_storage("track-id")

        self.assertEqual(path, "user-a/track-id.mp3")
        upload.assert_called_once_with(
            "user-a/track-id.mp3", b"audio bytes", "audio/mpeg"
        )
        second_session.commit.assert_called_once()

    def test_does_not_read_legacy_audio_when_storage_path_exists(self) -> None:
        session = MagicMock()
        session.execute.return_value.one_or_none.return_value = (
            "song.mp3",
            "user-a/track-id.mp3",
        )
        with patch.object(
            library, "tenant_session", return_value=nullcontext(session)
        ):
            path = library.Library("user-a").ensure_audio_storage("track-id")

        self.assertEqual(path, "user-a/track-id.mp3")
        session.scalar.assert_not_called()

    def test_does_not_save_path_when_upload_fails(self) -> None:
        session = MagicMock()
        session.execute.return_value.one_or_none.return_value = ("song.mp3", None)
        session.scalar.return_value = b"audio bytes"
        with (
            patch.object(
                library, "tenant_session", return_value=nullcontext(session)
            ),
            patch.object(
                library.audio_store,
                "upload",
                side_effect=library.audio_store.StorageError("storage failed"),
            ),
        ):
            with self.assertRaises(library.audio_store.StorageError):
                library.Library("user-a").ensure_audio_storage("track-id")

        self.assertEqual(session.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
