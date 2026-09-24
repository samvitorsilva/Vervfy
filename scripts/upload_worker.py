#!/usr/bin/env python3
"""Process staged uploads: python scripts/upload_worker.py."""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audio_store
import upload_queue
from db import SessionLocal, UploadJob
from library import Library, UploadQuotaExceeded
from sqlalchemy import select

log = logging.getLogger("vervfy.upload_worker")
MAX_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))


def process(job_id: str) -> None:
    with SessionLocal() as session:
        job = session.scalar(select(UploadJob).where(UploadJob.id == job_id))
        if not job or job.status not in {"pending", "processing"}:
            return
        job.status = "processing"
        session.commit()
        filename, user_id, path = job.filename, job.user_id, job.storage_path
    try:
        size = audio_store.object_size(path)
        if size is None or size > MAX_BYTES:
            raise ValueError("staged upload is missing or exceeds the size limit")
        data = audio_store.read_all(path, size)
        track = Library(user_id).add_upload(
            filename,
            data,
            quota_bytes=QUOTA_BYTES,
            max_tracks=MAX_TRACKS,
            storage_path_override=path,
        )
        if track is None:
            raise ValueError("could not read uploaded audio file")
        with SessionLocal() as session:
            job = session.get(UploadJob, job_id)
            if job:
                job.status = "completed"
                job.track_id = track.id
                session.commit()
    except (Exception,) as exc:
        log.exception("upload job %s failed", job_id)
        with SessionLocal() as session:
            job = session.get(UploadJob, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)[:500]
                session.commit()
        audio_store.delete_quietly(path)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    while True:
        job_id = upload_queue.dequeue()
        if job_id:
            process(job_id)
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
