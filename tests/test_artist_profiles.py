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


if __name__ == "__main__":
    unittest.main()
