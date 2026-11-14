"""Phase 3 real restricted PostgreSQL + synthetic in-process Storage transport."""
import asyncio
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

import audio_store
import library
import server
import storage_lifecycle as lifecycle
import test_storage_lifecycle as foundation
from db import TrackRecord, UploadJob, User
from scripts import upload_worker


class StorageWriterTests(unittest.TestCase):
    setUpClass=classmethod(foundation.StorageLifecycleTests.setUpClass.__func__)
    tx=foundation.StorageLifecycleTests.tx
    attach=foundation.StorageLifecycleTests.attach
    retire=foundation.StorageLifecycleTests.retire
    request=foundation.StorageLifecycleTests.request
    ready=foundation.StorageLifecycleTests.ready
    wait_blocked=foundation.StorageLifecycleTests.wait_blocked

    def setUp(self):
        self.files=self.enterContext(tempfile.TemporaryDirectory(prefix='vervfy-writer-data-'))
        self.objects={}
        self.requests=[]
        self.lock=threading.Lock()
        self.fault=None
        self.enterContext(patch.dict(os.environ,{'VERVFY_STORAGE_NAMESPACE_ID':str(self.binding.namespace_id),
            'VERVFY_ENVIRONMENT':self.binding.environment,'SUPABASE_URL':self.binding.endpoint,
            'SUPABASE_SERVICE_KEY':'synthetic-private-test-key','SUPABASE_BUCKET':self.binding.bucket}))
        self.enterContext(patch.object(audio_store,'_transport',httpx.MockTransport(self.handle)))
        for module in (library,lifecycle,server,upload_worker):
            self.enterContext(patch.object(module,'tenant_session',self.session))
        self.enterContext(patch.object(upload_worker,'resolve_cover',AsyncMock()))
        self.enterContext(patch.object(upload_worker.upload_queue,'requeue'))

    @contextmanager
    def session(self, tenant):
        with Session(self.engines['app_runtime'],expire_on_commit=False) as session:
            @sa.event.listens_for(session,'after_begin')
            def context(_session,_transaction,connection):
                connection.execute(sa.text("SELECT set_config('app.current_user_id',:tenant,true)"),{'tenant':tenant})
            yield session

    def handle(self,request):
        self.requests.append(request)
        self.assertEqual(request.url.host,'vervfy.invalid')
        key=request.url.path.split('/object/',1)[1]
        if key.startswith('authenticated/'):key=key[len('authenticated/'):]
        with self.lock:
            if request.method=='POST':
                self.assertEqual(request.headers['x-upsert'],'false')
                if key in self.objects:return httpx.Response(409)
                self.objects[key]=request.read()
                if self.fault=='after_store':raise httpx.ReadError('Synthetic ambiguous upload',request=request)
                return httpx.Response(200)
            if request.method=='GET':
                if key not in self.objects:return httpx.Response(404)
                return httpx.Response(200,content=b'corrupt' if self.fault=='verify' else self.objects[key])
        self.fail('Unexpected Storage operation: '+request.method)

    def wav(self):
        path=Path(self.files)/(uuid.uuid4().hex+'.wav')
        with wave.open(str(path),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(uuid.uuid4().bytes*1000)
        return str(path)

    def object(self,path):
        with self.admin.connect() as c:
            return c.execute(sa.text('SELECT id,state,classification,upload_verified FROM vervfy_storage.objects WHERE path=:p'),{'p':path}).one()

    def test_upload_verification_immutable_paths_and_retired_escape_hatches(self):
        first=lifecycle.upload_bytes('a','track-cover',b'synthetic jpeg')
        second=lifecycle.upload_bytes('a','track-cover',b'synthetic jpeg')
        self.assertNotEqual(first,second)
        self.assertEqual(self.object(first).state,'ready')
        self.assertEqual(self.objects['synthetic/'+first],b'synthetic jpeg')
        count=len(self.requests)
        for function in (audio_store.upload,audio_store.upload_file,audio_store.delete,audio_store.delete_quietly,audio_store.delete_many):
            with self.subTest(function=function.__name__),self.assertRaises(audio_store.StorageError):function('legacy/object')
        self.assertEqual(len(self.requests),count)

    def test_ambiguous_upload_and_failed_verification_remain_held_and_retry_is_unique(self):
        for fault in ('after_store','verify'):
            self.fault=fault
            with self.assertRaises((httpx.HTTPError,audio_store.StorageError)):
                lifecycle.upload_bytes('a','track-cover',b'private retained bytes')
            path=list(self.objects)[-1].split('/',1)[1]
            row=self.object(path)
            self.assertEqual(row.state,'hold');self.assertFalse(row.upload_verified)
            self.assertFalse(self.retire(type('Obj',(),{'object_id':row.id})()))
            self.fault=None
            retry=lifecycle.upload_bytes('a','track-cover',b'private retained bytes')
            self.assertNotEqual(path,retry)
            self.assertEqual(self.objects['synthetic/'+path],b'private retained bytes')

    def test_namespace_mismatch_and_sqlite_never_issue_storage_requests(self):
        with patch.dict(os.environ,{'VERVFY_STORAGE_NAMESPACE_ID':str(uuid.uuid4())}),self.assertRaises(sa.exc.DBAPIError):
            lifecycle.upload_bytes('a','track-cover',b'private')
        self.assertEqual(self.requests,[])
        @contextmanager
        def sqlite_session(_tenant):
            with Session(sa.create_engine('sqlite://')) as session:yield session
        with patch.object(lifecycle,'tenant_session',sqlite_session),self.assertRaises(audio_store.StorageError):
            lifecycle.upload_bytes('a','track-cover',b'private')
        self.assertEqual(self.requests,[])

    def test_concurrent_duplicate_uploads_retain_winning_music(self):
        source=self.wav();barrier=threading.Barrier(2)
        original=lifecycle.upload_file
        def uploaded(*args,**kwargs):
            result=original(*args,**kwargs);barrier.wait(timeout=10);return result
        with patch.object(lifecycle,'upload_file',side_effect=uploaded),ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(library.Library('a').add_upload_file,Path(source).name,source) for _ in range(2)]
            tracks=[f.result(timeout=20) for f in futures]
        self.assertEqual(tracks[0].id,tracks[1].id)
        info=library.Library('a').audio_info(tracks[0].id)
        self.assertEqual(self.objects['synthetic/'+info.storage_path],Path(source).read_bytes())
        self.assertEqual(len(self.objects),2)
        self.assertEqual(sorted(self.object(key.split('/',1)[1]).state for key in self.objects),['live','ready'])

    def stage(self):
        source=self.wav();job_id=uuid.uuid4().hex
        with patch.object(server.upload_queue,'enqueue'):
            server._queue_staged_upload(job_id,'a',Path(source).name,source)
        with self.session('a') as s:path=s.get(UploadJob,job_id).storage_path
        return job_id,path,Path(source).read_bytes()

    def test_staged_copy_completes_transactionally_without_deleting_source(self):
        job_id,staged,data=self.stage()
        upload_worker.process(job_id,'a')
        with self.session('a') as s:
            job=s.get(UploadJob,job_id)
            self.assertEqual(job.status,'completed');self.assertIsNone(job.storage_path)
            track=s.get(TrackRecord,{'id':job.track_id,'user_id':'a'})
            permanent=track.storage_path
        self.assertIn('/audio/',permanent);self.assertIn('/staged-audio/',staged)
        self.assertEqual(self.objects['synthetic/'+permanent],data)
        self.assertEqual(self.objects['synthetic/'+staged],data)
        self.assertNotEqual(staged,permanent)
        self.assertEqual(self.object(permanent).state,'live')

    def test_duplicate_worker_tokens_fence_late_attachment(self):
        job_id,staged,data=self.stage()
        first_ready=threading.Event();release=threading.Event();first_thread=[]
        original=lifecycle.upload_file
        def upload(*args,**kwargs):
            path=original(*args,**kwargs)
            if args[1]=='audio' and threading.get_ident()==first_thread[0]:
                first_ready.set();self.assertTrue(release.wait(10))
            return path
        def first():
            first_thread.append(threading.get_ident());upload_worker.process(job_id,'a')
        with patch.object(lifecycle,'upload_file',side_effect=upload),ThreadPoolExecutor(max_workers=1) as pool:
            result=pool.submit(first)
            self.assertTrue(first_ready.wait(10))
            try:upload_worker.process(job_id,'a')
            finally:release.set()
            result.result(timeout=10)
        with self.session('a') as s:
            job=s.get(UploadJob,job_id)
            self.assertEqual(job.status,'completed');self.assertEqual(job.attempts,2)
            track=s.get(TrackRecord,{'id':job.track_id,'user_id':'a'})
            self.assertEqual(self.objects['synthetic/'+track.storage_path],data)
        self.assertEqual(self.objects['synthetic/'+staged],data)
        self.assertEqual(len(self.objects),3)

    def test_worker_read_failure_keeps_source_and_retries(self):
        job_id,staged,data=self.stage()
        with patch.object(lifecycle,'download_staged',side_effect=audio_store.StorageError('synthetic interruption')):
            upload_worker.process(job_id,'a')
        with self.session('a') as s:
            job=s.get(UploadJob,job_id)
            self.assertEqual(job.status,'pending');self.assertEqual(job.storage_path,staged)
        self.assertEqual(self.objects['synthetic/'+staged],data)
        upload_worker.process(job_id,'a')
        with self.session('a') as s:self.assertEqual(s.get(UploadJob,job_id).status,'completed')

    def test_shared_artwork_survives_detach_and_stale_resolution(self):
        ids=[uuid.uuid4().hex for _ in range(2)]
        album=uuid.uuid4().hex
        with self.tx() as c:
            for ident in ids:self.attach(c,None,ident=ident)
            c.execute(sa.text('UPDATE tracks SET album=:album WHERE id IN (:a,:b)'),{'album':album,'a':ids[0],'b':ids[1]})
        lib=library.Library('a')
        self.assertEqual(lib.set_album_user_cover(ids[0],b'shared album cover'),2)
        before=lib.get(ids[1]);shared=before.cover_path
        lib.remove(ids[0])
        obj=self.object(shared)
        self.assertFalse(self.retire(type('Obj',(),{'object_id':obj.id})()))
        lib.set_user_cover(ids[1],b'new user cover')
        self.assertFalse(lib.set_resolved_cover(ids[1],'upload',b'stale upload cover',expected_version=before.media_version))
        current=lib.get(ids[1])
        self.assertEqual(self.objects['synthetic/'+current.cover_path],b'new user cover')
        self.assertEqual(self.objects['synthetic/'+shared],b'shared album cover')

    def test_account_deletion_racing_upload_retains_ambiguous_object(self):
        tenant=uuid.uuid4().hex
        with self.admin.begin() as c:
            c.execute(sa.text("INSERT INTO users(id,username,username_key,password_hash,created_at) VALUES(:id,:id,:id,'synthetic',1)"),{'id':tenant})
        source=self.wav();uploaded=threading.Event();release=threading.Event()
        original=lifecycle.upload_file
        def pause(*args,**kwargs):
            path=original(*args,**kwargs);uploaded.set();self.assertTrue(release.wait(10));return path
        with patch.object(lifecycle,'upload_file',side_effect=pause),ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(library.Library(tenant).add_upload_file,Path(source).name,source)
            self.assertTrue(uploaded.wait(10))
            try:
                with self.session(tenant) as s:
                    s.delete(s.get(User,tenant,with_for_update=True));s.commit()
            finally:release.set()
            with self.assertRaises(RuntimeError):pending.result(timeout=10)
        self.assertEqual(len(self.objects),1)
        with self.admin.connect() as c:
            self.assertEqual(c.execute(sa.text('SELECT count(*) FROM tracks WHERE user_id=:id'),{'id':tenant}).scalar_one(),0)
            self.assertEqual(c.execute(sa.text('SELECT count(*) FROM vervfy_storage.cleanup_jobs j JOIN vervfy_storage.objects o ON o.id=j.object_id WHERE o.tenant_id=:id'),{'id':tenant}).scalar_one(),1)

    def test_lazy_migration_preserves_database_bytes(self):
        ident=uuid.uuid4().hex
        with self.session('a') as s:
            s.add(TrackRecord(id=ident,user_id='a',filename='synthetic.wav',title='lazy',artist='r',album='l',duration=1,has_cover=False,cover_source='generated',audio_data=b'legacy private audio',size_bytes=20));s.commit()
        path=library.Library('a').ensure_audio_storage(ident)
        self.assertEqual(self.objects['synthetic/'+path],b'legacy private audio')
        with self.session('a') as s:
            self.assertEqual(s.get(TrackRecord,{'id':ident,'user_id':'a'}).audio_data,b'legacy private audio')
        self.assertEqual(library.Library('a').ensure_audio_storage(ident),path)

    def test_active_sources_have_no_direct_delete_or_unmanaged_upload_calls(self):
        import ast
        root=Path(__file__).resolve().parents[1]
        for rel in ('library.py','server.py','scripts/upload_worker.py','cover_art.py'):
            tree=ast.parse((root/rel).read_text())
            forbidden=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='audio_store' and node.func.attr in {'upload','upload_file','delete','delete_quietly','delete_many'}:
                    forbidden.append(node.lineno)
            self.assertEqual(forbidden,[],rel)

    def test_unsafe_maintenance_entry_points_fail_before_work(self):
        root=Path(__file__).resolve().parents[1]
        for rel in ('migrate.py','scripts/migrate_audio_to_storage.py','scripts/move_audio_to_storage.py','scripts/backfill_cover_storage.py','scripts/backfill_covers.py','scripts/rebuild_covers.py','scripts/migrate_local_data.py'):
            with self.subTest(script=rel):
                result=subprocess.run([sys.executable,str(root/rel)],cwd=root,env={**os.environ,'DATABASE_URL':'sqlite://'},capture_output=True,text=True,timeout=15)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('retired',(result.stdout+result.stderr).lower())


    def test_create_only_collision_never_overwrites_existing_bytes(self):
        reserve=lifecycle._reserve
        def collide(*args):
            obj=reserve(*args)
            self.objects['synthetic/'+obj.path]=b'previous private bytes'
            return obj
        with patch.object(lifecycle,'_reserve',side_effect=collide),self.assertRaises(audio_store.StorageError):
            lifecycle.upload_bytes('a','track-cover',b'new private bytes')
        key=next(iter(self.objects))
        self.assertEqual(self.objects[key],b'previous private bytes')
        self.assertEqual(self.object(key.split('/',1)[1]).state,'hold')

    def test_interrupted_upload_survives_unavailable_database_and_fresh_connection(self):
        advance=lifecycle._advance
        def unavailable(user,obj,state):
            if state=='hold':raise RuntimeError('Synthetic database outage')
            return advance(user,obj,state)
        self.fault='after_store'
        with patch.object(lifecycle,'_advance',side_effect=unavailable),self.assertRaises(audio_store.StorageError):
            lifecycle.upload_bytes('a','track-cover',b'uncertain completion')
        path=next(iter(self.objects)).split('/',1)[1]
        obj=self.object(path)
        self.assertEqual(obj.state,'uploading');self.assertFalse(obj.upload_verified)
        self.assertFalse(self.retire(type('Obj',(),{'object_id':obj.id})()))
        with self.admin.connect() as c:
            self.assertEqual(c.execute(sa.text('SELECT state FROM vervfy_storage.cleanup_jobs WHERE object_id=:id'),{'id':obj.id}).scalar_one(),'held')

    def test_managed_file_upload_has_explicit_length_create_only_and_full_verification(self):
        data=os.urandom(150*1024)
        source=Path(self.files)/'synthetic.bin';source.write_bytes(data)
        path=lifecycle.upload_file('a','audio',str(source),'application/octet-stream','bin')
        post=[request for request in self.requests if request.method=='POST'][0]
        self.assertEqual(post.content,data)
        self.assertEqual(post.headers['content-length'],str(len(data)))
        self.assertEqual(post.headers['cache-control'],'max-age=31536000')
        self.assertNotIn('transfer-encoding',post.headers)
        self.assertEqual(self.objects['synthetic/'+path],data)
        self.assertTrue(self.object(path).upload_verified)

    def test_artist_photo_swap_and_removal_keep_bytes_and_queue_references(self):
        name=uuid.uuid4().hex
        first=lifecycle.upload_bytes('a','artist-photo',b'first private photo')
        second=lifecycle.upload_bytes('a','artist-photo',b'second private photo')
        server._save_artist_photo('a',name,None,source='user',storage_path=first)
        server._save_artist_photo('a',name,None,source='user',storage_path=second)
        self.assertEqual(server._artist_photo_record('a',name)['storage_path'],second)
        self.assertIsNone(server._artist_photo_record('b',name))
        self.assertFalse(self.retire(type('Obj',(),{'object_id':self.object(second).id})()))
        server._delete_artist_photo('a',name)
        self.assertTrue(self.retire(type('Obj',(),{'object_id':self.object(second).id})()))
        self.assertEqual(self.objects['synthetic/'+first],b'first private photo')
        self.assertEqual(self.objects['synthetic/'+second],b'second private photo')

    def test_worker_permanent_failure_retains_staged_reference(self):
        job_id,path,data=self.stage()
        with self.session('a') as s:
            s.get(UploadJob,job_id).attempts=upload_worker.MAX_ATTEMPTS-1;s.commit()
        with patch.object(lifecycle,'download_staged',side_effect=audio_store.StorageError('synthetic failure')):
            upload_worker.process(job_id,'a')
        with self.session('a') as s:
            job=s.get(UploadJob,job_id)
            self.assertEqual(job.status,'failed');self.assertEqual(job.storage_path,path)
        self.assertEqual(self.objects['synthetic/'+path],data)
        self.assertFalse(self.retire(type('Obj',(),{'object_id':self.object(path).id})()))

    def test_job_row_lock_preserves_source_during_account_cascade(self):
        # Use a disposable synthetic tenant so deletion cannot affect other tests.
        tenant=uuid.uuid4().hex
        with self.admin.begin() as c:
            c.execute(sa.text("INSERT INTO users(id,username,username_key,password_hash,created_at) VALUES(:id,:id,:id,'synthetic',1)"),{'id':tenant})
        source=self.wav();job_id=uuid.uuid4().hex
        with patch.object(server.upload_queue,'enqueue'):
            server._queue_staged_upload(job_id,tenant,Path(source).name,source)
        with self.session(tenant) as s:path=s.get(UploadJob,job_id).storage_path
        reading=threading.Event();release=threading.Event();pids=__import__('queue').Queue()
        original=lifecycle.download_staged
        def read(*args):
            reading.set();self.assertTrue(release.wait(10));return original(*args)
        def delete():
            with self.session(tenant) as s:
                pids.put(s.execute(sa.text('SELECT pg_backend_pid()')).scalar_one())
                s.delete(s.get(User,tenant,with_for_update=True));s.commit()
        with patch.object(lifecycle,'download_staged',side_effect=read),ThreadPoolExecutor(max_workers=2) as pool:
            worker=pool.submit(upload_worker.process,job_id,tenant)
            self.assertTrue(reading.wait(10))
            deletion=pool.submit(delete)
            try:self.wait_blocked(pids.get(timeout=10))
            finally:release.set()
            deletion.result(timeout=15);worker.result(timeout=15)
        self.assertEqual(self.objects['synthetic/'+path],Path(source).read_bytes())
        with self.admin.connect() as c:
            self.assertEqual(c.execute(sa.text('SELECT count(*) FROM users WHERE id=:id'),{'id':tenant}).scalar_one(),0)

    def test_production_startup_refuses_missing_guards_using_existing_catalog_access(self):
        with patch.object(server,'engine',self.engines['app_runtime']):
            server._require_migrated_schema()
            with self.admin.begin() as c:
                c.exec_driver_sql('ALTER TABLE public.tracks DISABLE TRIGGER storage_reference_guard')
            try:
                with patch.object(server,'is_production',True),patch.object(server,'_require_private_upload_storage') as storage_check,self.assertRaisesRegex(RuntimeError,'reference guards'):
                    server.startup()
                storage_check.assert_not_called()
            finally:
                with self.admin.begin() as c:
                    c.exec_driver_sql('ALTER TABLE public.tracks ENABLE TRIGGER storage_reference_guard')
