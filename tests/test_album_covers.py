from __future__ import annotations

from contextlib import contextmanager
import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, undefer

os.environ.setdefault("VERVFY_SECRET_KEY", "test-only-vervfy-session-secret")

from db import Base, TrackRecord, User
import library


class AlbumCoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.sessions() as session:
            session.add_all(
                [
                    User(
                        id="album-user-a",
                        username="album-a",
                        username_key="album-a",
                        password_hash="test",
                        created_at=1,
                    ),
                    User(
                        id="album-user-b",
                        username="album-b",
                        username_key="album-b",
                        password_hash="test",
                        created_at=1,
                    ),
                ]
            )
            session.add_all(
                [
                    self.track("placeholder", "album-user-a", "Artist", "Album", "placeholder"),
                    self.track("owned", "album-user-a", "Artist", "Album", "user"),
                    self.track("embedded", "album-user-a", "Artist", "Album", "embedded"),
                    self.track("other-artist", "album-user-a", "Other Artist", "Album", "placeholder"),
                    self.track("other-album", "album-user-a", "Artist", "Other Album", "placeholder"),
                    self.track("other-user", "album-user-b", "Artist", "Album", "placeholder"),
                    self.track("no-album", "album-user-a", "Artist", "", "placeholder"),
                ]
            )
            session.commit()

        @contextmanager
        def tenant_session(user_id: str):
            del user_id
            session = self.sessions()
            try:
                yield session
            finally:
                session.close()

        self.tenant_patch = patch.object(library, "tenant_session", side_effect=tenant_session)
        self.tenant_patch.start()

    @staticmethod
    def track(track_id: str, user_id: str, artist: str, album: str, source: str):
        return TrackRecord(
            id=track_id,
            user_id=user_id,
            filename=f"{track_id}.mp3",
            title=track_id,
            artist=artist,
            album=album,
            duration=1,
            has_cover=source != "placeholder",
            cover_source=source,
            cover_data=b"existing",
        )

    def tearDown(self) -> None:
        self.tenant_patch.stop()
        self.engine.dispose()

    def test_album_cover_skips_user_covers_until_explicit_confirmation(self) -> None:
        album_library = library.Library("album-user-a")
        updated = album_library.set_album_user_cover("placeholder", b"new-cover")
        self.assertEqual(updated, 2)

        with self.sessions() as session:
            tracks = {
                track.id: track
                for track in session.scalars(
                    select(TrackRecord).options(undefer(TrackRecord.cover_data))
                ).all()
            }
        self.assertEqual(tracks["placeholder"].cover_data, b"new-cover")
        self.assertEqual(tracks["embedded"].cover_data, b"new-cover")
        self.assertEqual(tracks["owned"].cover_data, b"existing")
        self.assertEqual(tracks["owned"].cover_source, "user")
        self.assertEqual(tracks["other-artist"].cover_data, b"existing")
        self.assertEqual(tracks["other-album"].cover_data, b"existing")
        self.assertEqual(tracks["other-user"].cover_data, b"existing")

        replaced = album_library.set_album_user_cover(
            "placeholder", b"confirmed-cover", replace_user_covers=True
        )
        self.assertEqual(replaced, 3)
        with self.sessions() as session:
            tracks = {
                track.id: track
                for track in session.scalars(
                    select(TrackRecord).options(undefer(TrackRecord.cover_data))
                ).all()
            }
        self.assertEqual(tracks["owned"].cover_data, b"confirmed-cover")
        self.assertEqual(tracks["other-artist"].cover_data, b"existing")
        self.assertEqual(tracks["other-user"].cover_data, b"existing")

    def test_album_cover_requires_an_existing_track_and_non_empty_album(self) -> None:
        album_library = library.Library("album-user-a")
        self.assertEqual(
            album_library.set_album_user_cover("no-album", b"cover"),
            0,
        )
        self.assertIsNone(album_library.set_album_user_cover("missing", b"cover"))

    def test_custom_track_cover_uses_user_scoped_storage_path(self) -> None:
        album_library = library.Library("album-user-a")
        with (
            patch.object(library.audio_store, "enabled", return_value=True),
            patch.object(library.audio_store, "upload") as upload,
        ):
            track = album_library.set_user_cover("placeholder", b"normalized-jpeg")

        self.assertEqual(track.cover_source, "user")
        self.assertEqual(track.cover_path, "covers/album-user-a/placeholder.jpg")
        upload.assert_called_once_with(
            "covers/album-user-a/placeholder.jpg",
            b"normalized-jpeg",
            "image/jpeg",
        )
        with self.sessions() as session:
            row = session.scalar(
                select(TrackRecord)
                .options(undefer(TrackRecord.cover_data))
                .where(
                    TrackRecord.id == "placeholder",
                    TrackRecord.user_id == "album-user-a",
                )
            )
        self.assertIsNone(row.cover_data)
        self.assertEqual(row.cover_path, "covers/album-user-a/placeholder.jpg")


if __name__ == "__main__":
    unittest.main()
