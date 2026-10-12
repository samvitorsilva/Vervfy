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
- **User-owned content**: audio tags, embedded artwork, uploaded cover images,
  and lyrics the user pastes.
- **Manual artist profiles**: curated in-app profile text with a source URL;
  do not use a commercial music-catalog service as a source.

**No new external data provider or image host may be added without reading its
terms for commercial use first.** Record the provider, permitted use, required
attribution, and any retention or caching restrictions here before adding an
integration.
