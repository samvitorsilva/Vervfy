from __future__ import annotations

import os
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VERVFY_SECRET_KEY", "test-only-vervfy-session-secret")

import server
from db import Base, Playlist, PlaylistTrack, TrackListen, TrackRecord, User


class TrackListenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.now = time.time()
        with Session(self.engine) as session:
            session.add(
                User(
                    id="test-user",
                    username="tester",
                    username_key="tester",
                    password_hash="test-hash",
                    created_at=self.now,
                )
            )
            session.add(
                User(
                    id="other-user",
                    username="other",
                    username_key="other",
                    password_hash="test-hash",
                    created_at=self.now,
                )
            )
            session.add(
                TrackRecord(
                    id="track-one",
                    user_id="test-user",
                    filename="song.mp3",
                    title="Song",
                    artist="Artist",
                    album="Album",
                    duration=180,
                )
            )
            session.add(
                Playlist(
                    id="playlist-one",
                    user_id="test-user",
                    name="Favorites mix",
                    position=0,
                )
            )
            session.add(
                PlaylistTrack(
                    playlist_id="playlist-one",
                    track_id="track-one",
                    position=0,
                )
            )
            session.add(
                Playlist(
                    id="private-playlist",
                    user_id="other-user",
                    name="Private",
                    position=0,
                )
            )
            session.add_all(
                [
                    TrackListen(
                        id="current-month",
                        user_id="test-user",
                        track_id="track-one",
                        played_at=self.now,
                    ),
                    TrackListen(
                        id="older-listen",
                        user_id="test-user",
                        track_id="track-one",
                        played_at=self.now - 60 * 24 * 60 * 60,
                    ),
                ]
            )
            session.commit()

        @contextmanager
        def tenant_session(_user_id: str):
            with Session(self.engine) as session:
                yield session

        self.tenant_session = tenant_session

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_summary_groups_month_year_and_last_played(self) -> None:
        with patch.object(server, "tenant_session", self.tenant_session):
            summary = server._listening_summary("test-user")

        month_start = datetime.fromtimestamp(summary["monthStart"], timezone.utc)
        self.assertEqual((month_start.day, month_start.hour, month_start.minute), (1, 0, 0))
        self.assertEqual(summary["month"]["playCount"], 1)
        year_start = datetime.now(timezone.utc).replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
        expected_year_count = 1 + int(self.now - 60 * 24 * 60 * 60 >= year_start)
        self.assertEqual(summary["year"]["playCount"], expected_year_count)
        self.assertEqual(summary["month"]["topTracks"], [
            {"trackId": "track-one", "playCount": 1}
        ])
        self.assertGreater(summary["lastPlayedAt"]["track-one"], self.now - 60)

    def test_recorded_listen_appears_in_summary(self) -> None:
        payload = server.TrackListenRequest(trackId="track-one")
        with patch.object(server, "tenant_session", self.tenant_session):
            result = server.record_track_listen(payload, {"id": "test-user"}, None)
            summary = server._listening_summary("test-user")

        self.assertEqual(result["trackId"], "track-one")
        self.assertEqual(summary["month"]["playCount"], 2)

    def test_record_listen_rejects_track_from_another_account_or_missing(self) -> None:
        payload = server.TrackListenRequest(trackId="missing-track")
        with patch.object(server, "tenant_session", self.tenant_session):
            with self.assertRaises(server.HTTPException) as error:
                server.record_track_listen(payload, {"id": "test-user"}, None)

        self.assertEqual(error.exception.status_code, 404)

    def test_recorded_playlist_listen_updates_state_without_changing_metadata_etag(self) -> None:
        with patch.object(server, "tenant_session", self.tenant_session):
            before = server._library_state("test-user")
            before_etag = server._library_state_etag(before)
            result = server.record_playlist_listen("playlist-one", {"id": "test-user"}, None)
            after = server._library_state("test-user")

        self.assertEqual(result["playlistId"], "playlist-one")
        self.assertGreater(result["lastPlayedAt"], self.now - 1)
        self.assertEqual(after["playlists"][0]["lastPlayedAt"], result["lastPlayedAt"])
        self.assertEqual(server._library_state_etag(after), before_etag)

    def test_record_playlist_listen_rejects_missing_or_foreign_playlist(self) -> None:
        with patch.object(server, "tenant_session", self.tenant_session):
            for playlist_id in ("missing-playlist", "private-playlist"):
                with self.subTest(playlist_id=playlist_id):
                    with self.assertRaises(server.HTTPException) as error:
                        server.record_playlist_listen(playlist_id, {"id": "test-user"}, None)
                    self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
