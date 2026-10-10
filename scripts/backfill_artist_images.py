"""Populate the shared artist portrait cache from existing library tracks."""

from __future__ import annotations

import time

from sqlalchemy import select

from db import SessionLocal, TrackRecord, User, tenant_session
from server import _artist_name_candidates, get_artist_image


def main() -> None:
    with SessionLocal() as session:
        user_ids = session.scalars(select(User.id)).all()

    names: set[str] = set()
    for user_id in user_ids:
        with tenant_session(user_id) as session:
            track_artists = session.scalars(
                select(TrackRecord.artist).where(TrackRecord.user_id == user_id).distinct()
            ).all()
        names.update(
            candidate
            for artist in track_artists
            for candidate in _artist_name_candidates(artist)
            if len(candidate) <= 200
        )
    ordered_names = sorted(names, key=str.casefold)
    print(f"Looking up {len(ordered_names)} distinct artists (maximum 5 requests/second).")
    for index, name in enumerate(ordered_names, start=1):
        get_artist_image(name)
        if index % 50 == 0 or index == len(ordered_names):
            print(f"Processed {index}/{len(ordered_names)} artists.")
        if index < len(ordered_names):
            time.sleep(0.2)


if __name__ == "__main__":
    main()
