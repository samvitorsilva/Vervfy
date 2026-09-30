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
from sqlalchemy import event, select

ROOT = Path(__file__).resolve().parents[1]


class FakeSupabase:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.bytes_served = 0
        self.range_requests = []
        self.fail_uploads = False
        self.ignore_ranges = False

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
            if not spec or self.ignore_ranges:
                self.bytes_served += len(data)
                return httpx.Response(200, content=data)
            self.range_requests.append(spec)
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
    for name in (
        "server",
        "auth",
        "db",
        "database",
        "library",
        "audio_store",
        "upload_queue",
        "scripts.upload_worker",
    ):
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


def register_another_user(server, username="bob"):
    client = TestClient(server.app)
    csrf_response = client.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', csrf_response.text).group(1)
    response = client.post(
        "/register",
        data={
            "username": username,
            "password": "other-password",
            "email": "",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    headers = {"X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"]}
    return client, headers


def library_state_headers(client, csrf_headers):
    return {
        **csrf_headers,
        "If-Match": client.get("/api/library/state").headers["etag"],
    }


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


@pytest.mark.parametrize("filename", ["Trust…Fall.mp3", "東京.mp3", "😀.mp3"])
def test_stream_supports_unicode_filenames(env, filename):
    server, client, fake, _, _ = env
    from db import TrackRecord
    from urllib.parse import quote

    user = server.user_store.get_by_username("alice")
    track_id = f"unicode-{len(filename.encode('utf-8'))}"
    storage_path = f"{user['id']}/{track_id}.mp3"
    payload = make_wav()
    fake.objects[storage_path] = payload
    with server.SessionLocal() as session:
        session.add(TrackRecord(
            id=track_id,
            user_id=user["id"],
            filename=filename,
            title="Unicode title",
            artist="Artist",
            album="Album",
            duration=1,
            has_cover=False,
            size_bytes=len(payload),
            cover_data=b"",
            storage_path=storage_path,
        ))
        session.commit()

    response = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": "bytes=0-3"})

    assert response.status_code == 206
    assert response.content == payload[:4]
    assert f"filename*=UTF-8''{quote(filename, safe='')}" in response.headers["content-disposition"]


def test_profile_photo_blob_is_not_loaded_for_library_requests(env):
    server, client, fake, _, _ = env
    from db import TrackRecord

    user = server.user_store.get_by_username("alice")
    track_id = "photo-query-track"
    storage_path = f"{user['id']}/{track_id}.wav"
    payload = make_wav()
    fake.objects[storage_path] = payload
    with server.SessionLocal() as session:
        session.add(TrackRecord(
            id=track_id,
            user_id=user["id"],
            filename="song.wav",
            title="Song",
            artist="Artist",
            album="Album",
            duration=1,
            has_cover=False,
            size_bytes=len(payload),
            cover_data=b"",
            storage_path=storage_path,
        ))
        session.commit()

    statements = []
    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(server.engine, "before_cursor_execute", capture_sql)
    try:
        assert client.get("/api/library/state").status_code == 200
        assert client.get(f"/api/tracks/{track_id}/stream").status_code == 200
        assert client.get("/api/me").status_code == 200
    finally:
        event.remove(server.engine, "before_cursor_execute", capture_sql)

    assert statements
    assert all("photo_data" not in statement for statement in statements)


@pytest.mark.parametrize("id3_tag_size, expected_ranges", [(0, 1), (300_000, 2)])
def test_tag_head_reads_metadata_with_one_or_two_bounded_ranges(env, id3_tag_size, expected_ranges):
    server, client, fake, _, _ = env
    from db import TrackRecord

    user = server.user_store.get_by_username("alice")
    track_id = f"tag-head-{id3_tag_size}"
    storage_path = f"{user['id']}/{track_id}.mp3"
    if id3_tag_size:
        synchsafe_size = bytes([
            (id3_tag_size >> 21) & 0x7F,
            (id3_tag_size >> 14) & 0x7F,
            (id3_tag_size >> 7) & 0x7F,
            id3_tag_size & 0x7F,
        ])
        payload = b"ID3\x04\x00\x00" + synchsafe_size + b"\0" * id3_tag_size + b"audio-data"
    else:
        payload = make_wav()
    fake.objects[storage_path] = payload
    with server.SessionLocal() as session:
        session.add(TrackRecord(
            id=track_id,
            user_id=user["id"],
            filename="song.mp3",
            title="Song",
            artist="Artist",
            album="Album",
            duration=1,
            has_cover=False,
            size_bytes=len(payload),
            cover_data=b"",
            storage_path=storage_path,
        ))
        session.commit()

    statements = []
    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(server.engine, "before_cursor_execute", capture_sql)
    requests_before = len(fake.range_requests)
    bytes_before = fake.bytes_served
    try:
        response = client.get(f"/api/tracks/{track_id}/tag-head")
    finally:
        event.remove(server.engine, "before_cursor_execute", capture_sql)

    assert response.status_code == 200
    assert sum("from tracks" in statement for statement in statements) == 1
    assert len(fake.range_requests) - requests_before == expected_ranges
    assert fake.bytes_served - bytes_before == (10 + id3_tag_size if id3_tag_size else len(payload))
    if id3_tag_size:
        assert response.content == payload[:10 + id3_tag_size]
        assert fake.range_requests[requests_before:] == ["bytes=0-262143", "bytes=262144-300009"]
    else:
        assert response.content == payload[:10]


def test_audio_storage_http_client_is_pooled_and_closed(env):
    server, _, _, _, _ = env
    audio_store = server.audio_store

    first = audio_store._client()
    assert audio_store._client() is first
    audio_store.close_client()
    assert first.is_closed
    assert audio_store._client() is not first


def test_upload_limit_is_per_user_and_returns_json(env, monkeypatch):
    server, client, _, headers, _ = env
    monkeypatch.setattr(server, "UPLOADS_PER_10MIN", 1)

    first = upload(client, headers, make_wav(level=1))
    blocked = upload(client, headers, make_wav(level=2))
    assert first.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Too many requests"}
    assert blocked.headers["retry-after"] == "600"

    other, other_headers = register_another_user(server)
    other_response = upload(other, other_headers, make_wav(level=3))
    assert other_response.status_code == 200, other_response.text


def test_upload_preserves_multiple_artist_tags(env, monkeypatch):
    server, _, _, _, _ = env
    import library
    from types import SimpleNamespace

    monkeypatch.setattr(
        library,
        "MutagenFile",
        lambda *_args, **_kwargs: SimpleNamespace(
            info=SimpleNamespace(length=1),
            tags={"title": ["Song"], "artist": ["Singer One", "Singer Two"], "album": ["Album"]},
        ),
    )

    metadata = library.Library("user")._read_metadata("song.wav", b"audio")

    assert metadata[0:3] == ("Song", "Singer One; Singer Two", "Album")


def test_async_upload_runs_under_the_job_tenant(env):
    server, client, fake, headers, monkeypatch = env
    import upload_queue
    from db import SessionLocal, UploadJob
    from sqlalchemy import select
    upload_worker = importlib.import_module("scripts.upload_worker")

    queued = []
    monkeypatch.setattr(server, "async_uploads", True)
    monkeypatch.setattr(upload_queue, "enqueue", lambda job_id, user_id: queued.append((job_id, user_id)))
    response = upload(client, headers, make_wav(level=7))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processing"
    assert len(queued) == 1
    assert queued[0][0] == payload["id"]

    with SessionLocal() as session:
        job = session.scalar(select(UploadJob).where(UploadJob.id == payload["id"]))
        assert job and job.user_id == queued[0][1] and job.status == "pending"
        assert job.storage_path in fake.objects

    tenant_ids = []
    original_tenant_session = upload_worker.tenant_session

    def recording_tenant_session(user_id):
        tenant_ids.append(user_id)
        return original_tenant_session(user_id)

    monkeypatch.setattr(upload_worker, "tenant_session", recording_tenant_session)
    upload_worker.process(*queued[0])
    assert tenant_ids and set(tenant_ids) == {queued[0][1]}
    with SessionLocal() as session:
        job = session.scalar(select(UploadJob).where(UploadJob.id == payload["id"]))
        assert job and job.status == "completed" and job.track_id

    csrf = client.get("/api/csrf").json()["csrf_token"]
    status = client.get(f"/api/library/upload/{payload['id']}", headers={"X-CSRF-Token": csrf})
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["track"]["id"] == job.track_id


def test_async_upload_retries_then_dead_letters_and_cleans_staging(env, monkeypatch):
    server, client, fake, headers, _ = env
    import upload_queue
    from db import SessionLocal, UploadJob
    upload_worker = importlib.import_module("scripts.upload_worker")

    queued = []
    dead_letters = []
    monkeypatch.setattr(server, "async_uploads", True)
    monkeypatch.setattr(upload_queue, "enqueue", lambda job_id, user_id: queued.append((job_id, user_id)))
    monkeypatch.setattr(upload_queue, "requeue", lambda job_id, user_id: queued.append((job_id, user_id)))
    monkeypatch.setattr(
        upload_queue,
        "dead_letter",
        lambda job_id, user_id, reason: dead_letters.append((job_id, user_id, reason)),
    )
    response = upload(client, headers, make_wav(level=8))
    job_id, user_id = queued[0]
    staging_path = response.json()["id"]
    with SessionLocal() as session:
        job = session.get(UploadJob, job_id)
        staging_path = job.storage_path

    def fail_read(path):
        raise RuntimeError("backend credentials must not reach user-facing error")

    monkeypatch.setattr(upload_worker.audio_store, "object_size", fail_read)
    upload_worker.process(job_id, user_id)
    with SessionLocal() as session:
        job = session.get(UploadJob, job_id)
        assert job.status == "pending" and job.attempts == 1
        assert job.error == "Upload processing will be retried."
    assert staging_path in fake.objects
    assert queued[-1] == (job_id, user_id)

    upload_worker.process(job_id, user_id)
    upload_worker.process(job_id, user_id)
    with SessionLocal() as session:
        job = session.get(UploadJob, job_id)
        assert job.status == "failed" and job.attempts == upload_worker.MAX_ATTEMPTS
        assert job.error == "Upload processing failed after repeated attempts."
    assert dead_letters and dead_letters[0][0:2] == (job_id, user_id)
    assert staging_path not in fake.objects


def test_staged_object_survives_upload_commit_error(env):
    server, client, fake, headers, monkeypatch = env
    monkeypatch.setattr(server, "async_uploads", True)
    import upload_queue
    monkeypatch.setattr(upload_queue, "enqueue", lambda *_args: None)
    response = upload(client, headers, make_wav(level=11))
    assert response.status_code == 200

    from db import UploadJob, SessionLocal
    from library import Library, UploadQuotaExceeded
    with SessionLocal() as session:
        job = session.get(UploadJob, response.json()["id"])
        staging_path = job.storage_path
    with pytest.raises(UploadQuotaExceeded):
        Library(job.user_id).add_upload(
            job.filename,
            make_wav(level=11),
            quota_bytes=0,
            storage_path_override=staging_path,
        )
    assert staging_path in fake.objects


def test_enqueue_failure_marks_job_failed_and_cleans_staging(env, monkeypatch):
    server, client, fake, headers, _ = env
    import upload_queue
    from db import SessionLocal, UploadJob
    from sqlalchemy import select

    monkeypatch.setattr(server, "async_uploads", True)
    monkeypatch.setattr(
        upload_queue,
        "enqueue",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("queue unavailable")),
    )
    response = upload(client, headers, make_wav(level=13))
    assert response.status_code == 503

    with SessionLocal() as session:
        job = session.scalar(select(UploadJob))
        assert job and job.status == "failed"
        assert job.error == "Upload could not be added to the processing queue."
        assert job.storage_path not in fake.objects


