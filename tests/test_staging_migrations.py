"""Full-chain regressions in a disposable Unix-socket-only PostgreSQL cluster."""
import ast
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.exc import DBAPIError
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HEAD = '0028_webauthn_enrollment'
PRE_ACCOUNT_MIGRATION_HEAD = '0020_playlist_last_played'
ACCOUNT_TABLES = {
    'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
    'upload_jobs', 'artist_photos', 'track_listens', 'provider_identities',
}


def migration(filename):
    spec = importlib.util.spec_from_file_location('reviewed_migration', ROOT / 'alembic/versions' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationChainTests(unittest.TestCase):
    def test_complete_linear_chain_includes_oauth_migrations(self):
        script = ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))
        self.assertEqual(script.get_heads(), [HEAD])
        chain = list(script.walk_revisions())
        self.assertEqual(len(chain), 28)
        for newer, older in zip(chain, chain[1:]):
            self.assertEqual(newer.down_revision, older.revision)
        self.assertIsNone(chain[-1].down_revision)
        self.assertTrue({'0021_provider_identities', '0022_provider_identity_lookup',
                         '0023_missing_media_columns', '0024_provider_identity_access',
                         '0027_webauthn_foundation', '0028_webauthn_enrollment'}
                        <= {r.revision for r in chain})

    def test_sqlite_cover_constraint_preserves_rows(self):
        engine = sa.create_engine('sqlite://')
        try:
            with engine.begin() as c:
                c.exec_driver_sql("CREATE TABLE tracks (id TEXT PRIMARY KEY, cover_source VARCHAR(20) NOT NULL, CONSTRAINT ck_tracks_cover_source CHECK (cover_source IN ('embedded','user','placeholder','unknown')))")
                c.exec_driver_sql("INSERT INTO tracks VALUES ('old','embedded')")
                with Operations.context(MigrationContext.configure(c)):
                    migration('0025_track_cover_sources.py').upgrade()
                    migration('0026_application_runtime_grants.py').upgrade()
                c.exec_driver_sql("INSERT INTO tracks VALUES ('new','generated')")
                self.assertEqual(c.exec_driver_sql('SELECT cover_source FROM tracks ORDER BY id').scalars().all(), ['generated', 'embedded'])
                with self.assertRaises(DBAPIError):
                    c.exec_driver_sql("INSERT INTO tracks VALUES ('bad','invalid')")
        finally:
            engine.dispose()

    def test_new_migrations_refuse_downgrade(self):
        for name in (
            '0023_missing_media_columns.py',
            '0024_provider_identity_runtime_access.py',
            '0025_track_cover_sources.py',
            '0026_application_runtime_grants.py',
        ):
            with self.assertRaisesRegex(RuntimeError, 'forward-only'):
                migration(name).downgrade()


class StagingPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getuid() == 0 or not all(shutil.which(x) for x in ('initdb', 'pg_ctl')):
            raise unittest.SkipTest('Requires non-root local PostgreSQL binaries')
        cls.directory = tempfile.TemporaryDirectory(prefix='vervfy-staging-test-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
        subprocess.run(['initdb', '-D', str(cls.root / 'data'), '-A', 'trust', '-U', 'test_admin', '--no-locale', '--encoding=UTF8'], env=env, check=True, capture_output=True)
        subprocess.run(['pg_ctl', '-D', str(cls.root / 'data'), '-l', str(cls.root / 'log'), '-o', f"-k {cls.root} -c listen_addresses='' -c unix_socket_permissions=0700", '-w', 'start'], env=env, check=True, capture_output=True)
        cls.addClassCleanup(subprocess.run, ['pg_ctl', '-D', str(cls.root / 'data'), '-m', 'fast', '-w', 'stop'], env=env, check=True, capture_output=True)
        cls.url = sa.URL.create('postgresql+psycopg', username='test_admin', database='postgres', query={'host': str(cls.root)})
        cls.engine = sa.create_engine(cls.url)
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.begin() as c:
            c.exec_driver_sql('CREATE ROLE postgres LOGIN CREATEROLE BYPASSRLS')
            c.exec_driver_sql('CREATE ROLE supabase_admin NOLOGIN CREATEROLE')
            c.exec_driver_sql('CREATE ROLE migration_owner LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS')
            c.exec_driver_sql('GRANT CREATE ON DATABASE postgres TO migration_owner')
            c.exec_driver_sql('ALTER SCHEMA public OWNER TO migration_owner')
            c.exec_driver_sql('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            for name in ('app_runtime', 'google_auth_lookup'):
                c.exec_driver_sql(f'CREATE ROLE {name} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS')
            for name in ('vervfy_identity_lookup_owner', 'vervfy_identity_lookup'):
                c.exec_driver_sql(f'CREATE ROLE {name} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS')
            for name in (
                'google_auth_lookup',
                'vervfy_identity_lookup_owner',
                'vervfy_identity_lookup',
            ):
                c.exec_driver_sql(
                    f'GRANT {name} TO postgres '
                    'WITH ADMIN TRUE, INHERIT FALSE, SET FALSE'
                )
                c.execute(sa.text("""
                    UPDATE pg_catalog.pg_auth_members
                    SET grantor='supabase_admin'::regrole
                    WHERE roleid=CAST(:role AS regrole)
                      AND member='postgres'::regrole
                      AND grantor=current_user::regrole
                """), {'role': name})
            c.exec_driver_sql('SET ROLE postgres')
            c.exec_driver_sql(
                'GRANT vervfy_identity_lookup_owner TO migration_owner '
                'WITH ADMIN FALSE, INHERIT FALSE, SET TRUE'
            )
            c.exec_driver_sql(
                'GRANT vervfy_identity_lookup TO google_auth_lookup '
                'WITH ADMIN FALSE, INHERIT TRUE, SET FALSE'
            )
            c.exec_driver_sql('RESET ROLE')
        cls.migration_url = cls.url.set(username='migration_owner').render_as_string(hide_password=False)
        # Both URLs are explicit local sockets; never consult a hosted URL.
        with patch.dict(os.environ, {'DATABASE_URL': cls.migration_url, 'MIGRATION_DATABASE_URL': cls.migration_url}):
            command.upgrade(Config(str(ROOT / 'alembic.ini')), PRE_ACCOUNT_MIGRATION_HEAD)
        import bcrypt

        cls.passwords = {
            'a': ('Synthetic-password-a', bcrypt.hashpw(
                b'Synthetic-password-a', bcrypt.gensalt(rounds=4)
            ).decode()),
            'b': ('Synthetic-password-b', bcrypt.hashpw(
                b'Synthetic-password-b', bcrypt.gensalt(rounds=4)
            ).decode()),
        }
        with cls.engine.begin() as c:
            c.execute(sa.text("""
                INSERT INTO users(id,username,username_key,password_hash,created_at)
                VALUES (:id,:username,:username,:password_hash,1)
            """), [
                {'id': user_id, 'username': f'synthetic-{user_id}',
                 'password_hash': password_hash}
                for user_id, (_, password_hash) in cls.passwords.items()
            ])
            for source in ('embedded', 'user', 'placeholder', 'unknown'):
                c.execute(sa.text("""
                    INSERT INTO tracks(
                        id,user_id,filename,title,artist,album,duration,has_cover,cover_source
                    ) VALUES (:s,'a','f','t','r','l',0,false,:s)
                """), {'s': source})
            c.exec_driver_sql("""
                INSERT INTO tracks(
                    id,user_id,filename,title,artist,album,duration,has_cover,cover_source
                ) VALUES ('track-b','b','f','t','r','l',0,false,'unknown')
            """)
            c.exec_driver_sql("""
                INSERT INTO playlists(id,user_id,name)
                VALUES ('playlist-a','a','Synthetic A'), ('playlist-b','b','Synthetic B')
            """)
            c.exec_driver_sql("""
                INSERT INTO playlist_tracks(playlist_id,track_id,position)
                VALUES ('playlist-a','embedded',0), ('playlist-b','track-b',0)
            """)
            c.exec_driver_sql("""
                INSERT INTO favorites(user_id,track_id)
                VALUES ('a','embedded'), ('b','track-b')
            """)
        with cls.engine.connect() as c:
            cls.pre_upgrade_snapshot = cls.account_snapshot(c)
        with patch.dict(os.environ, {'DATABASE_URL': cls.migration_url, 'MIGRATION_DATABASE_URL': cls.migration_url}):
            command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')

    @staticmethod
    def account_snapshot(connection):
        return {
            table: connection.execute(sa.text(query)).all()
            for table, query in (
                ('users', 'SELECT id, username, password_hash FROM users ORDER BY id'),
                ('tracks', 'SELECT id, user_id FROM tracks ORDER BY id'),
                ('playlists', 'SELECT id, user_id, name FROM playlists ORDER BY id'),
                ('playlist_tracks', 'SELECT playlist_id, track_id, position FROM playlist_tracks ORDER BY playlist_id, track_id'),
                ('favorites', 'SELECT user_id, track_id FROM favorites ORDER BY user_id, track_id'),
            )
        }

    def setUp(self):
        self.c = self.engine.connect()
        self.addCleanup(self.c.close)
        self.tx = self.c.begin()
        self.addCleanup(self.tx.rollback)

    def sql(self, sql):
        return self.c.exec_driver_sql(sql)

    def test_existing_accounts_credentials_playlists_favorites_and_ownership_survive(self):
        self.assertEqual(self.account_snapshot(self.c), self.pre_upgrade_snapshot)
        self.assertEqual(self.sql('SELECT version_num FROM alembic_version').scalar_one(), HEAD)

        constraints = self.c.execute(sa.text("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE contype = 'f'
              AND conrelid IN (
                  'tracks'::regclass, 'favorites'::regclass, 'playlists'::regclass,
                  'playlist_tracks'::regclass
              )
        """)).all()
        definitions = {name: definition for name, definition in constraints}
        self.assertIn('fk_favorites_track_owner', definitions)
        self.assertRegex(
            definitions['fk_favorites_track_owner'].replace('public.', ''),
            r'FOREIGN KEY \(user_id, track_id\) REFERENCES tracks\(user_id, id\) ON DELETE CASCADE',
        )
        self.assertTrue(any(
            'FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE' in definition
            for name, definition in constraints if name == 'tracks_user_id_fkey'
        ))
        self.assertTrue(any(
            'FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE' in definition
            for name, definition in constraints if name == 'playlists_user_id_fkey'
        ))
        self.assertTrue(any(
            'FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE' in definition
            for name, definition in constraints if name == 'playlist_tracks_playlist_id_fkey'
        ))
        mismatched_playlist_tracks = self.sql("""
            SELECT count(*)
            FROM playlist_tracks pt
            JOIN playlists p ON p.id = pt.playlist_id
            JOIN tracks t ON t.id = pt.track_id
            WHERE p.user_id <> t.user_id
        """).scalar_one()
        self.assertEqual(mismatched_playlist_tracks, 0)
        with self.assertRaises(DBAPIError), self.c.begin_nested():
            self.sql("INSERT INTO favorites(user_id,track_id) VALUES ('a','track-b')")

        with patch.dict(os.environ, {'DATABASE_URL': self.migration_url}):
            from auth import verify_password

        for user_id, (password, password_hash) in self.passwords.items():
            stored_hash = self.c.execute(
                sa.text('SELECT password_hash FROM users WHERE id = :user_id'),
                {'user_id': user_id},
            ).scalar_one()
            self.assertEqual(stored_hash, password_hash)
            self.assertTrue(verify_password(password, stored_hash))
            self.assertFalse(verify_password('not-the-password', stored_hash))

    def test_google_identity_lookup_works_without_oauth_flow(self):
        issuer = 'https://accounts.google.com'
        subject = 'synthetic-google-subject-a'
        self.sql('SET LOCAL ROLE app_runtime')
        self.sql("SELECT set_config('app.current_user_id','a',true)")
        self.c.execute(
            sa.text("""
                INSERT INTO provider_identities(issuer,subject,user_id,created_at)
                VALUES (:issuer,:subject,'a',1)
            """),
            {'issuer': issuer, 'subject': subject},
        )
        self.sql('RESET ROLE')
        self.sql('SET LOCAL ROLE google_auth_lookup')

        from provider_identity_lookup import lookup_verified_google_identity

        self.assertEqual(
            lookup_verified_google_identity(self.c, issuer=issuer, subject=subject), 'a'
        )
        self.assertIsNone(
            lookup_verified_google_identity(self.c, issuer=issuer, subject=subject.upper())
        )

    def test_upgrade_functions_do_not_drop_or_delete_account_data(self):
        destructive_sql = re.compile(
            r'\b(?:DELETE\s+FROM|TRUNCATE(?:\s+TABLE)?|DROP\s+TABLE)\s+'
            r'(?:(?:ONLY\s+)?(?:(?:public|vervfy_auth)\s*\.\s*)?)["`]?'
            r'(' + '|'.join(sorted(ACCOUNT_TABLES)) + r')\b',
            re.IGNORECASE,
        )
        dropped_account_columns = re.compile(
            r'\bALTER\s+TABLE\s+(?:ONLY\s+)?'
            r'(?:(?:public|vervfy_auth)\s*\.\s*)?["`]?'
            r'(' + '|'.join(sorted(ACCOUNT_TABLES)) + r')\b.*?\bDROP\s+COLUMN\b',
            re.IGNORECASE | re.DOTALL,
        )
        violations = []
        for path in sorted((ROOT / 'alembic/versions').glob('*.py')):
            module = ast.parse(path.read_text(), filename=str(path))
            upgrade = next(
                node for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name == 'upgrade'
            )
            for node in ast.walk(upgrade):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'drop_table' and node.args:
                        target = node.args[0]
                        if isinstance(target, ast.Constant) and target.value in ACCOUNT_TABLES:
                            violations.append(f'{path.name}: drop_table({target.value})')
                    if node.func.attr == 'drop_column' and node.args:
                        target = node.args[0]
                        if isinstance(target, ast.Constant) and target.value in ACCOUNT_TABLES:
                            violations.append(f'{path.name}: drop_column from {target.value}')
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if destructive_sql.search(node.value) or dropped_account_columns.search(node.value):
                        violations.append(f'{path.name}: destructive SQL on account table')
        self.assertEqual(violations, [])

    def denied(self, sql):
        with self.assertRaises(DBAPIError), self.c.begin_nested():
            self.sql(sql)

    def test_sources_preserved_generated_insert_and_invalid_rejected(self):
        self.assertEqual(self.sql("SELECT cover_source FROM tracks WHERE user_id='a' ORDER BY cover_source").scalars().all(), ['embedded', 'placeholder', 'unknown', 'user'])
        self.sql('SET LOCAL ROLE app_runtime')
        self.sql("SELECT set_config('app.current_user_id','a',true)")
        for source in ('generated', 'upload', 'musicbrainz', 'audiodb'):
            self.c.execute(sa.text("INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source) VALUES (:s,'a','f','t','r','l',0,false,:s)"), {'s': source})
        self.sql("UPDATE tracks SET cover_source=NULL WHERE id='generated'")
        self.denied("UPDATE tracks SET cover_source='invalid'")
        self.assertEqual(self.sql('SELECT count(*) FROM tracks').scalar_one(), 8)

    def test_runtime_grants_rls_and_lookup_boundaries(self):
        grants = migration('0026_application_runtime_grants.py')
        for table in grants.CRUD_TABLES + grants.CACHE_TABLES:
            for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
                actual = self.c.execute(sa.text('SELECT has_table_privilege(:role,:table,:p)'), {'role':'app_runtime','table':table,'p':privilege}).scalar_one()
                self.assertEqual(actual, privilege in ('SELECT','INSERT','UPDATE') or (privilege=='DELETE' and table in grants.CRUD_TABLES), (table, privilege))
        rls_tables = set(self.sql("""
            SELECT relname FROM pg_class
            WHERE relnamespace='public'::regnamespace
              AND relrowsecurity AND relforcerowsecurity
        """).scalars())
        self.assertEqual(rls_tables, {
            'tracks', 'favorites', 'playlists', 'playlist_tracks', 'upload_jobs',
            'artist_photos', 'track_listens', 'provider_identities',
            'webauthn_handles', 'webauthn_credentials', 'account_action_intents',
            'account_verification_proofs', 'account_recovery_codes',
            'account_recovery_states',
            'webauthn_enrollments',
        })
        self.assertFalse(self.sql("SELECT has_table_privilege('app_runtime','alembic_version','SELECT')").scalar_one())
        self.sql('SET LOCAL ROLE app_runtime')
        self.assertEqual(self.sql('SELECT count(*) FROM tracks').scalar_one(), 0)
        self.sql("SELECT set_config('app.current_user_id','b',true)")
        self.assertEqual(self.sql("DELETE FROM tracks WHERE id='embedded'").rowcount, 0)
        self.denied("INSERT INTO tracks(id,user_id,filename,title,artist,album,duration,has_cover,cover_source) VALUES ('cross','a','f','t','r','l',0,false,'generated')")
        self.sql("INSERT INTO users(id,username,username_key,password_hash,created_at) VALUES ('new','new','new','hash',1)")
        self.assertEqual(self.sql("DELETE FROM users WHERE id='new'").rowcount, 1)
        self.denied("INSERT INTO provider_identities VALUES ('https://accounts.google.com','wrong','a',1)")
        self.sql("INSERT INTO provider_identities VALUES ('https://accounts.google.com','sub-b','b',1)")
        self.denied("UPDATE provider_identities SET subject='changed'")
        self.denied("SELECT vervfy_auth.lookup_provider_identity('https://accounts.google.com','sub-b')")
        self.sql('RESET ROLE')
        self.sql('SET LOCAL ROLE google_auth_lookup')
        self.assertEqual(self.sql("SELECT vervfy_auth.lookup_provider_identity('https://accounts.google.com','sub-b')").scalar_one(), 'b')
        self.assertIsNone(self.sql("SELECT vervfy_auth.lookup_provider_identity('https://accounts.google.com','SUB-B')").scalar_one())
        self.denied('SELECT * FROM public.provider_identities')
        # SET ROLE authorization uses session_user, not current_user. Test
        # escalation on a real restricted login, not the administrator session.
        login_engine = sa.create_engine(self.url.set(username='google_auth_lookup'))
        try:
            with login_engine.connect() as login:
                with self.assertRaises(DBAPIError):
                    login.exec_driver_sql('SET ROLE vervfy_identity_lookup_owner')
        finally:
            login_engine.dispose()

    def test_web_authn_downgrade_refuses_retained_recovery_and_enrollment_data(self):
        self.sql("""
            INSERT INTO account_recovery_codes(id, user_id, code_hash, created_at)
            VALUES (
                'retained-recovery-code', 'a',
                decode(repeat('00', 32), 'hex'), 1
            )
        """)
        with self.assertRaisesRegex(RuntimeError, 'security data exists'):
            with Operations.context(MigrationContext.configure(self.c)):
                migration('0027_webauthn_foundation.py').downgrade()

        self.sql("""
            INSERT INTO webauthn_enrollments(
                id, user_id, session_binding, session_version, method,
                signup_transaction, created_at, expires_at
            ) VALUES (
                'retained-enrollment', 'a', 'session-binding', 1, 'password',
                NULL, 1, 301
            )
        """)
        with self.assertRaisesRegex(RuntimeError, 'retained enrollment/recovery security data'):
            with Operations.context(MigrationContext.configure(self.c)):
                migration('0028_webauthn_enrollment.py').downgrade()

    def test_sequences_are_scoped_and_only_usage_is_granted(self):
        self.sql('SET LOCAL ROLE migration_owner')
        self.sql('ALTER TABLE users ADD COLUMN test_serial bigserial')
        self.sql('CREATE SEQUENCE unrelated_sequence')
        self.sql('GRANT ALL ON SEQUENCE users_test_serial_seq TO app_runtime')
        with Operations.context(MigrationContext.configure(self.c)):
            migration('0026_application_runtime_grants.py').upgrade()
        self.sql('RESET ROLE')
        self.sql('SET LOCAL ROLE app_runtime')
        self.sql("SELECT nextval('users_test_serial_seq')")
        self.denied("SELECT setval('users_test_serial_seq',100)")
        self.denied("SELECT nextval('unrelated_sequence')")
        self.denied('CREATE TABLE public.unapproved(id int)')
