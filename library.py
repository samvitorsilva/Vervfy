"""PostgreSQL-backed music library; no durable data is written to disk."""
from __future__ import annotations
import base64, hashlib, io, logging, math, os, re, tempfile
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from sqlalchemy import func, select, update
from sqlalchemy.orm import load_only
import audio_store
from db import TrackRecord, User, tenant_session

log = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = int(os.environ.get("VERVFY_MAX_IMAGE_PIXELS", "12000000"))
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import APIC, ID3
    from mutagen.flac import Picture
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError: MUTAGEN_AVAILABLE = False

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".aac", ".flac", ".ogg", ".oga", ".opus", ".wav", ".weba"}
BytesLike = bytes | bytearray | memoryview
@dataclass
class Track:
    id: str; filename: str; title: str; artist: str; album: str; duration: float; has_cover: bool; cover_source: str | None; custom_lyrics: str | None; audio_data: bytes; cover_data: bytes; cover_path: str | None; cover_url: str | None


class UploadQuotaExceeded(RuntimeError):
    """Raised when an upload no longer fits the account quota at commit time."""


class AudioUnavailableError(RuntimeError):
    """A track has neither a Storage object nor a legacy database audio blob."""


def track_id_for_bytes(data: BytesLike) -> str:
    return hashlib.sha256(data).hexdigest()


def track_id_for_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as audio_file:
        while chunk := audio_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()

def make_placeholder_cover(title: str, size: int = 512) -> Image.Image:
    """Create title-specific abstract aura artwork for tracks without a cover."""
    seed = hashlib.sha256(title.strip().casefold().encode("utf-8")).digest()
    palettes = (
        ("8b7fff", "54e8d4"),
        ("ff8fb1", "8b7fff"),
        ("54e8d4", "3aa0ff"),
        ("ffb86b", "ff6b9d"),
        ("6bd6ff", "8b7fff"),
        ("c084fc", "54e8d4"),
    )
    palette = palettes[seed[2] % len(palettes)]
    angle = int.from_bytes(seed[:2], "big") / 65535 * math.tau
    x = size * (0.5 + math.cos(angle) * 0.15)
    y = size * (0.5 + math.sin(angle) * 0.15)

    gradient = Image.linear_gradient("L").resize((size, size), Image.Resampling.BILINEAR)
    gradient = Image.blend(gradient, gradient.transpose(Image.Transpose.ROTATE_90), 0.5)
    image = ImageOps.colorize(gradient, "#0c0e14", "#191d2b").convert("RGBA")
    glow = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(glow)
    for color, center, radius, alpha in (
        (palette[0], (x, y), size * 0.72, 150),
        (palette[1], (size - x, size - y), size * 0.58, 115),
    ):
        rgb = tuple(bytes.fromhex(color))
        draw.ellipse(
            (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
            fill=(*rgb, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, size * 0.18)))
    return Image.alpha_composite(image, glow).convert("RGB")

