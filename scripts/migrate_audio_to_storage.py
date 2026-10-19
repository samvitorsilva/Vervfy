#!/usr/bin/env python3
"""Move legacy track audio from Postgres into the private Supabase Storage bucket.

Set MIGRATION_DATABASE_URL to the PostgreSQL admin/owner connection string,
plus SUPABASE_URL and SUPABASE_SERVICE_KEY. The script uploads and verifies
each audio object, commits its storage_path, then clears audio_data.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audio_store


def _database():
    database_url = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "MIGRATION_DATABASE_URL must be set to a PostgreSQL admin/owner URL "
            "that can bypass tracks RLS"
        )
    os.environ["DATABASE_URL"] = database_url
    from db import SessionLocal, TrackRecord, engine
    from sqlalchemy import select, tuple_, update

    if engine.dialect.name != "postgresql":
        raise RuntimeError("MIGRATION_DATABASE_URL must use PostgreSQL")
    return SessionLocal, TrackRecord, engine, select, tuple_, update


def _verify(path: str, data: bytes) -> bool:
    if audio_store.object_size(path) != len(data):
        return False
    sample_size = min(16, len(data))
    return (
        audio_store.read_range(path, 0, sample_size - 1) == data[:sample_size]
        and audio_store.read_range(
            path, len(data) - sample_size, len(data) - 1
        )
        == data[-sample_size:]
    )


def _upload_with_retries(path: str, data: bytes, content_type: str) -> None:
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            audio_store.upload(path, data, content_type)
            if not _verify(path, data):
                raise RuntimeError("Storage verification failed")
            return
        except Exception as exc:
            if attempt == attempts:
                raise RuntimeError(
                    f"upload/verification failed after {attempts} attempts: {exc}"
                ) from exc
            delay = attempt
            print(
                f"  retry {attempt}/{attempts - 1} in {delay}s: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list eligible tracks without reading, uploading, or changing audio",
    )
    args = parser.parse_args()

    if not args.dry_run:
        if not audio_store.enabled():
            parser.error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        if not audio_store.bucket_exists():
            parser.error(
                "Supabase Storage bucket was not found. Create a private bucket named "
                f"'{audio_store._settings()[2]}' first."
            )

    try:
        SessionLocal, TrackRecord, engine, select, tuple_, update = _database()
    except RuntimeError as exc:
        parser.error(str(exc))

    moved = failed = skipped = 0
    last_key: tuple[str, str] | None = None
    try:
        while True:
            with SessionLocal() as session:
                query = select(
                    TrackRecord.user_id,
                    TrackRecord.id,
                    TrackRecord.filename,
                    TrackRecord.storage_path,
                ).where(TrackRecord.audio_data.is_not(None))
                if last_key is not None:
                    query = query.where(
                        tuple_(TrackRecord.user_id, TrackRecord.id)
                        > tuple_(*last_key)
                    )
                row = session.execute(
                    query.order_by(TrackRecord.user_id, TrackRecord.id).limit(1)
                ).one_or_none()

            if row is None:
                break
            user_id, track_id, filename, existing_path = row
            last_key = (user_id, track_id)
            label = f"{filename} ({track_id})"

            if args.dry_run:
                target = existing_path or f"{user_id}/{track_id}.mp3"
                print(f"  would migrate {label} -> {target}")
                moved += 1
                continue

            data: bytes | None = None
            try:
                with SessionLocal() as session:
                    stored_audio = session.scalar(
                        select(TrackRecord.audio_data).where(
                            TrackRecord.user_id == user_id,
                            TrackRecord.id == track_id,
                            TrackRecord.audio_data.is_not(None),
                        )
                    )
                if stored_audio is None:
                    print(f"  skip {label}: audio_data was already cleared")
                    skipped += 1
                    continue
                data = bytes(stored_audio)
                del stored_audio
                if not data:
                    print(f"  skip {label}: audio_data is empty", file=sys.stderr)
                    skipped += 1
                    continue

                path = existing_path or f"{user_id}/{track_id}.mp3"
                _upload_with_retries(
                    path, data, audio_store.guess_content_type(filename)
                )

                with SessionLocal() as session:
                    session.execute(
                        update(TrackRecord)
                        .where(
                            TrackRecord.user_id == user_id,
                            TrackRecord.id == track_id,
                        )
                        .values(storage_path=path, size_bytes=len(data))
                    )
                    session.commit()

                with SessionLocal() as session:
                    result = session.execute(
                        update(TrackRecord)
                        .where(
                            TrackRecord.user_id == user_id,
                            TrackRecord.id == track_id,
                            TrackRecord.storage_path == path,
                            TrackRecord.audio_data.is_not(None),
                        )
                        .values(audio_data=None)
                    )
                    session.commit()
                if result.rowcount != 1:
                    raise RuntimeError(
                        "Storage path was saved but audio_data was not cleared; "
                        "the database copy was kept"
                    )
                print(f"  ok {label} ({len(data) / 1_000_000:.1f} MB) -> {path}")
                moved += 1
            except Exception as exc:
                failed += 1
                print(
                    f"  FAIL {label}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            finally:
                data = None
    finally:
        engine.dispose()

    print(
        f"Done: {moved} {'would be migrated' if args.dry_run else 'migrated'}, "
        f"{skipped} skipped, {failed} failed."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
