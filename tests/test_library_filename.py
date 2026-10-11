from __future__ import annotations

import unittest

from library import _parse_filename


class ParseFilenameTests(unittest.TestCase):
    def test_strips_trailing_youtube_video_id(self) -> None:
        self.assertEqual(
            _parse_filename("Tauren Wells - Come Home (Live) [lA6QdRXIDSU].mp3"),
            ("Come Home (Live)", "Tauren Wells"),
        )

    def test_strips_youtube_id_in_parentheses(self) -> None:
        self.assertEqual(
            _parse_filename("Artist - Song (a_b-C123456).mp3"),
            ("Song", "Artist"),
        )

    def test_keeps_non_id_bracketed_descriptors(self) -> None:
        self.assertEqual(
            _parse_filename("Artist - Song [Official Audio].mp3"),
            ("Song", "Artist"),
        )


if __name__ == "__main__":
    unittest.main()
