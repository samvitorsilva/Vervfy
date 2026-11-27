"""Real RLS/quota/reference triggers with a synthetic Storage HTTP transport."""
from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch
import uuid

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

import audio_cache_remediation as repair
import audio_store
import db
import storage_lifecycle
import test_staging_migrations as fixtures


class AudioCachePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StagingPostgresTests.setUpClass.__func__(cls)
        cls.runtime = sa.create_engine(cls.url.set(username="app_runtime"))
        cls.addClassCleanup(cls.runtime.dispose)
        cls.namespace = uuid.uuid4()
        with cls.engine.begin() as c:
            c.execute(sa.text("INSERT INTO vervfy_storage.namespaces VALUES (1,:id,'test','https://audio-test.supabase.co','synthetic',false)"), {"id": cls.namespace})
        cls.sessions = sessionmaker(bind=cls.runtime)
        sa.event.listen(cls.sessions, "after_begin", db.set_database_tenant)

    account_snapshot = staticmethod(fixtures.StagingPostgresTests.account_snapshot)

    def test_rehome_keeps_both_objects_charged_and_cleanup_disabled(self):
        objects = {}
        policies = []

        def handler(request):
            path = request.url.path.split("/synthetic/", 1)[1]
            if request.method == "POST":
                self.assertEqual(request.headers["x-upsert"], "false")
                self.assertNotIn(path, objects)
                objects[path] = request.content
                policies.append(request.headers["cache-control"])
                return httpx.Response(200)
            self.assertEqual(request.method, "GET")
            data = objects[path]
            if request.headers.get("range"):
                start, end = map(int, request.headers["range"][6:].split("-"))
                return httpx.Response(206, content=data[start:end + 1], headers={"Content-Range": f"bytes {start}-{end}/{len(data)}"})
            return httpx.Response(200, content=data)

        def tenant(user):
            return self.sessions(info={"tenant_id": user})

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {
                "VERVFY_ENVIRONMENT": "test", "VERVFY_AUDIO_SECURITY_HARDENING": "1",
                "VERVFY_STORAGE_WRITES_PAUSED": "0", "VERVFY_STORAGE_NAMESPACE_ID": str(self.namespace),
                "SUPABASE_URL": "https://audio-test.supabase.co", "SUPABASE_BUCKET": "synthetic", "SUPABASE_SERVICE_KEY": "synthetic-test-key",
            }))
            for module in (db, repair, storage_lifecycle):
                stack.enter_context(patch.object(module, "tenant_session", tenant))
            stack.enter_context(patch.object(audio_store, "_transport", httpx.MockTransport(handler)))
            audio_store.close_client()
            try:
                with patch.dict(os.environ, {"VERVFY_AUDIO_SECURITY_HARDENING": "0"}):
                    old = storage_lifecycle.upload_bytes("a", "audio", b"abc", "audio/wav", "wav")
                with tenant("a") as session:
                    session.add(db.TrackRecord(id="cache-repair", user_id="a", filename="sample.wav", title="t", artist="a", album="b", duration=1, has_cover=False, storage_path=old, size_bytes=3))
                    session.commit()
                approved = repair.plan("a", "cache-repair")
                with self.engine.connect() as c:
                    previous_hold = c.execute(sa.text("SELECT j.state,j.available_at,j.claim_token,j.lease_until,j.error_code FROM vervfy_storage.cleanup_jobs j JOIN vervfy_storage.objects o ON o.id=j.object_id WHERE o.path=:path"), {"path": old}).one()
                with self.engine.begin() as operator:
                    repair.apply(approved, attachment_connection=operator)
                with tenant("a") as session:
                    new = session.scalar(sa.select(db.TrackRecord.storage_path).where(db.TrackRecord.id == "cache-repair"))
                    retained = session.execute(sa.text("SELECT vervfy_storage.retained_bytes()" )).scalar_one()
                self.assertNotEqual(new, old)
                self.assertEqual(objects[old], objects[new])
                self.assertEqual(retained, 6)
                self.assertEqual(policies, ["max-age=31536000", "private, no-store, max-age=0, must-revalidate"])
                with self.engine.connect() as c:
                    current_hold = c.execute(sa.text("SELECT j.state,j.available_at,j.claim_token,j.lease_until,j.error_code FROM vervfy_storage.cleanup_jobs j JOIN vervfy_storage.objects o ON o.id=j.object_id WHERE o.path=:path"), {"path": old}).one()
                    self.assertEqual(current_hold, previous_hold)
                    self.assertFalse(c.exec_driver_sql("SELECT physical_cleanup_enabled FROM vervfy_storage.namespaces WHERE id=1").scalar_one())
                    jobs = c.exec_driver_sql("SELECT state FROM vervfy_storage.cleanup_jobs").scalars().all()
                    self.assertTrue(jobs)
                    self.assertEqual(set(jobs), {"held"})
                    self.assertNotIn("claimed", jobs)
                    self.assertNotIn("done", jobs)
                    self.assertEqual(c.exec_driver_sql("SELECT count(*) FROM vervfy_storage.objects WHERE reserved_bytes=3").scalar_one(), 2)
            finally:
                audio_store.close_client()
