"""PostgreSQL-backed music library; no durable data is written to disk."""
from __future__ import annotations
import base64, hashlib, io, logging, os, re, tempfile
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont, ImageOps
from sqlalchemy import func, select
from sqlalchemy.orm import load_only
import audio_store
from db import TrackRecord, User, tenant_session

Image.MAX_IMAGE_PIXELS = int(os.environ.get("VERVFY_MAX_IMAGE_PIXELS", "25000000"))
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
    id: str; filename: str; title: str; artist: str; album: str; duration: float; has_cover: bool; custom_lyrics: str | None; audio_data: bytes; cover_data: bytes


class UploadQuotaExceeded(RuntimeError):
    """Raised when an upload no longer fits the account quota at commit time."""


class AudioUnavailableError(RuntimeError):
    """A track has neither a Storage object nor a legacy database audio blob."""


def track_id_for_bytes(data: BytesLike) -> str:
    size, sample_size = len(data), 65536; digest = hashlib.sha1(str(size).encode()); digest.update(data[:sample_size])
    if size > sample_size: digest.update(data[-sample_size:])
    return digest.hexdigest()[:16]

def make_placeholder_cover(title: str, size: int = 512) -> Image.Image:
    seed = sum(map(ord, title)) or 1; image = Image.new("RGB", (size, size), ((seed*47)%180, 55, 90)); draw = ImageDraw.Draw(image)
    try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size*.42))
    except Exception: font = ImageFont.load_default()
    letter = (title.strip()[:1] or "?").upper(); box = draw.textbbox((0, 0), letter, font=font)
    draw.text((size/2-(box[2]-box[0])/2, size/2-(box[3]-box[1])/2), letter, font=font, fill=(220, 245, 245)); return image

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
    stem = re.sub(r"\s+", " ", stem.replace("_", " ")).strip()
    parts = [part.strip() for part in re.split(r"\s[-–—]\s", stem) if part.strip()]
    topic = len(parts) > 2 and parts[-1].lower() == "topic"
    if topic:
        parts.pop()
        return (_strip_noise(" - ".join(parts[:-1])) or parts[0]), parts[-1]
    if len(parts) < 2:
        return (_strip_noise(stem) or stem), "Unknown Artist"

    first, second = parts[0], parts[1]
    if _is_channel(second) or (_strip_noise(first) != first and _strip_noise(second) == second):
        artist = _channel_to_artist(second) if _is_channel(second) else second
        title = first
    else:
        artist, rest = (_channel_to_artist(first) if _is_channel(first) else first), parts[1:]
        if len(rest) > 1 and (_is_channel(rest[-1]) or _squash(rest[-1]) == _squash(artist)):
            rest = rest[:-1]
        title = " - ".join(rest)
    return (_strip_noise(title) or title), artist

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
            row.custom_lyrics,
            bytes(row.audio_data) if include_audio and row.audio_data is not None else b"",
            bytes(row.cover_data) if include_cover and row.cover_data is not None else b"",
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
                TrackRecord.custom_lyrics,
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
                TrackRecord.custom_lyrics,
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
        safe=os.path.basename(filename.replace("\\","/")).replace("\x00","") or "upload.mp3"
        if os.path.splitext(safe)[1].lower() not in AUDIO_EXTENSIONS:return None
        track_id=track_id_for_bytes(data)
        with tenant_session(self.user_id) as s:
            old=s.get(TrackRecord,{"id":track_id,"user_id":self.user_id})
            if old:return self._track(old)
        meta=self._read_metadata(safe,data)
        if not meta:return None
        title,artist,album,duration,cover,has_cover=meta; cover.thumbnail((1024,1024), Image.LANCZOS); output=io.BytesIO();cover.save(output,format="JPEG",quality=90)
        storage_path=None
        if storage_path_override:
            storage_path = storage_path_override
        elif audio_store.enabled():
            # Audio goes to Supabase Storage; Postgres keeps only the object path.
            storage_path=audio_store.object_path(self.user_id,track_id,safe)
            audio_store.upload(storage_path,data,audio_store.guess_content_type(safe))
        row=TrackRecord(id=track_id,user_id=self.user_id,filename=safe,title=title,artist=artist,album=album,duration=duration,has_cover=has_cover,audio_data=None if storage_path else data,storage_path=storage_path,size_bytes=len(data),cover_data=output.getvalue())
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
                        quota_bytes is not None and current_bytes + len(data) > quota_bytes
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
            if not still_used and not storage_path_override:
                audio_store.delete_quietly(storage_path)
            raise

    def remove(self, track_id: str):
        from db import Favorite, Playlist, PlaylistTrack
        with tenant_session(self.user_id) as s:
            row=s.get(TrackRecord,{"id":track_id,"user_id":self.user_id})
            if not row:return False
            storage_path=row.storage_path
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
        return True

    def cover_bytes(self, track_id: str):
        with tenant_session(self.user_id) as s:
            row = s.execute(
                select(TrackRecord.cover_data).where(TrackRecord.id == track_id, TrackRecord.user_id == self.user_id)
            ).scalar_one_or_none()
            return bytes(row) if row is not None else b""

    def cover_jpeg(self, track_id: str, size: int=512):
        cover_data = self.cover_bytes(track_id)
        if not cover_data:
            return b""
        image=Image.open(io.BytesIO(cover_data)).convert("RGB"); image=ImageOps.fit(image,(size,size),method=Image.LANCZOS);out=io.BytesIO();image.save(out,format="JPEG",quality=90);return out.getvalue()

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

    def _read_metadata(self, filename, data: BytesLike):
        title,artist=_parse_filename(filename);album="Unknown Album";duration=0.;cover=make_placeholder_cover(title);has_cover=False
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1],delete=False) as f:path=f.name;f.write(data)
        try:
            if MUTAGEN_AVAILABLE:
                try:
                    audio=MutagenFile(path,easy=True)
                    if audio is None:return None
                    duration=float(getattr(getattr(audio,"info",None),"length",0) or 0);tags=getattr(audio,"tags",None) or {}
                    title=_tag_text(tags.get("title"), title)
                    artist=_tag_text(tags.get("artist"), artist, join_values=True)
                    album=_tag_text(tags.get("album"), album)
                except Exception:return None
                ext = os.path.splitext(filename)[1].lower()
                if ext == ".mp3":
                    try: duration=float(MP3(path).info.length or duration)
                    except Exception: pass
                embedded_cover = _extract_cover(path, ext)
                if embedded_cover is not None:
                    cover = embedded_cover
                    has_cover = True
            return title,artist,album,duration,cover,has_cover
        finally:
            try:os.unlink(path)
            except OSError:pass
