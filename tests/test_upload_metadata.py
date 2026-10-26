from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import socket
import struct
import tempfile
import unittest
import wave
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db import Base, TrackRecord, User
from library import Library, _same_recording_metadata, make_placeholder_cover


def silent_wav() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(struct.pack("<h", 0) * 800)
    return output.getvalue()


class UploadMetadataTests(unittest.TestCase):
    def test_upload_skips_a_differently_encoded_duplicate_recording(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        with sessions() as session:
            session.add(
                User(
                    id="test-user",
                    username="test-user",
                    username_key="test-user",
                    password_hash="test",
                    created_at=1,
                )
            )
            session.add(
                TrackRecord(
                    id="existing",
                    user_id="test-user",
                    filename="existing.mp3",
                    title="Beyoncé—Song",
                    artist="Strings & Hearts",
                    album="Sunrise",
                    duration=180,
                    has_cover=False,
                    cover_source="placeholder",
                    size_bytes=1,
                )
            )
            session.commit()

        @contextmanager
        def tenant_session(user_id: str):
            self.assertEqual(user_id, "test-user")
            with sessions() as session:
                yield session

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
                audio_file.write(b"different file encoding")
                audio_file.flush()
                with (
                    patch("library.tenant_session", side_effect=tenant_session),
                    patch.object(
                        Library,
                        "_read_metadata_path",
                        return_value=(
                            "beyonce song",
                            " strings & hearts ",
                            "different compilation",
                            182,
                            make_placeholder_cover("duplicate"),
                            False,
                        ),
                    ),
                ):
                    result = Library("test-user").add_upload_file(
                        "different-copy.wav", audio_file.name
                    )

            self.assertIsNotNone(result)
            self.assertEqual(result.id, "existing")
            with sessions() as session:
                self.assertEqual(
                    len(session.scalars(select(TrackRecord)).all()),
                    1,
                )
        finally:
            engine.dispose()

    def test_duplicate_metadata_requires_same_title_artist_album_and_nearby_duration(self) -> None:
        existing = TrackRecord(
            id="existing",
            user_id="test-user",
            filename="existing.mp3",
            title="Beyoncé—Song",
            artist="Strings & Hearts",
            album="Sunrise",
            duration=180,
            has_cover=False,
            size_bytes=1,
        )

        self.assertTrue(
            _same_recording_metadata(
                existing,
                "beyonce song",
                " strings & hearts ",
                182,
            )
        )
        self.assertTrue(
            _same_recording_metadata(
                existing,
                "Beyoncé Song",
                "Strings & Hearts",
                180,
            )
        )
        self.assertFalse(
            _same_recording_metadata(
                existing,
                "Beyoncé Song",
                "Different Artist",
                180,
            )
        )
        self.assertFalse(
            _same_recording_metadata(
                existing,
                "Beyoncé Song",
                "Strings & Hearts",
                183,
            )
        )

    def test_placeholder_cover_uses_deterministic_aura_artwork(self) -> None:
        first = make_placeholder_cover("Aura song")
        second = make_placeholder_cover("Aura song")
        other = make_placeholder_cover("Another song")

        self.assertEqual(first.size, (512, 512))
        self.assertEqual(first.mode, "RGB")
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertNotEqual(first.tobytes(), other.tobytes())

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
