import base64
from contextvars import ContextVar
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("VERVFY_ENABLE_DOCS", raising=False)
    monkeypatch.delenv("VERVFY_HTTPS_ONLY", raising=False)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    module = importlib.import_module("server")
    with TestClient(module.app) as client:
        yield module, client


def _csrf(client):
    response = client.get("/login")
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def _register(client, username="alice", passphrase="old-password"):
    response = client.post(
        "/register",
        data={
            "username": username,
            "password": passphrase,
            "email": "",
            "csrf_token": _csrf(client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _login(client, username="alice", passphrase="old-password"):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": passphrase,
            "csrf_token": _csrf(client),
        },
        follow_redirects=False,
    )


def _library_state_headers(client):
    return {
        "X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"],
        "If-Match": client.get("/api/library/state").headers["etag"],
    }


def test_redis_throttle_keeps_first_hit_window(app_module):
    server, _ = app_module
    auth = server.auth

    class FakeRedisCounter:
        def __init__(self):
            self.counts = {}
            self.expirations = []

        def eval(self, script, key_count, key, window):
            assert script == auth._INCREMENT_WINDOW_SCRIPT
            assert key_count == 1
            count = self.counts.get(key, 0) + 1
            self.counts[key] = count
            if count == 1:
                self.expirations.append((key, window))
            return count

        def get(self, key):
            return self.counts.get(key)

        def delete(self, key):
            self.counts.pop(key, None)

    limiter = auth.RequestThrottle()
    fake = FakeRedisCounter()
    limiter._redis = fake

    key = "login:ip:user"
    assert limiter.peek(key, 60) == 0
    assert limiter.increment(key, 60) == 1
    assert limiter.peek(key, 60) == 1
    assert limiter.allow(key, 2, 60)
    assert not limiter.allow(key, 2, 60)
    assert fake.expirations == [("vervfy:ratelimit:login:ip:user", 60)]


