"""Shared TheAudioDB artist-image lookup and paced background resolution."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

from db import ArtistImage, SessionLocal

log = logging.getLogger("vervfy.artist_images")

AUDIODB_BASE_URL = "https://www.theaudiodb.com/api/v1/json"
AUDIODB_DEFAULT_API_KEY = "123"
AUDIODB_FRESH_SECONDS = 180 * 24 * 60 * 60
AUDIODB_NOT_FOUND_SECONDS = 30 * 24 * 60 * 60
AUDIODB_MIN_REQUEST_INTERVAL_SECONDS = 2.4
AUDIODB_MAX_QUEUE_SIZE = 2_000


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


def fetch_artist_image(name: str) -> dict[str, str | None]:
    """Look up an artist and accept only a normalized exact-name match."""
    cleaned_name = clean_artist_name(name)
    normalized_name = normalize_artist_name(cleaned_name)
    if not normalized_name:
        raise ValueError("Artist name is empty after normalization")

    api_key = os.environ.get("AUDIODB_API_KEY", AUDIODB_DEFAULT_API_KEY).strip()
    if not api_key or not re.fullmatch(r"[A-Za-z0-9_-]+", api_key):
        raise ValueError("AUDIODB_API_KEY must be a non-empty path-safe key")

    with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
        response = client.get(
            f"{AUDIODB_BASE_URL}/{api_key}/search.php",
            params={"s": cleaned_name},
        )
        response.raise_for_status()
        payload = response.json()

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


class ArtistImageQueue:
    """One low-memory worker per backend process, globally throttled via Redis."""

    def __init__(self, rate_limiter: Callable[[str, int, int], bool]):
        self._rate_limiter = rate_limiter
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue(
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
        with self._lock:
            if key in self._pending or self._retry_after.get(key, 0) > time.monotonic():
                return False
            try:
                self._queue.put_nowait((key, cleaned))
            except queue.Full:
                log.warning("TheAudioDB artist queue is full; skipped %r", cleaned)
                return False
            self._pending.add(key)
            if not self._worker_started:
                self._worker_started = True
                threading.Thread(
                    target=self._run,
                    name="theaudiodb-artist-images",
                    daemon=True,
                ).start()
            return True

    def _save(self, key: str, data: dict[str, str | None]) -> None:
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

    def _run(self) -> None:
        while True:
            key, name = self._queue.get()
            try:
                try:
                    allowed = self._rate_limiter("theaudiodb:global", 25, 60)
                except RuntimeError:
                    log.exception("TheAudioDB lookup skipped: rate limiter unavailable")
                    with self._lock:
                        self._pending.discard(key)
                        self._retry_after[key] = time.monotonic() + 60
                    time.sleep(60)
                    continue
                if not allowed:
                    self._queue.put((key, name))
                    time.sleep(60)
                    continue

                try:
                    self._save(key, fetch_artist_image(name))
                except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                    log.warning("TheAudioDB artist lookup failed for %r: %s", name, exc)
                    with self._lock:
                        self._pending.discard(key)
                        self._retry_after[key] = time.monotonic() + 60
                except Exception:
                    log.exception("Could not persist TheAudioDB data for %r", name)
                    with self._lock:
                        self._pending.discard(key)
                        self._retry_after[key] = time.monotonic() + 60
                else:
                    with self._lock:
                        self._pending.discard(key)
                        self._retry_after.pop(key, None)
                    time.sleep(AUDIODB_MIN_REQUEST_INTERVAL_SECONDS)
            finally:
                self._queue.task_done()
