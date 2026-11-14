"""Sensitive-action admission tests: synthetic users and disposable Redis only."""

import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import redis
from fastapi import HTTPException

import auth
import server


class PasswordAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id="synthetic-a", password_hash="synthetic-hash")
        self.limiter = auth.RequestThrottle()
        self.patcher = patch.object(server, "request_throttle", self.limiter)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def fail_attempt(self, user=None):
        with self.assertRaises(HTTPException) as error:
            server.verify_current_password(user or self.user, "synthetic-wrong")
        return error.exception.status_code

    def test_ten_failures_then_no_password_verification_even_for_correct_password(self):
        with patch.object(auth, "verify_password", return_value=False) as verify:
            self.assertEqual([self.fail_attempt() for _ in range(10)], [400] * 10)
            verify.assert_called()
        with patch.object(auth, "verify_password", return_value=True) as verify:
            self.assertEqual(self.fail_attempt(), 429)
            verify.assert_not_called()

    def test_admitted_success_resets_failures(self):
        with patch.object(auth, "verify_password", return_value=False):
            for _ in range(9):
                self.assertEqual(self.fail_attempt(), 400)
        with patch.object(auth, "verify_password", return_value=True):
            server.verify_current_password(self.user, "synthetic-correct")
        self.assertEqual(self.limiter.peek("current-password:synthetic-a", 900), 0)
        with patch.object(auth, "verify_password", return_value=False):
            self.assertEqual(self.fail_attempt(), 400)

    def test_expiry_restores_admission_without_sleep(self):
        with (
            patch.object(auth.time, "time", return_value=1000),
            patch.object(auth, "verify_password", return_value=False),
        ):
            for _ in range(10):
                self.fail_attempt()
        with (
            patch.object(auth.time, "time", return_value=1901),
            patch.object(auth, "verify_password", return_value=True),
        ):
            server.verify_current_password(self.user, "synthetic-correct")

    def test_accounts_have_independent_limits(self):
        with patch.object(auth, "verify_password", return_value=False):
            for _ in range(10):
                self.fail_attempt()
            self.assertEqual(
                self.fail_attempt(
                    SimpleNamespace(id="synthetic-b", password_hash="hash")
                ),
                400,
            )

    def test_backend_failure_does_not_verify_password(self):
        with (
            patch.object(
                self.limiter, "allow", side_effect=RuntimeError("unavailable")
            ),
            patch.object(auth, "verify_password", return_value=True) as verify,
        ):
            self.assertEqual(self.fail_attempt(), 503)
            verify.assert_not_called()

    def test_reset_failure_fails_closed(self):
        with (
            patch.object(
                self.limiter, "discard", side_effect=RuntimeError("unavailable")
            ),
            patch.object(auth, "verify_password", return_value=True),
        ):
            self.assertEqual(self.fail_attempt(), 503)

    def check_concurrent_admission(self):
        start = threading.Barrier(16)
        admitted = threading.Barrier(10)

        def verify(*_args):
            admitted.wait(timeout=10)
            return False

        def attempt(_index):
            start.wait(timeout=10)
            return self.fail_attempt()

        with patch.object(
            auth, "verify_password", side_effect=verify
        ) as password_check:
            with ThreadPoolExecutor(max_workers=16) as pool:
                statuses = list(pool.map(attempt, range(16)))
            self.assertEqual(statuses.count(400), 10)
            self.assertEqual(statuses.count(429), 6)
            self.assertEqual(password_check.call_count, 10)

    def test_concurrent_memory_admission_is_bounded(self):
        self.check_concurrent_admission()

    @unittest.skipUnless(shutil.which("redis-server"), "Requires local redis-server")
    def test_concurrent_real_redis_admission_is_bounded(self):
        with tempfile.TemporaryDirectory(prefix="vervfy-password-redis-") as directory:
            sock = str(Path(directory) / "redis.sock")
            process = subprocess.Popen(
                [
                    shutil.which("redis-server"),
                    "--port",
                    "0",
                    "--unixsocket",
                    sock,
                    "--unixsocketperm",
                    "700",
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                    "--dir",
                    directory,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            client = redis.Redis(unix_socket_path=sock, decode_responses=True)
            try:
                deadline = time.monotonic() + 5
                while True:
                    try:
                        client.ping()
                        break
                    except redis.RedisError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("Disposable Redis did not start")
                        time.sleep(0.01)
                self.limiter._redis = client
                self.check_concurrent_admission()
            finally:
                self.limiter._redis = None
                client.close()
                process.terminate()
                process.wait(timeout=5)
