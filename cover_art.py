"""Ordered cover-art resolution using user-owned and permitted artwork sources."""
from __future__ import annotations

import asyncio
from difflib import SequenceMatcher
from io import BytesIO
import logging
import os
import re
import threading
import time
from typing import Awaitable, Callable

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from artist_images import fetch_track_cover
from library import _extract_cover, make_placeholder_cover

log = logging.getLogger("vervfy.cover_art")

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording"
COVER_ART_ARCHIVE_URL = "https://coverartarchive.org/release-group"
MUSICBRAINZ_MIN_INTERVAL = 1.0
_musicbrainz_lock = asyncio.Lock()
_last_musicbrainz_request = 0.0
_lookup_pending_lock = threading.Lock()
_lookup_pending: set[tuple[str, str]] = set()

_FEAT_RE = re.compile(
    r"\s*[\[(]\s*(?:feat(?:uring)?|ft)\.?\s*[^\])]*[\])]",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(r"\s*-\s*single\s*$", re.IGNORECASE)
_OFFICIAL_VIDEO_RE = re.compile(
    r"\s*[\[(]\s*official\s+video\s*[\])]\s*$",
    re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """Strip common release/video noise and underscores; preserve case."""
    value = title.replace("_", " ")
    value = _FEAT_RE.sub("", value)
    value = _OFFICIAL_VIDEO_RE.sub("", value)
    value = _SINGLE_RE.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title: str) -> str:
    """Case-folded title used when scoring MusicBrainz matches."""
    return clean_title(title).casefold()


def uploaded_cover(data: bytes | None) -> bytes | None:
    """Validate and normalize a supplied JPEG, PNG, or WebP cover to JPEG."""
    if not data:
        return None
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("cover must be 5 MB or smaller")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("cover must be a JPEG, PNG, or WebP image")
            if image.width <= 0 or image.height <= 0 or image.width * image.height > 12_000_000:
                raise ValueError("cover dimensions exceed the configured limit")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((600, 600), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("invalid cover image") from exc


def embedded_cover(audio_path: str) -> bytes | None:
    """Extract embedded art using mutagen and return a normalized JPEG."""
    try:
        image = _extract_cover(audio_path, os.path.splitext(audio_path)[1].lower())
        if image is None:
            return None
        image.thumbnail((600, 600), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue()
    except (OSError, ValueError):
        log.exception("embedded cover extraction failed for %s", audio_path)
        raise


async def _wait_for_musicbrainz_slot() -> None:
    global _last_musicbrainz_request
    async with _musicbrainz_lock:
        delay = MUSICBRAINZ_MIN_INTERVAL - (time.monotonic() - _last_musicbrainz_request)
        if delay > 0:
            await asyncio.sleep(delay)
        _last_musicbrainz_request = time.monotonic()


def _musicbrainz_client() -> httpx.AsyncClient:
    email = os.environ.get("MB_CONTACT_EMAIL", "").strip()
    if not email:
        raise ValueError("MB_CONTACT_EMAIL must be set for MusicBrainz requests")
    return httpx.AsyncClient(
        timeout=httpx.Timeout(8.0),
        follow_redirects=True,
        headers={"User-Agent": f"Vervfy/1.0 ({email})"},
    )


def _release_group_id(recording: dict) -> str | None:
    top = recording.get("release-group")
    if isinstance(top, dict) and top.get("id"):
        return str(top["id"])

    best_id: str | None = None
    best_score = -1
    for release in recording.get("releases") or []:
        if not isinstance(release, dict):
            continue
        group = release.get("release-group")
        if not isinstance(group, dict) or not group.get("id"):
            continue
        score = 0
        if release.get("status") == "Official":
            score += 2
        primary = group.get("primary-type")
        if primary in {"Single", "Album", "EP"}:
            score += 2
        secondary = group.get("secondary-types") or []
        if "DJ-mix" in secondary:
            score -= 3
        if "Compilation" in secondary:
            score -= 1
        if score > best_score:
            best_score = score
            best_id = str(group["id"])
    return best_id


def _recording_score(recording: dict, wanted_title: str, wanted_artist: str) -> float:
    result_title = normalize_title(str(recording.get("title") or ""))
    result_artist = " ".join(
        str(credit.get("name") or "")
        for credit in recording.get("artist-credit", [])
        if isinstance(credit, dict)
    ).casefold()
    title_score = SequenceMatcher(None, wanted_title, result_title).ratio()
    artist_score = SequenceMatcher(None, wanted_artist.casefold(), result_artist).ratio()
    score = title_score * 0.75 + artist_score * 0.25
    if recording.get("video"):
        score -= 0.05
    return score


async def musicbrainz_cover(artist: str, title: str) -> str | None:
    """Find the best recording match and return its Cover Art Archive front URL."""
    query_title = clean_title(title)
    wanted_title = normalize_title(title)
    if not artist.strip() or not wanted_title:
        return None

    cover_url: str | None = None
    async with _musicbrainz_client() as client:
        params = {
            "query": f'artist:"{artist.strip()}" AND recording:"{query_title}"',
            "fmt": "json",
            "limit": "5",
        }
        response = None
        for attempt in range(2):
            await _wait_for_musicbrainz_slot()
            response = await client.get(MUSICBRAINZ_URL, params=params)
            if response.status_code != 503 or attempt == 1:
                break
        assert response is not None
        response.raise_for_status()
        payload = response.json()

        recordings = payload.get("recordings", []) if isinstance(payload, dict) else []
        candidates: list[tuple[float, str]] = []
        for item in recordings:
            if not isinstance(item, dict):
                continue
            mbid = _release_group_id(item)
            if not mbid:
                continue
            candidates.append(
                (_recording_score(item, wanted_title, artist.strip()), mbid)
            )
        if not candidates:
            return None
        _, mbid = max(candidates, key=lambda item: item[0])
        cover_url = f"{COVER_ART_ARCHIVE_URL}/{mbid}/front-500"

        # Confirm art exists without retaining the image body.
        await _wait_for_musicbrainz_slot()
        head = await client.head(cover_url)
        if head.status_code == 404:
            return None
        if head.status_code in {200, 301, 302, 303, 307, 308}:
            return cover_url
        if head.status_code not in {405, 501}:
            head.raise_for_status()
            return cover_url

        async with client.stream("GET", cover_url) as streamed:
            if streamed.status_code == 404:
                return None
            streamed.raise_for_status()
            return cover_url


def audiodb_cover(
    artist: str,
    title: str,
    album: str,
    request_json: Callable[[str, dict[str, str]], dict] | None = None,
) -> str | None:
    result = (
        fetch_track_cover(artist, title, album)
        if request_json is None
        else fetch_track_cover(artist, title, album, request_json)
    )
    return result.get("cover_url") if result.get("status") == "found" else None


def generated_cover(title: str) -> bytes:
    """Create the final local fallback image without storing a remote asset."""
    output = BytesIO()
    make_placeholder_cover(title).save(output, format="JPEG", quality=90)
    return output.getvalue()


def schedule_cover_resolution(background_tasks, user_id: str, track_id: str, **kwargs) -> bool:
    key = (user_id, track_id)
    with _lookup_pending_lock:
        if key in _lookup_pending:
            return True
        from library import Library

        if not Library(user_id).claim_cover_resolution(
            track_id, force=bool(kwargs.get("force", False))
        ):
            return False
        _lookup_pending.add(key)
    background_tasks.add_task(
        _resolve_scheduled_cover, user_id, track_id, key, kwargs
    )
    return True


async def _resolve_scheduled_cover(
    user_id: str, track_id: str, key: tuple[str, str], kwargs: dict
) -> None:
    try:
        await resolve_cover(user_id, track_id, **kwargs)
    except Exception:
        log.exception("cover lookup track_id=%s step=chain result=error", track_id)
    finally:
        with _lookup_pending_lock:
            _lookup_pending.discard(key)


async def resolve_cover(
    user_id: str,
    track_id: str,
    *,
    uploaded_data: bytes | None = None,
    audio_path: str | None = None,
    force: bool = False,
    lookup_musicbrainz: Callable[[str, str], Awaitable[str | None] | str | None] | None = None,
    lookup_audiodb: Callable[[str, str, str], str | None] | None = None,
) -> None:
    """Run the ordered lookup; each failed provider logs and falls through."""
    from library import Library

    library = Library(user_id)
    track = library.get(track_id)
    if track is None:
        return

    owned = {"upload", "user"}
    if not force and track.cover_source in owned and not uploaded_data:
        log.info("cover lookup track_id=%s step=upload result=miss", track_id)
        return

    async def persist(source: str, image: bytes | None = None, url: str | None = None) -> None:
        await asyncio.to_thread(library.set_resolved_cover, track_id, source, image, url)

    try:
        image = uploaded_cover(uploaded_data)
        if image is not None:
            await persist("upload", image=image)
            log.info("cover lookup track_id=%s step=upload result=hit", track_id)
            return
        log.info("cover lookup track_id=%s step=upload result=miss", track_id)
    except Exception:
        log.exception("cover lookup track_id=%s step=upload result=error", track_id)

    track = library.get(track_id) or track
    if track.cover_source in owned:
        return

    try:
        image = None
        if not force and track.cover_source == "embedded" and track.has_cover:
            log.info("cover lookup track_id=%s step=embedded result=hit", track_id)
            return
        if audio_path is not None:
            image = embedded_cover(audio_path)
        else:
            image = await asyncio.to_thread(library.embedded_cover, track_id)
        if image:
            await persist("embedded", image=image)
            log.info("cover lookup track_id=%s step=embedded result=hit", track_id)
            return
        log.info("cover lookup track_id=%s step=embedded result=miss", track_id)
    except Exception:
        log.exception("cover lookup track_id=%s step=embedded result=error", track_id)

    track = library.get(track_id) or track
    if track.cover_source in {"embedded", *owned}:
        return

    try:
        lookup = lookup_musicbrainz or musicbrainz_cover
        result = lookup(track.artist, track.title)
        url = await result if asyncio.iscoroutine(result) else result
        if url:
            await persist("musicbrainz", url=url)
            log.info("cover lookup track_id=%s step=musicbrainz result=hit", track_id)
            return
        log.info("cover lookup track_id=%s step=musicbrainz result=miss", track_id)
    except Exception:
        log.exception("cover lookup track_id=%s step=musicbrainz result=error", track_id)

    try:
        lookup = lookup_audiodb or audiodb_cover
        url = await asyncio.to_thread(lookup, track.artist, track.title, track.album)
        if url:
            await persist("audiodb", url=url)
            log.info("cover lookup track_id=%s step=audiodb result=hit", track_id)
            return
        log.info("cover lookup track_id=%s step=audiodb result=miss", track_id)
    except Exception:
        log.exception("cover lookup track_id=%s step=audiodb result=error", track_id)

    try:
        image = generated_cover(track.title)
        await persist("generated", image=image)
        log.info("cover lookup track_id=%s step=generated result=hit", track_id)
    except Exception:
        log.exception("cover lookup track_id=%s step=generated result=error", track_id)
