"""Rebuild unknown track covers from user-uploaded audio tags."""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

import audio_store  # noqa: E402
from db import SessionLocal, TrackRecord, User, tenant_session  # noqa: E402
from library import (  # noqa: E402
    AudioUnavailableError,
    Library,
    _extract_cover,
    make_placeholder_cover,
)


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
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="process at most N tracks (0 = all)",
    )
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be 0 or greater")

    with SessionLocal() as session:
        user_ids = session.scalars(select(User.id).order_by(User.id)).all()

    processed = embedded = placeholders = skipped = updated = 0
    skipped_ids = []
    for user_id in user_ids:
        if args.limit and processed >= args.limit:
            break
        last_id = ""
        while True:
            if args.limit and processed >= args.limit:
                break
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
                audio = b""
                audio_filename = filename
            if not audio:
                skipped += 1
                skipped_ids.append(track_id)
                print(f"{track_id}: skipped (audio unavailable or empty)")
                continue

            image = _embedded_cover(audio_filename or filename, audio)
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
        f"skipped {skipped}; written {updated}."
    )
    print(f"Skipped track ids: {', '.join(skipped_ids) if skipped_ids else 'none'}")
    audio_store.close_client()


if __name__ == "__main__":
    main()
