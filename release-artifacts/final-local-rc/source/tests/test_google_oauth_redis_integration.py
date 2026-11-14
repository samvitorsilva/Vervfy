"""Disposable local Redis tests; never connects to configured application Redis.

Run with:
    python -m unittest discover -s tests -p test_google_oauth_redis_integration.py

Tests skip when redis-server is unavailable. Each test starts a fresh Redis
process bound only to a private Unix socket in a temporary directory.
"""
from __future__ import annotations

import concurrent.futures
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path

import redis

import google_oauth


REDIS_SERVER = shutil.which("redis-server")


@unittest.skipUnless(REDIS_SERVER, "redis-server is not installed")
class LocalRedisOAuthIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="vervfy-oauth-redis-")
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.socket_path = root / "redis.sock"
        self.process = subprocess.Popen(
            [
                REDIS_SERVER,
                "--port",
                "0",
                "--unixsocket",
                str(self.socket_path),
                "--unixsocketperm",
                "700",
                "--save",
                "",
                "--appendonly",
                "no",
                "--daemonize",
                "no",
                "--protected-mode",
                "yes",
                "--dir",
                str(root),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self._stop_server)
        self.client = redis.Redis(
            unix_socket_path=str(self.socket_path),
            decode_responses=True,
            socket_connect_timeout=0.1,
            socket_timeout=0.1,
        )
        self.addCleanup(self.client.close)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail("Disposable Redis exited before becoming ready")
            try:
                if self.client.ping():
                    break
            except redis.RedisError:
                time.sleep(0.02)
        else:
            self.fail("Disposable Redis did not become ready")
        self.store = google_oauth.RedisOAuthTransactionStore(
            "", client=self.client
        )
        self.state = f"state-{uuid.uuid4().hex}"
        self.browser_binding = f"browser-{uuid.uuid4().hex}"
        self.transaction = {
            "purpose": "login",
            "nonce": "synthetic-nonce",
            "code_verifier": "synthetic-verifier",
            "browser_binding": self.store.binding_digest(self.browser_binding),
            "issued_at": int(time.time()),
        }

    def _stop_server(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

    def test_consumption_is_atomic_and_replay_fails(self):
        self.store.create(self.state, self.transaction)
        barrier = threading.Barrier(8)

        def consume():
            barrier.wait(timeout=3)
            return self.store.consume(self.state, self.browser_binding)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _index: consume(), range(8)))

        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertIsNone(self.store.consume(self.state, self.browser_binding))

    def test_redis_enforces_transaction_expiry(self):
        self.assertEqual(google_oauth.RedisOAuthTransactionStore.TTL_SECONDS, 600)
        self.store.TTL_SECONDS = 1
        self.store.create(self.state, self.transaction)
        key = (
            self.store.KEY_PREFIX
            + self.store.state_digest(self.state)
        )
        self.assertGreater(self.client.ttl(key), 0)
        time.sleep(1.1)
        self.assertIsNone(self.store.consume(self.state, self.browser_binding))

    def test_evicted_transaction_fails_closed_without_fallback(self):
        self.store.create(self.state, self.transaction)
        key = self.store.KEY_PREFIX + self.store.state_digest(self.state)
        self.assertIsNotNone(self.client.get(key))

        self.client.delete(key)

        self.assertIsNone(self.store.consume(self.state, self.browser_binding))

    def test_redis_outage_fails_closed_without_memory_fallback(self):
        self.store.create(self.state, self.transaction)
        self.process.terminate()
        self.process.wait(timeout=3)

        with self.assertRaises(google_oauth.OAuthBackendUnavailable):
            self.store.consume(self.state, self.browser_binding)
        with self.assertRaises(google_oauth.OAuthBackendUnavailable):
            self.store.create(f"new-{self.state}", self.transaction)


if __name__ == "__main__":
    unittest.main()
