"""0021 tests on a disposable private PostgreSQL cluster, never DATABASE_URL.

Run explicitly: python -m unittest discover -s tests -p test_oauth_postgres.py
Requires local initdb/pg_ctl binaries; listens only on a private Unix socket.
"""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import DBAPIError

from provider_identity_lookup import lookup_verified_google_identity


class ProviderPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getuid() == 0 or not all(shutil.which(x) for x in ('initdb', 'pg_ctl')):
            raise unittest.SkipTest('Requires non-root local PostgreSQL binaries')
        cls.directory = tempfile.TemporaryDirectory(prefix='vervfy-oauth-pg-')
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        cls.data = root / 'data'
        env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
        subprocess.run(['initdb', '-D', str(cls.data), '-A', 'trust', '-U', 'test_admin', '--no-locale', '--encoding=UTF8'], env=env, check=True, capture_output=True)
        subprocess.run(['pg_ctl', '-D', str(cls.data), '-l', str(root / 'postgres.log'), '-o', f"-k {root} -c listen_addresses='' -c unix_socket_permissions=0700 -c allow_system_table_mods=on", '-w', 'start'], env=env, check=True, capture_output=True)
        cls.addClassCleanup(subprocess.run, ['pg_ctl', '-D', str(cls.data), '-m', 'fast', '-w', 'stop'], env=env, check=True, capture_output=True)
        cls.engine = sa.create_engine(sa.URL.create('postgresql+psycopg', username='test_admin', database='postgres', query={'host': str(root)}))
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.begin() as connection:
            from storage_lifecycle_fixture import provision_storage_roles
            from supabase_pg17_fixture import (
                grant_creator_edges,
                provision_supabase_catalog,
            )

            provision_supabase_catalog(connection)
            connection.exec_driver_sql('CREATE ROLE migration_owner LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS')
            connection.exec_driver_sql('GRANT CREATE ON DATABASE postgres TO migration_owner')
            connection.exec_driver_sql('CREATE ROLE app_user NOSUPERUSER NOBYPASSRLS')
            connection.exec_driver_sql('CREATE ROLE app_runtime NOSUPERUSER NOBYPASSRLS')
            connection.exec_driver_sql(
                'CREATE ROLE google_auth_lookup LOGIN NOINHERIT '
                'NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION'
            )
            for role in ('vervfy_identity_lookup_owner', 'vervfy_identity_lookup'):
                connection.exec_driver_sql(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT')
            provision_storage_roles(connection)
            grant_creator_edges(
                connection,
                (
                    "app_runtime",
                    "google_auth_lookup",
                    "vervfy_identity_lookup_owner",
                    "vervfy_identity_lookup",
                ),
            )
            connection.exec_driver_sql("SET ROLE postgres")
            try:
                connection.exec_driver_sql(
                    "GRANT vervfy_identity_lookup_owner TO migration_owner "
                    "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
                )
                connection.exec_driver_sql(
                    "GRANT vervfy_identity_lookup TO google_auth_lookup "
                    "WITH ADMIN FALSE, INHERIT TRUE, SET FALSE"
                )
            finally:
                connection.exec_driver_sql("RESET ROLE")
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/0021_provider_identities.py'
        spec = importlib.util.spec_from_file_location('migration_0021', path)
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)
        path = path.with_name('0022_provider_identity_lookup.py')
        spec = importlib.util.spec_from_file_location('migration_0022', path)
        cls.lookup_migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.lookup_migration)
        path = path.with_name('0024_provider_identity_runtime_access.py')
        spec = importlib.util.spec_from_file_location('migration_0024', path)
        cls.runtime_access_migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.runtime_access_migration)
        path = path.with_name('0023_missing_media_columns.py')
        spec = importlib.util.spec_from_file_location('migration_0023', path)
        cls.media_columns_migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.media_columns_migration)
        cls.migration_engine = sa.create_engine(
            sa.URL.create(
                'postgresql+psycopg',
                username='migration_owner',
                database='postgres',
                query={'host': str(root)},
            )
        )
        cls.addClassCleanup(cls.migration_engine.dispose)

    def setUp(self):
        self.connection = self.engine.connect()
        self.addCleanup(self.connection.close)
        self.transaction = self.connection.begin()
        self.addCleanup(self.transaction.rollback)
        self.schema = 'test_' + uuid.uuid4().hex
        self.sql(f'CREATE SCHEMA {self.schema} AUTHORIZATION migration_owner')
        self.sql(f'SET LOCAL search_path TO {self.schema}')
        self.sql('SET LOCAL ROLE migration_owner')
        self.sql('CREATE TABLE users (id VARCHAR(32) PRIMARY KEY, password_hash VARCHAR(128) NOT NULL, session_version INTEGER NOT NULL)')
        self.sql('CREATE TABLE library (user_id VARCHAR(32) REFERENCES users(id), payload TEXT)')
        self.sql("INSERT INTO users VALUES ('a', 'existing-hash', 7), ('b', 'other-hash', 3)")
        self.sql("INSERT INTO library VALUES ('a', 'keep-a'), ('b', 'keep-b')")
        with Operations.context(MigrationContext.configure(self.connection)):
            self.migration.upgrade()
        self.sql(f'GRANT USAGE ON SCHEMA {self.schema} TO app_user')
        self.sql(f'GRANT USAGE ON SCHEMA {self.schema} TO app_runtime')
        self.sql('GRANT SELECT, INSERT, UPDATE, DELETE ON provider_identities TO app_user')

    def sql(self, statement):
        return self.connection.exec_driver_sql(statement)

    def downgrade(self):
        with Operations.context(MigrationContext.configure(self.connection)):
            self.migration.downgrade()

    def seed(self):
        self.sql('RESET ROLE')
        self.sql("INSERT INTO provider_identities VALUES ('issuer', 'a-sub', 'a', 1), ('issuer', 'b-sub', 'b', 1)")
        self.sql('SET LOCAL ROLE migration_owner')

    def test_empty_downgrade_as_non_bypass_owner(self):
        self.downgrade()
        self.assertEqual(self.sql('SELECT * FROM users ORDER BY id').all(), [('a', 'existing-hash', 7), ('b', 'other-hash', 3)])
        self.assertEqual(self.sql('SELECT * FROM library ORDER BY user_id').all(), [('a', 'keep-a'), ('b', 'keep-b')])
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql("INSERT INTO users VALUES ('c', NULL, 0)")

    def test_downgrade_rejects_hidden_identity_and_preserves_rls(self):
        self.seed()
        with self.assertRaisesRegex(RuntimeError, 'identities'), self.connection.begin_nested():
            self.downgrade()
        self.assertEqual(self.sql('SELECT * FROM provider_identities').all(), [])
        flags = self.sql("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid='provider_identities'::regclass").one()
        self.assertEqual(flags, (True, True))

    def test_passwordless_downgrade_guard(self):
        self.sql("INSERT INTO users VALUES ('c', NULL, 0)")
        with self.assertRaisesRegex(RuntimeError, 'passwordless'):
            self.downgrade()

    def test_rls_prelogin_and_tenant_read_write_isolation(self):
        self.seed()
        self.sql('SET LOCAL ROLE app_user')
        self.assertEqual(self.sql('SELECT * FROM provider_identities').all(), [])
        self.sql("SELECT set_config('app.current_user_id', 'a', true)")
        self.assertEqual(self.sql('SELECT subject FROM provider_identities').all(), [('a-sub',)])
        self.assertEqual(self.sql("DELETE FROM provider_identities WHERE user_id='b'").rowcount, 0)
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql("INSERT INTO provider_identities VALUES ('issuer', 'wrong-owner', 'b', 1)")
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql("UPDATE provider_identities SET user_id='b' WHERE user_id='a'")
        self.assertEqual(self.sql("DELETE FROM provider_identities WHERE user_id='a'").rowcount, 1)
        self.sql("SELECT set_config('app.current_user_id', 'b', true)")
        self.assertEqual(self.sql('SELECT subject FROM provider_identities').all(), [('b-sub',)])

    def test_runtime_identity_grants_remain_tenant_scoped(self):
        self.seed()
        self.sql('GRANT ALL ON provider_identities TO app_runtime')
        with Operations.context(MigrationContext.configure(self.connection)):
            self.runtime_access_migration.upgrade()
        for privilege in ('SELECT', 'INSERT', 'DELETE'):
            self.assertTrue(
                self.connection.execute(
                    sa.text(
                        "SELECT has_table_privilege('app_runtime', "
                        "'provider_identities', :privilege)"
                    ),
                    {'privilege': privilege},
                ).scalar_one()
            )
        self.assertFalse(
            self.connection.exec_driver_sql(
                "SELECT has_table_privilege('app_runtime', "
                "'provider_identities', 'UPDATE')"
            ).scalar_one()
        )
        self.sql('RESET ROLE')
        self.sql('SET LOCAL ROLE app_runtime')
        self.assertEqual(self.sql('SELECT * FROM provider_identities').all(), [])
        self.sql("SELECT set_config('app.current_user_id', 'a', true)")
        self.assertEqual(self.sql('SELECT subject FROM provider_identities').all(), [('a-sub',)])
        self.sql(
            "INSERT INTO provider_identities "
            "VALUES ('issuer', 'a-new-sub', 'a', 2)"
        )
        self.assertEqual(
            self.sql(
                "DELETE FROM provider_identities WHERE user_id='a' "
                "AND subject='a-new-sub'"
            ).rowcount,
            1,
        )
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql(
                "INSERT INTO provider_identities "
                "VALUES ('issuer', 'b-new-sub', 'b', 2)"
            )

    def test_fresh_migrations_0021_through_0024_preserve_schema_and_security(self):
        self.sql('CREATE TABLE tracks (id VARCHAR(64) PRIMARY KEY)')
        self.sql('CREATE TABLE upload_jobs (id VARCHAR(32) PRIMARY KEY)')
        self.install_lookup()
        with Operations.context(MigrationContext.configure(self.connection)):
            self.media_columns_migration.upgrade()
            self.runtime_access_migration.upgrade()

        self.assertEqual(
            self.sql(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND "
                "((table_name='tracks' AND column_name='cover_url') OR "
                "(table_name='upload_jobs' AND column_name='cover_data')) "
                "ORDER BY table_name"
            ).all(),
            [('tracks', 'cover_url'), ('upload_jobs', 'cover_data')],
        )
        self.assertEqual(
            self.sql(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE oid='provider_identities'::regclass"
            ).one(),
            (True, True),
        )
        for privilege in ('SELECT', 'INSERT', 'DELETE'):
            self.assertTrue(
                self.connection.execute(
                    sa.text(
                        "SELECT has_table_privilege('app_runtime', "
                        "'provider_identities', :privilege)"
                    ),
                    {'privilege': privilege},
                ).scalar_one()
            )
        self.assertFalse(
            self.sql(
                "SELECT has_table_privilege('app_runtime', "
                "'provider_identities', 'UPDATE')"
            ).scalar_one()
        )
        self.assertFalse(
            self.sql(
                "SELECT has_function_privilege('app_runtime', "
                "'vervfy_auth.lookup_provider_identity(text,text)', 'EXECUTE')"
            ).scalar_one()
        )

        self.sql('SET LOCAL ROLE app_runtime')
        self.sql("SELECT set_config('app.current_user_id', 'a', true)")
        self.assertEqual(
            self.sql('SELECT subject FROM provider_identities').all(),
            [('a-sub',)],
        )

    def test_media_columns_migration_preserves_existing_track_cover_url(self):
        self.sql(
            'CREATE TABLE tracks (id VARCHAR(64) PRIMARY KEY, cover_url TEXT)'
        )
        self.sql(
            "INSERT INTO tracks (id, cover_url) VALUES ('track-a', 'https://covers.test/a')"
        )
        self.sql('CREATE TABLE upload_jobs (id VARCHAR(32) PRIMARY KEY)')

        with Operations.context(MigrationContext.configure(self.connection)):
            self.media_columns_migration.upgrade()

        self.assertEqual(
            self.sql("SELECT cover_url FROM tracks WHERE id='track-a'").scalar_one(),
            'https://covers.test/a',
        )
        self.assertIn(
            'cover_data',
            {
                column['name']
                for column in sa.inspect(self.connection).get_columns('upload_jobs')
            },
        )

    def test_identity_constraints_and_user_delete_cascade(self):
        self.seed()
        self.sql('RESET ROLE')
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql("INSERT INTO provider_identities VALUES ('issuer', 'a-sub', 'b', 2)")
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql("INSERT INTO provider_identities VALUES ('issuer', 'orphan', 'missing', 2)")
        self.sql("DELETE FROM library WHERE user_id='a'")
        self.sql("DELETE FROM users WHERE id='a'")
        self.assertEqual(self.sql('SELECT user_id FROM provider_identities').all(), [('b',)])
        self.assertEqual(self.sql('SELECT * FROM library').all(), [('b', 'keep-b')])

    def install_lookup(self):
        self.seed()
        self.sql('RESET ROLE')
        self.sql("UPDATE provider_identities SET issuer='https://accounts.google.com'")
        self.sql('SET LOCAL ROLE migration_owner')
        # Simulate unsafe deployment default function grants: migration must remove them.
        self.sql('ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO app_user')
        self.sql('ALTER DEFAULT PRIVILEGES GRANT ALL ON SCHEMAS TO app_user')
        with Operations.context(MigrationContext.configure(self.connection)):
            self.lookup_migration.upgrade()

    def lookup(self, subject, issuer='https://accounts.google.com'):
        return lookup_verified_google_identity(self.connection, issuer=issuer, subject=subject)

    def test_lookup_exact_only_and_no_profile_or_email_access(self):
        self.install_lookup()
        self.sql('SET LOCAL ROLE vervfy_identity_lookup')
        self.assertEqual(self.lookup('a-sub'), 'a')
        self.assertEqual(self.lookup('b-sub'), 'b')
        for subject in ('missing', 'A-sub', 'a-sub ', '%', "a-sub' OR true --", 'a@example.com'):
            self.assertIsNone(self.lookup(subject))
        self.assertIsNone(self.lookup('a-sub', 'accounts.google.com'))
        with self.assertRaises(ValueError):
            self.lookup('a-sub', 'https://evil.example')
        with self.assertRaises(ValueError):
            self.lookup('')
        for table in ('provider_identities', 'users', 'library'):
            with self.assertRaises(DBAPIError), self.connection.begin_nested():
                self.sql(f'SELECT * FROM {self.schema}.{table}')
        self.sql('SET LOCAL SESSION AUTHORIZATION vervfy_identity_lookup')
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql('SET ROLE vervfy_identity_lookup_owner')

    def test_lookup_denied_to_regular_app_even_with_tenant_context(self):
        self.install_lookup()
        self.sql('SET LOCAL ROLE app_user')
        self.sql("SELECT set_config('app.current_user_id', 'a', true)")
        self.assertEqual(self.sql('SELECT subject FROM provider_identities').all(), [('a-sub',)])
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.lookup('b-sub')
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql('CREATE TABLE vervfy_auth.shadow (id int)')
        # Even if schema USAGE is later granted accidentally, EXECUTE is denied.
        self.sql('RESET ROLE')
        self.sql('GRANT USAGE ON SCHEMA vervfy_auth TO app_user')
        self.sql('SET LOCAL ROLE app_user')
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.lookup('a-sub')
        self.sql('SET LOCAL SESSION AUTHORIZATION app_user')
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.sql('SET ROLE vervfy_identity_lookup')

    def test_lookup_definer_has_only_identity_column_reads(self):
        self.install_lookup()
        self.sql('SET LOCAL ROLE vervfy_identity_lookup_owner')
        self.assertEqual(len(self.sql('SELECT issuer, subject, user_id FROM provider_identities').all()), 2)
        for statement in (
            'SELECT created_at FROM provider_identities',
            'SELECT * FROM users',
            'SELECT * FROM library',
            'DELETE FROM provider_identities',
            "UPDATE provider_identities SET user_id='a'",
            'CREATE TABLE vervfy_auth.unexpected (id int)',
        ):
            with self.assertRaises(DBAPIError), self.connection.begin_nested():
                self.sql(statement)
        self.assertEqual(self.sql("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid='provider_identities'::regclass").one(), (True, True))

    def test_lookup_ignores_search_path_shadowing(self):
        self.install_lookup()
        self.sql('RESET ROLE')
        self.sql('CREATE TEMP TABLE provider_identities (issuer text, subject text, user_id text)')
        self.sql("INSERT INTO pg_temp.provider_identities VALUES ('https://accounts.google.com', 'a-sub', 'attacker')")
        self.sql('SET LOCAL ROLE vervfy_identity_lookup')
        self.sql('SET LOCAL search_path TO pg_temp, public')
        self.assertEqual(self.lookup('a-sub'), 'a')

    def test_lookup_downgrade_preserves_identities_and_tenant_rls(self):
        self.install_lookup()
        with Operations.context(MigrationContext.configure(self.connection)):
            self.lookup_migration.downgrade()
        self.sql('SET LOCAL ROLE app_user')
        self.assertEqual(self.sql('SELECT * FROM provider_identities').all(), [])
        self.sql("SELECT set_config('app.current_user_id', 'b', true)")
        self.assertEqual(self.sql('SELECT subject FROM provider_identities').all(), [('b-sub',)])
        with self.assertRaises(DBAPIError), self.connection.begin_nested():
            self.lookup('b-sub')
        self.sql('RESET ROLE')
        self.assertEqual(self.sql('SELECT count(*) FROM provider_identities').scalar(), 2)
        self.assertEqual(self.sql('SELECT count(*) FROM library').scalar(), 2)

    def test_lookup_migration_rejects_unsafe_owner_before_mutating_schema(self):
        self.sql('RESET ROLE')
        self.sql('GRANT vervfy_identity_lookup_owner TO app_user')
        self.sql('SET LOCAL ROLE migration_owner')
        with self.assertRaisesRegex(
            RuntimeError,
            'Unexpected membership graph for vervfy_identity_lookup_owner',
        ), Operations.context(MigrationContext.configure(self.connection)):
            self.lookup_migration.upgrade()
        self.assertIsNone(self.sql("SELECT to_regnamespace('vervfy_auth')").scalar())

    def assert_lookup_migration_rejects_membership(self, setup_sql, message):
        self.sql('RESET ROLE')
        for statement in setup_sql:
            self.sql(statement)
        self.sql('SET LOCAL ROLE migration_owner')
        with self.assertRaisesRegex(RuntimeError, message), Operations.context(
            MigrationContext.configure(self.connection)
        ):
            self.lookup_migration.upgrade()
        self.assertIsNone(self.sql("SELECT to_regnamespace('vervfy_auth')").scalar())

    def test_lookup_migration_rejects_an_extra_executor_member(self):
        self.assert_lookup_migration_rejects_membership(
            [
                'GRANT vervfy_identity_lookup TO app_user '
                'WITH ADMIN FALSE, INHERIT TRUE, SET FALSE'
            ],
            'Unexpected membership graph for vervfy_identity_lookup',
        )

    def test_lookup_migration_rejects_nested_executor_membership(self):
        self.assert_lookup_migration_rejects_membership(
            [
                'CREATE ROLE lookup_group NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS',
                'GRANT vervfy_identity_lookup TO lookup_group '
                'WITH ADMIN FALSE, INHERIT TRUE, SET FALSE',
                'GRANT lookup_group TO app_user '
                'WITH ADMIN FALSE, INHERIT TRUE, SET FALSE',
            ],
            'Unexpected membership graph for vervfy_identity_lookup',
        )

    def test_lookup_migration_rejects_delegation_through_trusted_login_role(self):
        self.sql('RESET ROLE')
        self.sql(
            'GRANT google_auth_lookup TO app_user '
            'WITH ADMIN FALSE, INHERIT TRUE, SET TRUE'
        )
        self.assertTrue(
            self.sql(
                "SELECT pg_has_role('app_user', "
                "'vervfy_identity_lookup', 'USAGE')"
            ).scalar_one()
        )
        self.sql('SET LOCAL ROLE migration_owner')
        with self.assertRaisesRegex(
            RuntimeError, 'Unexpected membership graph for google_auth_lookup'
        ), Operations.context(MigrationContext.configure(self.connection)):
            self.lookup_migration.upgrade()
        self.assertIsNone(self.sql("SELECT to_regnamespace('vervfy_auth')").scalar())

    def test_lookup_migration_rejects_extra_inherited_privileges_on_lookup_login(self):
        self.assert_lookup_migration_rejects_membership(
            [
                'CREATE ROLE unrelated_capability NOLOGIN NOINHERIT '
                'NOSUPERUSER NOBYPASSRLS',
                'GRANT unrelated_capability TO google_auth_lookup '
                'WITH ADMIN FALSE, INHERIT TRUE, SET FALSE',
            ],
            'Unexpected memberships held by google_auth_lookup',
        )

    def test_deleted_identity_no_longer_resolves(self):
        self.install_lookup()
        self.sql('RESET ROLE')
        self.sql("DELETE FROM library WHERE user_id='a'")
        self.sql("DELETE FROM users WHERE id='a'")
        self.sql('SET LOCAL ROLE vervfy_identity_lookup')
        self.assertIsNone(self.lookup('a-sub'))
        self.assertEqual(self.lookup('b-sub'), 'b')

    def test_lookup_migration_rejects_bypass_role(self):
        self.sql('RESET ROLE')
        self.sql('ALTER ROLE vervfy_identity_lookup BYPASSRLS')
        self.sql('SET LOCAL ROLE migration_owner')
        with self.assertRaisesRegex(RuntimeError, 'restricted'), Operations.context(MigrationContext.configure(self.connection)):
            self.lookup_migration.upgrade()
        self.assertIsNone(self.sql("SELECT to_regnamespace('vervfy_auth')").scalar())

    def test_lookup_migration_grants_execute_as_restricted_migration_login(self):
        schema = 'migration_login_' + uuid.uuid4().hex
        with self.engine.begin() as admin:
            admin.exec_driver_sql(
                f'CREATE SCHEMA {schema} AUTHORIZATION migration_owner'
            )
            admin.exec_driver_sql('SET LOCAL ROLE migration_owner')
            admin.exec_driver_sql(
                f'CREATE TABLE {schema}.users (id VARCHAR(32) PRIMARY KEY)'
            )
            admin.exec_driver_sql(f'''
                CREATE TABLE {schema}.provider_identities (
                    issuer VARCHAR(255) NOT NULL,
                    subject VARCHAR(255) NOT NULL,
                    user_id VARCHAR(32) NOT NULL REFERENCES {schema}.users(id),
                    created_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (issuer, subject)
                )
            ''')
            admin.exec_driver_sql(
                f"INSERT INTO {schema}.users VALUES ('synthetic-user')"
            )
            admin.exec_driver_sql(f'''
                INSERT INTO {schema}.provider_identities
                VALUES ('https://accounts.google.com', 'synthetic-subject',
                        'synthetic-user', 1)
            ''')

        with self.migration_engine.begin() as migration_connection:
            migration_connection.exec_driver_sql(
                f'SET LOCAL search_path TO {schema}'
            )
            with Operations.context(
                MigrationContext.configure(migration_connection)
            ):
                self.lookup_migration.upgrade()

        try:
            with self.engine.begin() as verifier:
                self.assertEqual(
                    verifier.exec_driver_sql("""
                        SELECT pg_get_userbyid(proowner)
                        FROM pg_proc
                        WHERE oid = 'vervfy_auth.lookup_provider_identity(text,text)'::regprocedure
                    """).scalar_one(),
                    'vervfy_identity_lookup_owner',
                )
                verifier.exec_driver_sql(
                    'SET LOCAL ROLE vervfy_identity_lookup'
                )
                self.assertEqual(
                    verifier.exec_driver_sql("""
                        SELECT vervfy_auth.lookup_provider_identity(
                            'https://accounts.google.com', 'synthetic-subject'
                        )
                    """).scalar_one(),
                    'synthetic-user',
                )
                with self.assertRaises(DBAPIError), verifier.begin_nested():
                    verifier.exec_driver_sql(
                        f'SELECT * FROM {schema}.provider_identities'
                    )
        finally:
            with self.engine.begin() as admin:
                admin.exec_driver_sql('DROP SCHEMA vervfy_auth CASCADE')
                admin.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
