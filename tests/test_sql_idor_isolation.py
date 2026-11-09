"""Real local database checks with two synthetic authenticated users."""
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import auth
import library
import server
from db import Base, User, TrackRecord, Playlist, UploadJob


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)
        self.addCleanup(self.engine.dispose)
        with self.sessions() as s:
            for uid in ('alice', 'bob'):
                s.add(User(id=uid, username=uid, username_key=uid, password_hash='hash', created_at=0))
                s.add(TrackRecord(id=uid+'-track', user_id=uid, filename='song.mp3', title=uid, artist='Artist', album='Album'))
                s.add(Playlist(id=uid+'-playlist', user_id=uid, name=uid))
                s.add(UploadJob(id=uid+'-job', user_id=uid, filename='song.mp3', storage_path=uid+'/song.mp3', created_at=0))
            s.commit()
        for p in (
            patch.object(server, 'tenant_session', lambda _: self.sessions()),
            patch.object(library, 'tenant_session', lambda _: self.sessions()),
            patch.object(auth, 'SessionLocal', self.sessions),
            patch.object(server, 'get_library', library.Library),
            patch.dict(server.app.dependency_overrides, {server.require_api_user: lambda: {'id': 'alice'}, auth.verify_api_csrf: lambda: None}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(server.app)
        self.addCleanup(self.client.close)

    def test_foreign_track_read_write_and_upload_status(self):
        for method, path, body in (
            ('GET', '/api/tracks/bob-track/stream', None),
            ('GET', '/api/tracks/bob-track/cover', None),
            ('DELETE', '/api/tracks/bob-track', None),
            ('PATCH', '/api/tracks/bob-track', dict(title='stolen', artist='x', album='x')),
            ('PUT', '/api/tracks/bob-track/lyrics', {'lyrics': 'stolen'}),
            ('DELETE', '/api/tracks/bob-track/cover', None),
            ('GET', '/api/library/upload/bob-job', None),
            ('POST', '/api/library/playlists/bob-playlist/listening', None),
        ):
            with self.subTest(path=path, method=method):
                r = self.client.request(method, path, json=body)
                self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(self.client.get('/api/library/upload/alice-job').status_code, 200)
        with self.sessions() as s:
            row = s.scalar(select(TrackRecord).where(TrackRecord.user_id == 'bob'))
            self.assertEqual(row.title, 'bob')
            self.assertIsNone(row.custom_lyrics)

    def test_sql_payloads_do_not_match_or_modify_other_users(self):
        store = auth.UserStore()
        for value in ("' OR 1=1 --", "bob' --", "'; DROP TABLE users; --", "' UNION SELECT NULL --"):
            with self.subTest(value=value):
                self.assertIsNone(store.get_by_username(value))
                self.assertIsNone(store.get_by_id(value))
                store.bump_session_version(value)
                r = self.client.get('/api/library/upload/' + quote(value, safe=''))
                self.assertEqual(r.status_code, 404, r.text)
        with self.sessions() as s:
            self.assertEqual(len(s.scalars(select(User)).all()), 2)
            self.assertEqual(s.get(User, 'bob').session_version, 0)

    def test_library_state_filters_foreign_references_and_blocks_playlist_takeover(self):
        r = self.client.get('/api/library/state')
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn('bob-playlist', r.text)
        headers = {'If-Match': r.headers['etag']}
        r = self.client.put('/api/library/state', headers=headers, json={
            'favorites': ['alice-track', 'bob-track'],
            'playlists': [{'id': 'alice-playlist', 'name': 'safe', 'trackIds': ['alice-track', 'bob-track']}],
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn('bob-track', r.text)
        r = self.client.put('/api/library/state', headers={'If-Match': r.headers['etag']}, json={
            'favorites': [], 'playlists': [{'id': 'bob-playlist', 'name': 'stolen', 'trackIds': []}],
        })
        self.assertEqual(r.status_code, 409, r.text)
        with self.sessions() as s:
            self.assertEqual(s.get(Playlist, 'bob-playlist').name, 'bob')
            self.assertEqual(s.get(Playlist, 'alice-playlist').name, 'safe')
