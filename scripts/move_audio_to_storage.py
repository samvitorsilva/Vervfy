#!/usr/bin/env python3
"""Move track audio from Postgres (tracks.audio_data) into Supabase Storage.

Run from the repo root with the same DATABASE_URL Render uses, plus:

    export SUPABASE_URL=https://<project-ref>.supabase.co
    export SUPABASE_SERVICE_KEY=<service_role key>
    export SUPABASE_BUCKET=songs            # optional, default "songs"

Recommended order:

    python scripts/move_audio_to_storage.py --limit 1     # try one song
    python scripts/move_audio_to_storage.py               # copy + verify everything
    ... deploy the new code, check that songs play from Storage ...
    python scripts/move_audio_to_storage.py --free-db --vacuum

Without --free-db the audio stays in Postgres as a safety copy (the app prefers
the Storage copy whenever ``storage_path`` is set).  --free-db empties
``audio_data`` only for rows whose Storage copy was re-verified in this run.
--vacuum then runs VACUUM FULL so the dashboard's database size actually drops.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, select, text  # noqa: E402

import audio_store  # noqa: E402
from db import SessionLocal, TrackRecord, engine  # noqa: E402


def ensure_schema() -> None:
    """Same idempotent schema changes as the app's startup shim / Alembic 0005."""
    columns = {c["name"] for c in inspect(engine).get_columns("tracks")}
    with engine.begin() as conn:
        if "storage_path" not in columns:
            conn.execute(text("ALTER TABLE tracks ADD COLUMN storage_path VARCHAR(600)"))
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE tracks ALTER COLUMN audio_data DROP NOT NULL"))


def verify(path: str, data: bytes) -> bool:
    """Size matches and the first/last 16 bytes read back identical."""
    if audio_store.object_size(path) != len(data):
        return False
    n = min(16, len(data))
    if audio_store.read_range(path, 0, n - 1) != data[:n]:
        return False
    return audio_store.read_range(path, len(data) - n, len(data) - 1) == data[-n:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--free-db", action="store_true", help="empty audio_data for rows verified in Storage")
    parser.add_argument("--vacuum", action="store_true", help="run VACUUM FULL tracks afterwards (Postgres)")
    parser.add_argument("--limit", type=int, default=0, help="process at most N tracks (0 = all)")
    args = parser.parse_args()

    if not audio_store.enabled():
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY first.", file=sys.stderr)
        return 2
    if not audio_store.bucket_exists():
        print("Bucket not found. Create a PRIVATE bucket named "
              f"'{audio_store._settings()[2]}' in Supabase > Storage first.", file=sys.stderr)
        return 2
    ensure_schema()

    with SessionLocal() as s:
        todo = s.execute(
            select(TrackRecord.id, TrackRecord.user_id, TrackRecord.filename, TrackRecord.storage_path)
            .where(TrackRecord.audio_data.is_not(None))
            .order_by(TrackRecord.user_id, TrackRecord.id)
        ).all()
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} track(s) still have audio in Postgres.")

    failures = moved = freed = 0
    for row in todo:
        label = f"{row.filename} ({row.id})"
        try:
            with SessionLocal() as s:
                data = s.scalar(select(TrackRecord.audio_data).where(
                    TrackRecord.id == row.id, TrackRecord.user_id == row.user_id))
            data = bytes(data or b"")
            if not data:
                print(f"  skip  {label}: empty audio_data")
                continue
            path = row.storage_path or audio_store.object_path(row.user_id, row.id, row.filename)
            if not row.storage_path:
                audio_store.upload(path, data, audio_store.guess_content_type(row.filename))
            if not verify(path, data):
                raise RuntimeError("verification failed (size or content mismatch)")
            with SessionLocal() as s:
                record = s.get(TrackRecord, {"id": row.id, "user_id": row.user_id})
                record.storage_path = path
                record.size_bytes = len(data)
                if args.free_db:
                    record.audio_data = None
                s.commit()
            moved += 1
            freed += len(data) if args.free_db else 0
            print(f"  ok    {label}  {len(data) / 1e6:.1f} MB -> {path}" + ("  (db copy removed)" if args.free_db else ""))
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            failures += 1
            print(f"  FAIL  {label}: {exc}", file=sys.stderr)

    print(f"\nDone: {moved} verified, {failures} failed" + (f", {freed / 1e6:.1f} MB removed from Postgres." if args.free_db else "."))
    if args.vacuum and args.free_db and engine.dialect.name == "postgresql":
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.exec_driver_sql("VACUUM FULL tracks")
            print("VACUUM FULL tracks finished — check the database size in the Supabase dashboard.")
        except Exception as exc:  # noqa: BLE001
            print(f"VACUUM FULL failed ({exc}). Run it yourself in psql / the SQL editor: VACUUM FULL tracks;", file=sys.stderr)
    elif args.free_db:
        print("Now run  VACUUM FULL tracks;  so the freed space is returned to Supabase (or rerun with --vacuum).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