_NOISE_WORDS = {
    "official", "lyric", "lyrics", "video", "music", "audio", "visualizer",
    "visualiser", "hd", "hq", "4k", "performance", "clip",
}


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _strip_noise(text: str) -> str:
    """Remove "(Lyric Video)", "[Official Audio]" and similar YouTube tags."""
    def repl(match):
        words = re.findall(r"[a-z0-9]+", match.group(1).lower())
        return " " if words and all(word in _NOISE_WORDS for word in words) else match.group(0)

    return re.sub(r"\s+", " ", re.sub(r"[(\[]([^)\]]*)[)\]]", repl, text)).strip()


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+(?:feat(?:uring)?|ft\.?|with)\s+.+$", "", title, flags=re.I).strip()
    title = re.sub(r"\s*[\[(][^)\]]*&[^)\]]*[)\]]", "", title).strip()
    cleaned = _strip_noise(title)
    cleaned = re.sub(
        r"\s*[\[(]from\b[^)\]]*\b(?:movie|film|soundtrack)[)\]]\s*$",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    return cleaned or title


def _is_channel(part: str) -> bool:
    return bool(re.search(r"vevo", part, re.I))


def _channel_to_artist(part: str) -> str:
    """'TateMcRaeVEVOTate McRae' -> 'Tate McRae'; 'TheWeekndVEVO' -> 'TheWeeknd'."""
    pieces = [piece.strip() for piece in re.split(r"vevo", part, flags=re.I) if piece.strip()]
    if not pieces:
        return part.strip()
    return ([piece for piece in pieces if " " in piece] or pieces)[0]


def _parse_filename(filename: str):
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"\s*(?:\[[A-Za-z0-9_-]{11}\]|\([A-Za-z0-9_-]{11}\))$", "", stem)
    underscore_parts = [part.strip() for part in stem.split("_")]
    if (
        len(underscore_parts) == 2
        and all(underscore_parts)
        and not re.search(r"\s[-–—]\s|[|｜]", stem)
    ):
        return _clean_title(underscore_parts[1]), underscore_parts[0]
    stem = re.sub(r"\s+", " ", stem.replace("_", " ")).strip()
    if re.search(r"[|｜]", stem):
        title, artist = (part.strip() for part in re.split(r"\s*[|｜]\s*", stem, maxsplit=1))
        if title and artist:
            return _clean_title(title), artist
    parts = [part.strip() for part in re.split(r"\s[-–—]\s", stem) if part.strip()]
    topic = len(parts) > 2 and parts[-1].lower() == "topic"
    if topic:
        parts.pop()
        return (_strip_noise(" - ".join(parts[:-1])) or parts[0]), parts[-1]
    if len(parts) < 2:
        return (_strip_noise(stem) or stem), "Unknown Artist"

    first, second = parts[0], parts[1]
    if (
        _is_channel(second)
        or (_strip_noise(first) != first and _strip_noise(second) == second)
        or re.match(r"^[A-Z]{2}\s+[A-Z]", second)
    ):
        artist = _channel_to_artist(second) if _is_channel(second) else second
        title = first
    else:
        artist, rest = (_channel_to_artist(first) if _is_channel(first) else first), parts[1:]
        if len(rest) > 1 and (_is_channel(rest[-1]) or _squash(rest[-1]) == _squash(artist)):
            rest = rest[:-1]
        title = " - ".join(rest)
    return _clean_title(title), artist

def _tag_text(value, fallback: str, *, join_values: bool = False) -> str:
    if value is None:
        return fallback
    values = value if isinstance(value, (list, tuple)) else [value]
    normalized = list(dict.fromkeys(
        text for item in values if (text := str(item).strip())
    ))
    if not normalized:
        return fallback
    return "; ".join(normalized) if join_values else normalized[0]


def _extract_cover(path: str, ext: str) -> Image.Image | None:
    """Read embedded artwork from the formats mutagen exposes differently."""
    try:
        if ext == ".mp3":
            for tag in ID3(path).values():
                if isinstance(tag, APIC) and tag.data:
                    return Image.open(io.BytesIO(tag.data)).convert("RGB")
        audio = MutagenFile(path)
        if audio is None:
            return None
        if ext in {".m4a", ".mp4"}:
            covers = (getattr(audio, "tags", None) or {}).get("covr") or []
            if covers:
                return Image.open(io.BytesIO(bytes(covers[0]))).convert("RGB")
        elif ext == ".flac":
            pictures = getattr(audio, "pictures", None) or []
            if pictures and pictures[0].data:
                return Image.open(io.BytesIO(pictures[0].data)).convert("RGB")
        elif ext in {".ogg", ".oga", ".opus"}:
            pictures = (getattr(audio, "tags", None) or {}).get("metadata_block_picture") or []
            if pictures:
                picture = Picture(base64.b64decode(str(pictures[0])))
                if picture.data:
                    return Image.open(io.BytesIO(picture.data)).convert("RGB")
    except Exception:
        return None
    return None