@pytest.mark.parametrize("backend", ["memory", "redis"])
def test_auth_throttles_count_only_successes_and_failures(app_module, backend):
    server, client = app_module
    limiter = server.auth.RequestThrottle()
    if backend == "redis":
        class FakeRedisCounter:
            def __init__(self):
                self.counts = {}

            def eval(self, _script, _key_count, key, _window):
                self.counts[key] = self.counts.get(key, 0) + 1
                return self.counts[key]

            def get(self, key):
                return self.counts.get(key)

            def delete(self, key):
                self.counts.pop(key, None)

        limiter._redis = FakeRedisCounter()
    server.request_throttle._redis = limiter._redis

    signup = server.auth.SignupThrottle(max_signups=5, limiter=limiter)
    for _ in range(5):
        assert not signup.is_limited("signup-ip")
    assert not signup.is_limited("signup-ip")
    for _ in range(5):
        signup.record_success("signup-ip")
    assert signup.is_limited("signup-ip")

    login = server.auth.LoginThrottle(limiter=limiter)
    for _ in range(5):
        assert not login.is_locked("login-ip", "alice")
    for _ in range(4):
        login.record_failure("login-ip", "alice")
        assert not login.is_locked("login-ip", "alice")
    login.record_failure("login-ip", "alice")
    assert login.is_locked("login-ip", "alice")

    _register(client)
    signup_client = TestClient(server.app)
    for _ in range(5):
        response = signup_client.post(
            "/register",
            data={
                "username": "alice",
                "password": "old-password",
                "email": "",
                "csrf_token": _csrf(signup_client),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
    response = signup_client.post(
        "/register",
        data={
            "username": "bob",
            "password": "old-password",
            "email": "",
            "csrf_token": _csrf(signup_client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_production_requires_stable_session_secret(app_module, monkeypatch):
    server, _ = app_module
    monkeypatch.setattr(server, "is_production", True)
    monkeypatch.delenv("VERVFY_SECRET_KEY", raising=False)
    monkeypatch.delenv("AURALIS_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="VERVFY_SECRET_KEY is required"):
        server._load_or_create_secret_key()


def test_browser_upload_retries_429_and_caps_retry_wait():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise the browser upload helper")
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    start = app_js.index("async function uploadFileToServer(file){")
    end = app_js.index("\nasync function deleteTrackOnServer", start)
    upload_function = app_js[start:end]
    script = upload_function + """
const assert = require("node:assert/strict");
const waits = [];
let responses = [];
let calls = 0;
globalThis.FormData = class { append() {} };
globalThis.ensureCsrfToken = async () => "csrf";
globalThis.wait = async ms => waits.push(ms);
globalThis.trackFromServer = value => value;
globalThis.fetch = async () => { calls++; return responses.shift(); };
const response = (status, retryAfter = null) => ({
  status,
  ok: status >= 200 && status < 300,
  headers: { get: name => name === "Retry-After" ? retryAfter : null },
  json: async () => ({ id: "track" }),
});
(async () => {
  responses = [response(429, "2"), response(429, "60"), response(200)];
  assert.equal((await uploadFileToServer({ name: "song.mp3" })).id, "track");
  assert.equal(calls, 3);
  assert.deepEqual(waits, [2000, 30000]);

  calls = 0;
  waits.length = 0;
  responses = [response(429), response(429), response(429), response(429)];
  await assert.rejects(
    uploadFileToServer({ name: "song.mp3" }),
    error => error.status === 429 && error.message.includes("rate limited"),
  );
  assert.equal(calls, 4);
  assert.deepEqual(waits, [1000, 1000, 1000]);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_server_track_sync_preserves_resolved_lyrics_state():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise the browser lyrics sync helper")
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    start = app_js.index("function applyServerCustomLyrics(track, payload){")
    end = app_js.index("\nasync function loadOfflineTracks", start)
    helpers = app_js[start:end]
    script = """
const LyricsEngine = {fromLRC: value => ({source:"custom", text:value})};
const normalizeSyncedLyrics = value => value;
function trackFromServer(payload){
  return {
    id: payload.id, title: payload.title, artist: payload.artist,
    album: payload.album, duration: payload.duration, art: payload.art,
    fallbackArt: payload.art, streamUrl: payload.stream_url,
    customLyrics: payload.custom_lyrics || null,
    lyrics: payload.custom_lyrics ? {source:"custom", text:payload.custom_lyrics} : null,
    lyricsResolved: !!payload.custom_lyrics, lyricsLoading: false,
    lyricsPromise: null, fingerprint: payload.id,
  };
}
""" + helpers + """
const assert = require("node:assert/strict");
const pending = Promise.resolve("pending");
const existing = {
  id:"track", title:"Song", artist:"Artist", album:"Album", duration:10, art:"cover",
  customLyrics:null, lyrics:{source:"online-synced", lines:[{time:0,text:"line"}]},
  lyricsResolved:true, lyricsLoading:true, lyricsPromise:pending, favorite:true,
};
const merged = mergeServerTrack(existing, {
  id:"track", title:"Song", artist:"Artist", album:"Album", duration:10, art:"cover",
  custom_lyrics:null,
});
assert.equal(merged.track, existing);
assert.equal(existing.lyricsResolved, true);
assert.equal(existing.lyricsLoading, true);
assert.equal(existing.lyricsPromise, pending);
assert.equal(existing.lyrics.source, "online-synced");
assert.equal(merged.changed, false);
const changed = mergeServerTrack(existing, {
  id:"track", title:"Song", artist:"Artist", album:"Album", duration:10, art:"cover",
  custom_lyrics:"new lyrics",
});
assert.equal(changed.track, existing);
assert.equal(changed.changed, true);
assert.equal(existing.lyricsResolved, true);
assert.equal(existing.lyricsLoading, false);
assert.equal(existing.lyricsPromise, null);
assert.equal(existing.lyrics.text, "new lyrics");
const legacyExisting = {
  id:"legacy", title:"Song", artist:"Artist", album:"Album", duration:10, art:"cover",
  lyrics:{source:"online-synced", lines:[{time:0,text:"cached lyric"}]},
  lyricsResolved:true, lyricsLoading:false,
};
const legacyMerged = mergeServerTrack(legacyExisting, {
  id:"legacy", title:"Song", artist:"Artist", album:"Album", duration:10, art:"cover",
  custom_lyrics:null,
});
assert.equal(legacyMerged.changed, false);
assert.equal(legacyExisting.lyricsResolved, true);
assert.equal(legacyExisting.lyrics.lines[0].text, "cached lyric");
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_library_state_refresh_keeps_local_edits_and_remote_changes():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise browser library-state merging")
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    start = app_js.index("let libraryMetaSaveQueue = Promise.resolve();")
    end = app_js.index("\nasync function persistLibraryMeta", start)
    helpers = app_js[start:end]
    script = """
const state = {tracks:[], playlists:[]};
const window = {};
""" + helpers + """
const assert = require("node:assert/strict");
const baseline = {
  favorites:["favorite-before"],
  playlists:[{id:"local-list", name:"Original", trackIds:["one"]}],
};
const remote = {
  favorites:["favorite-before", "favorite-remote"],
  playlists:[
    {id:"local-list", name:"Original", trackIds:["one"]},
    {id:"remote-list", name:"Remote", trackIds:["two"]},
  ],
};
const local = {
  favorites:[],
  playlists:[{id:"local-list", name:"Edited locally", trackIds:["one","three"]}],
};
const merged = mergeUnsavedLibraryMeta(remote, baseline, local);
assert.deepEqual(merged.favorites, ["favorite-remote"]);
assert.deepEqual(merged.playlists, [
  {id:"local-list", name:"Edited locally", trackIds:["one","three"]},
  {id:"remote-list", name:"Remote", trackIds:["two"]},
]);
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_lrclib_rejects_distant_duration_candidates():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise LRCLIB lookup")
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    start = app_js.index("const LyricsEngine = (() => {")
    end = app_js.index("\nfunction normalizeSyncedLyrics", start)
    engine = app_js[start:end]
    script = """
const LyricsDebug = {log(){}, warn(){}};
let candidates = [];
let calls = 0;
globalThis.fetch = async (url, options) => {
  calls++;
  assert.ok(options.signal instanceof AbortSignal);
  if(url.includes("/get?")) return {status:404, ok:false};
  return {status:200, ok:true, json:async () => candidates};
};
""" + engine + """
const assert = require("node:assert/strict");
(async () => {
  const track = {title:"Song", artist:"Artist", album:"Album", duration:180};
  candidates = [{trackName:"Song", artistName:"Artist", duration:190, plainLyrics:"wrong"}];
  assert.equal(await LyricsEngine.fromOnline(track), null);
  assert.equal(calls, 2);
  candidates = [{trackName:"Song", artistName:"Artist", duration:183, plainLyrics:"right"}];
  calls = 0;
  assert.deepEqual(await LyricsEngine.fromOnline(track), {source:"online-plain", text:"right"});
  assert.equal(calls, 2);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_lyrics_cache_includes_not_found_results():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise browser lyrics caching")
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    start = app_js.index("function ensureTrackLyrics(track){")
    end = app_js.index("\nfunction updateNowPlayingUI", start)
    resolver = app_js[start:end]
    script = """
const LyricsDebug = {log(){}, warn(){}};
const activeAccountId = "account";
const entries = new Map();
const AuralisDB = {
  get: async key => entries.get(key) || null,
  set: async (key, value) => { entries.set(key, value); return true; },
};
const LyricsEngine = {fromID3(){return null;}, fromOnline:async () => {onlineLookups++; return null;}};
let onlineLookups = 0, headRequests = 0;
globalThis.fetch = async () => {headRequests++; return {ok:false};};
let track;
const currentTrack = () => track;
const updateMobileLyricsPreview = () => {};
const $ = () => ({classList:{contains:()=>false}});
""" + resolver + """
const assert = require("node:assert/strict");
(async () => {
  track = {id:"track", title:"Song", artist:"Artist", album:"Album", duration:10,
    customLyrics:null, lyrics:null, lyricsResolved:false, lyricsLoading:false};
  await ensureTrackLyrics(track);
  track = {id:"track", title:"Song", artist:"Artist", album:"Album", duration:10,
    customLyrics:null, lyrics:null, lyricsResolved:false, lyricsLoading:false};
  await ensureTrackLyrics(track);
  assert.equal(headRequests, 1);
  assert.equal(onlineLookups, 1);
  assert.equal(track.lyricsResolved, true);
  assert.equal(entries.get("lyrics:account:track").lyrics, null);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _reload_server(tmp_path, monkeypatch, env_name, env_value):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / (env_name + '.db')}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", env_name + "-secret")
    monkeypatch.setenv(env_name, env_value)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    return importlib.import_module("server")


def test_sleep_timer_stops_playback_and_can_be_canceled():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise the browser sleep timer")
    app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
    start = app_js.index("let sleepTimer = null;")
    end = app_js.index("\nfunction playCurrent(){", start)
    timer_code = app_js[start:end]
    script = """
const assert = require("node:assert/strict");
const timers = new Map();
let nextTimerId = 0;
let paused = 0, stopped = 0, lastToast = "";
const audioEl = {pause(){ paused++; }};
const syncPlayIcons = () => {};
const toast = message => { lastToast = message; };
const currentTrack = () => ({id:"track"});
const fmtTime = value => `${value}s`;
const $ = selector => ({
  classList:{remove(){}},
  textContent:"",
  hidden:false,
  focus(){},
  ...(selector === "#sleepTimerStatus" ? {set textContent(value){this.value=value;}, get textContent(){return this.value;}} : {}),
});
const setTimeout = (callback, delay) => {
  const id = ++nextTimerId;
  timers.set(id, {callback, delay});
  return id;
};
const clearTimeout = id => timers.delete(id);
""" + timer_code + """
startSleepTimer(5);
assert.equal(timers.size, 1);
const [timerId, timer] = [...timers.entries()][0];
assert.equal(timer.delay, 5 * 60 * 1000);
timers.delete(timerId);
timer.callback();
assert.equal(paused, 1);
assert.match(lastToast, /Sleep timer ended/);
assert.equal(sleepTimer, null);

startSleepTimer(10);
const [cancelId, canceled] = [...timers.entries()][0];
clearSleepTimer();
canceled.callback();
assert.equal(paused, 1);
assert.equal(timers.has(cancelId), false);

setSleepTimerForTrackEnd();
assert.equal(stopAtTrackEnd(), true);
assert.equal(paused, 2);
assert.equal(stopAtTrackEnd(), false);
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_sync_dependency_contextvar_is_not_visible_to_endpoint_or_sqlalchemy(tmp_path):
    tenant_context = ContextVar("reproduction_tenant", default=None)
    observed = {}
    sessions = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'context.db'}"))

    def dependency():
        tenant_context.set("tenant-a")
        observed["dependency"] = tenant_context.get()
        yield

    @event.listens_for(sessions, "after_begin")
    def capture_sqlalchemy_context(session, transaction, connection):
        del session, transaction, connection
        observed["listener"] = tenant_context.get()

    app = FastAPI()

    @app.get("/", dependencies=[Depends(dependency)])
    def endpoint():
        observed["endpoint"] = tenant_context.get()
        with sessions() as session:
            session.execute(text("SELECT 1"))
        return {"tenant": observed["endpoint"]}

    with TestClient(app) as client:
        assert client.get("/").json() == {"tenant": None}

    assert observed == {
        "dependency": "tenant-a",
        "endpoint": None,
        "listener": None,
    }


def test_api_docs_disabled_by_default_and_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'docs.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "docs-secret")
    monkeypatch.delenv("VERVFY_ENABLE_DOCS", raising=False)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)
    server = importlib.import_module("server")
    with TestClient(server.app) as client:
        assert [client.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")] == [404] * 3

    monkeypatch.setenv("VERVFY_ENABLE_DOCS", "1")
    server = importlib.reload(server)
    with TestClient(server.app) as client:
        assert [client.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")] == [200] * 3


def test_production_can_use_synchronous_uploads_without_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'production.db'}")
    monkeypatch.setenv("VERVFY_SECRET_KEY", "production-test-secret")
    monkeypatch.setenv("VERVFY_ENVIRONMENT", "production")
    monkeypatch.setenv("VERVFY_HTTPS_ONLY", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("VERVFY_ASYNC_UPLOADS", raising=False)
    for name in ("server", "auth", "db", "database"):
        sys.modules.pop(name, None)

    server = importlib.import_module("server")
    assert server.is_production
    assert server.async_uploads is False


def test_hsts_only_when_https_only(tmp_path, monkeypatch):
    server = _reload_server(tmp_path, monkeypatch, "VERVFY_HTTPS_ONLY", "1")
    with TestClient(server.app) as client:
        assert client.get("/login").headers["strict-transport-security"] == "max-age=15552000"

    monkeypatch.setenv("VERVFY_HTTPS_ONLY", "0")
    server = importlib.reload(server)
    with TestClient(server.app) as client:
        assert "strict-transport-security" not in client.get("/login").headers


def test_unknown_username_verifies_dummy_hash_once(app_module, monkeypatch):
    server, client = app_module
    _register(client)
    login_client = TestClient(server.app)
    real = _login(login_client, passphrase="wrong-password")
    calls = []
    original = server.auth.verify_password

    def spy(passphrase, password_hash):
        calls.append(password_hash)
        return original(passphrase, password_hash)

    monkeypatch.setattr(server.auth, "verify_password", spy)
    unknown = _login(login_client, username="nobody")
    assert unknown.status_code == real.status_code == 400
    assert "Incorrect username or password" in unknown.text
    assert "Incorrect username or password" in real.text
    assert len(calls) == 1


def test_library_ids_are_validated(app_module):
    _, client = app_module
    _register(client)
    bad = '\"><img src=x onerror=alert(1)>'
    assert client.put(
        "/api/library/state",
        headers=_library_state_headers(client),
        json={"favorites": [bad], "playlists": [{"id": "ok", "name": "x", "trackIds": []}]},
    ).status_code == 422
    assert client.put(
        "/api/library/state",
        headers=_library_state_headers(client),
        json={"favorites": [], "playlists": [{"id": "abc_01-Z", "name": "x", "trackIds": ["abc_01-Z"]}]},
    ).status_code == 200
    assert client.put(
        "/api/library/state",
        headers=_library_state_headers(client),
        json={"favorites": [], "playlists": [{"id": bad, "name": "x", "trackIds": []}]},
    ).status_code == 422


def test_favorites_persist_for_owned_tracks(app_module):
    server, client = app_module
    _register(client)
    user = server.user_store.get_by_username("alice")
    with server.SessionLocal() as session:
        session.add(server.TrackRecord(
            id="track-one",
            user_id=user["id"],
            filename="song.wav",
            title="Song",
            artist="Artist",
            album="Album",
            duration=1,
            has_cover=False,
            size_bytes=10,
            cover_data=b"",
        ))
        session.commit()

    headers = _library_state_headers(client)
    saved = client.put(
        "/api/library/state",
        headers=headers,
        json={"favorites": ["track-one"], "playlists": []},
    )
    assert saved.status_code == 200
    assert saved.json()["favorites"] == ["track-one"]
    assert client.get("/api/library/state").json()["favorites"] == ["track-one"]


def test_library_state_etag_rejects_stale_and_missing_preconditions(app_module):
    _, client = app_module
    _register(client)
    state = client.get("/api/library/state")
    etag = state.headers["etag"]
    csrf = client.get("/api/csrf").json()["csrf_token"]
    assert client.put(
        "/api/library/state",
        headers={"X-CSRF-Token": csrf},
        json={"favorites": [], "playlists": []},
    ).status_code == 428

    first = client.put(
        "/api/library/state",
        headers={"X-CSRF-Token": csrf, "If-Match": etag},
        json={"favorites": [], "playlists": [{"id": "new-list", "name": "New", "trackIds": []}]},
    )
    assert first.status_code == 200
    assert first.headers["etag"] != etag
    stale = client.put(
        "/api/library/state",
        headers={"X-CSRF-Token": csrf, "If-Match": etag},
        json={"favorites": [], "playlists": []},
    )
    assert stale.status_code == 409
    assert stale.headers["etag"] == first.headers["etag"]
    assert client.get("/api/library/state").json()["playlists"][0]["id"] == "new-list"


def test_artist_photo_fetches_exact_deezer_match_and_caches(app_module, monkeypatch):
    server, _ = app_module
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {"name": "Tate McRae tribute", "picture_medium": "https://cdn.dzcdn.net/wrong.jpg"},
                    {"name": "Tate McRae", "picture_medium": "https://cdn.dzcdn.net/tate.jpg"},
                ]
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            return FakeResponse()

    server._artist_photo_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    assert server._lookup_artist_photo("Tate McRae") == "https://cdn.dzcdn.net/tate.jpg"
    assert server._lookup_artist_photo("Tate McRae") == "https://cdn.dzcdn.net/tate.jpg"
    assert len(calls) == 1


def test_postgres_psycopg_disables_prepared_statements(app_module):
    server, _ = app_module
    import db
    assert server.engine.dialect.name == "sqlite"
    assert db.engine_connect_args("postgresql+psycopg://host/database") == {
        "prepare_threshold": None
    }
    assert db.engine_connect_args("sqlite:///database.db") == {}


def test_session_revocation_and_logout_all(app_module):
    server, client_a = app_module
    _register(client_a)
    client_b = TestClient(server.app)
    _login(client_b)
    copied_cookie = client_a.cookies.get("auralis_session")
    client_c = TestClient(server.app)
    client_c.cookies.set("auralis_session", copied_cookie)

    csrf = client_a.get("/api/csrf").json()["csrf_token"]
    response = client_a.post(
        "/api/account/password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": "old-password", "new_password": "new-password"},
    )
    assert response.status_code == 200
    assert client_a.get("/api/me").status_code == 200
    assert client_b.get("/api/me").status_code == 401

    csrf = client_a.get("/api/csrf").json()["csrf_token"]
    assert client_a.post("/api/account/logout-all", headers={"X-CSRF-Token": csrf}).json() == {"ok": True}
    assert client_c.get("/api/me").status_code == 401


def test_verified_email_recovery_flow(app_module, monkeypatch):
    server, client = app_module
    _register(client)
    sent = []
    monkeypatch.setattr(
        server,
        "_send_account_email",
        lambda recipient, subject, body: sent.append((recipient, subject, body)),
    )

    csrf = client.get("/api/csrf").json()["csrf_token"]
    response = client.put(
        "/api/account/email",
        headers={"X-CSRF-Token": csrf},
        json={"email": "Alice@example.com", "current_password": "old-password"},
    )
    assert response.status_code == 200
    assert response.json()["pending_email"] == "alice@example.com"
    assert sent[0][0] == "alice@example.com"
    csrf = client.get("/api/csrf").json()["csrf_token"]
    client.post(
        "/forgot-password",
        data={"email": "alice@example.com", "csrf_token": csrf},
    )
    assert len(sent) == 1

    verify_link = re.search(r"https?://\S+", sent[0][2]).group(0)
    verify_token = parse_qs(urlparse(verify_link).query)["token"][0]
    verify_form = client.get(f"/verify-email?token={verify_token}")
    verify_csrf = re.search(r'name="csrf_token" value="([^"]+)"', verify_form.text).group(1)
    confirmed = client.post(
        "/verify-email",
        data={"token": verify_token, "csrf_token": verify_csrf},
    )
    assert "Email verified" in confirmed.text
    assert client.get("/api/me").json()["email_verified"] is True

    def request_reset(email):
        csrf_token = client.get("/api/csrf").json()["csrf_token"]
        client.post(
            "/forgot-password",
            data={"email": email, "csrf_token": csrf_token},
        )
        link = re.search(r"https?://\S+", sent[-1][2]).group(0)
        return parse_qs(urlparse(link).query)["token"][0]

    stale_reset_token = request_reset("alice@example.com")
    csrf = client.get("/api/csrf").json()["csrf_token"]
    change = client.put(
        "/api/account/email",
        headers={"X-CSRF-Token": csrf},
        json={"email": "alice-new@example.com", "current_password": "old-password"},
    )
    assert change.status_code == 200
    new_verify_link = re.search(r"https?://\S+", sent[-1][2]).group(0)
    new_verify_token = parse_qs(urlparse(new_verify_link).query)["token"][0]
    new_verify_form = client.get(f"/verify-email?token={new_verify_token}")
    new_verify_csrf = re.search(r'name="csrf_token" value="([^"]+)"', new_verify_form.text).group(1)
    assert "Email verified" in client.post(
        "/verify-email",
        data={"token": new_verify_token, "csrf_token": new_verify_csrf},
    ).text

    stale_form = client.get(f"/reset-password?token={stale_reset_token}")
    stale_csrf = re.search(r'name="csrf_token" value="([^"]+)"', stale_form.text).group(1)
    stale_reset = client.post(
        "/reset-password",
        data={
            "token": stale_reset_token,
            "password": "another-password",
            "password_confirm": "another-password",
            "csrf_token": stale_csrf,
        },
    )
    assert "invalid or expired" in stale_reset.text

    reset_token = request_reset("alice-new@example.com")
    reset_form = client.get(f"/reset-password?token={reset_token}")
    reset_csrf = re.search(r'name="csrf_token" value="([^"]+)"', reset_form.text).group(1)
    reset = client.post(
        "/reset-password",
        data={
            "token": reset_token,
            "password": "new-password",
            "password_confirm": "new-password",
            "csrf_token": reset_csrf,
        },
    )
    assert "Password updated" in reset.text
    assert _login(client, passphrase="old-password").status_code == 400
    assert _login(client, passphrase="new-password").status_code == 303

    replay = client.post(
        "/reset-password",
        data={
            "token": reset_token,
            "password": "another-password",
            "password_confirm": "another-password",
            "csrf_token": client.get("/api/csrf").json()["csrf_token"],
        },
    )
    assert "invalid or expired" in replay.text


def test_account_email_links_use_canonical_public_origin(app_module, monkeypatch):
    server, _ = app_module
    from starlette.requests import Request

    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "server": ("attacker.example", 443),
        "client": ("127.0.0.1", 1234),
        "headers": [(b"host", b"attacker.example")],
        "path": "/",
        "query_string": b"",
    })
    monkeypatch.setenv("VERVFY_PUBLIC_URL", "https://music.example")
    assert server._account_link(request, "/reset-password", "signed-token") == (
        "https://music.example/reset-password?token=signed-token"
    )
    monkeypatch.setattr(server, "is_production", True)
    monkeypatch.delenv("VERVFY_PUBLIC_URL")
    with pytest.raises(RuntimeError, match="VERVFY_PUBLIC_URL"):
        server._account_link(request, "/reset-password", "signed-token")


def test_logout_redirects_even_with_stale_csrf_token(app_module):
    server, client = app_module
    _register(client)

    response = client.post(
        "/logout",
        headers={"X-CSRF-Token": "stale-token"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert client.get("/api/me").status_code == 401


def test_login_form_is_not_cached(app_module):
    _, client = app_module
    response = client.get("/login")

    assert response.headers["cache-control"] == "no-store"


def test_cookie_without_session_version_is_valid_at_zero(app_module):
    server, client = app_module
    _register(client)
    cookie = client.cookies.get("auralis_session")
    signed = cookie.split(".", 1)[0]
    payload = json.loads(base64.b64decode(signed + "=" * (-len(signed) % 4)))
    payload.pop("sv", None)
    unsigned = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode())
    old_cookie = TimestampSigner("test-secret-key").sign(unsigned).decode()
    old_client = TestClient(server.app)
    old_client.cookies.set("auralis_session", old_cookie)
    assert old_client.get("/api/me").status_code == 200


def test_authenticated_user_cannot_access_another_users_library(app_module):
    server, client_a = app_module
    _register(client_a, username="alice")
    client_b = TestClient(server.app)
    _register(client_b, username="bob")

    response = client_a.put(
        "/api/library/state",
        headers=_library_state_headers(client_a),
        json={"favorites": [], "playlists": [{"id": "private", "name": "Private", "trackIds": []}]},
    )
    assert response.status_code == 200
    assert client_b.get("/api/library/state").json()["playlists"] == []
    assert client_b.get("/api/tracks").json()["tracks"] == []
    assert client_b.delete("/api/tracks/not-owned", headers={
        "X-CSRF-Token": client_b.get("/api/csrf").json()["csrf_token"]
    }).status_code == 404


def test_artist_profile_fetches_theaudiodb_result(app_module, monkeypatch):
    server, _ = app_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "artists": [
                    {
                        "strArtist": "Example Artist",
                        "strBiographyEN": "Example Artist is a musician known for influential recordings. More details.",
                        "strGenre": "Pop",
                        "strWebsite": "example.com",
                    }
                ]
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            return FakeResponse()

    server._artist_profile_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    profile = server._lookup_artist_profile("Example Artist")
    assert profile["bio"] == "Example Artist is a musician known for influential recordings."
    assert profile["genre"] == "Pop"
    assert profile["website"] == "https://example.com"
    assert profile["source"] == "TheAudioDB"


def test_artist_profile_falls_back_to_wikipedia(app_module, monkeypatch):
    server, _ = app_module

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            if "theaudiodb.com" in url:
                return FakeResponse({"artists": None})
            if url.endswith("/w/api.php"):
                return FakeResponse({"query": {"search": [{"title": "Example Artist"}]}})
            return FakeResponse({
                "extract": "Example Artist is a musician known for influential recordings.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Example_Artist"}},
            })

    server._artist_profile_cache.clear()
    monkeypatch.setattr(server.httpx, "Client", lambda **kwargs: FakeClient())
    profile = server._lookup_artist_profile("Example Artist")
    assert profile["bio"] == "Example Artist is a musician known for influential recordings."
    assert profile["source"] == "Wikipedia"


@pytest.mark.parametrize("name", ["Dave", "Dave Santan", "Santan Dave"])
def test_dave_artist_photo_uses_verified_british_rapper_profile(app_module, monkeypatch, name):
    server, _ = app_module

    def unexpected_lookup(*args, **kwargs):
        pytest.fail("Verified artist photos must not trigger catalog searches")

    monkeypatch.setattr(server, "urlopen", unexpected_lookup, raising=False)

    assert server._lookup_artist_photo(name) == (
        "https://cdn-images.dzcdn.net/images/artist/"
        "eb2c8952b7328fdf32b3546d5ffab8c2/500x500-000000-80-0-0.jpg"
    )
