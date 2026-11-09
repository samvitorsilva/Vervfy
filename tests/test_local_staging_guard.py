"""No database imports or connections; exercise staging rejection boundaries."""
import hashlib
import runpy
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import staging_guard as guard


class LocalProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.state = self.home / '.local' / 'share' / 'vervfy-staging-local-Ab12Cd34'
        self.config = self.home / '.config' / 'vervfy'
        for directory in (
            self.config, self.state, self.state / 'postgres',
            self.state / 'postgres' / 'data',
            self.state / 'postgres' / 'data' / 'global',
            self.state / 'postgres' / 'socket',
            self.state / 'valkey', self.state / 'valkey' / 'data',
        ):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)

        self.passwords = {
            'vervfy_oauth_staging_user': '1' * 64,
            'app_runtime': '2' * 64,
            'google_auth_lookup': '3' * 64,
        }
        self.env_file = self.config / 'staging-local.env'
        self.pgpass = self.config / 'staging-local.pgpass'
        self.valkey_config = self.state / 'valkey' / 'valkey.conf'
        self._write_pgpass()
        self._write_valkey_config()
        (self.state / 'postgres' / 'data' / 'PG_VERSION').write_text(
            '18\n', encoding='ascii'
        )
        (self.state / 'postgres' / 'data' / 'global' / 'pg_control').write_bytes(
            b'synthetic control file'
        )
        (self.state / '.local-staging-ready').write_text(
            'local-disposable-v1\n', encoding='ascii'
        )
        (self.state / '.local-staging-ready').chmod(0o600)

        host = guard.LOCAL_HOST
        port = guard.LOCAL_PORT
        database = guard.LOCAL_DATABASE
        query = '?sslmode=disable&gssencmode=disable'
        self.env = {
            'HOME': str(self.home),
            'VERVFY_ENVIRONMENT': 'staging',
            'VERVFY_STAGING_PROFILE': guard.LOCAL_PROFILE,
            'VERVFY_LOCAL_STATE_DIR': str(self.state),
            'VERVFY_SECRET_KEY': 'a' * 64,
            'VERVFY_HTTPS_ONLY': '0',
            'VERVFY_TRUSTED_PROXY_HOPS': '0',
            'VERVFY_COOKIE_SAME_SITE': 'lax',
            'VERVFY_ASYNC_UPLOADS': '0',
            'LYRICS_PROVIDER_LRCLIB': '0',
            'GOOGLE_OAUTH_ENABLED': '0',
            'PGPASSFILE': str(self.pgpass),
            'MIGRATION_DATABASE_URL':
                f'postgresql+psycopg://vervfy_oauth_staging_user@{host}:{port}/{database}{query}',
            'DATABASE_URL':
                f'postgresql+psycopg://app_runtime@{host}:{port}/{database}{query}',
            'GOOGLE_IDENTITY_LOOKUP_DATABASE_URL':
                f'postgresql+psycopg://google_auth_lookup@{host}:{port}/{database}{query}',
            'REDIS_URL':
                f"redis://:{'4' * 64}@{host}:{guard.LOCAL_REDIS_PORT}/0",
        }
        self._write_env_file()

    def _write_env_file(self, values=None):
        values = self.env if values is None else values
        self.env_file.write_text(''.join(
            f'export {key}={shlex.quote(values[key])}\n'
            for key in sorted(guard.LOCAL_PROCESS_KEYS)
        ), encoding='utf-8')
        self.env_file.chmod(0o600)

    def _write_pgpass(self):
        self.pgpass.write_text(''.join(
            f'{guard.LOCAL_HOST}:{guard.LOCAL_PORT}:{guard.LOCAL_DATABASE}:'
            f'{role}:{password}\n'
            for role, password in self.passwords.items()
        ), encoding='ascii')
        self.pgpass.chmod(0o600)

    def _write_valkey_config(self):
        password = '4' * 64
        self.valkey_config.write_text('\n'.join((
            f'bind {guard.LOCAL_HOST}',
            'protected-mode yes',
            f'port {guard.LOCAL_REDIS_PORT}',
            f'dir "{self.state}/valkey/data"',
            f'pidfile "{self.state}/valkey/valkey.pid"',
            f'logfile "{self.state}/valkey/valkey.log"',
            'daemonize yes',
            'save ""',
            'appendonly no',
            'maxmemory 256mb',
            'maxmemory-policy noeviction',
            f'requirepass {password}',
            '',
        )), encoding='utf-8')
        self.valkey_config.chmod(0o600)

    def test_local_profile_accepts_only_the_three_exact_local_roles(self):
        _, urls = guard.validate(self.env)
        self.assertEqual(set(urls), set(guard.ROLES))
        for key, role in guard.ROLES.items():
            self.assertEqual(urls[key].hostname, guard.LOCAL_HOST)
            self.assertEqual(urls[key].port, guard.LOCAL_PORT)
            self.assertEqual(urls[key].username, role)

    def test_external_hosts_aliases_ports_databases_and_usernames_are_rejected(self):
        variants = (
            ('host', 'db.example.test'),
            ('host', '127.0.0.2'),
            ('host', 'localhost'),
            ('host', '::1'),
            ('port', 55434),
            ('database', 'postgres'),
            ('username', 'postgres'),
        )
        for key in guard.ROLES:
            for field, value in variants:
                with self.subTest(key=key, field=field, value=value):
                    bad = dict(self.env)
                    url = bad[key]
                    if field == 'host':
                        url = url.replace(guard.LOCAL_HOST, value)
                    elif field == 'port':
                        url = url.replace(':55433/', f':{value}/')
                    elif field == 'database':
                        url = url.replace(f'/{guard.LOCAL_DATABASE}?', f'/{value}?')
                    else:
                        expected_user = guard.ROLES[key]
                        url = url.replace(f'://{expected_user}@', f'://{value}@')
                    bad[key] = url
                    self._write_env_file(bad)
                    with self.assertRaises(RuntimeError):
                        guard.validate(bad)

    def test_local_database_urls_reject_extra_connection_overrides(self):
        for parameter in (
            'host=production.example.test', 'hostaddr=127.0.0.1',
            'service=production', 'options=-crole=postgres',
            'sslmode=require', 'gssencmode=prefer',
        ):
            bad = dict(self.env)
            bad['DATABASE_URL'] += '&' + parameter
            self._write_env_file(bad)
            with self.subTest(parameter=parameter), self.assertRaises(RuntimeError):
                guard.validate(bad)

    def test_production_and_provider_credentials_are_rejected(self):
        for key, value in (
            ('SUPABASE_URL', 'https://production.supabase.co'),
            ('SUPABASE_KEY', 'synthetic'),
            ('SUPABASE_SERVICE_KEY', 'synthetic'),
            ('PRODUCTION_DATABASE_URL', 'postgresql://synthetic'),
            ('PRODUCTION_REDIS_URL', 'redis://synthetic'),
            ('GOOGLE_CLIENT_ID', 'synthetic'),
            ('GOOGLE_CLIENT_SECRET', 'synthetic'),
            ('GOOGLE_PROJECT_ID', 'synthetic'),
            ('GOOGLE_OAUTH_ENABLED', '1'),
            ('AWS_SECRET_ACCESS_KEY', 'synthetic'),
            ('SENTRY_AUTH_TOKEN', 'synthetic'),
        ):
            bad = dict(self.env)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                guard.validate(bad)

    def test_environment_file_cannot_hide_unapproved_provider_settings(self):
        original = self.env_file.read_text(encoding='utf-8')
        self.env_file.write_text(
            original + 'export SUPABASE_SERVICE_KEY=synthetic\n',
            encoding='utf-8',
        )
        self.env_file.chmod(0o600)
        with self.assertRaises(RuntimeError):
            guard.validate(self.env)

    def test_unapproved_postgresql_environment_variables_are_rejected(self):
        for key in ('PGHOST', 'PGHOSTADDR', 'PGSERVICE', 'PGOPTIONS',
                    'PGPASSWORD', 'PGSSLMODE', 'PGSSLROOTCERT',
                    'SSL_CERT_FILE', 'SSL_CERT_DIR'):
            bad = dict(self.env)
            bad[key] = 'synthetic'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                guard.validate(bad)

    def test_only_the_canonical_private_pgpassfile_is_accepted(self):
        outside = self.home / 'outside.pgpass'
        outside.write_text(self.pgpass.read_text(encoding='ascii'), encoding='ascii')
        outside.chmod(0o600)
        bad = dict(self.env, PGPASSFILE=str(outside))
        self._write_env_file(bad)
        with self.assertRaises(RuntimeError):
            guard.validate(bad)
        self._write_env_file()

        self.pgpass.chmod(0o644)
        with self.assertRaises(RuntimeError):
            guard.validate(self.env)
        self.pgpass.chmod(0o600)

        target = self.home / 'other.pgpass'
        target.write_text(self.pgpass.read_text(encoding='ascii'), encoding='ascii')
        target.chmod(0o600)
        self.pgpass.unlink()
        self.pgpass.symlink_to(target)
        with self.assertRaises(RuntimeError):
            guard.validate(self.env)

    def test_pgpass_requires_exact_local_accounts_and_no_wildcards(self):
        original = self.pgpass.read_text(encoding='ascii')
        self.pgpass.write_text(original.replace(guard.LOCAL_HOST, '*', 1), encoding='ascii')
        self.pgpass.chmod(0o600)
        with self.assertRaises(RuntimeError):
            guard.validate(self.env)

    def test_local_valkey_config_must_match_authenticated_local_url(self):
        self._write_valkey_config()
        bad = dict(self.env, REDIS_URL=f"redis://:{'5' * 64}@127.0.0.1:56379/0")
        self._write_env_file(bad)
        with self.assertRaises(RuntimeError):
            guard.validate(bad)

        self._write_env_file()
        self._write_valkey_config()
        self.valkey_config.write_text(
            self.valkey_config.read_text(encoding='utf-8').replace(
                'bind 127.0.0.1', 'bind 0.0.0.0'
            ),
            encoding='utf-8',
        )
        self.valkey_config.chmod(0o600)
        with self.assertRaises(RuntimeError):
            guard.validate(self.env)

    def test_partial_initialization_is_rejected_without_removing_artifacts(self):
        pg_control = self.state / 'postgres' / 'data' / 'global' / 'pg_control'
        before = self.pgpass.read_bytes()
        pg_control.unlink()
        with self.assertRaisesRegex(RuntimeError, 'partial local staging initialization'):
            guard.validate(self.env)
        self.assertTrue(self.pgpass.exists())
        self.assertTrue(self.valkey_config.exists())
        self.assertEqual(self.pgpass.read_bytes(), before)

    def test_empty_claimed_state_directory_is_partial_not_reusable(self):
        for path in (
            self.env_file, self.pgpass, self.valkey_config,
            self.state / 'postgres' / 'data' / 'PG_VERSION',
            self.state / 'postgres' / 'data' / 'global' / 'pg_control',
            self.state / '.local-staging-ready',
        ):
            path.unlink()
        with self.assertRaisesRegex(RuntimeError, 'partial local staging initialization'):
            guard.validate(self.env)

    def test_local_child_environment_excludes_ambient_configuration(self):
        source = dict(self.env, HTTP_PROXY='http://proxy.invalid',
                      EXTRA_PROVIDER_SETTING='synthetic')
        child = guard.local_child_environment(source)
        self.assertEqual(child['DATABASE_URL'], self.env['DATABASE_URL'])
        self.assertEqual(child['PGPASSFILE'], self.env['PGPASSFILE'])
        self.assertNotIn('HTTP_PROXY', child)
        self.assertNotIn('EXTRA_PROVIDER_SETTING', child)
        self.assertNotIn('SUPABASE_URL', child)
        self.assertNotIn('GOOGLE_CLIENT_SECRET', child)

    def test_local_profile_main_is_check_only_and_does_not_spawn(self):
        with patch.dict(guard.os.environ, self.env, clear=True), \
             patch.object(guard.sys, 'argv', ['staging_guard.py', 'check']), \
             patch.object(guard.subprocess, 'run',
                          side_effect=AssertionError('local check must not spawn')):
            guard.main()
        for action in ('preflight', 'postflight', 'upgrade'):
            with patch.dict(guard.os.environ, self.env, clear=True), \
                 patch.object(guard.sys, 'argv', ['staging_guard.py', action]), \
                 patch.object(guard.subprocess, 'run',
                              side_effect=AssertionError('local action must not spawn')), \
                 self.subTest(action=action), self.assertRaises(RuntimeError):
                guard.main()

    def test_alembic_is_blocked_for_local_profile_but_not_hosted_profile(self):
        with self.assertRaises(RuntimeError):
            guard.require_alembic_execution_enabled(self.env)
        guard.require_alembic_execution_enabled({
            'VERVFY_ENVIRONMENT': 'staging',
            'VERVFY_STAGING_PROFILE': 'hosted',
        })