class Library:
    def __init__(self, user_id: str): self.user_id = user_id

    @staticmethod
    def _track(row: TrackRecord, include_audio: bool = False, include_cover: bool = False) -> Track:
        return Track(
            row.id,
            row.filename,
            row.title,
            row.artist,
            row.album,
            row.duration,
            row.has_cover,
            row.cover_source,
            row.custom_lyrics,
            bytes(row.audio_data) if include_audio and row.audio_data is not None else b"",
            bytes(row.cover_data) if include_cover and row.cover_data is not None else b"",
            row.cover_path,
            row.cover_url,
        )

    def list_tracks(self):
        with tenant_session(self.user_id) as s:
            selected = [
                TrackRecord.id,
                TrackRecord.filename,
                TrackRecord.title,
                TrackRecord.artist,
                TrackRecord.album,
                TrackRecord.duration,
                TrackRecord.has_cover,
                TrackRecord.cover_source,
                TrackRecord.custom_lyrics,
                TrackRecord.cover_path,
                TrackRecord.cover_url,
            ]
            rows = s.scalars(select(TrackRecord).options(load_only(*selected)).where(TrackRecord.user_id == self.user_id)).all()
            return sorted((self._track(r) for r in rows), key=lambda t: (t.artist.lower(), t.title.lower()))

    def get(self, track_id: str, include_audio: bool = False, include_cover: bool = False):
        with tenant_session(self.user_id) as s:
            selected = [
                TrackRecord.id,
                TrackRecord.filename,
                TrackRecord.title,
                TrackRecord.artist,
                TrackRecord.album,
                TrackRecord.duration,
                TrackRecord.has_cover,
                TrackRecord.cover_source,
                TrackRecord.custom_lyrics,
                TrackRecord.cover_path,
                TrackRecord.cover_url,
            ]
            if include_audio:
                selected.append(TrackRecord.audio_data)
            if include_cover:
                selected.append(TrackRecord.cover_data)
            row = s.scalar(select(TrackRecord).options(load_only(*selected)).where(TrackRecord.id == track_id, TrackRecord.user_id == self.user_id))
            return self._track(row, include_audio=include_audio, include_cover=include_cover) if row else None

    def count_tracks(self) -> int:
        with tenant_session(self.user_id) as s:
            return s.scalar(select(func.count()).select_from(TrackRecord).where(TrackRecord.user_id == self.user_id)) or 0

    def total_bytes(self) -> int:
        with tenant_session(self.user_id) as s:
            return s.scalar(
                select(func.sum(TrackRecord.size_bytes)).where(TrackRecord.user_id == self.user_id)
            ) or 0

    def set_custom_lyrics(self, track_id: str, lyrics: str):
        with tenant_session(self.user_id) as s:
            row = s.get(TrackRecord, {"id": track_id, "user_id": self.user_id})
            if not row:
                return None
            row.custom_lyrics = lyrics
            s.commit()
            return self._track(row)

    def add_upload(
        self,
        filename: str,
        data: BytesLike,
        *,
        quota_bytes: int | None = None,
        max_tracks: int | None = None,
        storage_path_override: str | None = None,
    ):
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(filename)[1], delete=False
            ) as audio_file:
                path = audio_file.name
                audio_file.write(data)
            return self.add_upload_file(
                filename,
                path,
                quota_bytes=quota_bytes,
                max_tracks=max_tracks,
                storage_path_override=storage_path_override,
                legacy_data=data,
            )
        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    log.warning("Could not remove temporary audio file %s", path)

    def add_upload_file(
        self,
        filename: str,
        path: str,
        *,
        quota_bytes: int | None = None,
        max_tracks: int | None = None,
        storage_path_override: str | None = None,
        legacy_data: BytesLike | None = None,
    ):
        safe=os.path.basename(filename.replace("\\","/")).replace("\x00","") or "upload.mp3"
        if os.path.splitext(safe)[1].lower() not in AUDIO_EXTENSIONS:return None
        track_id=track_id_for_file(path)
        size_bytes=os.path.getsize(path)
        with tenant_session(self.user_id) as s:
            old=s.get(TrackRecord,{"id":track_id,"user_id":self.user_id})
            if old:return self._track(old)
        meta=self._read_metadata_path(safe,path)
        if not meta:return None
        title,artist,album,duration,cover,has_cover=meta
        try:
            cover.thumbnail((600,600), Image.Resampling.LANCZOS)
            output=io.BytesIO()
            cover.save(output,format="JPEG",quality=90)
        except Exception:
            if not has_cover:
                raise
            log.warning("Could not encode cover for %r by %r; using placeholder", title, artist, exc_info=True)
            has_cover=False
            output=io.BytesIO()
            make_placeholder_cover(title).save(output,format="JPEG",quality=90)
        storage_path=None
        cover_path=None
        if storage_path_override:
            storage_path = storage_path_override
        elif audio_store.enabled():
            # Audio goes to Supabase Storage; Postgres keeps only the object path.
            storage_path=audio_store.object_path(self.user_id,track_id,safe)
            audio_store.upload_file(storage_path,path,audio_store.guess_content_type(safe))
        try:
            if has_cover and audio_store.enabled():
                cover_path = audio_store.cover_object_path(self.user_id, track_id)
                audio_store.upload(cover_path, output.getvalue(), "image/jpeg")
        except Exception:
            if storage_path and not storage_path_override:
                audio_store.delete_quietly(storage_path)
            raise
        if not storage_path and legacy_data is None:
            with open(path, "rb") as audio_file:
                legacy_data = audio_file.read()
        row=TrackRecord(id=track_id,user_id=self.user_id,filename=safe,title=title,artist=artist,album=album,duration=duration,has_cover=has_cover,cover_source="embedded" if has_cover else "generated",cover_url=None,audio_data=None if storage_path else legacy_data,storage_path=storage_path,size_bytes=size_bytes,cover_data=None if cover_path else output.getvalue(),cover_path=cover_path)
        try:
            with tenant_session(self.user_id) as s:
                if s.bind.dialect.name == "postgresql":
                    # Serialize quota checks for this account across workers.
                    s.get(User, self.user_id, with_for_update=True)
                if quota_bytes is not None or max_tracks is not None:
                    current_bytes = s.scalar(
                        select(func.coalesce(func.sum(TrackRecord.size_bytes), 0)).where(
                            TrackRecord.user_id == self.user_id
                        )
                    ) or 0
                    current_count = s.scalar(
                        select(func.count()).select_from(TrackRecord).where(
                            TrackRecord.user_id == self.user_id
                        )
                    ) or 0
                    if (
                        quota_bytes is not None and current_bytes + size_bytes > quota_bytes
                    ) or (
                        max_tracks is not None and current_count >= max_tracks
                    ):
                        raise UploadQuotaExceeded()
                s.add(row)
                s.commit()
                return self._track(row)
        except Exception:
            # Don't leave an orphaned object behind — unless a concurrent upload of
            # the same file already owns it (or we can't tell).
            try:
                with tenant_session(self.user_id) as s:still_used=s.get(TrackRecord,{"id":track_id,"user_id":self.user_id}) is not None
            except Exception:still_used=True
            if not still_used:
                if not storage_path_override:
                    audio_store.delete_quietly(storage_path)
                audio_store.delete_quietly(cover_path)
            raise

    def remove(self, track_id: str):
        from db import Favorite, Playlist, PlaylistTrack
        with tenant_session(self.user_id) as s:
            row=s.get(TrackRecord,{"id":track_id,"user_id":self.user_id})
            if not row:return False
            storage_path=row.storage_path
            cover_path=row.cover_path
            s.delete(row)
            s.query(Favorite).filter_by(user_id=self.user_id,track_id=track_id).delete()
            owned_playlist_ids = s.scalars(select(Playlist.id).where(Playlist.user_id == self.user_id)).all()
            if owned_playlist_ids:
                s.query(PlaylistTrack).filter(
                    PlaylistTrack.playlist_id.in_(owned_playlist_ids),
                    PlaylistTrack.track_id == track_id,
                ).delete(synchronize_session=False)
            s.commit()
        audio_store.delete_quietly(storage_path)
        audio_store.delete_quietly(cover_path)
        return True

    def cover_storage_path(self, track_id: str) -> str | None:
        with tenant_session(self.user_id) as s:
            return s.scalar(
                select(TrackRecord.cover_path).where(
                    TrackRecord.id == track_id,
                    TrackRecord.user_id == self.user_id,
                )
            )

    def _delete_unreferenced_cover(self, path: str | None) -> None:
        if not path:
            return
        with tenant_session(self.user_id) as s:
            referenced = s.scalar(
                select(TrackRecord.id)
                .where(
                    TrackRecord.user_id == self.user_id,
                    TrackRecord.cover_path == path,
                )
                .limit(1)
            )
        if not referenced:
            audio_store.delete_quietly(path)

    def cover_bytes(self, track_id: str):
        with tenant_session(self.user_id) as s:
            row = s.execute(
                select(TrackRecord.cover_data).where(TrackRecord.id == track_id, TrackRecord.user_id == self.user_id)
            ).scalar_one_or_none()
            return bytes(row) if row is not None else b""

    def cover_jpeg(self, track_id: str, size: int=512):
        with tenant_session(self.user_id) as s:
            row = s.execute(
                select(TrackRecord.cover_data, TrackRecord.title, TrackRecord.cover_source).where(
                    TrackRecord.id == track_id,
                    TrackRecord.user_id == self.user_id,
                )
            ).one_or_none()
        if row is None:
            return b""
        cover_data, title, cover_source = row
        if cover_source in {"unknown", "generated", "placeholder", None} or not cover_data:
            image = make_placeholder_cover(title)
        else:
            image = Image.open(io.BytesIO(bytes(cover_data))).convert("RGB")
        image = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90)
        return output.getvalue()

    def set_user_cover(self, track_id: str, cover_data: bytes):
        stored_path = None
        with tenant_session(self.user_id) as s:
            row = s.get(TrackRecord, {"id": track_id, "user_id": self.user_id})
            if row is None:
                return None
            old_path = row.cover_path
            if audio_store.enabled():
                stored_path = audio_store.cover_object_path(self.user_id, track_id)
                audio_store.upload(stored_path, cover_data, "image/jpeg")
            row.cover_data = None if stored_path else cover_data
            row.cover_path = stored_path
            row.has_cover = True
            row.cover_source = "user"
            row.cover_url = None
            s.commit()
            track = self._track(row)
        if old_path != stored_path:
            self._delete_unreferenced_cover(old_path)
        return track

    def set_album_user_cover(
        self, track_id: str, cover_data: bytes, *, replace_user_covers: bool = False
    ) -> int | None:
        old_paths: set[str] = set()
        new_path = None
        with tenant_session(self.user_id) as s:
            track = s.get(TrackRecord, {"id": track_id, "user_id": self.user_id})
            if track is None:
                return None
            if not track.album.strip() or re.fullmatch(
                r"unknown album", track.album.strip(), re.IGNORECASE
            ):
                return 0
            if audio_store.enabled():
                album_key = hashlib.sha256(
                    f"{track.artist.casefold()}\0{track.album.casefold()}".encode("utf-8")
                ).hexdigest()[:24]
                image_key = hashlib.sha256(cover_data).hexdigest()[:16]
                new_path = (
                    f"covers/{self.user_id}/albums/{album_key}-{image_key}.jpg"
                )
                audio_store.upload(new_path, cover_data, "image/jpeg")
            old_paths = set(s.scalars(
                select(TrackRecord.cover_path).where(
                    TrackRecord.user_id == self.user_id,
                    TrackRecord.artist == track.artist,
                    TrackRecord.album == track.album,
                    TrackRecord.cover_path.is_not(None),
                )
            ).all())
            statement = update(TrackRecord).where(
                TrackRecord.user_id == self.user_id,
                TrackRecord.artist == track.artist,
                TrackRecord.album == track.album,
            )
            if not replace_user_covers:
                statement = statement.where(TrackRecord.cover_source != "user")
            result = s.execute(statement.values(
                cover_data=None if new_path else cover_data,
                cover_path=new_path,
                has_cover=True,
                cover_source="user",
                cover_url=None,
            ))
            s.commit()
            updated_count = result.rowcount
        for old_path in old_paths:
            if old_path != new_path:
                self._delete_unreferenced_cover(old_path)
        if not updated_count and new_path:
            audio_store.delete_quietly(new_path)
        return updated_count

    def remove_user_cover(self, track_id: str):
        try:
            audio, filename = self.audio_bytes(track_id)
        except AudioUnavailableError:
            audio, filename = b"", None
        embedded_cover = None
        if audio and filename:
            path = None
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(filename)[1], delete=False
                ) as audio_file:
                    path = audio_file.name
                    audio_file.write(audio)
                embedded_cover = _extract_cover(
                    path, os.path.splitext(filename)[1].lower()
                )
            finally:
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        log.warning("Could not remove temporary audio file %s", path)

        with tenant_session(self.user_id) as s:
            row = s.get(TrackRecord, {"id": track_id, "user_id": self.user_id})
            if row is None:
                return None
            if embedded_cover is not None:
                embedded_cover.thumbnail((600, 600), Image.Resampling.LANCZOS)
                image = embedded_cover.convert("RGB")
                row.has_cover = True
                row.cover_source = "embedded"
            else:
                image = make_placeholder_cover(row.title)
                row.has_cover = False
                row.cover_source = "placeholder"
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=90)
            old_path = row.cover_path
            new_path = None
            if embedded_cover is not None and audio_store.enabled():
                new_path = audio_store.cover_object_path(self.user_id, track_id)
                audio_store.upload(new_path, output.getvalue(), "image/jpeg")
            row.cover_path = new_path
            row.cover_data = None if new_path else output.getvalue()
            row.cover_url = None
            s.commit()
            track = self._track(row)
        if old_path != new_path:
            self._delete_unreferenced_cover(old_path)
        return track

    def update_metadata(self, track_id: str, title: str, artist: str, album: str):
        with tenant_session(self.user_id) as s:
            row = s.get(TrackRecord, {"id": track_id, "user_id": self.user_id})
            if row is None:
                return None
            row.title = title
            row.artist = artist
            row.album = album
            s.commit()
            return self._track(row)

    def audio_info(self, track_id: str):
        """``(filename, size_bytes, storage_path)`` or None — never touches the audio itself."""
        with tenant_session(self.user_id) as s:
            return s.execute(
                select(TrackRecord.filename, TrackRecord.size_bytes, TrackRecord.storage_path).where(
                    TrackRecord.id == track_id,
                    TrackRecord.user_id == self.user_id,
                )
            ).one_or_none()

    def storage_paths(self) -> list[str]:
        """Every Storage object this user owns (used when deleting an account)."""
        with tenant_session(self.user_id) as s:
            return list(s.scalars(select(TrackRecord.storage_path).where(
                TrackRecord.user_id == self.user_id, TrackRecord.storage_path.is_not(None))).all())

    def read_range(self, track_id: str, start: int, end: int, info=None):
        """Bytes ``start..end`` (inclusive) of a track, fetching only that slice.

        Storage-backed tracks do a ranged request; legacy tracks whose audio is
        still in Postgres use ``substr`` so the database sends just the slice.
        """
        if info is None:
            info = self.audio_info(track_id)
        if info is None:
            return None
        if info.storage_path:
            return audio_store.read_range(info.storage_path, start, end)
        with tenant_session(self.user_id) as s:
            data = s.scalar(
                select(func.substr(TrackRecord.audio_data, start + 1, end - start + 1)).where(
                    TrackRecord.id == track_id,
                    TrackRecord.user_id == self.user_id,
                )
            )
        if data is None:
            raise AudioUnavailableError(f"Track {track_id} has no audio in Storage or the database.")
        return bytes(data)

    def audio_bytes(self, track_id: str, max_bytes: int | None = None):
        """``(data, filename)``.  Prefer :meth:`read_range`; this reads the whole file when ``max_bytes`` is None."""
        info = self.audio_info(track_id)
        if info is None:
            return None, None
        filename, size, path = info.filename, info.size_bytes, info.storage_path
        if max_bytes is not None:
            if max_bytes <= 0:
                return b"", filename
            end = max_bytes - 1
            if path and size:
                end = min(end, size - 1)
            return self.read_range(track_id, 0, end), filename
        if path:
            return audio_store.read_range(path, 0, max(size - 1, 0)), filename
        with tenant_session(self.user_id) as s:
            data = s.scalar(select(TrackRecord.audio_data).where(
                TrackRecord.id == track_id, TrackRecord.user_id == self.user_id))
        if data is None:
            raise AudioUnavailableError(f"Track {track_id} has no audio in Storage or the database.")
        return bytes(data), filename

    def embedded_cover(self, track_id: str) -> bytes | None:
        info = self.audio_info(track_id)
        if info is None:
            return None
        filename, size, storage_path = info
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(filename)[1], delete=False
            ) as audio_file:
                path = audio_file.name
                if storage_path:
                    audio_store.download_to_file(storage_path, path, size)
                else:
                    with tenant_session(self.user_id) as session:
                        offset = 0
                        while offset < size:
                            chunk = session.scalar(
                                select(func.substr(TrackRecord.audio_data, offset + 1, 64 * 1024)).where(
                                    TrackRecord.user_id == self.user_id,
                                    TrackRecord.id == track_id,
                                )
                            )
                            if not chunk:
                                break
                            audio_file.write(bytes(chunk))
                            offset += len(chunk)
            from cover_art import embedded_cover

            return embedded_cover(path)
        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    log.warning("Could not remove temporary audio file %s", path)

    def set_resolved_cover(
        self,
        track_id: str,
        source: str,
        image: bytes | None = None,
        url: str | None = None,
    ) -> bool:
        if source not in {"upload", "embedded", "musicbrainz", "audiodb", "generated"}:
            raise ValueError("unsupported resolved cover source")
        stored_path = None
        old_path = None
        with tenant_session(self.user_id) as session:
            row = session.get(TrackRecord, {"id": track_id, "user_id": self.user_id})
            if row is None:
                return False
            old_path = row.cover_path
            if source != "upload" and row.cover_source in {"upload", "user"}:
                return False
            if source not in {"upload", "embedded"} and row.cover_source == "embedded":
                return False
            if source in {"upload", "embedded", "generated"}:
                if not image:
                    raise ValueError("cover image is required")
                if source != "generated" and audio_store.enabled():
                    stored_path = audio_store.cover_object_path(self.user_id, track_id)
                    audio_store.upload(stored_path, image, "image/jpeg")
                elif source == "generated" and audio_store.enabled():
                    # Generated art stays in Postgres / is regenerated on demand;
                    # avoid filling Storage with placeholders.
                    stored_path = None
                row.cover_data = None if stored_path else image
                row.cover_path = stored_path
                row.has_cover = source != "generated"
                row.cover_url = None
            elif source in {"musicbrainz", "audiodb"}:
                if not url:
                    raise ValueError("remote cover URL is required")
                row.cover_data = None
                row.cover_path = None
                row.has_cover = False
                row.cover_url = url
            else:
                raise ValueError("unsupported resolved cover source")
            row.cover_source = source
            session.commit()
        if old_path != stored_path:
            self._delete_unreferenced_cover(old_path)
        return True

    def _read_metadata(self, filename, data: BytesLike):
        title,artist=_parse_filename(filename);album="Unknown Album";duration=0.;cover=make_placeholder_cover(title);has_cover=False
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1],delete=False) as f:path=f.name;f.write(data)
        try:
            return self._read_metadata_path(filename, path)
        finally:
            try:os.unlink(path)
            except OSError:pass

    def _read_metadata_path(self, filename, path: str):
        title,artist=_parse_filename(filename);album="Unknown Album";duration=0.;cover=make_placeholder_cover(title);has_cover=False
        if MUTAGEN_AVAILABLE:
            try:
                audio=MutagenFile(path,easy=True)
                if audio is None:return None
                duration=float(getattr(getattr(audio,"info",None),"length",0) or 0);tags=getattr(audio,"tags",None) or {}
                title=_clean_title(_tag_text(tags.get("title"), title))
                artist=_tag_text(tags.get("artist"), artist, join_values=True)
                album=_tag_text(tags.get("album"), album)
            except Exception:return None
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".mp3":
                try: duration=float(MP3(path).info.length or duration)
                except Exception: pass
            embedded = _extract_cover(path, ext)
        else:
            embedded = None
        if embedded is not None:
            cover = embedded
            has_cover = True
        return title,artist,album,duration,cover,has_cover
