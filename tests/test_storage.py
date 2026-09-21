"""Audio lives in Supabase Storage; Postgres only keeps the object path.

Supabase is replaced by an in-memory fake behind ``httpx.MockTransport``.
"""
import importlib
import importlib.util
import io
import re
import sys
import wave
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]


class FakeSupabase:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.bytes_served = 0
        self.fail_uploads = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != "Bearer service-key":
            return httpx.Response(401, json={"error": "unauthorized"})
        path = unquote(request.url.path)
        prefix = "/storage/v1"
        assert path.startswith(prefix), path
        path = path[len(prefix):]
        if path == "/bucket/songs" and request.method == "GET":
            return httpx.Response(200, json={"id": "songs"})
        if path == "/object/songs" and request.method == "DELETE":
            import json
            for key in json.loads(request.content)["prefixes"]:
                self.objects.pop(key, None)
            return httpx.Response(200, json=[])
        if path.startswith("/object/authenticated/songs/") and request.method == "GET":
            key = path[len("/object/authenticated/songs/"):]
            if key not in self.objects:
                return httpx.Response(400, json={"error": "not_found"})
            data = self.objects[key]
            spec = request.headers.get("range")
            if not spec:
                self.bytes_served += len(data)
                return httpx.Response(200, content=data)
            start, end = re.fullmatch(r"bytes=(\d+)-(\d+)", spec).groups()
            start, end = int(start), min(int(end), len(data) - 1)
            chunk = data[start : end + 1]
            self.bytes_served += len(chunk)
            return httpx.Response(206, content=chunk, headers={"Content-Range": f"bytes {start}-{end}/{len(data)}"})
        if path.startswith("/object/songs/"):
            key = path[len("/object/songs/"):]
            if request.method == "POST":
                if self.fail_uploads:
                    return httpx.Response(500, json={"error": "boom"})
                self.objects[key] = request.content
                return httpx.Response(200, json={"Key": f"songs/{key}"})
            if request.method == "DELETE":
                if self.objects.pop(key, None) is None:
                    return httpx.Response(404, json={"error": "not_found"})
                return httpx.Response(200, json={})
        raise AssertionError(f"unexpected storage call {request.method} {path}")


def make_wav(seconds=1, rate=8000, level=0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(int(level).to_bytes(2, "little", signed=True) * rate * seconds)
    return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setenv("SUPABASE_BUCKET", "songs")
    for name in ("server", "auth", "db", "database", "library", "audio_store"):
        sys.modules.pop(name, None)
    audio_store = importlib.import_module("audio_store")
    fake = FakeSupabase()
    audio_store._transport = httpx.MockTransport(fake.handler)
    server = importlib.import_module("server")
    with TestClient(server.app) as client:
        csrf = client.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', csrf.text).group(1)
        r = client.post("/register", data={"username": "alice", "password": "old-password", "email": "", "csrf_token": token},
                        follow_redirects=False)
        assert r.status_code == 303
        headers = {"X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"]}
        yield server, client, fake, headers, monkeypatch


def upload(client, headers, data, name="song.wav"):
    return client.post("/api/library/upload", headers=headers, files={"file": (name, data, "audio/wav")})


def test_upload_goes_to_storage_not_postgres(env):
    server, client, fake, headers, _ = env
    data = make_wav()
    r = upload(client, headers, data)
    assert r.status_code == 200, r.text
    track_id = r.json()["id"]
    from db import SessionLocal, TrackRecord
    with SessionLocal() as s:
        row = s.scalar(select(TrackRecord).where(TrackRecord.id == track_id))
        assert row.audio_data is None
        assert row.storage_path == f"{row.user_id}/{track_id}.wav"
        assert row.size_bytes == len(data)
    assert fake.objects[row.storage_path] == data


def test_stream_relays_only_requested_range(env):
    server, client, fake, headers, _ = env
    data = make_wav(seconds=2)
    track_id = upload(client, headers, data).json()["id"]

    fake.bytes_served = 0
    r = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206
    assert r.content == data[100:200]
    assert r.headers["content-range"] == f"bytes 100-199/{len(data)}"
    assert r.headers["content-length"] == "100"
    assert fake.bytes_served == 100  # not the whole file

    r = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": "bytes=-50"})
    assert r.status_code == 206 and r.content == data[-50:]

    r = client.get(f"/api/tracks/{track_id}/stream")
    assert r.status_code == 200 and r.content == data
    assert r.headers["content-length"] == str(len(data))

    r = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": f"bytes={len(data) + 5}-"})
    assert r.status_code == 416


def test_stream_is_scoped_to_the_owner(env):
    server, client, fake, headers, _ = env
    track_id = upload(client, headers, make_wav()).json()["id"]
    other = TestClient(server.app)
    assert other.get(f"/api/tracks/{track_id}/stream").status_code == 401


