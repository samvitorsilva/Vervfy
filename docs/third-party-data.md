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
- **MusicBrainz + Cover Art Archive**: track cover URLs only. Search recordings
  with the MusicBrainz JSON web service, pick a release-group, then link
  `https://coverartarchive.org/release-group/<mbid>/front-500`. Store the URL
  and `cover_source='musicbrainz'`; do not download or rehost the image.
  Require `MB_CONTACT_EMAIL` for the User-Agent `Vervfy/1.0 (<email>)`, keep
  at most one MusicBrainz request per second, use an 8s timeout, and retry once
  on HTTP 503. Show attribution when a playing track uses this source.
- **TheAudioDB**: artist identifiers and artwork URLs only, from the official
  official v1 endpoints. Artist records use `search.php?s=`; the global cache
  keeps URL metadata (not image files) by normalized artist name. Track lookups
  try `searchtrack.php?s=&t=`, retry `searchtrack.php?s=` when the exact-title
  query has no match, and use `album.php?m=` for `strAlbumThumb`; if needed,
  `searchalbum.php?s=&a=` matches tagged album data. Track cache rows contain
  only album IDs, URLs, statuses, and timestamps, keyed by a versioned digest
  of normalized artist plus title so lookup changes invalidate old misses. The shared background queue rate-limits all
  provider calls to at most 25/minute and spaces them by 2.4 seconds.
  The public docs use key `123` but also show `2` in an example. The free tier
  is documented at 30 requests/minute; Premium is documented at 100/minute.
  The docs label track-search parameter `t` Premium-only, although a live test
  with key `123` returned a title-specific result. The app attempts that
  endpoint and falls back to artist+album search; free-key title-only coverage
  is not guaranteed. The docs/API pages mention an $8/month Premium price,
  while the current home page advertises $10/month. Confirm key access and
  current pricing before upgrading.
  The API docs permit displaying returned image URLs directly and `strAlbumThumb`
  is a thumbnail URL. The supplied `/terms.php` URL returned 404 during review,
  and the API documentation does not specify a separate image copyright
  license or commercial-use grant; verify current terms with TheAudioDB before
  relying on a commercial license.
- **User-owned content**: audio tags, embedded artwork, uploaded cover images,
  and lyrics the user pastes.
- **Manual artist profiles**: curated in-app profile text with a source URL;
  do not use a commercial music-catalog service as a source.

**No new external data provider or image host may be added without reading its
terms for commercial use first.** Record the provider, permitted use, required
attribution, and any retention or caching restrictions here before adding an
integration.

## Track cover storage

Cover resolution after upload runs in the background and never fails the
upload. Order: optional uploaded cover → embedded tags (MP3 ID3/APIC, FLAC,
M4A/MP4, Ogg) → MusicBrainz/Cover Art Archive URL → TheAudioDB URL →
generated placeholder. Uploaded and embedded images are normalized to at most
600x600 JPEG and stored in the private Supabase Storage bucket under
`covers/<user_id>/...`. MusicBrainz and TheAudioDB results store only
`cover_url` plus `cover_source`.

Run `migrations/0018_cover_art_sources.sql` as the Postgres admin, set
`MB_CONTACT_EMAIL` on the API service, then backfill missing covers with
`python scripts/backfill_covers.py` using `BACKFILL_DATABASE_URL` (admin) and
the normal `DATABASE_URL` used by the app.

Older Storage migration: run `python -m scripts.backfill_cover_storage` once
after applying migration 0017 when moving legacy `cover_data` into Storage.
