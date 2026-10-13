# Third-party data and attribution

## Allowed sources

- **Wikipedia**: artist biography summaries only. Show a link to the article,
  attribute the text to Wikipedia, link **CC BY-SA 4.0**, and identify text
  that has been shortened or adapted.
- **LRCLIB**: optional lyrics lookup. The browser sends the `Lrclib-Client`
  identifier, caches results locally for three days, and does not persist
  fetched lyrics in the Vervfy database. Disable requests with
  `LYRICS_PROVIDER_LRCLIB=0`. Lyrics may remain subject to rights held by their
  respective owners; this integration does not grant a license to reproduce
  them commercially.
- **TheAudioDB**: artist identifiers and artwork URLs only, from the official
  v1 `search.php?s=` API. The application caches URL metadata (not image files)
  globally by normalized artist name, shows images directly from TheAudioDB,
  and credits TheAudioDB in the Credits page. The documented public key is
  `123`; free use is limited to 30 requests/minute, and Premium is documented
  at 100 requests/minute. The API docs explicitly permit using returned image
  URLs on the frontend and document `/small` and `/medium` image suffixes.
  The supplied `/terms.php` URL returned 404 during review, and the API
  documentation does not specify a separate image copyright license or
  commercial-use grant; verify current terms with TheAudioDB before relying on
  a commercial license.
- **User-owned content**: audio tags, embedded artwork, uploaded cover images,
  and lyrics the user pastes.
- **Manual artist profiles**: curated in-app profile text with a source URL;
  do not use a commercial music-catalog service as a source.

**No new external data provider or image host may be added without reading its
terms for commercial use first.** Record the provider, permitted use, required
attribution, and any retention or caching restrictions here before adding an
integration.
