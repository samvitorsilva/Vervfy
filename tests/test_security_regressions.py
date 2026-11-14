from __future__ import annotations

import asyncio
import os
import unittest
from contextlib import nullcontext
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from starlette.responses import Response

import audio_store
import server
from auth import SessionStore
from db import (
    ArtistPhoto,
    Base,
    Favorite,
    Playlist,
    PlaylistTrack,
    TrackListen,
    TrackRecord,
    UploadJob,
    User,
)
from library import track_id_for_bytes


class SessionStoreTests(unittest.TestCase):
    def test_revoked_session_is_not_valid(self) -> None:
        store = SessionStore()
        session_id = store.create("user-a")

        self.assertTrue(store.is_valid(session_id, "user-a"))
        self.assertFalse(store.is_valid(session_id, "user-b"))
        store.revoke(session_id)
        self.assertFalse(store.is_valid(session_id, "user-a"))

    def test_revoke_user_invalidates_only_that_users_sessions(self) -> None:
        store = SessionStore()
        deleted_user_sessions = [
            store.create("deleted-user"),
            store.create("deleted-user"),
        ]
        other_user_session = store.create("other-user")

        store.revoke_user("deleted-user")

        self.assertTrue(
            all(
                not store.is_valid(session_id, "deleted-user")
                for session_id in deleted_user_sessions
            )
        )
        self.assertTrue(store.is_valid(other_user_session, "other-user"))

    def test_redis_create_session_sets_expiry_and_user_index(self) -> None:
        store = SessionStore()
        redis_client = MagicMock()
        store._redis = redis_client

        session_id = store.create("user-a")

        redis_client.eval.assert_called_once_with(
            server.auth._CREATE_SESSION_SCRIPT,
            2,
            f"{store.KEY_PREFIX}{session_id}",
            f"{store.USER_SESSIONS_PREFIX}user-a",
            "user-a",
            store.TTL_SECONDS,
            session_id,
        )

    def test_redis_revoke_user_cleans_indexed_and_pre_index_sessions(self) -> None:
        store = SessionStore()
        redis_client = MagicMock()
        user_session_key = f"{store.KEY_PREFIX}legacy-session"
        other_session_key = f"{store.KEY_PREFIX}other-session"
        redis_client.scan_iter.return_value = [user_session_key, other_session_key]
        redis_client.get.side_effect = lambda key: {
            user_session_key: "deleted-user",
            other_session_key: "other-user",
        }[key]
        store._redis = redis_client

        store.revoke_user("deleted-user")

        redis_client.eval.assert_any_call(
            server.auth._REVOKE_SESSION_SCRIPT,
            1,
            user_session_key,
            store.USER_SESSIONS_PREFIX,
            "legacy-session",
        )
        redis_client.eval.assert_called_with(
            server.auth._REVOKE_USER_SESSIONS_SCRIPT,
            1,
            f"{store.USER_SESSIONS_PREFIX}deleted-user",
            store.KEY_PREFIX,
        )
        self.assertEqual(redis_client.eval.call_count, 2)

    def test_redis_revoke_user_surfaces_backend_failure(self) -> None:
        store = SessionStore()
        redis_client = MagicMock()
        redis_client.scan_iter.return_value = []
        redis_client.eval.side_effect = OSError("Redis unavailable")
        store._redis = redis_client

        with (
            patch.object(server.auth, "redis", SimpleNamespace(RedisError=OSError)),
            self.assertRaisesRegex(RuntimeError, "session backend unavailable"),
        ):
            store.revoke_user("deleted-user")

    def test_logout_rejects_invalid_csrf_for_an_active_session(self) -> None:
        request = type("Request", (), {"session": {"sid": "active"}, "headers": {}})()
        with patch.object(
            server.auth,
            "verify_csrf",
            side_effect=HTTPException(status_code=403),
        ), self.assertRaises(HTTPException):
            server.logout(request, "stale-token")

    def test_logout_remains_idempotent_without_an_active_session(self) -> None:
        request = type("Request", (), {"session": {}, "headers": {}})()
        response = server.logout(request, "stale-token")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session, {})

    def test_logout_all_bumps_session_version_and_clears_current_session(self) -> None:
        user_id = "logout-all-user"
        request = SimpleNamespace(session={"user_id": user_id, "sid": "active", "sv": 2})

        with (
            patch.object(server, "verify_current_password"),
            patch.object(server.user_store, "bump_session_version", return_value=3) as bump,
            patch.object(server.session_store, "revoke_user") as revoke,
        ):
            response = server.logout_all(
                server.LogoutAllRequest(current_password="current"),
                request,
                {"id": user_id, "password_hash": "hash"},
                _csrf=None,
            )

        self.assertEqual(response, {"ok": True})
        self.assertEqual(request.session, {})
        bump.assert_called_once_with(user_id)
        revoke.assert_called_once_with(user_id)

    def test_current_user_rejects_stale_session_version_before_store_lookup(self) -> None:
        request = SimpleNamespace(
            session={"user_id": "versioned-user", "sid": "stale-session", "sv": 2}
        )
        current_user = {"id": "versioned-user", "session_version": 3}

        with (
            patch.object(server.user_store, "get_by_id", return_value=current_user),
            patch.object(server.session_store, "is_valid") as is_valid,
        ):
            self.assertIsNone(server.current_user_row(request))

        self.assertEqual(request.session, {})
        is_valid.assert_not_called()

    def test_account_deletion_enqueues_storage_cleanup_without_direct_deletion(self) -> None:
        user_id = "storage-cleanup-user"
        session = MagicMock()
        session.scalar = lambda *_args, **_kwargs: user_id
        request = SimpleNamespace(
            session={"sid": "active"},
            app=SimpleNamespace(state=SimpleNamespace(is_first_account=False)),
        )
        with (
            patch.object(server, "tenant_session", return_value=nullcontext(session)),
            patch.object(server, "verify_current_password"),
            patch.object(server.user_store, "bump_session_version", return_value=1),
            patch.object(server.session_store, "revoke_user"),
            patch.object(server.audio_store, "delete_many") as delete_many,
            patch.object(server.user_store, "count", return_value=0),
        ):
            result = server.delete_account(
                server.AccountDeletionRequest(
                    current_password="test-password",
                    confirmation="DELETE",
                ),
                request,
                {"id": user_id, "password_hash": "hash"},
            )

        self.assertEqual(result, {"ok": True, "storage_cleanup": "pending"})
        delete_many.assert_not_called()

    def test_account_deletion_removes_account_rows_without_relying_on_cascades(self) -> None:
        user_id = "delete-integration-user"
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with sessions() as session:
                session.add(
                    User(
                        id=user_id,
                        username="delete-user",
                        username_key="delete-user",
                        password_hash="hash",
                        created_at=1,
                    )
                )
                other_user_id = "untouched-account-user"
                session.add(
                    User(
                        id=other_user_id,
                        username="untouched-user",
                        username_key="untouched-user",
                        password_hash="hash",
                        created_at=1,
                    )
                )
                session.add(
                    TrackRecord(
                        id="delete-track",
                        user_id=user_id,
                        filename="track.mp3",
                        title="Title",
                        artist="Artist",
                        album="Album",
                        duration=60,
                        has_cover=True,
                        custom_lyrics="saved lyrics",
                        audio_data=b"audio",
                        storage_path=f"{user_id}/track.mp3",
                        size_bytes=5,
                        cover_data=b"cover",
                        cover_path=f"covers/{user_id}/track.jpg",
                    )
                )
                session.add(
                    TrackRecord(
                        id="untouched-track",
                        user_id=other_user_id,
                        filename="other.mp3",
                        title="Other title",
                        artist="Other artist",
                        album="Other album",
                        duration=60,
                        has_cover=False,
                        storage_path=f"{other_user_id}/other.mp3",
                        size_bytes=5,
                    )
                )
                session.add(
                    ArtistPhoto(
                        user_id=user_id,
                        normalized_artist_name="artist",
                        jpeg_data=b"photo",
                        storage_path=f"artist-photos/{user_id}/artist/photo.jpg",
                        source="user",
                    )
                )
                session.add(
                    Playlist(id="delete-playlist", user_id=user_id, name="Playlist")
                )
                session.add(
                    PlaylistTrack(
                        playlist_id="delete-playlist",
                        track_id="delete-track",
                        position=0,
                    )
                )
                session.add(Favorite(user_id=user_id, track_id="delete-track"))
                session.add(
                    TrackListen(
                        id="delete-listen",
                        user_id=user_id,
                        track_id="delete-track",
                        played_at=1,
                    )
                )
                session.add(
                    UploadJob(
                        id="delete-job",
                        user_id=user_id,
                        filename="track.mp3",
                        storage_path=f"{user_id}/.staging/upload.mp3",
                        created_at=1,
                    )
                )
                session.commit()

            request = SimpleNamespace(
                session={"sid": "active"},
                app=SimpleNamespace(state=SimpleNamespace(is_first_account=False)),
            )
            with (
                patch.object(server, "tenant_session", side_effect=lambda _user_id: sessions()),
                patch.object(server, "verify_current_password"),
                patch.object(server.user_store, "bump_session_version", return_value=1),
                patch.object(server.session_store, "revoke_user") as revoke_user,
                patch.object(server.audio_store, "delete_many") as delete_many,
                patch.object(server.user_store, "count", return_value=1),
            ):
                result = server.delete_account(
                    server.AccountDeletionRequest(
                        current_password="test-password",
                        confirmation="DELETE",
                    ),
                    request,
                    {"id": user_id, "password_hash": "hash"},
                )

            self.assertEqual(result, {"ok": True, "storage_cleanup": "pending"})
            revoke_user.assert_called_once_with(user_id)
            self.assertEqual(request.session, {})
            delete_many.assert_not_called()
            with sessions() as session:
                expected_counts = {
                    User: 1,
                    TrackRecord: 1,
                    ArtistPhoto: 0,
                    Playlist: 0,
                    PlaylistTrack: 0,
                    Favorite: 0,
                    TrackListen: 0,
                    UploadJob: 0,
                }
                for model, count in expected_counts.items():
                    self.assertEqual(session.query(model).count(), count, model.__name__)
                self.assertEqual(
                    session.query(TrackRecord)
                    .filter_by(user_id=other_user_id)
                    .one()
                    .storage_path,
                    f"{other_user_id}/other.mp3",
                )
        finally:
            engine.dispose()

    def test_account_deletion_fails_closed_when_session_revocation_fails(self) -> None:
        request = SimpleNamespace(
            session={"sid": "active"},
            app=SimpleNamespace(state=SimpleNamespace(is_first_account=False)),
        )
        with (
            patch.object(server, "verify_current_password"),
            patch.object(server.user_store, "bump_session_version", return_value=1),
            patch.object(
                server.session_store,
                "revoke_user",
                side_effect=RuntimeError("session backend unavailable"),
            ),
            patch.object(server, "tenant_session") as tenant_session,
            patch.object(server.audio_store, "delete_many") as delete_many,
            self.assertRaises(HTTPException) as raised,
        ):
            server.delete_account(
                server.AccountDeletionRequest(
                    current_password="test-password",
                    confirmation="DELETE",
                ),
                request,
                {"id": "delete-user", "password_hash": "hash"},
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("deletion was not completed", raised.exception.detail)
        tenant_session.assert_not_called()
        delete_many.assert_not_called()

    def test_account_deletion_reports_database_failure_without_storage_deletion(self) -> None:
        user_id = "partial-delete-user"
        session = MagicMock()
        session.scalar.return_value = user_id
        session.scalars.return_value.all.return_value = []
        request = SimpleNamespace(
            session={"sid": "active"},
            app=SimpleNamespace(state=SimpleNamespace(is_first_account=False)),
        )

        with (
            patch.object(server, "tenant_session", return_value=nullcontext(session)),
            patch.object(server, "verify_current_password"),
            patch.object(server.user_store, "bump_session_version", return_value=1),
            patch.object(server.session_store, "revoke_user"),
            patch.object(server.user_store, "count", return_value=1),
            patch.object(server.audio_store, "delete_many") as delete_many,
        ):
            session.commit.side_effect = SQLAlchemyError("database unavailable")
            with self.assertRaises(HTTPException) as raised:
                server.delete_account(
                    server.AccountDeletionRequest(
                        current_password="test-password",
                        confirmation="DELETE",
                    ),
                    request,
                    {"id": user_id, "password_hash": "hash"},
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("sign in again and retry deletion", raised.exception.detail)
        delete_many.assert_not_called()
        session.commit.assert_called_once()
        self.assertEqual(request.session, {"sid": "active"})


class TrackIdentityTests(unittest.TestCase):
    def test_identity_includes_bytes_between_the_old_sample_windows(self) -> None:
        first = b"a" * 65_536 + b"x" + b"b" * 65_536
        second = b"a" * 65_536 + b"y" + b"b" * 65_536

        self.assertNotEqual(track_id_for_bytes(first), track_id_for_bytes(second))


class StorageRangeTests(unittest.TestCase):
    def tearDown(self) -> None:
        audio_store.close_client()

    def test_bulk_delete_is_retired_without_storage_access(self) -> None:
        with patch.object(audio_store, "_client") as client:
            with self.assertRaises(audio_store.StorageError):
                audio_store.delete_many([])

        client.assert_not_called()

    def test_read_range_slices_streaming_response_when_storage_ignores_range(self) -> None:
        body = bytes(range(256)) * 1024

        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["range"], "bytes=100000-100099")
            return httpx.Response(200, content=body)

        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://project.supabase.co",
                    "SUPABASE_SERVICE_KEY": "test-key",
                    "SUPABASE_BUCKET": "songs",
                },
            ),
            patch.object(audio_store, "_transport", httpx.MockTransport(respond)),
        ):
            self.assertEqual(
                audio_store.read_range("user/track.mp3", 100_000, 100_099),
                body[100_000:100_100],
            )


class ApiResponseCacheTests(unittest.TestCase):
    def test_api_get_responses_are_not_cached_between_account_sessions(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/account/photo",
                "query_string": b"",
                "headers": [],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
                "http_version": "1.1",
            }
        )

        async def call_next(_request):
            return Response(headers={"Cache-Control": "private, max-age=86400"})

        response = asyncio.run(server.add_security_headers(request, call_next))
        self.assertEqual(response.headers["cache-control"], "private, no-store")


class HealthCheckTests(unittest.TestCase):
    def test_public_health_check_is_available_without_database_access(self) -> None:
        response = server.healthz()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"ok")
        self.assertEqual(response.headers["cache-control"], "no-store")


class ProfilePhotoValidationTests(unittest.TestCase):
    def test_rejects_images_exceeding_pixel_limit(self) -> None:
        output = BytesIO()
        Image.new("RGB", (3600, 3600)).save(output, format="JPEG")

        with self.assertRaises(HTTPException) as raised:
            server._validate_profile_photo(output.getvalue())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("dimensions", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
