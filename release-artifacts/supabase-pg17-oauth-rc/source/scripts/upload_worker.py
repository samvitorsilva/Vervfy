#!/usr/bin/env python3
"""Process staged uploads; retain artwork durably until guarded attachment."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import undefer

import storage_lifecycle
import upload_queue
from cover_art import resolve_cover, uploaded_cover
from db import TrackRecord, UploadJob, User, tenant_session
from library import Library, StaleUploadOperation

log = logging.getLogger("vervfy.upload_worker")
MAX_BYTES = int(os.environ.get("VERVFY_MAX_UPLOAD_MB", "50")) * 1024 * 1024
QUOTA_BYTES = int(os.environ.get("VERVFY_USER_QUOTA_MB", "150")) * 1024 * 1024
MAX_TRACKS = int(os.environ.get("VERVFY_MAX_TRACKS_PER_USER", "200"))
MAX_ATTEMPTS = 3


def _artwork_rows(session, job_id, user_id):
    storage_lifecycle.bound_transaction(session)
    if session.get(User, user_id, with_for_update=True) is None:
        return None, None
    job = session.scalar(
        select(UploadJob)
        .options(undefer(UploadJob.cover_data))
        .where(UploadJob.id == job_id, UploadJob.user_id == user_id)
        .with_for_update()
    )
    track = (
        session.get(
            TrackRecord, {"id": job.track_id, "user_id": user_id}, with_for_update=True
        )
        if job and job.track_id
        else None
    )
    return job, track


def _complete_artwork(job_id: str, user_id: str) -> bool:
    """Snapshot -> bounded I/O without business locks -> fenced atomic attach.

    Concurrent attempts may create extra held candidates, but only one may consume
    the durable source. Retried completed jobs never reapply an attached cover.
    """
    with tenant_session(user_id) as session:
        job, track = _artwork_rows(session, job_id, user_id)
        if job is None:
            return True
        if job.status != "completed":
            return False
        if job.cover_data is None:
            return True
        if (
            track is None
            or job.processing_token is None
            or track.media_version != job.processing_token
        ):
            job.error = "Artwork held: track changed or ownership is uncertain; original retained."
            session.commit()
            return True
        original = bytes(job.cover_data)
        fence, track_id = job.processing_token, job.track_id
    try:
        image = uploaded_cover(original)
    except ValueError:
        image = None
    if image is None:
        # Recheck the source below before reporting its held status.
        path = None
    else:
        path = storage_lifecycle.upload_bytes(user_id, "track-cover", image)
    # No user/job/track row or SQL connection was held during upload/verification.
    with tenant_session(user_id) as session:
        job, track = _artwork_rows(session, job_id, user_id)
        if job is None or job.cover_data is None:
            return True
        if job.status != "completed":
            return False
        if (
            job.track_id != track_id
            or job.processing_token != fence
            or bytes(job.cover_data) != original
        ):
            return False  # A different durable operation owns the current source.
        if track is None or track.media_version != fence:
            job.error = "Artwork held: track changed; original retained."
            session.commit()
            return True
        if path is None:
            job.error = "Artwork held: source could not be decoded; original retained."
            session.commit()
            return True
        track.cover_path = path
        track.cover_data = None
        track.cover_source = "upload"
        track.cover_url = None
        track.has_cover = True
        track.media_version = uuid.uuid4()
        session.flush()
        session.refresh(track, ["cover_path", "media_version"])
        if track.cover_path != path:
            raise RuntimeError("Artwork attachment was not confirmed")
        job.cover_data = None
        job.processing_token = None
        job.error = None
        session.commit()
        return True


def process(job_id: str, user_id: str) -> bool:
    """True allows queue acknowledgement; False leaves its durable lease intact."""
    audio_path = None
    token = uuid.uuid4()
    try:
        with tenant_session(user_id) as session:
            storage_lifecycle.bound_transaction(session)
            job = session.scalar(
                select(UploadJob)
                .options(undefer(UploadJob.cover_data))
                .where(UploadJob.id == job_id, UploadJob.user_id == user_id)
                .with_for_update()
            )
            if job is None:
                return True
            artwork_retry = job.status == "completed" and job.cover_data is not None
            if not artwork_retry:
                if job.status not in {"pending", "processing"} or not job.storage_path:
                    return True
                job.processing_token = token
                job.status = "processing"
                job.attempts += 1
                filename = job.filename
                has_sidecar = job.cover_data is not None
                with tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(filename)[1], delete=False
                ) as source:
                    audio_path = source.name
            session.commit()
        if artwork_retry:
            return _complete_artwork(job_id, user_id)
        with tenant_session(user_id) as session:
            storage_lifecycle.bound_transaction(session)
            job = session.scalar(
                select(UploadJob)
                .where(UploadJob.id == job_id, UploadJob.user_id == user_id)
                .with_for_update()
            )
            if not job or job.processing_token != token or not job.storage_path:
                raise StaleUploadOperation("Upload source was superseded")
            storage_lifecycle.download_staged(
                session, job.storage_path, audio_path, MAX_BYTES
            )
            session.commit()
        track = Library(user_id).add_upload_file(
            filename,
            audio_path,
            quota_bytes=QUOTA_BYTES,
            max_tracks=MAX_TRACKS,
            job_context=(job_id, token),
        )
        if track is None:
            raise ValueError("Could not parse uploaded audio")
        artwork_complete = _complete_artwork(job_id, user_id)
        if has_sidecar or not artwork_complete:
            return artwork_complete
        try:
            asyncio.run(
                resolve_cover(user_id, track.id, expected_version=track.media_version)
            )
        except Exception:
            log.exception("Cover lookup failed after upload job %s", job_id)
        return True
    except StaleUploadOperation:
        log.info("Upload attempt superseded for job %s", job_id)
        # A stale delivery must not acknowledge another worker's active lease.
        return False
    except Exception:
        log.exception("Upload job %s failed", job_id)
        retry = False
        with tenant_session(user_id) as session:
            storage_lifecycle.bound_transaction(session)
            job = session.scalar(
                select(UploadJob)
                .options(undefer(UploadJob.cover_data))
                .where(UploadJob.id == job_id, UploadJob.user_id == user_id)
                .with_for_update()
            )
            if job and job.status == "completed" and job.cover_data is not None:
                job.error = "Artwork processing will retry; original retained."
                session.commit()
                return False
            if job and job.status == "processing" and job.processing_token != token:
                return False
            if job and job.processing_token == token and job.status == "processing":
                retry = job.attempts < MAX_ATTEMPTS
                job.status = "pending" if retry else "failed"
                job.error = (
                    "Upload processing will be retried."
                    if retry
                    else "Upload processing failed; source retained for review."
                )
                session.commit()
        if retry:
            upload_queue.requeue(job_id, user_id)
        return True
    finally:
        if audio_path:
            try:
                os.unlink(audio_path)
            except OSError:
                log.warning("Could not remove temporary upload file")


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    while True:
        job = upload_queue.dequeue()
        if job:
            try:
                with upload_queue.keep_lease(*job):
                    completed = process(*job)
                if completed:
                    upload_queue.acknowledge(*job)
            except Exception:
                log.exception("worker failed while processing job %s", job[0])
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
