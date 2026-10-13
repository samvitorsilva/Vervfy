from __future__ import annotations

import contextlib
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from library import AudioUnavailableError  # noqa: E402
from scripts import rebuild_covers  # noqa: E402


class RebuildCoversTests(unittest.TestCase):
    def test_unavailable_audio_is_skipped_without_rebuilding_cover(self) -> None:
        candidate = ("unavailable-track", "track.mp3", "Track")
        record = SimpleNamespace(
            cover_source="unknown",
            cover_data=b"original-cover",
        )
        first_query = SimpleNamespace(one_or_none=lambda: candidate)
        update_query = SimpleNamespace(scalar_one_or_none=lambda: record)
        tenant_session = SimpleNamespace(
            execute=Mock(side_effect=[first_query, update_query]),
            commit=Mock(),
        )
        user_session = SimpleNamespace(
            scalars=lambda _query: SimpleNamespace(all=lambda: ["user-id"])
        )
        output = io.StringIO()

        with (
            patch.object(rebuild_covers, "SessionLocal", return_value=contextlib.nullcontext(user_session)),
            patch.object(rebuild_covers, "tenant_session", return_value=contextlib.nullcontext(tenant_session)),
            patch.object(
                rebuild_covers.Library,
                "audio_bytes",
                side_effect=AudioUnavailableError("audio missing"),
            ),
            patch.object(rebuild_covers.audio_store, "close_client"),
            patch("sys.argv", ["rebuild_covers.py", "--apply", "--limit", "1"]),
            contextlib.redirect_stdout(output),
        ):
            rebuild_covers.main()

        self.assertEqual(record.cover_source, "unknown")
        self.assertEqual(record.cover_data, b"original-cover")
        tenant_session.execute.assert_called_once()
        tenant_session.commit.assert_not_called()
        self.assertIn("unavailable-track: skipped", output.getvalue())
        self.assertIn("Processed 1; embedded 0; placeholders 0; skipped 1;", output.getvalue())
        self.assertIn("Skipped track ids: unavailable-track", output.getvalue())


if __name__ == "__main__":
    unittest.main()
