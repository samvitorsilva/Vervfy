"""Local-only credential/schema regressions; no Google services required."""
import importlib.util
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import auth
import server
from db import Base, ProviderIdentity, User


class CredentialTests(unittest.TestCase):
    def test_existing_password_login_rotates_session(self):
        hashed = auth.hash_password('existing-password')
        request = SimpleNamespace(session={'csrf_token': 'csrf', 'sid': 'old'}, client=None)
        with (
            patch.object(server.user_store, 'get_by_username', return_value={
                'id': 'existing', 'password_hash': hashed, 'session_version': 7,
            }),
            patch.object(server.login_throttle, 'is_locked', return_value=False),
            patch.object(server.login_throttle, 'clear'),
            patch.object(server.session_store, 'revoke') as revoke,
            patch.object(server.session_store, 'create', return_value='fresh') as create,
        ):
            response = server.login_submit(request, 'existing', 'existing-password', 'csrf')
        self.assertEqual(response.status_code, 303)
        revoke.assert_called_once_with('old')
        create.assert_called_once_with('existing')
        self.assertEqual(request.session, {'user_id': 'existing', 'sv': 7, 'sid': 'fresh'})

    def test_password_and_missing_credentials(self):
        hashed = auth.hash_password('existing-password')
        self.assertTrue(auth.verify_password('existing-password', hashed))
        self.assertFalse(auth.verify_password('wrong', hashed))
        with patch.object(auth.bcrypt, 'checkpw', return_value=True):
            self.assertFalse(auth.verify_password('anything', None))
            self.assertFalse(auth.verify_password('anything', ''))

    def test_passwordless_sensitive_action_fails_closed(self):
        with (
            patch.object(server.request_throttle, 'allow', return_value=True),
            self.assertRaises(HTTPException) as caught,
        ):
            server.verify_current_password(SimpleNamespace(id='a', password_hash=None), 'anything')
        self.assertEqual(caught.exception.status_code, 400)

    def test_passwordless_login_does_not_issue_session(self):
        request = SimpleNamespace(session={'csrf_token': 'csrf'}, client=None)
        with (
            patch.object(server.user_store, 'get_by_username', return_value={'password_hash': None}),
            patch.object(server.login_throttle, 'is_locked', return_value=False),
            patch.object(server.login_throttle, 'record_failure'),
            patch.object(server.session_store, 'create') as create,
        ):
            response = server.login_submit(request, 'someone', 'password', 'csrf')
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()
        self.assertEqual(request.session, {'csrf_token': 'csrf'})

    def test_passwordless_account_routes_never_mutate_data(self):
        user = User(id='a', username='someone', password_hash=None)
        request = SimpleNamespace(session={'sid': 'existing', 'sv': 3})
        actions = (
            lambda: server.change_account_email(
                server.EmailChangeRequest(email='new@example.com', current_password='guess'), request, user, None),
            lambda: server.change_password(
                server.PasswordChangeRequest(current_password='guess', new_password='new-password'), request, user, None),
            lambda: server.delete_account(
                server.AccountDeletionRequest(current_password='guess', confirmation='DELETE'), request, user, None),
        )
        with (
            patch.object(server.request_throttle, 'allow', return_value=True),
            patch.object(server.user_store, 'update_email') as email,
            patch.object(server.user_store, 'update_password') as password,
            patch.object(server.user_store, 'bump_session_version') as version,
            patch.object(server.session_store, 'revoke_user') as revoke,
            patch.object(server, 'tenant_session') as database,
            patch.object(server.user_store, 'account_security', return_value={
                'has_password': False, 'google_linked': True,
            }),
            patch.object(server.audio_store, 'delete_many') as storage,
        ):
            for action in actions:
                with self.assertRaises(HTTPException) as caught:
                    action()
                self.assertEqual(caught.exception.status_code, 403)
            for mutation in (email, password, version, revoke, database, storage):
                mutation.assert_not_called()
        self.assertEqual(request.session, {'sid': 'existing', 'sv': 3})


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine('sqlite://')
        self.addCleanup(self.engine.dispose)

    def test_identity_uniqueness_ownership_and_deletion(self):
        with self.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        sessions = sessionmaker(self.engine)
        with sessions() as session:
            session.add_all([User(id=x, username=x, username_key=x, password_hash=None, created_at=1) for x in ('a', 'b')])
            session.commit()
            session.add_all([ProviderIdentity(issuer='issuer', subject=x, user_id=x, created_at=1) for x in ('a', 'b')])
            session.commit()
            session.add(ProviderIdentity(issuer='issuer', subject='a', user_id='b', created_at=1))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()
            session.add(ProviderIdentity(issuer='issuer', subject='orphan', user_id='missing', created_at=1))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()
            session.execute(sa.delete(User).where(User.id == 'a'))
            session.commit()
            self.assertIsNone(session.get(ProviderIdentity, ('issuer', 'a')))
            self.assertEqual(session.get(ProviderIdentity, ('issuer', 'b')).user_id, 'b')
            self.assertIsNotNone(session.get(User, 'b'))

    def test_user_store_deletion_cleans_only_owned_identities_without_sqlite_cascade(self):
        Base.metadata.create_all(self.engine)
        sessions = sessionmaker(self.engine)
        with sessions() as session:
            session.add_all([User(id=x, username=x, username_key=x, password_hash='hash', created_at=1) for x in ('a', 'b')])
            session.commit()
            session.add_all([ProviderIdentity(issuer='issuer', subject=x, user_id=x, created_at=1) for x in ('a', 'b')])
            session.commit()
        with patch.object(auth, 'tenant_session', side_effect=lambda user_id: sessions()):
            auth.UserStore().delete_user('a')
        with sessions() as session:
            self.assertIsNone(session.get(ProviderIdentity, ('issuer', 'a')))
            self.assertIsNotNone(session.get(ProviderIdentity, ('issuer', 'b')))
            self.assertIsNotNone(session.get(User, 'b'))

    def test_migration_preserves_existing_data_and_guards_downgrade(self):
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/0021_provider_identities.py'
        spec = importlib.util.spec_from_file_location('oauth_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE users (id VARCHAR(32) PRIMARY KEY, password_hash VARCHAR(128) NOT NULL, session_version INTEGER NOT NULL)')
            connection.exec_driver_sql('CREATE TABLE library (user_id VARCHAR(32) REFERENCES users(id), payload TEXT)')
            connection.exec_driver_sql("INSERT INTO users VALUES ('existing', 'unchanged-hash', 7)")
            connection.exec_driver_sql("INSERT INTO library VALUES ('existing', 'unchanged-library')")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertEqual(connection.exec_driver_sql('SELECT * FROM users').one(), ('existing', 'unchanged-hash', 7))
                self.assertEqual(connection.exec_driver_sql('SELECT * FROM library').one(), ('existing', 'unchanged-library'))
                connection.exec_driver_sql("INSERT INTO users VALUES ('passwordless', NULL, 0)")
                with self.assertRaisesRegex(RuntimeError, 'passwordless'):
                    migration.downgrade()
                connection.exec_driver_sql("DELETE FROM users WHERE id='passwordless'")
                connection.exec_driver_sql("INSERT INTO provider_identities VALUES ('issuer', 'subject', 'existing', 1)")
                with self.assertRaisesRegex(RuntimeError, 'identities'):
                    migration.downgrade()
                connection.exec_driver_sql('DELETE FROM provider_identities')
                migration.downgrade()
                self.assertNotIn('provider_identities', sa.inspect(connection).get_table_names())
                self.assertFalse(next(c for c in sa.inspect(connection).get_columns('users') if c['name'] == 'password_hash')['nullable'])
                self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_key_check').all(), [])
                self.assertEqual(connection.exec_driver_sql('SELECT * FROM library').one(), ('existing', 'unchanged-library'))

    def test_missing_media_columns_migration_preserves_existing_rows(self):
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/0023_missing_media_columns.py'
        spec = importlib.util.spec_from_file_location('media_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                'CREATE TABLE tracks (id VARCHAR(64) PRIMARY KEY, title TEXT NOT NULL)'
            )
            connection.exec_driver_sql(
                'CREATE TABLE upload_jobs (id VARCHAR(32) PRIMARY KEY, filename TEXT NOT NULL)'
            )
            connection.exec_driver_sql("INSERT INTO tracks VALUES ('track-1', 'synthetic')")
            connection.exec_driver_sql(
                "INSERT INTO upload_jobs VALUES ('job-1', 'synthetic.mp3')"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            self.assertEqual(
                connection.exec_driver_sql(
                    'SELECT id, title, cover_url FROM tracks'
                ).one(),
                ('track-1', 'synthetic', None),
            )
            self.assertEqual(
                connection.exec_driver_sql(
                    'SELECT id, filename, cover_data FROM upload_jobs'
                ).one(),
                ('job-1', 'synthetic.mp3', None),
            )

            with Operations.context(MigrationContext.configure(connection)):
                with self.assertRaisesRegex(RuntimeError, 'forward-only'):
                    migration.downgrade()


class StartupSchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine('sqlite://')
        self.addCleanup(self.engine.dispose)

    def start(self):
        with (
            patch.object(server, 'engine', self.engine),
            patch.object(server, 'is_production', False),
            patch.object(server.audio_store, 'enabled', return_value=False),
            patch.object(server.user_store, 'count', return_value=0),
        ):
            server.startup()

    def test_startup_refuses_unverified_public_upload_storage(self):
        with (
            patch.object(server, 'is_production', False),
            patch.object(server, '_require_migrated_schema'),
            patch.object(server.audio_store, 'enabled', return_value=True),
            patch.object(server.audio_store, 'bucket_is_private', return_value=False),
            patch.object(server.user_store, 'count') as count,
        ):
            with self.assertRaisesRegex(RuntimeError, 'must be explicitly private'):
                server.startup()
        count.assert_not_called()

    def test_fresh_database_requires_explicit_migration_without_creating_tables(self):
        with self.assertRaisesRegex(RuntimeError, 'alembic upgrade head'):
            self.start()
        self.assertEqual(sa.inspect(self.engine).get_table_names(), [])

    def test_existing_schema_is_not_created_or_altered_at_startup(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                'CREATE TABLE users (id VARCHAR(32) PRIMARY KEY)'
            )
            connection.exec_driver_sql(
                'CREATE TABLE upload_jobs (id VARCHAR(32) PRIMARY KEY, cover_data BLOB)'
            )
            connection.exec_driver_sql(
                "INSERT INTO upload_jobs (id) VALUES ('preserve-me')"
            )
            connection.exec_driver_sql(
                'CREATE TABLE tracks (id VARCHAR(64) PRIMARY KEY, cover_url TEXT)'
            )
            connection.exec_driver_sql(
                "INSERT INTO tracks VALUES ('track-1', 'preserve-url')"
            )
        self.start()
        self.assertEqual(
            {column['name'] for column in sa.inspect(self.engine).get_columns('upload_jobs')},
            {'id', 'cover_data'},
        )
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.exec_driver_sql('SELECT id FROM upload_jobs').scalar_one(),
                'preserve-me',
            )
            self.assertEqual(
                connection.exec_driver_sql(
                    'SELECT id, cover_url FROM tracks'
                ).one(),
                ('track-1', 'preserve-url'),
            )

    def test_existing_schema_missing_0023_column_is_rejected_without_repair(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                'CREATE TABLE users (id VARCHAR(32) PRIMARY KEY)'
            )
            connection.exec_driver_sql(
                'CREATE TABLE tracks (id VARCHAR(64) PRIMARY KEY, cover_url TEXT)'
            )
            connection.exec_driver_sql(
                'CREATE TABLE upload_jobs (id VARCHAR(32) PRIMARY KEY)'
            )

        with self.assertRaisesRegex(RuntimeError, 'missing_tables_or_columns'):
            self.start()
        self.assertEqual(
            {column['name'] for column in sa.inspect(self.engine).get_columns('upload_jobs')},
            {'id'},
        )

    def test_startup_does_not_preempt_pending_migration_0023(self):
        path = (
            Path(__file__).resolve().parents[1]
            / 'alembic/versions/0023_missing_media_columns.py'
        )
        spec = importlib.util.spec_from_file_location('startup_migration_0023', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                'CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'
            )
            connection.exec_driver_sql(
                "INSERT INTO alembic_version VALUES ('0022_provider_identity_lookup')"
            )
            connection.exec_driver_sql(
                'CREATE TABLE tracks (id VARCHAR(64) PRIMARY KEY, title TEXT NOT NULL)'
            )
            connection.exec_driver_sql(
                'CREATE TABLE upload_jobs (id VARCHAR(32) PRIMARY KEY, filename TEXT NOT NULL)'
            )
            connection.exec_driver_sql(
                "INSERT INTO tracks VALUES ('track-1', 'preserve-track')"
            )
            connection.exec_driver_sql(
                "INSERT INTO upload_jobs VALUES ('job-1', 'preserve-job')"
            )

        with self.assertRaisesRegex(RuntimeError, 'schema is incomplete'):
            self.start()
        self.assertNotIn(
            'cover_url',
            {column['name'] for column in sa.inspect(self.engine).get_columns('tracks')},
        )
        self.assertNotIn(
            'cover_data',
            {
                column['name']
                for column in sa.inspect(self.engine).get_columns('upload_jobs')
            },
        )

        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            self.assertEqual(
                connection.exec_driver_sql(
                    'SELECT id, title, cover_url FROM tracks'
                ).one(),
                ('track-1', 'preserve-track', None),
            )
            self.assertEqual(
                connection.exec_driver_sql(
                    'SELECT id, filename, cover_data FROM upload_jobs'
                ).one(),
                ('job-1', 'preserve-job', None),
            )


class GoogleAccountLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(
            self.engine, autoflush=False, expire_on_commit=False
        )
        self.patches = (
            patch.object(auth, "SessionLocal", self.sessions),
            patch.object(
                auth,
                "tenant_session",
                side_effect=lambda tenant_id: self.sessions(
                    info={"tenant_id": tenant_id}
                ),
            ),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.engine.dispose)
        self.store = auth.UserStore()

    def _add_user(self, user_id, *, password_hash="existing-hash", email=None):
        with self.sessions() as session:
            session.add(
                User(
                    id=user_id,
                    username=user_id,
                    username_key=user_id.lower(),
                    email=email,
                    password_hash=password_hash,
                    created_at=1,
                    session_version=0,
                )
            )
            session.commit()

    def test_google_onboarding_is_unique_and_keeps_email_non_authoritative(self):
        self._add_user("existing", email="used@example.com")
        created = self.store.create_google_user(
            "new-user", "new@example.com", "google-subject"
        )
        self.assertIsNone(self.store.get_by_id(created["id"]).password_hash)
        self.assertEqual(created["email"], "new@example.com")
        self.assertEqual(
            self.store.account_security(created["id"]),
            {"has_password": False, "google_linked": True},
        )
        with self.assertRaises(ValueError):
            self.store.create_google_user(
                "another-user", "another@example.com", "google-subject"
            )
        self.assertIsNone(self.store.get_by_username("another-user"))
        with self.assertRaises(ValueError):
            self.store.create_google_user(
                "other-user", "used@example.com", "other-subject"
            )
        self.assertIsNone(self.store.get_by_username("other-user"))

    def test_google_signup_flushes_user_before_identity_and_commits_both(self):
        insert_order = []

        def capture_insert_order(
            connection, cursor, statement, parameters, context, executemany
        ):
            del connection, cursor, parameters, context, executemany
            statement = statement.lower()
            if statement.startswith("insert into users"):
                insert_order.append("users")
            elif statement.startswith("insert into provider_identities"):
                insert_order.append("provider_identities")

        sa.event.listen(self.engine, "before_cursor_execute", capture_insert_order)
        self.addCleanup(
            sa.event.remove,
            self.engine,
            "before_cursor_execute",
            capture_insert_order,
        )

        created = self.store.create_google_user(
            "ordered-user", "ordered@example.com", "ordered-subject"
        )

        self.assertEqual(insert_order, ["users", "provider_identities"])
        self.assertIsNotNone(self.store.get_by_id(created["id"]))
        with self.sessions() as session:
            identity = session.get(
                ProviderIdentity,
                ("https://accounts.google.com", "ordered-subject"),
            )
        self.assertIsNotNone(identity)
        self.assertEqual(identity.user_id, created["id"])

    def test_google_signup_rolls_back_flushed_user_if_identity_insert_fails(self):
        existing = self.store.create_google_user(
            "existing-google-user", None, "already-linked-subject"
        )

        with self.assertRaisesRegex(
            ValueError, "username or Google account"
        ):
            self.store.create_google_user(
                "rolled-back-user", None, "already-linked-subject"
            )

        self.assertIsNone(self.store.get_by_username("rolled-back-user"))
        with self.sessions() as session:
            identity = session.get(
                ProviderIdentity,
                ("https://accounts.google.com", "already-linked-subject"),
            )
            user_count = session.query(User).filter_by(
                username="rolled-back-user"
            ).count()
        self.assertIsNotNone(identity)
        self.assertEqual(identity.user_id, existing["id"])
        self.assertEqual(user_count, 0)

    def test_link_unlink_and_password_creation_preserve_last_login_method(self):
        self._add_user("password-user")
        version = self.store.link_google_identity(
            "password-user", "linked-subject"
        )
        self.assertEqual(version, 1)
        self.assertEqual(
            self.store.account_security("password-user"),
            {"has_password": True, "google_linked": True},
        )
        with self.assertRaises(ValueError):
            self.store.link_google_identity("password-user", "linked-subject")
        version = self.store.unlink_google_identity("password-user")
        self.assertEqual(version, 2)

        passwordless = self.store.create_google_user(
            "google-user", None, "google-only-subject"
        )
        with self.assertRaisesRegex(ValueError, "another sign-in method"):
            self.store.unlink_google_identity(passwordless["id"])
        version = self.store.set_password_and_bump_version(
            passwordless["id"],
            "new-password-hash",
            expected_password_hash=None,
        )
        self.assertEqual(version, 1)
        with self.assertRaisesRegex(ValueError, "already set"):
            self.store.set_password_and_bump_version(
                passwordless["id"],
                "replacement-hash",
                expected_password_hash=None,
            )
        self.assertEqual(
            self.store.unlink_google_identity(passwordless["id"]), 2
        )

    def test_google_reauthentication_proof_is_bound_to_session_and_consumed_once(self):
        user = User(
            id="google-user",
            username="google-user",
            password_hash=None,
            session_version=3,
        )
        request = SimpleNamespace(
            session={"sid": "active-session", "sv": 3}
        )
        proof = {
            "purpose": "account_delete",
            "user_id": "google-user",
            "session_id": "active-session",
            "session_version": 3,
            "auth_time": int(time.time()),
            "verified_at": int(time.time()),
        }

        class ProofStore:
            consumed = False

            def consume_reauthentication_proof(self, _session_id, _purpose):
                if self.consumed:
                    return None
                self.consumed = True
                return proof

        store = ProofStore()
        with patch.object(server, "google_oauth_service", store):
            server.verify_google_action_proof(request, user, "account_delete")
            with self.assertRaises(HTTPException) as caught:
                server.verify_google_action_proof(request, user, "account_delete")
        self.assertEqual(caught.exception.status_code, 403)

        request.session["sv"] = 4
        with (
            patch.object(server, "google_oauth_service", store),
            self.assertRaises(HTTPException) as caught,
        ):
            server.verify_google_action_proof(request, user, "account_delete")
        self.assertEqual(caught.exception.status_code, 403)
