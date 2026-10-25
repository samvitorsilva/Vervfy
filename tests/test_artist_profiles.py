from __future__ import annotations

import unittest

import httpx

import server


class WikipediaArtistProfileLanguageTests(unittest.TestCase):
    def test_french_and_spanish_profiles_use_the_matching_wikipedia(self) -> None:
        cases = (
            (
                "fr",
                "chanteuse",
                "Artiste Exemple est une chanteuse française.",
                "Wikipédia",
                "fr.wikipedia.org",
            ),
            (
                "es",
                "cantante",
                "Artista Ejemplo es una cantante española.",
                "Wikipedia",
                "es.wikipedia.org",
            ),
        )
        for language, description, extract, source, host in cases:
            with self.subTest(language=language):
                requests: list[httpx.Request] = []

                def handler(request: httpx.Request) -> httpx.Response:
                    requests.append(request)
                    return httpx.Response(
                        200,
                        json={
                            "type": "standard",
                            "title": "Artiste Exemple",
                            "description": description,
                            "extract": extract,
                            "content_urls": {
                                "desktop": {
                                    "page": f"https://{host}/wiki/Artiste_Exemple"
                                }
                            },
                        },
                    )

                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    profile = server._fetch_wikipedia_artist_profile(
                        client, "Artiste Exemple", language
                    )

                self.assertIsNotNone(profile)
                self.assertEqual(profile["source"], source)
                self.assertEqual(profile["bio"], extract)
                self.assertEqual(requests[0].url.host, host)


class VerifiedArtistProfileLanguageTests(unittest.TestCase):
    def test_all_verified_profile_copy_is_available_in_each_app_language(self) -> None:
        for artist, english_profile in server._VERIFIED_ARTIST_PROFILES.items():
            for language in ("pt-BR", "fr", "es"):
                with self.subTest(artist=artist, language=language):
                    profile = server._verified_artist_profile(artist, language)
                    self.assertIsNotNone(profile)
                    assert profile is not None
                    translated_fields = (
                        server._VERIFIED_ARTIST_PROFILES_PT.get(artist, {}).copy()
                        if language == "pt-BR"
                        else {}
                    )
                    translated_fields.update(
                        server._VERIFIED_ARTIST_PROFILE_TRANSLATIONS[language].get(
                            artist, {}
                        )
                    )
                    for field in ("bio", "genre", "highlights"):
                        if field not in english_profile:
                            continue
                        self.assertIn(field, translated_fields)
                        if field in {"bio", "highlights"}:
                            self.assertNotEqual(profile[field], english_profile[field])


if __name__ == "__main__":
    unittest.main()
