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
from db import UploadJob, tenant_session
from library import Library, UploadQuotaExceeded
from sqlalchemy import select

log = logging.getLogger("vervfy.upload_worker")
MAX_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))
MAX_ATTEMPTS = 3


def process(job_id: str, user_id: str) -> None:
    path: str | None = None
    try:
        with tenant_session(user_id) as session:
            job = session.scalar(select(UploadJob).where(
                UploadJob.id == job_id,
                UploadJob.user_id == user_id,
            ))
            if not job or job.status not in {"pending", "processing"}:
                return
            job.status = "processing"
            job.attempts += 1
            session.commit()
            filename, path = job.filename, job.storage_path
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
        stored_info = Library(user_id).audio_info(track.id)
        if stored_info and stored_info.storage_path != path:
            audio_store.delete_quietly(path)
        with tenant_session(user_id) as session:
            job = session.scalar(select(UploadJob).where(
                UploadJob.id == job_id,
                UploadJob.user_id == user_id,
            ))
            if job:
                job.status = "completed"
                job.track_id = track.id
                session.commit()
    except Exception as exc:
        log.exception("upload job %s failed", job_id)
        retry = False
        with tenant_session(user_id) as session:
            job = session.scalar(select(UploadJob).where(
                UploadJob.id == job_id,
                UploadJob.user_id == user_id,
            ))
            if job:
                retry = job.attempts < MAX_ATTEMPTS
                job.status = "pending" if retry else "failed"
                job.error = (
                    "Upload processing will be retried."
                    if retry
                    else "Upload processing failed after repeated attempts."
                )
                session.commit()
        if retry:
            upload_queue.requeue(job_id, user_id)
        else:
            upload_queue.dead_letter(job_id, user_id, str(exc))
            audio_store.delete_quietly(path)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    while True:
        job = upload_queue.dequeue()
        if job:
            try:
                with upload_queue.keep_lease(*job):
                    process(*job)
                upload_queue.acknowledge(*job)
            except Exception:
                log.exception("worker failed while processing job %s", job[0])
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
