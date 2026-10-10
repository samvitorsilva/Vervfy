"""Best-effort cover-art lookup for tracks that have no embedded artwork.

Uses Apple's public iTunes Search API (no key needed).  Never raises: if the
network is down or nothing matches, callers just keep the placeholder cover.
"""
from __future__ import annotations

import io
import logging
import re
from urllib.parse import urlsplit

import httpx
from PIL import Image

log = logging.getLogger("vervfy.online_cover")

# Tests can inject an ``httpx.MockTransport`` here.
_transport: httpx.BaseTransport | None = None
_MAX_COVER_BYTES = 5 * 1024 * 1024


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def fetch_cover(title: str, artist: str):
    """Return a PIL image for ``artist`` - ``title``, or None."""
    if not title or not artist or artist.strip().lower() == "unknown artist":
        return None
    want_title, want_artist = _squash(title), _squash(artist)
    if not want_title or not want_artist:
        return None
    try:
        with httpx.Client(
            timeout=httpx.Timeout(5.0, connect=3.0), follow_redirects=True, transport=_transport
        ) as client:
            resp = client.get(
                "https://itunes.apple.com/search",
                params={"term": f"{artist} {title}", "media": "music", "entity": "song", "limit": 10},
            )
            resp.raise_for_status()
            for item in resp.json().get("results", []):
                found_title = _squash(str(item.get("trackName", "")))
                found_artist = _squash(str(item.get("artistName", "")))
                if not (found_title == want_title or found_title.startswith(want_title)):
                    continue
                if not (want_artist in found_artist or found_artist in want_artist):
                    continue
                art_url = str(item.get("artworkUrl100", ""))
                host = urlsplit(art_url).hostname or ""
                if not art_url.startswith("https://") or not host.endswith(".mzstatic.com"):
                    continue  # only ever download from Apple's image CDN
                art = client.get(art_url.replace("100x100bb", "600x600bb"))
                art.raise_for_status()
                if len(art.content) > _MAX_COVER_BYTES:
                    continue
                return Image.open(io.BytesIO(art.content)).convert("RGB")
    except Exception:  # noqa: BLE001 - network/format problems just mean "no cover"
        log.warning("online cover lookup failed for %r / %r", artist, title, exc_info=True)
    return None
