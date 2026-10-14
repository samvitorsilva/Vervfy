"""Shared TheAudioDB artist and track artwork lookups with paced background resolution."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import queue
import re
import threading
import time
import unicodedata
from typing import Callable
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from db import ArtistImage, SessionLocal, TrackCoverCache

log = logging.getLogger("vervfy.artist_images")

AUDIODB_BASE_URL = "https://www.theaudiodb.com/api/v1/json"
AUDIODB_DEFAULT_API_KEY = "123"
AUDIODB_FRESH_SECONDS = 180 * 24 * 60 * 60
AUDIODB_NOT_FOUND_SECONDS = 30 * 24 * 60 * 60
AUDIODB_MIN_REQUEST_INTERVAL_SECONDS = 2.4
AUDIODB_MAX_QUEUE_SIZE = 2_000
TRACK_COVER_LOOKUP_VERSION = "2"


def clean_artist_name(name: str) -> str:
    """Return the lead artist only from a compound artist credit."""
    value = re.sub(
        r"\b(?:feat(?:uring)?|ft)(?:\.|\b).*$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    value = re.split(r"\s*(?:&|,)\s*|\s+x\s+", value, maxsplit=1)[0]
    return re.sub(r"\s+", " ", value.strip(" \t-–—·•")).strip()


def normalize_artist_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    return "".join(character.casefold() for character in normalized if character.isalnum())


def track_cover_cache_key(artist: str, title: str) -> tuple[str, str, str]:
    normalized_artist = normalize_artist_name(clean_artist_name(artist))
    normalized_title = normalize_artist_name(title)
    if not normalized_artist or not normalized_title:
        return "", normalized_artist, normalized_title
    key = hashlib.sha256(
        f"{TRACK_COVER_LOOKUP_VERSION}\0{normalized_artist}\0{normalized_title}".encode(
            "utf-8"
        )
    ).hexdigest()
    return key, normalized_artist, normalized_title


def artists_from_credit(credit: str) -> list[str]:
    """Keep the artist-page grouping while returning clean search candidates."""
    parts = re.split(
        r"\s*(?:,|;|/|&|\bfeat(?:uring)?\.?|\bft\.?|\bwith\b)\s*",
        credit,
        flags=re.IGNORECASE,
    )
    candidates: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for delimited in re.split(r"\s+x\s+", part):
            for candidate in re.split(r"\s+and\s+", delimited, flags=re.IGNORECASE):
                cleaned = clean_artist_name(candidate)
                key = normalize_artist_name(cleaned)
                if cleaned and key and key not in seen:
                    seen.add(key)
                    candidates.append(cleaned)
    return candidates


def _validated_image_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not (
            parsed.hostname == "theaudiodb.com"
            or parsed.hostname.endswith(".theaudiodb.com")
        )
        or parsed.username
        or parsed.password
    ):
        return None
    return url


def _fetch_json(
    endpoint: str,
    params: dict[str, str],
    request_json: Callable[[str, dict[str, str]], dict] | None,
) -> dict:
    if request_json is not None:
        return request_json(endpoint, params)
    api_key = os.environ.get("AUDIODB_API_KEY", AUDIODB_DEFAULT_API_KEY).strip()
    if not api_key or not re.fullmatch(r"[A-Za-z0-9_-]+", api_key):
        raise ValueError("AUDIODB_API_KEY must be a non-empty path-safe key")
    with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
        response = client.get(
            f"{AUDIODB_BASE_URL}/{api_key}/{endpoint}",
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}


def fetch_artist_image(
    name: str,
    request_json: Callable[[str, dict[str, str]], dict] | None = None,
) -> dict[str, str | None]:
    """Look up an artist and accept only a normalized exact-name match."""
    cleaned_name = clean_artist_name(name)
    normalized_name = normalize_artist_name(cleaned_name)
    if not normalized_name:
        raise ValueError("Artist name is empty after normalization")

    payload = _fetch_json("search.php", {"s": cleaned_name}, request_json)

    artists = payload.get("artists") if isinstance(payload, dict) else None
    if not isinstance(artists, list):
        return {
            "audiodb_id": None,
            "image_url": None,
            "banner_url": None,
            "status": "not_found",
        }

    for artist in artists:
        if not isinstance(artist, dict):
            continue
        result_name = artist.get("strArtist")
        if (
            not isinstance(result_name, str)
            or normalize_artist_name(clean_artist_name(result_name)) != normalized_name
        ):
            continue
        artist_id = artist.get("idArtist")
        return {
            "audiodb_id": str(artist_id) if artist_id is not None else None,
            "image_url": _validated_image_url(artist.get("strArtistThumb")),
            "banner_url": (
                _validated_image_url(artist.get("strArtistFanart"))
                or _validated_image_url(artist.get("strArtistBanner"))
            ),
            "status": "found",
        }

    return {
        "audiodb_id": None,
        "image_url": None,
        "banner_url": None,
        "status": "not_found",
    }


def fetch_track_cover(
    artist: str,
    title: str,
    album: str,
    request_json: Callable[[str, dict[str, str]], dict] | None = None,
) -> dict[str, str | None]:
    """Find an album thumbnail only when TheAudioDB confirms the artist."""
    cleaned_artist = clean_artist_name(artist)
    artist_key = normalize_artist_name(cleaned_artist)
    title_key = normalize_artist_name(title)
    if not artist_key or not title_key:
        raise ValueError("Track artist and title are required")

    album_id: str | None = None
    track_search_error: httpx.HTTPError | None = None

    def matching_album_id(payload: dict) -> str | None:
        tracks = payload.get("track") if isinstance(payload, dict) else None
        if not isinstance(tracks, list):
            return None
        for track in tracks:
            if not isinstance(track, dict):
                continue
            if (
                normalize_artist_name(
                    clean_artist_name(str(track.get("strArtist") or ""))
                )
                != artist_key
                or normalize_artist_name(str(track.get("strTrack") or ""))
                != title_key
            ):
                continue
            candidate_id = track.get("idAlbum")
            if candidate_id is not None and str(candidate_id).strip():
                return str(candidate_id).strip()
        return None

    try:
        payload = _fetch_json(
            "searchtrack.php",
            {"s": cleaned_artist, "t": title.strip()},
            request_json,
        )
    except httpx.HTTPError as exc:
        if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code not in {
            400,
            403,
            404,
        }:
            track_search_error = exc
            payload = {}
        else:
            log.info(
                "TheAudioDB title search unavailable for %r; trying free artist search",
                title,
            )
            payload = {}
    album_id = matching_album_id(payload)

    if album_id is None and track_search_error is None:
        try:
            payload = _fetch_json(
                "searchtrack.php", {"s": cleaned_artist}, request_json
            )
            album_id = matching_album_id(payload)
        except httpx.HTTPError as exc:
            if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code not in {
                400,
                403,
                404,
            }:
                track_search_error = exc

    if album_id is not None:
        try:
            album_payload = _fetch_json("album.php", {"m": album_id}, request_json)
        except httpx.HTTPError as exc:
            log.info("TheAudioDB album-ID lookup failed for %s: %s", album_id, exc)
            album_payload = {}
        albums = album_payload.get("album") if isinstance(album_payload, dict) else None
        if isinstance(albums, list):
            for result in albums:
                if not isinstance(result, dict):
                    continue
                if (
                    normalize_artist_name(
                        clean_artist_name(str(result.get("strArtist") or ""))
                    )
                    != artist_key
                ):
                    continue
                candidate_id = result.get("idAlbum")
                if candidate_id is not None and str(candidate_id) != album_id:
                    continue
                cover_url = _validated_image_url(result.get("strAlbumThumb"))
                if cover_url:
                    return {
                        "audiodb_album_id": album_id,
                        "cover_url": cover_url,
                        "status": "found",
                    }

    album_name = album.strip()
    has_album_name = bool(
        album_name
        and normalize_artist_name(album_name) not in {"unknownalbum", "unknown"}
    )
    if has_album_name:
        album_payload = _fetch_json(
            "searchalbum.php",
            {"s": cleaned_artist, "a": album_name},
            request_json,
        )
        albums = album_payload.get("album") if isinstance(album_payload, dict) else None
        if isinstance(albums, list):
            album_key = normalize_artist_name(album_name)
            for result in albums:
                if not isinstance(result, dict):
                    continue
                if (
                    normalize_artist_name(
                        clean_artist_name(str(result.get("strArtist") or ""))
                    )
                    != artist_key
                    or normalize_artist_name(str(result.get("strAlbum") or ""))
                    != album_key
                ):
                    continue
                cover_url = _validated_image_url(result.get("strAlbumThumb"))
                if cover_url:
                    candidate_id = result.get("idAlbum")
                    return {
                        "audiodb_album_id": (
                            str(candidate_id) if candidate_id is not None else None
                        ),
                        "cover_url": cover_url,
                        "status": "found",
                    }

    if track_search_error is not None and not has_album_name:
        raise track_search_error

    return {
        "audiodb_album_id": album_id,
        "cover_url": None,
        "status": "not_found",
    }


def is_stale(record: dict[str, object] | None, now: datetime | None = None) -> bool:
    if record is None:
        return True
    fetched_at = record.get("fetched_at")
    if not isinstance(fetched_at, datetime):
        return True
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    max_age = (
        AUDIODB_NOT_FOUND_SECONDS
        if record.get("status") == "not_found"
        else AUDIODB_FRESH_SECONDS
    )
    return current - fetched_at >= timedelta(seconds=max_age)


def is_track_cover_stale(
    record: dict[str, object] | None, now: datetime | None = None
) -> bool:
    return is_stale(record, now)


class TheAudioDBQueue:
    """One low-memory worker per backend process, globally throttled via Redis."""

    def __init__(self, rate_limiter: Callable[[str, int, int], bool]):
        self._rate_limiter = rate_limiter
        self._queue: queue.Queue[tuple[str, str, str, str, str]] = queue.Queue(
            maxsize=AUDIODB_MAX_QUEUE_SIZE
        )
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._retry_after: dict[str, float] = {}
        self._worker_started = False

    def enqueue(self, name: str) -> bool:
        cleaned = clean_artist_name(name)
        key = normalize_artist_name(cleaned)
        if not key:
            return False
        return self._enqueue("artist", key, cleaned, "", "")

    def enqueue_track(self, artist: str, title: str, album: str) -> bool:
        key, normalized_artist, normalized_title = track_cover_cache_key(
            artist, title
        )
        if not key or normalize_artist_name(artist) in {"unknown", "unknownartist"}:
            return False
        cleaned_artist = clean_artist_name(artist)
        return self._enqueue(
            "track",
            key,
            cleaned_artist,
            title.strip(),
            album.strip(),
        )

    def _enqueue(
        self, kind: str, key: str, first: str, second: str, third: str
    ) -> bool:
        pending_key = f"{kind}:{key}"
        with self._lock:
            if (
                pending_key in self._pending
                or self._retry_after.get(pending_key, 0) > time.monotonic()
            ):
                return False
            try:
                self._queue.put_nowait((kind, key, first, second, third))
            except queue.Full:
                log.warning("TheAudioDB queue is full; skipped %r", first)
                return False
            self._pending.add(pending_key)
            if not self._worker_started:
                self._worker_started = True
                threading.Thread(
                    target=self._run,
                    name="theaudiodb-lookup-queue",
                    daemon=True,
                ).start()
            return True

    def _save_artist(self, key: str, data: dict[str, str | None]) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(ArtistImage, key)
            if row is None:
                row = ArtistImage(normalized_artist_name=key)
                session.add(row)
            row.audiodb_id = data["audiodb_id"]
            row.image_url = data["image_url"]
            row.banner_url = data["banner_url"]
            row.status = str(data["status"])
            row.fetched_at = now
            session.commit()

    def _save_track(
        self,
        key: str,
        normalized_artist: str,
        normalized_title: str,
        data: dict[str, str | None],
    ) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(TrackCoverCache, key)
            if row is None:
                row = TrackCoverCache(
                    cache_key=key,
                    normalized_artist=normalized_artist,
                    normalized_title=normalized_title,
                )
                session.add(row)
            row.audiodb_album_id = data["audiodb_album_id"]
            row.cover_url = data["cover_url"]
            row.status = str(data["status"])
            row.fetched_at = now
            session.commit()

    def _request_json(self, endpoint: str, params: dict[str, str]) -> dict:
        while True:
            try:
                allowed = self._rate_limiter("theaudiodb:global", 25, 60)
            except RuntimeError:
                log.exception("TheAudioDB lookup skipped: rate limiter unavailable")
                raise
            if allowed:
                break
            time.sleep(60)

        api_key = os.environ.get("AUDIODB_API_KEY", AUDIODB_DEFAULT_API_KEY).strip()
        if not api_key or not re.fullmatch(r"[A-Za-z0-9_-]+", api_key):
            raise ValueError("AUDIODB_API_KEY must be a non-empty path-safe key")
        try:
            with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
                response = client.get(
                    f"{AUDIODB_BASE_URL}/{api_key}/{endpoint}",
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                return {}
            return payload
        finally:
            time.sleep(AUDIODB_MIN_REQUEST_INTERVAL_SECONDS)

    def _run(self) -> None:
        while True:
            kind, key, first, second, third = self._queue.get()
            pending_key = f"{kind}:{key}"
            try:
                try:
                    if kind == "artist":
                        self._save_artist(
                            key,
                            fetch_artist_image(first, self._request_json),
                        )
                    else:
                        _, normalized_artist, normalized_title = (
                            track_cover_cache_key(first, second)
                        )
                        self._save_track(
                            key,
                            normalized_artist,
                            normalized_title,
                            fetch_track_cover(
                                first, second, third, self._request_json
                            ),
                        )
                except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                    log.warning("TheAudioDB %s lookup failed for %r: %s", kind, first, exc)
                    with self._lock:
                        self._pending.discard(pending_key)
                        self._retry_after[pending_key] = time.monotonic() + 60
                except Exception:
                    log.exception("Could not persist TheAudioDB %s data for %r", kind, first)
                    with self._lock:
                        self._pending.discard(pending_key)
                        self._retry_after[pending_key] = time.monotonic() + 60
                else:
                    with self._lock:
                        self._pending.discard(pending_key)
                        self._retry_after.pop(pending_key, None)
            finally:
                self._queue.task_done()
