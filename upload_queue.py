"""Durable Redis queue for staged audio uploads."""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from threading import Event, Thread
from typing import Iterator

import redis

QUEUE_KEY = "vervfy:upload-jobs"
LEASE_KEY = "vervfy:upload-jobs:leases"
DEAD_LETTER_KEY = "vervfy:upload-jobs:dead"
LEASE_SECONDS = 90
log = logging.getLogger("vervfy.upload_queue")

_CLAIM_SCRIPT = """
local expired = redis.call('ZRANGEBYSCORE', KEYS[2], '-inf', ARGV[1], 'LIMIT', 0, 100)
for _, task in ipairs(expired) do
  redis.call('ZREM', KEYS[2], task)
  redis.call('RPUSH', KEYS[1], task)
end
local task = redis.call('LPOP', KEYS[1])
if task then redis.call('ZADD', KEYS[2], ARGV[2], task) end
return task
"""

_RENEW_SCRIPT = """
if redis.call('ZSCORE', KEYS[1], ARGV[1]) then
  return redis.call('ZADD', KEYS[1], 'XX', ARGV[2], ARGV[1])
end
return 0
"""


def client() -> redis.Redis:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL is required for asynchronous uploads")
    return redis.Redis.from_url(url, decode_responses=True)


def enqueue(job_id: str, user_id: str) -> None:
    queue = client()
    try:
        queue.rpush(QUEUE_KEY, _encode(job_id, user_id))
    finally:
        queue.close()


def _encode(job_id: str, user_id: str) -> str:
    return json.dumps({"job_id": job_id, "user_id": user_id}, separators=(",", ":"))


def dequeue(timeout: int = 5) -> tuple[str, str] | None:
    deadline = time.monotonic() + timeout
    queue = client()
    try:
        while True:
            now = time.time()
            task = queue.eval(
                _CLAIM_SCRIPT,
                2,
                QUEUE_KEY,
                LEASE_KEY,
                now,
                now + LEASE_SECONDS,
            )
            if task:
                payload = json.loads(task)
                return str(payload["job_id"]), str(payload["user_id"])
            if time.monotonic() >= deadline:
                return None
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    finally:
        queue.close()


def acknowledge(job_id: str, user_id: str) -> None:
    queue = client()
    try:
        queue.zrem(LEASE_KEY, _encode(job_id, user_id))
    finally:
        queue.close()


def _renew(job_id: str, user_id: str) -> None:
    queue = client()
    try:
        now = time.time()
        queue.eval(
            _RENEW_SCRIPT,
            1,
            LEASE_KEY,
            _encode(job_id, user_id),
            now + LEASE_SECONDS,
        )
    finally:
        queue.close()


@contextmanager
def keep_lease(job_id: str, user_id: str) -> Iterator[None]:
    """Renew a claimed task while processing; expired leases are reclaimed by dequeue."""
    stopped = Event()

    def renew_loop() -> None:
        while not stopped.wait(LEASE_SECONDS / 3):
            try:
                _renew(job_id, user_id)
            except redis.RedisError:
                # Do not terminate processing on a transient heartbeat failure.
                # If the lease expires, duplicate delivery is safe/idempotent.
                log.warning("could not renew upload lease for job %s", job_id, exc_info=True)

    heartbeat = Thread(target=renew_loop, name=f"upload-lease-{job_id}", daemon=True)
    heartbeat.start()
    try:
        yield
    finally:
        stopped.set()
        heartbeat.join(timeout=LEASE_SECONDS / 3 + 1)


def requeue(job_id: str, user_id: str) -> None:
    enqueue(job_id, user_id)


def dead_letter(job_id: str, user_id: str, reason: str) -> None:
    queue = client()
    try:
        queue.rpush(
            DEAD_LETTER_KEY,
            json.dumps({
                "job_id": job_id,
                "user_id": user_id,
                "reason": reason[:500],
                "failed_at": time.time(),
            }),
        )
    finally:
        queue.close()