def test_redis_queue_reclaims_jobs_after_worker_crash(monkeypatch):
    import json
    import upload_queue

    class FakeRedis:
        def __init__(self):
            self.lists = {}
            self.leases = {}

        def close(self):
            pass

        def rpush(self, key, value):
            self.lists.setdefault(key, []).append(value)

        def zrem(self, key, value):
            return int(self.leases.pop(value, None) is not None)

        def eval(self, script, key_count, *args):
            if script == upload_queue._CLAIM_SCRIPT:
                queue_key, lease_key, now, lease_until = args
                for value, expiry in list(self.leases.items()):
                    if expiry <= float(now):
                        del self.leases[value]
                        self.lists.setdefault(queue_key, []).append(value)
                values = self.lists.setdefault(queue_key, [])
                if not values:
                    return None
                task = values.pop(0)
                self.leases[task] = float(lease_until)
                return task
            if script == upload_queue._RENEW_SCRIPT:
                lease_key, task, lease_until = args
                if task not in self.leases:
                    return 0
                self.leases[task] = float(lease_until)
                return 1
            raise AssertionError("unexpected Redis script")

    fake = FakeRedis()
    monkeypatch.setattr(upload_queue, "client", lambda: fake)
    upload_queue.enqueue("job-1", "user-1")
    assert upload_queue.dequeue(timeout=0) == ("job-1", "user-1")
    encoded = json.dumps({"job_id": "job-1", "user_id": "user-1"}, separators=(",", ":"))
    assert encoded in fake.leases

    fake.leases[encoded] = 0
    assert upload_queue.dequeue(timeout=0) == ("job-1", "user-1")
    assert encoded in fake.leases
    upload_queue.acknowledge("job-1", "user-1")
    assert encoded not in fake.leases
    assert upload_queue.dequeue(timeout=0) is None


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

    for malformed in ("bytes=wat", "bytes=0-1,3-4"):
        r = client.get(f"/api/tracks/{track_id}/stream", headers={"Range": malformed})
        assert r.status_code == 200
        assert r.content == data


