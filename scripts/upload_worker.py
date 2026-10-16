#!/usr/bin/env python3
"""Process staged uploads: python scripts/upload_worker.py."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audio_store
import upload_queue
from cover_art import resolve_cover
from db import UploadJob, tenant_session
from library import Library
from sqlalchemy import select
from sqlalchemy.orm import undefer

log = logging.getLogger("vervfy.upload_worker")
MAX_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))
MAX_ATTEMPTS = 3


def process(job_id: str, user_id: str) -> None:
    path: str | None = None
    audio_path: str | None = None
    cover_data: bytes | None = None
    try:
        with tenant_session(user_id) as session:
            job = session.scalar(
                select(UploadJob)
                .options(undefer(UploadJob.cover_data))
                .where(
                    UploadJob.id == job_id,
                    UploadJob.user_id == user_id,
                )
            )
            if not job or job.status not in {"pending", "processing"}:
                return
            job.status = "processing"
            job.attempts += 1
            session.commit()
            filename, path = job.filename, job.storage_path
            if job.cover_data is not None:
                cover_data = bytes(job.cover_data)
        size = audio_store.object_size(path)
        if size is None or size > MAX_BYTES:
            raise ValueError("staged upload is missing or exceeds the size limit")
        suffix = os.path.splitext(os.path.basename(filename))[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
            audio_path = audio_file.name
        audio_store.download_to_file(path, audio_path, size)
        track = Library(user_id).add_upload_file(
            filename,
            audio_path,
            quota_bytes=QUOTA_BYTES,
            max_tracks=MAX_TRACKS,
            storage_path_override=path,
        )
        if track is None:
            raise ValueError("could not read uploaded audio file")
        stored_info = Library(user_id).audio_info(track.id)
        if stored_info and stored_info.storage_path != path:
            audio_store.delete_quietly(path)
        try:
            asyncio.run(
                resolve_cover(user_id, track.id, uploaded_data=cover_data)
            )
        except Exception:
            log.exception(
                "cover lookup failed after upload job %s for track %s",
                job_id,
                track.id,
            )
        with tenant_session(user_id) as session:
            job = session.scalar(select(UploadJob).where(
                UploadJob.id == job_id,
                UploadJob.user_id == user_id,
            ))
            if job:
                job.status = "completed"
                job.track_id = track.id
                job.cover_data = None
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
    finally:
        if audio_path:
            try:
                os.unlink(audio_path)
            except OSError:
                log.warning("Could not remove temporary audio file %s", audio_path)


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
