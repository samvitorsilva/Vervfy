"""Fetch and store online cover art for existing tracks without embedded covers."""

from __future__ import annotations

import io
import time

from PIL import Image
from sqlalchemy import or_, select

from db import SessionLocal, TrackRecord, User, tenant_session
from online_cover import fetch_track_metadata

Image.MAX_IMAGE_PIXELS = 25_000_000


def main() -> None:
    with SessionLocal() as session:
        user_ids = session.scalars(select(User.id)).all()

    processed = updated = 0
    for user_id in user_ids:
        with tenant_session(user_id) as session:
            tracks = session.execute(
                select(
                    TrackRecord.id,
                    TrackRecord.title,
                    TrackRecord.artist,
                    TrackRecord.album,
                    TrackRecord.duration,
                ).where(
                    TrackRecord.user_id == user_id,
                    or_(
                        TrackRecord.has_cover.is_(False),
                        TrackRecord.album == "Unknown Album",
                        TrackRecord.duration <= 0,
                    ),
                )
            ).all()

        for track_id, title, artist, album, duration in tracks:
            processed += 1
            metadata = fetch_track_metadata(title, artist, fetch_artwork=True)
            if metadata is not None:
                with tenant_session(user_id) as session:
                    row = session.scalar(
                        select(TrackRecord).where(
                            TrackRecord.id == track_id,
                            TrackRecord.user_id == user_id,
                        )
                    )
                    if row is not None:
                        changed = False
                        if not row.has_cover and metadata.cover is not None:
                            cover = metadata.cover
                            cover.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                            output = io.BytesIO()
                            cover.save(output, format="JPEG", quality=90)
                            row.cover_data = output.getvalue()
                            row.has_cover = True
                            changed = True
                        if row.album == "Unknown Album" and metadata.album:
                            row.album = metadata.album
                            changed = True
                        if row.duration <= 0 and metadata.duration:
                            row.duration = metadata.duration
                            changed = True
                        if changed:
                            session.commit()
                            updated += 1

            if processed % 25 == 0:
                print(f"Processed {processed} tracks; updated {updated} covers.")
            time.sleep(0.2)

    print(f"Finished: processed {processed} tracks; updated {updated} covers.")


if __name__ == "__main__":
    main()