def test_stream_slices_when_storage_ignores_range(env):
    server, client, fake, headers, _ = env
    data = make_wav(seconds=2)
    track_id = upload(client, headers, data).json()["id"]
    fake.ignore_ranges = True

    response = client.get(
        f"/api/tracks/{track_id}/stream",
        headers={"Range": "bytes=100-199"},
    )

    assert response.status_code == 206
    assert response.content == data[100:200]
    assert response.headers["content-range"] == f"bytes 100-199/{len(data)}"
    assert response.headers["content-length"] == "100"
    assert fake.bytes_served == len(data)


def test_stream_is_scoped_to_the_owner(env):
    server, client, fake, headers, _ = env
    track_id = upload(client, headers, make_wav()).json()["id"]
    other = TestClient(server.app)
    assert other.get(f"/api/tracks/{track_id}/stream").status_code == 401


def test_authenticated_other_user_cannot_access_or_mutate_track(env):
    server, owner, fake, owner_headers, _ = env
    data = make_wav()
    track_id = upload(owner, owner_headers, data).json()["id"]
    owner_lyrics = owner.put(
        f"/api/tracks/{track_id}/lyrics",
        headers=owner_headers,
        json={"lyrics": "private lyrics"},
    )
    assert owner_lyrics.status_code == 200
    other, other_headers = register_another_user(server)

    for path in (
        f"/api/tracks/{track_id}/cover",
        f"/api/tracks/{track_id}/stream",
        f"/api/tracks/{track_id}/tag-head",
    ):
        assert other.get(path).status_code == 404

    assert other.put(
        f"/api/tracks/{track_id}/lyrics",
        headers=other_headers,
        json={"lyrics": "attacker text"},
    ).status_code == 404
    assert other.delete(
        f"/api/tracks/{track_id}",
        headers=other_headers,
    ).status_code == 404
    assert owner.get(f"/api/tracks/{track_id}/stream").content == data
    assert owner.get("/api/tracks").json()["tracks"][0]["custom_lyrics"] == "private lyrics"


