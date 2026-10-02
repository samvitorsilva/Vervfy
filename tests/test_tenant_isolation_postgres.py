"""PostgreSQL RLS integration test; set VERVFY_TEST_POSTGRES_URL to run."""
import importlib
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture
def postgres_app(monkeypatch):
    database_url = os.environ.get("VERVFY_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("set VERVFY_TEST_POSTGRES_URL to run the PostgreSQL RLS integration test")

    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    admin_engine = create_engine(url)
    with admin_engine.connect() as connection:
        is_superuser, bypasses_rls = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user"
            )
        ).one()
    if is_superuser or bypasses_rls:
        admin_engine.dispose()
        pytest.fail("VERVFY_TEST_POSTGRES_URL must use a role that is not superuser or BYPASSRLS")

    schema = f"vervfy_test_{uuid.uuid4().hex}"
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    query = dict(url.query)
    query["options"] = f"-csearch_path={schema}"
    app_database_url = str(url.set(query=query))
    monkeypatch.setenv("DATABASE_URL", app_database_url)
    monkeypatch.setenv("VERVFY_SECRET_KEY", "postgres-rls-test-secret")
    monkeypatch.delenv("VERVFY_ENVIRONMENT", raising=False)
    for name in ("server", "auth", "db", "database", "library", "audio_store", "upload_queue"):
        sys.modules.pop(name, None)

    server = None
    try:
        server = importlib.import_module("server")
        with TestClient(server.app) as client:
            with server.engine.begin() as connection:
                for table in ("tracks", "favorites", "playlists", "playlist_tracks"):
                    connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                    connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
                    if table != "playlist_tracks":
                        connection.execute(text(
                            f"CREATE POLICY {table}_tenant_isolation ON {table} "
                            "USING (user_id = current_setting('app.current_user_id', true)) "
                            "WITH CHECK (user_id = current_setting('app.current_user_id', true))"
                        ))
                connection.execute(text("""
                    CREATE POLICY playlist_tracks_tenant_isolation ON playlist_tracks
                    USING (
                        EXISTS (
                            SELECT 1 FROM playlists
                            WHERE playlists.id = playlist_tracks.playlist_id
                              AND playlists.user_id = current_setting('app.current_user_id', true)
                        )
                    )
                    WITH CHECK (
                        EXISTS (
                            SELECT 1 FROM playlists
                            WHERE playlists.id = playlist_tracks.playlist_id
                              AND playlists.user_id = current_setting('app.current_user_id', true)
                        )
                    )
                """))
            yield server, client
    finally:
        if server is not None:
            server.engine.dispose()
        for name in ("server", "auth", "db", "database", "library", "audio_store", "upload_queue"):
            sys.modules.pop(name, None)
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _login(client, username, password):
    csrf_token = client.get("/api/csrf").json()["csrf_token"]
    response = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_tracks_are_isolated_by_postgres_rls_for_each_logged_in_user(postgres_app):
    server, client_a = postgres_app
    server.user_store.create_user("tenant-a", None, "password-a")
    server.user_store.create_user("tenant-b", None, "password-b")
    user_a = server.user_store.get_by_username("tenant-a")
    user_b = server.user_store.get_by_username("tenant-b")

    expected_ids = {
        user_a["id"]: {f"{user_a['id']}-track-{index}" for index in range(3)},
        user_b["id"]: {f"{user_b['id']}-track-0"},
    }
    for user_id, track_ids in expected_ids.items():
        with server.tenant_session(user_id) as session:
            for track_id in track_ids:
                session.add(server.TrackRecord(
                    id=track_id,
                    user_id=user_id,
                    filename=f"{track_id}.wav",
                    title=track_id,
                    artist="Test Artist",
                    album="Test Album",
                    duration=1,
                    has_cover=False,
                    size_bytes=1,
                    audio_data=b"x",
                    cover_data=b"",
                ))
            session.commit()

    _login(client_a, "tenant-a", "password-a")
    with TestClient(server.app) as client_b:
        _login(client_b, "tenant-b", "password-b")
        response_a = client_a.get("/api/tracks")
        response_b = client_b.get("/api/tracks")
        assert response_a.status_code == response_b.status_code == 200
        tracks_a = {track["id"] for track in response_a.json()["tracks"]}
        tracks_b = {track["id"] for track in response_b.json()["tracks"]}
        assert len(tracks_a) == 3
        assert len(tracks_b) == 1
        assert tracks_a == expected_ids[user_a["id"]]
        assert tracks_b == expected_ids[user_b["id"]]

        track_a = sorted(tracks_a)[0]
        headers_a = {
            "X-CSRF-Token": client_a.get("/api/csrf").json()["csrf_token"],
            "If-Match": client_a.get("/api/library/state").headers["etag"],
        }
        saved_state = client_a.put(
            "/api/library/state",
            headers=headers_a,
            json={
                "favorites": [track_a],
                "playlists": [{"id": "tenant-a-list", "name": "A's list", "trackIds": [track_a]}],
            },
        )
        assert saved_state.status_code == 200
        assert client_a.get("/api/library/state").json()["favorites"] == [track_a]
        assert client_b.get("/api/library/state").json() == {"favorites": [], "playlists": []}
        assert client_a.get("/api/library/usage").json()["track_count"] == 3
        assert client_b.get("/api/library/usage").json()["track_count"] == 1
        assert client_a.get(f"/api/tracks/{track_a}/stream").content == b"x"
        assert client_b.get(f"/api/tracks/{track_a}/stream").status_code == 404
        assert client_a.get(f"/api/tracks/{track_a}/cover").status_code == 200
        assert client_b.get(f"/api/tracks/{track_a}/cover").status_code == 404
