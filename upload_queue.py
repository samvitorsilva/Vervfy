"""Durable Redis queue for staged audio uploads."""
from __future__ import annotations

import json
import os
import time

import redis

QUEUE_KEY = "vervfy:upload-jobs"


def client() -> redis.Redis:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL is required for asynchronous uploads")
    return redis.Redis.from_url(url, decode_responses=True)


def enqueue(job_id: str) -> None:
    client().rpush(QUEUE_KEY, json.dumps({"job_id": job_id}))


def dequeue(timeout: int = 5) -> str | None:
    result = client().blpop(QUEUE_KEY, timeout=timeout)
    if not result:
        return None
    return str(json.loads(result[1])["job_id"])


def requeue(job_id: str) -> None:
    client().rpush(QUEUE_KEY, json.dumps({"job_id": job_id, "retry_at": time.time()}))