def test_tag_head_reads_only_the_tag(env):
    server, client, fake, headers, _ = env
    data = make_wav()
    track_id = upload(client, headers, data).json()["id"]
    fake.bytes_served = 0
    r = client.get(f"/api/tracks/{track_id}/tag-head")
    assert r.status_code == 200 and r.content == data[:10]  # no ID3 tag: just the first bytes
    assert fake.bytes_served == 10

    # A real ID3v2 tag: 10-byte header + 20 bytes of frames, then audio.
    from db import SessionLocal, TrackRecord, User
    blob = b"ID3\x03\x00\x00" + bytes([0, 0, 0, 20]) + b"T" * 20 + b"AUDIO" * 1000
    with SessionLocal() as s:
        user_id = s.scalar(select(User.id))
        s.add(TrackRecord(id="idtag", user_id=user_id, filename="x.mp3", title="t", artist="a", album="b", duration=1,
                          has_cover=False, storage_path=f"{user_id}/idtag.mp3", size_bytes=len(blob), cover_data=b""))
        s.commit()
    fake.objects[f"{user_id}/idtag.mp3"] = blob
    fake.bytes_served = 0
    r = client.get("/api/tracks/idtag/tag-head")
    assert r.content == blob[:30]
    assert fake.bytes_served == 10 + 30


def test_delete_track_removes_storage_object(env):
    server, client, fake, headers, _ = env
    track_id = upload(client, headers, make_wav()).json()["id"]
    assert len(fake.objects) == 1
    assert client.delete(f"/api/tracks/{track_id}", headers=headers).status_code == 200
    assert fake.objects == {}


def test_delete_account_removes_storage_objects(env):
    server, client, fake, headers, _ = env
    upload(client, headers, make_wav(level=1))
    upload(client, headers, make_wav(level=2))
    assert len(fake.objects) == 2
    r = client.request("DELETE", "/api/account", headers=headers, json={"current_password": "old-password", "confirmation": "DELETE"})
    assert r.status_code == 200, r.text
    assert fake.objects == {}


def test_storage_outage_gives_502_and_no_row(env):
    server, client, fake, headers, _ = env
    fake.fail_uploads = True
    r = upload(client, headers, make_wav())
    assert r.status_code == 502
    assert client.get("/api/tracks").json()["tracks"] == []


def test_legacy_rows_still_stream_by_slice_and_migrate(env, tmp_path):
    server, client, fake, headers, monkeypatch = env
    # Storage switched off: the old behaviour (audio in Postgres) keeps working...
    monkeypatch.delenv("SUPABASE_URL")
    data = make_wav(seconds=2)
    track_id = upload(client, headers, data).json()["id"]
    from db import SessionLocal, TrackRecord
    with SessionLocal() as s:
        row = s.scalar(select(TrackRecord).where(TrackRecord.id == track_id))
        assert row.storage_path is None and bytes(row.audio_data) == data
    r = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == data[10:20]
    assert client.get(f"/api/tracks/{track_id}/tag-head").content == data[:10]
    assert fake.objects == {}

    # ...and scripts/move_audio_to_storage.py moves it, verified, and frees the DB copy.
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    spec = importlib.util.spec_from_file_location("move_audio", ROOT / "scripts" / "move_audio_to_storage.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(sys, "argv", ["move_audio_to_storage.py"])
    assert script.main() == 0  # copy only: safety copy stays in Postgres
    with SessionLocal() as s:
        row = s.scalar(select(TrackRecord).where(TrackRecord.id == track_id))
        assert row.storage_path and bytes(row.audio_data) == data
    assert fake.objects[row.storage_path] == data

    monkeypatch.setattr(sys, "argv", ["move_audio_to_storage.py", "--free-db"])
    assert script.main() == 0
    with SessionLocal() as s:
        row = s.scalar(select(TrackRecord).where(TrackRecord.id == track_id))
        assert row.audio_data is None
    fake.bytes_served = 0
    r = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == data[10:20]
    assert fake.bytes_served == 10


def test_unreachable_storage_is_reported_not_a_bare_500(env):
    server, client, fake, headers, monkeypatch = env
    import audio_store

    def boom(request):
        raise httpx.ConnectError("name resolution failed")

    audio_store._transport = httpx.MockTransport(boom)
    r = upload(client, headers, make_wav())
    assert r.status_code == 502
    assert "ConnectError" in r.json()["detail"]
    assert client.get("/api/tracks").json()["tracks"] == []


@pytest.mark.parametrize("bad_url", [
    "sb_secret_" + "x" * 170,                # key pasted into SUPABASE_URL (no scheme)
    "https://" + "a" * 170 + ".supabase.co",  # label too long -> idna UnicodeError
    "https://fake.supabase.co/storage/v1",    # extra path
    "not a url",
])
def test_bad_supabase_url_gives_clear_502_without_leaking_it(env, bad_url):
    server, client, fake, headers, monkeypatch = env
    monkeypatch.setenv("SUPABASE_URL", bad_url)
    r = upload(client, headers, make_wav())
    assert r.status_code == 502, r.text
    detail = r.json()["detail"]
    assert "SUPABASE_URL" in detail
    assert bad_url not in detail and "x" * 20 not in detail
    assert client.get("/api/tracks").json()["tracks"] == []


def test_unicode_error_from_the_resolver_is_wrapped(env):
    server, client, fake, headers, monkeypatch = env
    import audio_store

    def boom(request):
        raise UnicodeError("encoding with 'idna' codec failed (label too long)")

    audio_store._transport = httpx.MockTransport(boom)
    r = upload(client, headers, make_wav())
    assert r.status_code == 502 and "UnicodeError" in r.json()["detail"]
