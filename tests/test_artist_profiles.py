from __future__ import annotations

import unittest
from urllib.parse import quote

import httpx

import server


class WikipediaArtistProfileLanguageTests(unittest.TestCase):
    def test_disambiguation_results_resolve_actor_qualified_artist_pages(
        self,
    ) -> None:
        cases = (
            (
                "en",
                "Kevin Quinn (actor)",
                "American actor and singer",
                "Kevin Gerard Quinn is an American actor and musician.",
                "en.wikipedia.org",
            ),
            (
                "pt-BR",
                "Kevin Quinn (ator)",
                "ator americano",
                "Kevin Quinn é um ator e cantor americano.",
                "pt.wikipedia.org",
            ),
        )
        for language, title, description, extract, host in cases:
            with self.subTest(language=language):
                artist_path = quote("Kevin Quinn", safe="")
                wiki_path = quote(title, safe="")

                def handler(request: httpx.Request) -> httpx.Response:
                    if request.url.path.endswith(
                        f"/api/rest_v1/page/summary/{artist_path}"
                    ):
                        return httpx.Response(
                            200,
                            json={"type": "disambiguation", "title": "Kevin Quinn"},
                        )
                    if request.url.path.endswith("/w/api.php"):
                        return httpx.Response(
                            200,
                            json={"query": {"search": [{"title": title}]}},
                        )
                    if request.url.path.endswith(f"/page/summary/{title}"):
                        return httpx.Response(
                            200,
                            json={
                                "type": "standard",
                                "title": title,
                                "description": description,
                                "extract": extract,
                                "content_urls": {
                                    "desktop": {
                                        "page": (
                                            f"https://{host}/wiki/"
                                            f"{title.replace(' ', '_')}"
                                        )
                                    }
                                },
                            },
                        )
                    return httpx.Response(404)

                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    profile = server._fetch_wikipedia_artist_profile(
                        client, "Kevin Quinn", language
                    )

                self.assertIsNotNone(profile)
                assert profile is not None
                self.assertEqual(profile["bio"], extract)
                self.assertEqual(
                    profile["source_url"],
                    f"https://{host}/wiki/{title.replace(' ', '_')}",
                )

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

    def test_english_profile_is_used_when_requested_language_has_no_entry(self) -> None:
        for language, localized_host in (
            ("pt-BR", "pt.wikipedia.org"),
            ("fr", "fr.wikipedia.org"),
            ("es", "es.wikipedia.org"),
        ):
            with self.subTest(language=language):
                requests: list[httpx.Request] = []

                def handler(request: httpx.Request) -> httpx.Response:
                    requests.append(request)
                    if request.url.host == localized_host:
                        return httpx.Response(404)
                    return httpx.Response(
                        200,
                        json={
                            "type": "standard",
                            "title": "Example Artist",
                            "description": "American singer",
                            "extract": (
                                "Example Artist is an American singer and songwriter."
                            ),
                            "content_urls": {
                                "desktop": {
                                    "page": "https://en.wikipedia.org/wiki/Example_Artist"
                                }
                            },
                        },
                    )

                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    profile = server._fetch_wikipedia_artist_profile(
                        client, "Example Artist", language
                    )

                self.assertIsNotNone(profile)
                assert profile is not None
                self.assertEqual(
                    profile["bio"],
                    "Example Artist is an American singer and songwriter.",
                )
                self.assertEqual(profile["source"], "Wikipedia")
                self.assertEqual(
                    [request.url.host for request in requests],
                    [localized_host, localized_host, "en.wikipedia.org"],
                )


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
