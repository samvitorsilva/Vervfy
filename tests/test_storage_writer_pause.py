import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("VERVFY_SECRET_KEY", "test-only-vervfy-session-secret")

import auth
import cover_art
import library
import server
import storage_lifecycle
from scripts.upload_worker import process


class StorageWriterPauseTests(unittest.TestCase):
    def test_pause_setting_fails_closed(self) -> None:
        with patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "0"}):
            storage_lifecycle.require_storage_writes_enabled()
        for value in ("1", "invalid"):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": value}),
                self.assertRaises(storage_lifecycle.StorageWritersPaused),
            ):
                storage_lifecycle.require_storage_writes_enabled()

    def test_upload_api_rejects_paused_writes_before_library_mutation(self) -> None:
        original_overrides = dict(server.app.dependency_overrides)
        server.app.dependency_overrides.clear()
        server.app.dependency_overrides[server.require_api_user] = lambda: {
            "id": "user-a"
        }
        server.app.dependency_overrides[auth.verify_api_csrf] = lambda: None
        self.addCleanup(
            lambda: (
                server.app.dependency_overrides.clear(),
                server.app.dependency_overrides.update(original_overrides),
            )
        )

        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            patch.object(server, "get_library") as get_library,
        ):
            response = TestClient(server.app).post(
                "/api/library/upload",
                files={"file": ("sample.mp3", b"audio", "audio/mpeg")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], "60")
        get_library.assert_not_called()

    def test_inline_upload_is_blocked_before_database_fallback(self) -> None:
        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            patch.object(library, "tenant_session") as tenant_session,
            self.assertRaises(storage_lifecycle.StorageWritersPaused),
        ):
            library.Library("user-a").add_upload_file(
                "sample.mp3", "/not-read-while-paused.mp3"
            )
        tenant_session.assert_not_called()

    def test_managed_upload_is_blocked_before_tempfile_or_reservation(self) -> None:
        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            patch.object(storage_lifecycle.tempfile, "NamedTemporaryFile") as temp_file,
            patch.object(storage_lifecycle, "_reserve") as reserve,
            self.assertRaises(storage_lifecycle.StorageWritersPaused),
        ):
            storage_lifecycle.upload_bytes("user-a", "track-cover", b"image")
        temp_file.assert_not_called()
        reserve.assert_not_called()

    def test_upload_worker_leaves_jobs_unclaimed_while_paused(self) -> None:
        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            patch("scripts.upload_worker.tenant_session") as tenant_session,
        ):
            self.assertFalse(process("job-a", "user-a"))
        tenant_session.assert_not_called()

    def test_cover_resolution_does_not_schedule_or_read_while_paused(self) -> None:
        tasks = MagicMock()
        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            patch.object(library, "Library") as library_class,
        ):
            self.assertFalse(
                cover_art.schedule_cover_resolution(tasks, "user-a", "track-a")
            )
            asyncio.run(cover_art.resolve_cover("user-a", "track-a"))

        tasks.add_task.assert_not_called()
        library_class.assert_not_called()

    def test_login_still_issues_session_while_writes_are_paused(self) -> None:
        password_hash = auth.hash_password("existing-password")
        request = SimpleNamespace(
            session={"csrf_token": "csrf"},
            client=None,
        )
        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            patch.object(
                server.user_store,
                "get_by_username",
                return_value={
                    "id": "user-a",
                    "password_hash": password_hash,
                    "session_version": 1,
                },
            ),
            patch.object(server.auth, "client_ip", return_value="127.0.0.1"),
            patch.object(server.login_throttle, "is_locked", return_value=False),
            patch.object(server.login_throttle, "clear"),
            patch.object(server.session_store, "create", return_value="fresh"),
        ):
            response = server.login_submit(
                request, "existing", "existing-password", "csrf"
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["sid"], "fresh")

    def test_api_pause_dependency_returns_retryable_unavailable(self) -> None:
        with (
            patch.dict(os.environ, {"VERVFY_STORAGE_WRITES_PAUSED": "1"}),
            self.assertRaises(HTTPException) as caught,
        ):
            server.require_storage_writes_enabled()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.headers["Retry-After"], "60")
