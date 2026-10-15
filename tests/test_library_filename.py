from __future__ import annotations

import unittest

from library import _parse_filename


class ParseFilenameTests(unittest.TestCase):
    def test_parses_simple_artist_title_underscore_filename(self) -> None:
        self.assertEqual(
            _parse_filename("Coldplay_Yellow.mp3"),
            ("Yellow", "Coldplay"),
        )

    def test_underscores_inside_hyphen_delimited_title_become_spaces(self) -> None:
        self.assertEqual(
            _parse_filename("Coldplay - Yellow_Submarine.mp3"),
            ("Yellow Submarine", "Coldplay"),
        )

    def test_strips_trailing_youtube_video_id(self) -> None:
        self.assertEqual(
            _parse_filename("Tauren Wells - Come Home (Live) [lA6QdRXIDSU].mp3"),
            ("Come Home (Live)", "Tauren Wells"),
        )

    def test_strips_movie_promotion_from_filename_title(self) -> None:
        self.assertEqual(
            _parse_filename(
                "Tate McRae - Just Keep Watching (From F1® The Movie) "
                "(Official Video) - Tate McRae.mp3"
            ),
            ("Just Keep Watching", "Tate McRae"),
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

    def test_strips_feature_credit_after_youtube_video_label(self) -> None:
        self.assertEqual(
            _parse_filename(
                "Tauren Wells, gio. - Let The Church Sing "
                "(Official Lyric Video) ft. ELEVATION RHYTHM [3oVhViT8-wY].mp3"
            ),
            ("Let The Church Sing", "Tauren Wells, gio."),
        )

    def test_parses_full_width_pipe_artist_suffix_and_removes_credit(self) -> None:
        self.assertEqual(
            _parse_filename(
                "New Thing Coming (Tiffany Hudson & Steven Furtick) "
                "｜ Elevation Worship [JRRbGCyr2Ac].mp3"
            ),
            ("New Thing Coming", "Elevation Worship"),
        )


if __name__ == "__main__":
    unittest.main()
