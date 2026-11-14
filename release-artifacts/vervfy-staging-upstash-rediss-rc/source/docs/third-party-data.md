# Third-party data and attribution

## Allowed sources

- **Wikipedia**: artist biography summaries only. Show a link to the article,
  attribute the text to Wikipedia, link **CC BY-SA 4.0**, and identify text
  that has been shortened or adapted.
- **LRCLIB**: optional lyrics lookup. The browser calls the app's same-origin
  proxy; the app server sends the `Lrclib-Client` identifier and track metadata
  to LRCLIB. The browser caches results locally for three days, and fetched
  lyrics are not persisted in the Vervfy database. Disable requests with
  `LYRICS_PROVIDER_LRCLIB=0`. Commercial permission from LRCLIB has not been
  confirmed; no response has been received. Do not treat API availability as
  commercial authorization. Lyrics may remain subject to rights held by their
  respective owners; this integration does not grant a license to reproduce
  them commercially.
- **MusicBrainz + Cover Art Archive**: track cover URLs only. Search recordings
  with the MusicBrainz JSON web service, pick a release-group, then link
  `https://coverartarchive.org/release-group/<mbid>/front-500`. Store the URL
  and `cover_source='musicbrainz'`; do not download or rehost the image.
  Require `MB_CONTACT_EMAIL` for the User-Agent `Vervfy/1.0 (<email>)`, keep
  at most one MusicBrainz request per second, use an 8s timeout, and retry once
  on HTTP 503. Show attribution when a playing track uses this source.
- **TheAudioDB**: server-side v1 lookups for artist identifiers and artwork
  URLs. Artist lookups send the cleaned artist name to `search.php?s=`. Track
  cover lookups send artist and title to `searchtrack.php?s=&t=`, may retry
  with artist only, and use a matched album ID with `album.php?m=`; when needed,
  tagged artist and album names are sent to `searchalbum.php?s=&a=`. These
  requests disclose those music tags to TheAudioDB, but do not send audio,
  lyrics, account IDs, or uploaded files. The API key (`AUDIODB_API_KEY`,
  defaulting to the public test key `123`) is sent in the server-side request
  URL. Artist and track caches retain IDs, image URLs, status, and timestamps,
  not TheAudioDB image files. The shared background queue caps requests at
  25/minute and spaces them by 2.4 seconds.

  The current [API guide](https://www.theaudiodb.com/free_music_api) describes
  the free key `123`, a free limit of 30 requests/minute, and direct display of
  image URLs returned by its API; it lists track metadata search as a Premium
  feature. Vervfy still attempts the title-specific `t` query and falls back
  to artist/album searches, so exact-title coverage is not guaranteed with the
  free key. The guide's sample also shows key `2`; Vervfy uses `123` by
  default. The current [pricing page](https://www.theaudiodb.com/pricing)
  lists €8/month for Single Developer, €20/month for Small Business, and
  separate request limits; verify current access and pricing before upgrading.

  The maintainer reports this informal reply from TheAudioDB maintainer Zag:
  “It's entirely up to you. Use our services as you like. Cheers, Zag.” The
  date and channel were not supplied here. Preserve it as informal
  correspondence, not a formal commercial licence, contractual grant, or
  image-specific copyright clearance. The API guide permits direct display of
  returned image URLs, but the reviewed guide does not state a clear
  attribution requirement. Confirm applicable terms, attribution, commercial
  use, and image rights with TheAudioDB and the relevant rights holders before
  relying on the service commercially.

  **API permission is not an image copyright license.** The API guide's
  statement that returned image URLs may be displayed describes API use; it
  does not establish an image-specific copyright license or commercial-reuse
  grant. The [artwork guide](https://www.theaudiodb.com/docs_artwork) notes
  that much of its artwork is fan-created but does not state a separate image
  license. The old `/terms.php` endpoint returned 404 when checked on
  2026-10-30. Do not treat API access or URL display as proof of image
  licensing; obtain or verify the applicable rights before relying on
  commercial reuse.
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
