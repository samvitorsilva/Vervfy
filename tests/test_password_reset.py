from __future__ import annotations

import asyncio
import hashlib
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import redis
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import auth
import email_smtp
import password_reset
import server
from db import Base, ProviderIdentity, User

REDIS_SERVER = shutil.which("redis-server")


class PasswordResetStoreTests(unittest.TestCase):
    def test_expiry_replay_and_new_request_invalidation(self) -> None:
        store = password_reset.PasswordResetStore(ttl_seconds=60)
        first = store.issue("user-a")
        self.assertIsNotNone(first)
        claim = store.claim(first)
        self.assertIsNotNone(claim)
        self.assertTrue(store.commit(first, claim))
        self.assertIsNone(store.claim(first))

        old_token = store.issue("user-a")
        new_token = store.issue("user-a")
        self.assertIsNotNone(old_token)
        self.assertIsNotNone(new_token)
        self.assertIsNone(store.claim(old_token))
        self.assertEqual(store.peek_user_id(new_token), "user-a")

        with patch("password_reset.time.time", return_value=10_000):
            expiring_store = password_reset.PasswordResetStore(ttl_seconds=60)
            expiring = expiring_store.issue("user-b")
        with patch("password_reset.time.time", return_value=10_061):
            self.assertIsNone(expiring_store.claim(expiring))

    def test_only_one_concurrent_claim_and_release_allows_retry(self) -> None:
        store = password_reset.PasswordResetStore()
        token = store.issue("user-a")
        self.assertIsNotNone(token)

        with ThreadPoolExecutor(max_workers=12) as executor:
            claims = list(executor.map(lambda _: store.claim(token), range(12)))

        winners = [claim for claim in claims if claim is not None]
        self.assertEqual(len(winners), 1)
        self.assertTrue(store.release(token, winners[0]))
        retried = store.claim(token)
        self.assertIsNotNone(retried)
        self.assertNotEqual(retried.claim_id, winners[0].claim_id)
        self.assertTrue(store.commit(token, retried))

    def test_email_verification_claim_binds_the_original_address(self) -> None:
        store = password_reset.EmailVerificationStore()
        token = store.issue(
            "user-a",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        claim = store.claim(token)
        self.assertIsNotNone(claim)
        self.assertEqual(claim.user_id, "user-a")
        self.assertEqual(
            claim.binding,
            hashlib.sha256(b"user@example.com").hexdigest(),
        )


@unittest.skipUnless(REDIS_SERVER, "redis-server is not installed")
class PasswordResetRedisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="vervfy-reset-redis-")
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
        self.store = password_reset.PasswordResetStore()
        self.store._redis = self.client

    def _stop_server(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

    def test_redis_claim_is_atomic_and_release_preserves_the_token(self):
        token = self.store.issue("user-redis")
        self.assertIsNotNone(token)
        barrier = threading.Barrier(8)

        def claim():
            barrier.wait(timeout=3)
            return self.store.claim(token)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _index: claim(), range(8)))

        winners = [claim_result for claim_result in results if claim_result]
        self.assertEqual(len(winners), 1)
        self.assertTrue(self.store.release(token, winners[0]))
        retry = self.store.claim(token)
        self.assertIsNotNone(retry)
        self.assertTrue(self.store.commit(token, retry))
        self.assertIsNone(self.store.claim(token))

    def test_redis_user_lock_prevents_overlapping_tokens_and_replaces_old_token(self):
        first = self.store.issue("user-redis")
        claim = self.store.claim(first)
        self.assertIsNotNone(claim)
        self.assertIsNone(self.store.issue("user-redis"))
        self.assertTrue(self.store.release(first, claim))

        second = self.store.issue("user-redis")
        self.assertIsNotNone(second)
        self.assertIsNone(self.store.claim(first))
        self.assertEqual(self.store.peek_user_id(second), "user-redis")

    def test_redis_token_expires(self):
        self.store.ttl_seconds = 1
        token = self.store.issue("user-redis")
        time.sleep(1.1)
        self.assertIsNone(self.store.claim(token))

    def test_email_verification_redis_tokens_use_a_separate_namespace(self):
        verification_store = password_reset.EmailVerificationStore()
        verification_store._redis = self.client
        reset_token = self.store.issue("user-redis")
        verification_token = verification_store.issue(
            "user-redis",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        reset_claim = self.store.claim(reset_token)
        verify_claim = verification_store.claim(verification_token)
        self.assertIsNotNone(reset_claim)
        self.assertIsNotNone(verify_claim)
        self.assertEqual(verify_claim.binding, hashlib.sha256(b"user@example.com").hexdigest())

    def test_redis_discard_removes_an_unsent_token(self):
        token = self.store.issue("user-redis")
        digest = password_reset.token_digest(token)
        token_key = f"{self.store.token_prefix}{digest}"
        user_key = f"{self.store.user_prefix}user-redis"
        self.assertIsNotNone(self.client.get(token_key))
        self.store.discard(token)
        self.assertIsNone(self.client.get(token_key))
        self.assertIsNone(self.client.get(user_key))

    def test_redis_outage_fails_closed_without_memory_fallback(self):
        self.process.terminate()
        self.process.wait(timeout=3)
        with self.assertRaises(RuntimeError):
            self.store.claim("synthetic-token")
        with self.assertRaises(RuntimeError):
            self.store.issue("user-redis")


class PasswordResetUserStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.session_local_patch = patch.object(auth, "SessionLocal", self.factory)
        self.session_local_patch.start()
        self.addCleanup(self.session_local_patch.stop)
        self.addCleanup(self.engine.dispose)

    def add_user(self, *, email_verified: bool, password_hash: str | None = "old-hash"):
        with self.factory() as session:
            session.add(
                User(
                    id="account-1",
                    username="reset-user",
                    username_key="reset-user",
                    email="user@example.com",
                    email_verified=email_verified,
                    password_hash=password_hash,
                    created_at=1,
                    session_version=4,
                )
            )
            session.commit()

    def test_target_requires_password_and_reports_email_verification(self) -> None:
        store = auth.UserStore()
        self.add_user(email_verified=False)
        self.assertEqual(
            store.get_password_reset_account(" USER@example.com "),
            ("account-1", False),
        )
        self.assertIsNone(store.get_password_reset_target("user@example.com"))

        with self.factory() as session:
            row = session.get(User, "account-1")
            row.password_hash = None
            session.commit()
        self.assertIsNone(store.get_password_reset_account("user@example.com"))

    def test_verified_reset_bumps_sessions_and_leaves_google_identity_untouched(self):
        store = auth.UserStore()
        self.add_user(email_verified=True)
        with self.factory() as session:
            session.add(
                ProviderIdentity(
                    issuer="https://accounts.google.com",
                    subject="google-subject",
                    user_id="account-1",
                    created_at=1,
                )
            )
            session.commit()

        with patch.object(auth, "hash_password", return_value="new-hash"):
            version = store.reset_password_and_invalidate_sessions(
                "account-1",
                "new-password-123",
            )

        self.assertEqual(version, 5)
        with self.factory() as session:
            user = session.get(User, "account-1")
            identity = session.scalar(
                select(ProviderIdentity).where(
                    ProviderIdentity.user_id == "account-1"
                )
            )
        self.assertEqual(user.password_hash, "new-hash")
        self.assertEqual(user.session_version, 5)
        self.assertEqual(identity.subject, "google-subject")

    def test_email_verification_rejects_an_address_changed_after_request(self):
        store = auth.UserStore()
        self.add_user(email_verified=False)
        old_digest = hashlib.sha256(b"user@example.com").hexdigest()
        with self.factory() as session:
            row = session.get(User, "account-1")
            row.email = "changed@example.com"
            session.commit()

        with self.assertRaises(ValueError):
            store.verify_password_reset_email("account-1", old_digest)
        with self.factory() as session:
            self.assertFalse(session.get(User, "account-1").email_verified)


class PasswordResetRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recovery_enabled_patch = patch.dict(
            "os.environ",
            {"VERVFY_PASSWORD_RECOVERY_ENABLED": "1"},
        )
        self.recovery_enabled_patch.start()
        self.addCleanup(self.recovery_enabled_patch.stop)

    @staticmethod
    def request(path: str) -> Request:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "root_path": "",
            "session": {},
        }
        return Request(scope)

    def assert_diagnostics(
        self,
        records,
        expected: tuple[tuple[str, str], ...],
        sensitive_values: tuple[str, ...] = (),
    ) -> None:
        diagnostic_records = [
            record
            for record in records
            if getattr(record, "event", None) == "password_recovery_diagnostic"
        ]
        actual = [
            (record.recovery_stage, record.recovery_reason)
            for record in diagnostic_records
        ]
        self.assertEqual(actual, list(expected))
        self.assertEqual(len(records), len(diagnostic_records))
        for record, (stage, reason) in zip(diagnostic_records, expected):
            self.assertEqual(record.getMessage(), f"password_recovery_diagnostic stage={stage} reason={reason}")
            self.assertEqual(record.recovery_stage, stage)
            self.assertEqual(record.recovery_reason, reason)
            serialized = f"{record.getMessage()} {record.__dict__!r}"
            for value in sensitive_values:
                self.assertNotIn(value, serialized)

    def test_forgot_response_is_generic_for_missing_unverified_and_verified(self):
        results = []
        mailer = _FakeMailer()
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", password_reset.PasswordResetStore()),
            patch.object(server, "email_verification_store", password_reset.EmailVerificationStore()),
            patch.object(server, "email_sender", mailer),
        ):
            for account in (None, ("account-1", False), ("account-2", True)):
                with patch.object(
                    server.user_store,
                    "get_password_reset_account",
                    return_value=account,
                ), patch.object(server.auth, "verify_password"):
                    results.append(
                        server.forgot_password(
                            server.ForgotPasswordRequest(email="user@example.com"),
                            self.request("/api/auth/forgot-password"),
                            _csrf=None,
                        )
                    )

        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(len(mailer.verification_tokens), 1)
        self.assertEqual(len(mailer.reset_tokens), 1)

    def test_smtp_failure_discards_the_unsent_token(self):
        store = password_reset.PasswordResetStore()
        mailer = _FakeMailer(error=email_smtp.SmtpSendError("synthetic SMTP failure"))
        request = self.request("/api/auth/forgot-password")
        request.session.update({"user_id": "account-1", "sid": "existing-session"})
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(server, "email_sender", mailer),
            patch.object(server.user_store, "reset_password_and_invalidate_sessions") as update_password,
            patch.object(server.session_store, "revoke_user") as revoke_user,
            patch.object(
                server.user_store,
                "get_password_reset_account",
                return_value=("account-1", True),
            ),
        ):
            result = server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                request,
                _csrf=None,
            )

        self.assertEqual(result, server._password_reset_generic_response())
        self.assertEqual(mailer.reset_tokens, [])
        self.assertEqual(store._tokens, {})
        self.assertEqual(request.session, {"user_id": "account-1", "sid": "existing-session"})
        update_password.assert_not_called()
        revoke_user.assert_not_called()

    def test_recovery_routes_remain_inert_until_explicitly_enabled(self):
        request = self.request("/api/auth/forgot-password")
        request.session.update({"user_id": "account-1", "sid": "existing-session"})
        with (
            self.assertLogs("vervfy.password_reset", level="INFO") as diagnostics,
            patch.dict("os.environ", {"VERVFY_PASSWORD_RECOVERY_ENABLED": "0"}),
            patch.object(server.user_store, "get_password_reset_account") as lookup,
            patch.object(server, "email_sender") as mailer,
            patch.object(server.user_store, "reset_password_and_invalidate_sessions") as update_password,
            patch.object(server.session_store, "revoke_user") as revoke_user,
        ):
            with self.assertRaises(HTTPException) as raised:
                server.forgot_password(
                    server.ForgotPasswordRequest(email="user@example.com"),
                    request,
                    _csrf=None,
                )
            self.assertEqual(raised.exception.status_code, 503)
            self.assertEqual(
                raised.exception.detail,
                "Service temporarily unavailable, try again shortly",
            )
            lookup.assert_not_called()
            mailer.send_password_reset.assert_not_called()

            for operation in (
                lambda: server.reset_password(
                    server.ResetPasswordRequest(
                        token="synthetic-token",
                        password="new-password-123",
                    ),
                    self.request("/api/auth/reset-password"),
                    _csrf=None,
                ),
                lambda: server.verify_reset_email(
                    server.VerifyResetEmailRequest(token="synthetic-token"),
                    self.request("/api/auth/verify-reset-email"),
                    _csrf=None,
                ),
            ):
                with self.assertRaises(HTTPException) as raised:
                    operation()
                self.assertEqual(raised.exception.status_code, 503)

        self.assert_diagnostics(
            diagnostics.records,
            (("feature_flag", "disabled"),) * 3,
            ("user@example.com", "synthetic-token"),
        )
        self.assertEqual(request.session, {"user_id": "account-1", "sid": "existing-session"})
        update_password.assert_not_called()
        revoke_user.assert_not_called()

    def test_middleware_rate_limiter_failure_is_diagnosed(self):
        for path in (
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
            "/api/auth/verify-reset-email",
        ):
            with self.subTest(path=path):
                async def call_next(_request):
                    self.fail("middleware should return on rate-limiter failure")

                with (
                    patch.object(
                        server,
                        "run_in_threadpool",
                        side_effect=RuntimeError("secret redis connection detail"),
                    ),
                    self.assertLogs(
                        "vervfy.password_reset",
                        level="WARNING",
                    ) as diagnostics,
                ):
                    response = asyncio.run(
                        server.add_security_headers(
                            self.request(path),
                            call_next,
                        )
                    )

                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.body,
                    b'{"detail":"Rate-limit service unavailable"}',
                )
                self.assert_diagnostics(
                    diagnostics.records,
                    (("rate_limiter", "middleware_backend_unavailable"),),
                    ("secret redis connection detail",),
                )

    def test_forgot_password_rate_limiter_failure_is_diagnosed(self):
        with (
            patch.object(
                server.request_throttle,
                "allow",
                side_effect=RuntimeError("secret redis connection detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                self.request("/api/auth/forgot-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("rate_limiter", "backend_unavailable"),),
            ("user@example.com", "secret redis connection detail"),
        )

    def test_reset_and_verification_rate_limiter_failures_are_diagnosed(self):
        operations = (
            (
                server.reset_password,
                server.ResetPasswordRequest(
                    token="sensitive-reset-token",
                    password="sensitive-password-123",
                ),
                "/api/auth/reset-password",
            ),
            (
                server.verify_reset_email,
                server.VerifyResetEmailRequest(token="sensitive-verification-token"),
                "/api/auth/verify-reset-email",
            ),
        )
        for handler, payload, path in operations:
            with self.subTest(path=path):
                with (
                    patch.object(
                        server.request_throttle,
                        "allow",
                        side_effect=RuntimeError("sensitive Redis connection detail"),
                    ),
                    self.assertLogs(
                        "vervfy.password_reset",
                        level="WARNING",
                    ) as diagnostics,
                    self.assertRaises(HTTPException) as raised,
                ):
                    handler(payload, self.request(path), _csrf=None)

                self.assertEqual(raised.exception.status_code, 503)
                self.assertEqual(
                    raised.exception.detail,
                    "Service temporarily unavailable, try again shortly",
                )
                self.assert_diagnostics(
                    diagnostics.records,
                    (("rate_limiter", "backend_unavailable"),),
                    (
                        "sensitive-reset-token",
                        "sensitive-verification-token",
                        "sensitive-password-123",
                        "sensitive Redis connection detail",
                    ),
                )

    def test_forgot_password_database_lookup_failure_is_diagnosed(self):
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(
                server.user_store,
                "get_password_reset_account",
                side_effect=SQLAlchemyError("secret user@example.com query detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                self.request("/api/auth/forgot-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("database_lookup", "account_lookup_failed"),),
            ("user@example.com", "secret user@example.com query detail"),
        )

    def test_forgot_password_token_storage_failure_is_diagnosed(self):
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(
                server.user_store,
                "get_password_reset_account",
                return_value=("account-1", True),
            ),
            patch.object(
                server.password_reset_store,
                "issue",
                side_effect=RuntimeError("secret reset-token storage detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                self.request("/api/auth/forgot-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "token_issue_failed"),),
            ("user@example.com", "secret reset-token storage detail"),
        )

    def test_forgot_verification_token_storage_failure_is_diagnosed(self):
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(
                server.user_store,
                "get_password_reset_account",
                return_value=("account-1", False),
            ),
            patch.object(
                server.email_verification_store,
                "issue",
                side_effect=RuntimeError("sensitive verification-token issue detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                self.request("/api/auth/forgot-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "token_issue_failed"),),
            ("user@example.com", "sensitive verification-token issue detail"),
        )

    def test_unsent_token_cleanup_failure_is_diagnosed(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        mailer = _FakeMailer(
            error=email_smtp.SmtpSendError("sensitive SMTP exception detail")
        )
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(store, "issue", return_value=token),
            patch.object(
                store,
                "discard",
                side_effect=RuntimeError("sensitive cleanup exception detail"),
            ) as discard,
            patch.object(server, "email_sender", mailer),
            patch.object(
                server.user_store,
                "get_password_reset_account",
                return_value=("account-1", True),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
        ):
            result = server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                self.request("/api/auth/forgot-password"),
                _csrf=None,
            )

        self.assertEqual(result, server._password_reset_generic_response())
        discard.assert_called_once_with(token)
        self.assertEqual(store.peek_user_id(token), "account-1")
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "unsent_token_cleanup_failed"),),
            (
                "user@example.com",
                token,
                "sensitive SMTP exception detail",
                "sensitive cleanup exception detail",
            ),
        )

    def test_reset_token_claim_failure_is_diagnosed(self):
        token = "sensitive-reset-token"
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", password_reset.PasswordResetStore()),
            patch.object(
                server.password_reset_store,
                "claim",
                side_effect=RuntimeError("sensitive claim exception detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="sensitive-password-123",
                ),
                self.request("/api/auth/reset-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "token_claim_failed"),),
            (token, "sensitive-password-123", "sensitive claim exception detail"),
        )

    def test_reset_token_commit_failure_is_diagnosed(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(
                store,
                "commit",
                side_effect=RuntimeError("sensitive commit exception detail"),
            ),
            patch.object(
                server.user_store,
                "reset_password_and_invalidate_sessions",
                return_value=5,
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="sensitive-password-123",
                ),
                self.request("/api/auth/reset-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable; the reset may have completed",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "token_commit_failed"),),
            (token, "sensitive-password-123", "sensitive commit exception detail"),
        )

    def test_verification_token_claim_failure_is_diagnosed(self):
        token = "sensitive-verification-token"
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(
                server,
                "email_verification_store",
                password_reset.EmailVerificationStore(),
            ),
            patch.object(
                server.email_verification_store,
                "claim",
                side_effect=RuntimeError("sensitive claim exception detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "verification_token_claim_failed"),),
            (token, "sensitive claim exception detail"),
        )

    def test_verification_token_commit_failure_is_diagnosed(self):
        store = password_reset.EmailVerificationStore()
        token = store.issue(
            "account-1",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", store),
            patch.object(
                store,
                "commit",
                side_effect=RuntimeError("sensitive commit exception detail"),
            ),
            patch.object(server.user_store, "verify_password_reset_email"),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable; verification may have completed",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "verification_token_commit_failed"),),
            (token, "user@example.com", "sensitive commit exception detail"),
        )

    def test_unverified_email_confirmation_sends_a_separate_reset_link(self):
        verification_store = password_reset.EmailVerificationStore()
        reset_store = password_reset.PasswordResetStore()
        digest = hashlib.sha256(b"user@example.com").hexdigest()
        token = verification_store.issue("account-1", binding=digest)
        mailer = _FakeMailer()
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", verification_store),
            patch.object(server, "password_reset_store", reset_store),
            patch.object(server, "email_sender", mailer),
            patch.object(server.user_store, "verify_password_reset_email") as verify,
            patch.object(
                server.user_store,
                "get_by_id",
                return_value=type("User", (), {"email": "user@example.com"})(),
            ),
        ):
            result = server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(result, server._email_verification_generic_response())
        verify.assert_called_once_with("account-1", digest)
        self.assertIsNone(verification_store.claim(token))
        self.assertEqual(len(mailer.reset_tokens), 1)
        self.assertEqual(
            reset_store.peek_user_id(mailer.reset_tokens[0]),
            "account-1",
        )

    def test_reset_mail_failure_after_verification_preserves_password_and_sessions(self):
        verification_store = password_reset.EmailVerificationStore()
        reset_store = password_reset.PasswordResetStore()
        token = verification_store.issue(
            "account-1",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        request = self.request("/api/auth/verify-reset-email")
        request.session.update({"user_id": "account-1", "sid": "existing-session"})
        mailer = _FakeMailer(error=email_smtp.SmtpSendError("synthetic SMTP failure"))
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", verification_store),
            patch.object(server, "password_reset_store", reset_store),
            patch.object(server, "email_sender", mailer),
            patch.object(server.user_store, "verify_password_reset_email"),
            patch.object(
                server.user_store,
                "get_by_id",
                return_value=type("User", (), {"email": "user@example.com"})(),
            ),
            patch.object(server.user_store, "reset_password_and_invalidate_sessions") as update_password,
            patch.object(server.session_store, "revoke_user") as revoke_user,
        ):
            result = server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                request,
                _csrf=None,
            )

        self.assertEqual(result, server._email_verification_generic_response())
        self.assertIsNone(verification_store.claim(token))
        self.assertEqual(reset_store._tokens, {})
        self.assertEqual(request.session, {"user_id": "account-1", "sid": "existing-session"})
        update_password.assert_not_called()
        revoke_user.assert_not_called()

    def test_password_policy_error_does_not_claim_reset_token(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        with (
            patch.object(server, "password_reset_store", store),
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(token=token, password="short"),
                self.request("/api/auth/reset-password"),
                _csrf=None,
            )
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(store.peek_user_id(token), "account-1")

    def test_rate_limit_checks_ip_and_email_before_account_lookup(self):
        with (
            patch.object(
                server.request_throttle,
                "allow",
                side_effect=[True, False],
            ) as allow,
            patch.object(server.user_store, "get_password_reset_account") as lookup,
            self.assertRaises(HTTPException) as raised,
        ):
            server.forgot_password(
                server.ForgotPasswordRequest(email="user@example.com"),
                self.request("/api/auth/forgot-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(allow.call_count, 2)
        lookup.assert_not_called()

    def test_database_failure_releases_claim_for_retry(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(
                server.user_store,
                "reset_password_and_invalidate_sessions",
                side_effect=SQLAlchemyError("synthetic database outage"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="new-password-123",
                ),
                self.request("/api/auth/reset-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("database_update", "password_update_failed"),),
            (token, "new-password-123", "synthetic database outage"),
        )
        retry_claim = store.claim(token)
        self.assertIsNotNone(retry_claim)
        self.assertTrue(store.release(token, retry_claim))

    def test_reset_database_failure_and_claim_release_failure_are_diagnosed(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(
                server.user_store,
                "reset_password_and_invalidate_sessions",
                side_effect=SQLAlchemyError("sensitive database exception detail"),
            ),
            patch.object(
                store,
                "release",
                side_effect=RuntimeError("sensitive token-store exception detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="sensitive-password-123",
                ),
                self.request("/api/auth/reset-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, request a new reset link if needed",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (
                ("database_update", "password_update_failed"),
                ("token_storage", "claim_release_failed"),
            ),
            (
                token,
                "sensitive-password-123",
                "sensitive database exception detail",
                "sensitive token-store exception detail",
            ),
        )

    def test_verification_claim_release_returning_false_is_diagnosed(self):
        store = password_reset.EmailVerificationStore()
        token = store.issue("account-1", binding="invalid-binding")
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", store),
            patch.object(store, "release", return_value=False),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "claim_release_failed"),),
            (token, "account-1", "invalid-binding"),
        )

    def test_verification_database_failure_releases_claim_and_is_diagnosed(self):
        store = password_reset.EmailVerificationStore()
        token = store.issue(
            "account-1",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", store),
            patch.object(
                server.user_store,
                "verify_password_reset_email",
                side_effect=SQLAlchemyError("sensitive verification database detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("database_update", "email_verification_update_failed"),),
            (token, "user@example.com", "sensitive verification database detail"),
        )
        claim = store.claim(token)
        self.assertIsNotNone(claim)
        self.assertTrue(store.release(token, claim))

    def test_verification_uncertain_database_commit_is_diagnosed(self):
        store = password_reset.EmailVerificationStore()
        token = store.issue(
            "account-1",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", store),
            patch.object(
                server.user_store,
                "verify_password_reset_email",
                side_effect=auth.PasswordResetCommitUncertain(
                    "sensitive uncertain-commit detail"
                ),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable; verification may have completed",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("database_update", "email_verification_commit_uncertain"),),
            (token, "user@example.com", "sensitive uncertain-commit detail"),
        )
        self.assertIsNone(store.claim(token))

    def test_ambiguous_database_commit_keeps_token_unreplayable(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(
                server.user_store,
                "reset_password_and_invalidate_sessions",
                side_effect=auth.PasswordResetCommitUncertain("unknown commit result"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="new-password-123",
                ),
                self.request("/api/auth/reset-password"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, request a new reset link if needed",
        )
        self.assert_diagnostics(
            diagnostics.records,
            (("database_update", "password_commit_uncertain"),),
            (token, "new-password-123", "unknown commit result"),
        )
        self.assertIsNone(store.claim(token))

    def test_success_commits_token_and_revokes_sessions_without_logging_in(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        request = self.request("/api/auth/reset-password")
        request.session.update({"user_id": "account-1", "sid": "old-session"})
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(
                server.user_store,
                "reset_password_and_invalidate_sessions",
                return_value=5,
            ) as update_password,
            patch.object(server.session_store, "revoke_user") as revoke_user,
        ):
            result = server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="new-password-123",
                ),
                request,
                _csrf=None,
            )

        self.assertTrue(result["ok"])
        update_password.assert_called_once_with("account-1", "new-password-123")
        revoke_user.assert_called_once_with("account-1")
        self.assertNotIn("user_id", request.session)
        self.assertIsNone(store.claim(token))

    def test_session_revocation_failure_is_diagnosed(self):
        store = password_reset.PasswordResetStore()
        token = store.issue("account-1")
        request = self.request("/api/auth/reset-password")
        request.session.update({"user_id": "account-1", "sid": "existing-session"})
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "password_reset_store", store),
            patch.object(
                server.user_store,
                "reset_password_and_invalidate_sessions",
                return_value=5,
            ),
            patch.object(
                server.session_store,
                "revoke_user",
                side_effect=RuntimeError("sensitive session-store exception detail"),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.reset_password(
                server.ResetPasswordRequest(
                    token=token,
                    password="sensitive-password-123",
                ),
                request,
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assertEqual(request.session, {"user_id": "account-1", "sid": "existing-session"})
        self.assertIsNone(store.claim(token))
        self.assert_diagnostics(
            diagnostics.records,
            (("session_revocation", "user_session_revoke_failed"),),
            (
                token,
                "sensitive-password-123",
                "account-1",
                "sensitive session-store exception detail",
            ),
        )

    def test_post_verification_reset_token_issue_failure_is_diagnosed(self):
        verification_store = password_reset.EmailVerificationStore()
        token = verification_store.issue(
            "account-1",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", verification_store),
            patch.object(
                server,
                "password_reset_store",
                password_reset.PasswordResetStore(),
            ),
            patch.object(
                server.password_reset_store,
                "issue",
                side_effect=RuntimeError("sensitive reset-token issue detail"),
            ),
            patch.object(server.user_store, "verify_password_reset_email"),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assertIsNone(verification_store.claim(token))
        self.assert_diagnostics(
            diagnostics.records,
            (("token_storage", "reset_token_issue_failed"),),
            (token, "user@example.com", "sensitive reset-token issue detail"),
        )

    def test_post_verification_account_lookup_failure_and_token_cleanup_are_diagnosed(self):
        verification_store = password_reset.EmailVerificationStore()
        reset_store = password_reset.PasswordResetStore()
        verification_token = verification_store.issue(
            "account-1",
            binding=hashlib.sha256(b"user@example.com").hexdigest(),
        )
        reset_token = reset_store.issue("account-1")
        with (
            patch.object(server.request_throttle, "allow", return_value=True),
            patch.object(server, "email_verification_store", verification_store),
            patch.object(server, "password_reset_store", reset_store),
            patch.object(reset_store, "issue", return_value=reset_token),
            patch.object(
                server.user_store,
                "verify_password_reset_email",
            ),
            patch.object(
                server.user_store,
                "get_by_id",
                side_effect=SQLAlchemyError(
                    "sensitive database lookup for user@example.com"
                ),
            ),
            self.assertLogs("vervfy.password_reset", level="WARNING") as diagnostics,
            self.assertRaises(HTTPException) as raised,
        ):
            server.verify_reset_email(
                server.VerifyResetEmailRequest(token=verification_token),
                self.request("/api/auth/verify-reset-email"),
                _csrf=None,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail,
            "Service temporarily unavailable, try again shortly",
        )
        self.assertIsNone(verification_store.claim(verification_token))
        self.assertIsNone(reset_store.peek_user_id(reset_token))
        self.assert_diagnostics(
            diagnostics.records,
            (("database_lookup", "verified_account_lookup_failed"),),
            (
                verification_token,
                reset_token,
                "user@example.com",
                "account-1",
                "sensitive database lookup for user@example.com",
            ),
        )


class EmailSenderTests(unittest.TestCase):
    def test_reset_links_use_fragments_and_in_memory_transport(self):
        transport = email_smtp.MemoryTransport()
        sender = email_smtp.EmailSender(transport)
        token = "synthetic-token"
        with (
            patch.dict(
                "os.environ",
                {
                    "VERVFY_EMAIL_FROM": "Vervfy <no-reply@example.test>",
                    "FRONTEND_URL": "https://vervfy-one.vercel.app",
                    "VERVFY_ENVIRONMENT": "test",
                },
            )
        ):
            sender.send_password_reset(to_email="user@example.test", token=token)
            sender.send_email_verification(to_email="user@example.test", token=token)

        bodies = [message.get_body(preferencelist=("plain",)).get_content() for message in transport.messages]
        self.assertIn(
            f"https://vervfy-one.vercel.app/reset-password#token={token}", bodies[0]
        )
        self.assertIn(
            f"https://vervfy-one.vercel.app/reset-password#verify={token}", bodies[1]
        )
        self.assertIn("request to verify this email address", bodies[1])
        self.assertNotIn("password-reset request", bodies[1])

    def test_production_origins_require_https(self):
        with patch.dict(
            "os.environ",
            {
                "VERVFY_ENVIRONMENT": "production",
                "FRONTEND_URL": "http://vervfy-one.vercel.app",
            },
            clear=True,
        ), self.assertRaises(email_smtp.SmtpConfigError):
            email_smtp.public_app_origin()

        with patch.dict(
            "os.environ",
            {
                "VERVFY_ENVIRONMENT": "production",
                "FRONTEND_URL": "https://vervfy-one.vercel.app",
            },
            clear=True,
        ):
            self.assertEqual(
                email_smtp.public_app_origin(),
                "https://vervfy-one.vercel.app",
            )

    def test_production_smtp_requires_authenticated_starttls_on_587(self):
        settings = email_smtp.SmtpSettings(
            host="in-v3.mailjet.com",
            port=587,
            username="synthetic-api-key",
            password="synthetic-secret",
            mail_from="vervfy.dev@proton.me",
        )
        with patch.dict("os.environ", {"VERVFY_ENVIRONMENT": "production"}, clear=True):
            settings.require_ready()
            self.assertTrue(settings.use_starttls)

            for invalid_settings in (
                email_smtp.SmtpSettings(
                    host="in-v3.mailjet.com",
                    port=587,
                    username="",
                    password="",
                    mail_from="vervfy.dev@proton.me",
                ),
                email_smtp.SmtpSettings(
                    host="in-v3.mailjet.com",
                    port=465,
                    username="synthetic-api-key",
                    password="synthetic-secret",
                    mail_from="vervfy.dev@proton.me",
                ),
            ):
                with self.assertRaises(email_smtp.SmtpConfigError):
                    invalid_settings.require_ready()

    def test_smtp_failure_logs_never_include_reset_token(self):
        token = "synthetic-token-do-not-log"
        transport = email_smtp.MemoryTransport()
        transport.fail_with = email_smtp.SmtpSendError("synthetic SMTP failure")
        sender = email_smtp.EmailSender(transport)
        with (
            patch.dict(
                "os.environ",
                {
                    "VERVFY_EMAIL_FROM": "vervfy.dev@proton.me",
                    "FRONTEND_URL": "https://vervfy-one.vercel.app",
                    "VERVFY_ENVIRONMENT": "test",
                },
            ),
            self.assertLogs("vervfy.email", level="WARNING") as captured,
            self.assertRaises(email_smtp.SmtpSendError),
        ):
            sender.send_password_reset(
                to_email="user@example.test",
                token=token,
            )

        self.assertNotIn(token, "\n".join(captured.output))

    def test_resend_test_sender_requires_explicit_nonproduction_environment(self):
        settings = email_smtp.SmtpSettings(
            host="smtp.example.test",
            mail_from="Vervfy <onboarding@resend.dev>",
        )
        for environment in ("", "production", "unknown"):
            with self.subTest(environment=environment), patch.dict(
                "os.environ", {"VERVFY_ENVIRONMENT": environment}, clear=True
            ), self.assertRaises(email_smtp.SmtpConfigError):
                settings.require_ready()

        for environment in ("development", "local", "local-test", "staging", "test"):
            with self.subTest(environment=environment), patch.dict(
                "os.environ", {"VERVFY_ENVIRONMENT": environment}, clear=True
            ):
                settings.require_ready()


class _FakeMailer:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.reset_tokens: list[str] = []
        self.verification_tokens: list[str] = []

    def send_password_reset(self, *, to_email: str, token: str) -> None:
        if self.error:
            raise self.error
        self.reset_tokens.append(token)

    def send_email_verification(self, *, to_email: str, token: str) -> None:
        if self.error:
            raise self.error
        self.verification_tokens.append(token)


if __name__ == "__main__":
    unittest.main()
