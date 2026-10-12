"""Rebuild unknown track covers from user-uploaded audio tags."""

from __future__ import annotations

import argparse
import io
import os
import tempfile

from PIL import Image
from sqlalchemy import select

import audio_store
from db import SessionLocal, TrackRecord, User, tenant_session
from library import AudioUnavailableError, Library, _extract_cover, make_placeholder_cover


def _jpeg_bytes(image: Image.Image) -> bytes:
    image = image.convert("RGB")
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def _embedded_cover(filename: str, audio: bytes) -> Image.Image | None:
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(filename)[1], delete=False
        ) as audio_file:
            path = audio_file.name
            audio_file.write(audio)
        return _extract_cover(path, os.path.splitext(filename)[1].lower())
    finally:
        if path:
            os.unlink(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write rebuilt covers (default is a dry run)",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        user_ids = session.scalars(select(User.id).order_by(User.id)).all()

    processed = embedded = placeholders = updated = 0
    for user_id in user_ids:
        last_id = ""
        while True:
            with tenant_session(user_id) as session:
                row = session.execute(
                    select(
                        TrackRecord.id,
                        TrackRecord.filename,
                        TrackRecord.title,
                    ).where(
                        TrackRecord.user_id == user_id,
                        TrackRecord.id > last_id,
                        TrackRecord.cover_source == "unknown",
                    ).order_by(TrackRecord.id).limit(1)
                ).one_or_none()
            if row is None:
                break

            track_id, filename, title = row
            last_id = track_id
            processed += 1
            try:
                audio, audio_filename = Library(user_id).audio_bytes(track_id)
            except AudioUnavailableError:
                audio, audio_filename = b"", filename
            image = _embedded_cover(audio_filename or filename, audio) if audio else None
            source = "embedded" if image is not None else "placeholder"
            if image is None:
                image = make_placeholder_cover(title)
                placeholders += 1
            else:
                embedded += 1

            cover_data = _jpeg_bytes(image)
            if args.apply:
                with tenant_session(user_id) as session:
                    changed = session.execute(
                        select(TrackRecord).where(
                            TrackRecord.id == track_id,
                            TrackRecord.user_id == user_id,
                            TrackRecord.cover_source == "unknown",
                        )
                    ).scalar_one_or_none()
                    if changed is not None:
                        changed.cover_data = cover_data
                        changed.has_cover = source == "embedded"
                        changed.cover_source = source
                        session.commit()
                        updated += 1
            print(f"{track_id}: {source}" + ("" if args.apply else " (dry run)"))

    print(
        f"Processed {processed}; embedded {embedded}; placeholders {placeholders}; "
        f"written {updated}."
    )
    audio_store.close_client()


if __name__ == "__main__":
    main()
