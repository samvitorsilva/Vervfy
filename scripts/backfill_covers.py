#!/usr/bin/env python3
"""Re-run the cover chain for tracks missing a durable cover source.

Safe to re-run. Processes one track at a time so MusicBrainz stays at
most 1 request/second.

  BACKFILL_DATABASE_URL=... MB_CONTACT_EMAIL=you@example.com \\
    python scripts/backfill_covers.py

Optional:
  --user-id <uuid>   limit to one account
  --limit <n>        stop after n tracks
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker

from cover_art import resolve_cover
from db import TrackRecord, normalize_database_url

log = logging.getLogger("vervfy.backfill_covers")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=os.environ.get("BACKFILL_USER_ID"))
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ["BACKFILL_LIMIT"]) if os.environ.get("BACKFILL_LIMIT") else None,
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database_url = os.environ.get("BACKFILL_DATABASE_URL", "").strip()
    if not database_url:
        parser.error(
            "Set BACKFILL_DATABASE_URL to a PostgreSQL admin/owner URL that can bypass tracks RLS"
        )
    if not os.environ.get("MB_CONTACT_EMAIL", "").strip():
        log.warning(
            "MB_CONTACT_EMAIL is unset; MusicBrainz lookups will log errors and fall through"
        )

    engine = create_engine(normalize_database_url(database_url), pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        statement = (
            select(TrackRecord.user_id, TrackRecord.id)
            .where(
                or_(
                    TrackRecord.cover_source.is_(None),
                    TrackRecord.cover_source.in_(
                        ("generated", "placeholder", "unknown")
                    ),
                )
            )
            .order_by(TrackRecord.user_id, TrackRecord.id)
        )
        if args.user_id:
            statement = statement.where(TrackRecord.user_id == args.user_id)
        if args.limit is not None:
            statement = statement.limit(args.limit)
        rows = list(session.execute(statement).all())

    log.info("backfill candidates=%s", len(rows))
    for index, (user_id, track_id) in enumerate(rows, start=1):
        log.info(
            "backfill progress=%s/%s track_id=%s user_id=%s",
            index,
            len(rows),
            track_id,
            user_id,
        )
        try:
            asyncio.run(resolve_cover(user_id, track_id, force=True))
        except Exception:
            log.exception(
                "cover lookup track_id=%s step=backfill result=error", track_id
            )
    log.info("backfill complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
