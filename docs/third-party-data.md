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

Embedded artwork is already extracted from MP3 ID3/APIC, FLAC, M4A/MP4, and
Ogg/Opus during upload. New embedded and user-selected cover images are
normalized to at most 600x600 JPEG and stored in the private Supabase Storage
bucket under `covers/<user_id>/...`; the database keeps only the user-scoped
path. When tags are absent, a simple `Artist_Title.ext` filename is parsed as
the artist/title pair, and existing `Artist - Track_Title.ext` names remain
supported. Older covers are already present in `tracks.cover_data`, so the
backfill uses those first and reads at most one legacy audio blob at a time
only when an embedded image is missing from `cover_data`.

Run `python -m scripts.backfill_cover_storage` once after applying migration
0017. Provide `BACKFILL_DATABASE_URL` using a PostgreSQL table owner/admin role
that can read tracks across RLS, plus the existing `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`, and `SUPABASE_BUCKET` settings. The script processes
metadata in small batches and never selects multiple audio blobs together.
