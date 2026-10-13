#!/usr/bin/env python3
"""Move existing embedded and custom track images into private Supabase Storage."""
from __future__ import annotations

import argparse
from io import BytesIO
import os
import tempfile

from PIL import Image, ImageOps
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

import audio_store
from db import TrackRecord, normalize_database_url
from library import _extract_cover


def _normalized_jpeg(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    image.thumbnail((600, 600), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def _extract_legacy_cover(
    session, user_id: str, track_id: str, filename: str, storage_path: str | None, size: int
) -> bytes | None:
    if storage_path:
        audio = audio_store.read_all(storage_path, size)
    else:
        audio = session.scalar(
            select(TrackRecord.audio_data).where(
                TrackRecord.user_id == user_id,
                TrackRecord.id == track_id,
            )
        )
        audio = bytes(audio) if audio is not None else b""
    if not audio:
        return None

    path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(filename)[1], delete=False
        ) as audio_file:
            path = audio_file.name
            audio_file.write(audio)
        image = _extract_cover(path, os.path.splitext(filename)[1].lower())
        if image is None:
            return None
        image.thumbnail((600, 600), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue()
    finally:
        if path:
            os.unlink(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 100:
        parser.error("--batch-size must be between 1 and 100")
    if not audio_store.enabled():
        parser.error("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    database_url = os.environ.get("BACKFILL_DATABASE_URL", "").strip()
    if not database_url:
        parser.error(
            "Set BACKFILL_DATABASE_URL to a PostgreSQL admin/owner URL that can bypass tracks RLS"
        )

    engine = create_engine(normalize_database_url(database_url), pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        candidates = session.execute(
            select(
                TrackRecord.user_id,
                TrackRecord.id,
                TrackRecord.cover_source,
                TrackRecord.filename,
                TrackRecord.storage_path,
                TrackRecord.size_bytes,
            )
            .where(
                TrackRecord.cover_path.is_(None),
                TrackRecord.cover_source.in_(("embedded", "user")),
            )
            .order_by(TrackRecord.user_id, TrackRecord.id)
        ).all()

        completed = 0
        skipped = 0
        for batch_start in range(0, len(candidates), args.batch_size):
            batch = candidates[batch_start : batch_start + args.batch_size]
            for user_id, track_id, source, filename, storage_path, size in batch:
                locked = session.execute(
                    select(TrackRecord.cover_source)
                    .where(
                        TrackRecord.user_id == user_id,
                        TrackRecord.id == track_id,
                        TrackRecord.cover_path.is_(None),
                        TrackRecord.cover_source == source,
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if locked is None:
                    skipped += 1
                    continue
                cover = session.scalar(
                    select(TrackRecord.cover_data).where(
                        TrackRecord.user_id == user_id,
                        TrackRecord.id == track_id,
                    )
                )
                if cover is not None:
                    cover_data = _normalized_jpeg(bytes(cover))
                elif source == "embedded":
                    cover_data = _extract_legacy_cover(
                        session,
                        user_id,
                        track_id,
                        filename,
                        storage_path,
                        size,
                    )
                else:
                    cover_data = None
                if not cover_data:
                    print(f"Skipped {track_id}: no readable existing cover")
                    skipped += 1
                    continue

                path = audio_store.cover_object_path(user_id, track_id)
                audio_store.upload(path, cover_data, "image/jpeg")
                result = session.execute(
                    update(TrackRecord)
                    .where(
                        TrackRecord.user_id == user_id,
                        TrackRecord.id == track_id,
                        TrackRecord.cover_path.is_(None),
                        TrackRecord.cover_source == source,
                    )
                    .values(cover_path=path, cover_data=None)
                )
                session.commit()
                if result.rowcount != 1:
                    skipped += 1
                    continue
                completed += 1
            print(f"Processed batch {batch_start // args.batch_size + 1}")

    engine.dispose()
    print(f"Moved {completed} covers; skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