def test_other_user_cannot_read_profile_photo_or_upload_job(env, monkeypatch):
    server, owner, fake, owner_headers, _ = env
    other, other_headers = register_another_user(server)
    import upload_queue
    from db import SessionLocal, UploadJob

    queued = []
    monkeypatch.setattr(server, "async_uploads", True)
    monkeypatch.setattr(upload_queue, "enqueue", lambda job_id, user_id: queued.append((job_id, user_id)))
    result = upload(owner, owner_headers, make_wav(level=4))
    assert result.status_code == 200
    job_id, owner_id = queued[0]
    assert owner.get(f"/api/library/upload/{job_id}").status_code == 200
    assert other.get(f"/api/library/upload/{job_id}").status_code == 404

    from PIL import Image
    import io

    image_bytes = io.BytesIO()
    Image.new("RGB", (4, 4), color="red").save(image_bytes, format="PNG")
    photo = owner.post(
        "/api/account/photo",
        headers=owner_headers,
        files={"file": ("photo.png", image_bytes.getvalue(), "image/png")},
    )
    assert photo.status_code == 200
    assert owner.get("/api/account/photo").status_code == 200
    assert other.get("/api/account/photo").status_code == 404

    with SessionLocal() as session:
        job = session.get(UploadJob, job_id)
        assert job and job.user_id == owner_id and job.storage_path in fake.objects


def test_library_state_never_attaches_another_users_track(env):
    server, owner, _, owner_headers, _ = env
    track_id = upload(owner, owner_headers, make_wav()).json()["id"]
    other, other_headers = register_another_user(server)

    result = other.put(
        "/api/library/state",
        headers=library_state_headers(other, other_headers),
        json={
            "favorites": [track_id],
            "playlists": [{"id": "foreign-track", "name": "Foreign", "trackIds": [track_id]}],
        },
    )
    assert result.status_code == 200
    assert result.json()["favorites"] == []
    assert result.json()["playlists"][0]["trackIds"] == []
    assert owner.get("/api/library/state").json()["favorites"] == []


def test_tag_head_reads_only_the_tag(env):
    server, client, fake, headers, _ = env
    data = make_wav()
    track_id = upload(client, headers, data).json()["id"]
    fake.bytes_served = 0
    r = client.get(f"/api/tracks/{track_id}/tag-head")
    assert r.status_code == 200 and r.content == data[:10]  # no ID3 tag: just the first bytes
    assert fake.bytes_served == min(len(data), 256 * 1024)

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
    assert fake.bytes_served == len(blob)


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
