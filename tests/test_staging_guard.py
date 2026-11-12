"""No database imports or connections; exercise staging rejection boundaries."""
import hashlib
import runpy
import shlex
import ssl
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import staging_guard as guard


class RuntimeRedisGuardTests(unittest.TestCase):
    URL = 'rediss://default:synthetic-token@staging-example.upstash.io:6379/0'

    def test_staging_rediss_requires_default_verified_tls(self):
        parsed = guard.validate_runtime_redis_url(
            self.URL,
            'staging',
            {
                'GOOGLE_OAUTH_ENABLED': '0',
                'VERVFY_STAGING_REDIS_HOST': 'staging-example.upstash.io',
            },
        )
        self.assertEqual(parsed.hostname, 'staging-example.upstash.io')

        import redis

        client = redis.Redis.from_url(self.URL)
        try:
            connection = client.connection_pool.make_connection()
            self.assertEqual(connection.cert_reqs, ssl.CERT_REQUIRED)
            self.assertTrue(connection.check_hostname)
        finally:
            client.close()

    def test_staging_rejects_insecure_or_overridden_redis_urls(self):
        invalid_urls = (
            'redis://default:synthetic-token@staging-example.upstash.io:6379/0',
            'rediss://staging-example.upstash.io:6379/0',
            'rediss://default:synthetic-token@staging-example.upstash.io/0',
            self.URL + '?ssl_cert_reqs=none',
            self.URL + '?ssl_check_hostname=false',
            self.URL + '#redis',
            'rediss://default:synthetic-token@staging-example.upstash.io:6379/1',
        )
        for value in invalid_urls:
            with self.subTest(url=value), self.assertRaises(RuntimeError):
                guard.validate_runtime_redis_url(
                    value,
                    'staging',
                    {'VERVFY_STAGING_REDIS_HOST': 'staging-example.upstash.io'},
                )

    def test_staging_rejects_missing_or_mismatched_host_allowlist(self):
        with self.assertRaises(RuntimeError):
            guard.validate_runtime_redis_url(self.URL, 'staging', {})
        with self.assertRaises(RuntimeError):
            guard.validate_runtime_redis_url(
                self.URL,
                'staging',
                {'VERVFY_STAGING_REDIS_HOST': 'production-example.upstash.io'},
            )

    def test_staging_rejects_production_redis_environment_variables(self):
        for key in ('PRODUCTION_REDIS_URL', 'REDIS_PRODUCTION_URL'):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                guard.validate_runtime_redis_url(
                    self.URL,
                    'staging',
                    {
                        'VERVFY_STAGING_REDIS_HOST': 'staging-example.upstash.io',
                        key: self.URL,
                    },
                )

    def test_unexpected_environments_are_rejected(self):
        for environment in ('preview', ' staging ', ''):
            with self.subTest(environment=environment), self.assertRaises(
                RuntimeError
            ):
                guard.validate_runtime_redis_url(self.URL, environment, {})

    def test_nonstaging_redis_behavior_and_optional_staging_redis_are_unchanged(self):
        for environment, url in (
            ('development', 'redis://127.0.0.1:6379/0'),
            ('local-test', 'redis://127.0.0.1:6379/0'),
            ('production', 'redis://internal:6379/0'),
        ):
            with self.subTest(environment=environment):
                self.assertIsNone(
                    guard.validate_runtime_redis_url(url, environment, {})
                )
        self.assertIsNone(
            guard.validate_runtime_redis_url(None, 'staging', {})
        )


class StagingGuardTests(unittest.TestCase):
    def setUp(self):
        self.approval = {
            'hostname': guard.STAGING_HOST,
            'port': 5432,
            'database': guard.STAGING_DATABASE,
            'resource_id': guard.STAGING_PROJECT_REF,
            'ca_file': '/approved/prod-ca-2021.crt',
            'ca_sha256': guard.STAGING_CA_SHA256,
        }

    def url(self, role='app_runtime', **overrides):
        parts = {
            'role': f'{role}.{guard.STAGING_PROJECT_REF}',
            'host': guard.STAGING_HOST,
            'port': '5432',
            'database': guard.STAGING_DATABASE,
            'query': urlencode({
                'sslmode': 'verify-full',
                'sslrootcert': self.approval['ca_file'],
                'gssencmode': 'disable',
            }),
        }
        parts.update(overrides)
        return (
            f"postgresql+psycopg://{parts['role']}:p%40ss@{parts['host']}:"
            f"{parts['port']}/{parts['database']}?{parts['query']}"
        )

    def test_valid_all_three_principals(self):
        for role in guard.ROLES.values():
            guard.validate_url(self.url(role), role, self.approval)

    def test_actual_target_and_tls_ca_are_pinned(self):
        for approval, url in (
            ({**self.approval, 'resource_id': 'another-project'}, self.url()),
            ({**self.approval, 'database': 'production'}, self.url()),
            ({**self.approval, 'ca_sha256': '0' * 64}, self.url()),
            ({**self.approval, 'ca_file': 'relative-ca.crt'}, self.url()),
            (self.approval, self.url(host='production.example.test')),
            (self.approval, self.url(database='production')),
            (self.approval, self.url(role='postgres')),
            (self.approval, self.url(role='app_runtime', port='5433')),
            (self.approval, self.url(query='sslmode=require')),
        ):
            with self.subTest(approval=approval, url=url), self.assertRaises(RuntimeError):
                guard.validate_url(url, 'app_runtime', approval)

    def test_mismatches_and_ambiguities(self):
        valid = self.url()
        variants = [
            None, '', valid.replace(':5432', ''), valid + '&host=production.example.test',
            valid + '&hostaddr=127.0.0.1', valid + '&service=production',
            valid + '&options=-crole=postgres',
            valid.replace('gssencmode=disable', 'gssencmode=prefer'),
            valid + '&sslmode=require', valid + '#fragment', valid + ' ',
            valid.replace(guard.STAGING_HOST, guard.STAGING_HOST + '.'),
            valid.replace(guard.STAGING_HOST, guard.STAGING_HOST + ',production.example.test'),
            valid.replace(guard.STAGING_HOST, '%61ws-0-us-east-1.pooler.supabase.com'),
            valid.replace('p%40ss', 'p@ss'),
            valid.replace(
                '%2Fapproved%2Fprod-ca-2021.crt',
                '%2Ftmp%2Fother.crt',
            ),
        ]
        for value in variants:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                guard.validate_url(value, 'app_runtime', self.approval)

    def test_environment_overrides_rejected_before_reading_approval(self):
        for key in ['PGHOST','PGHOSTADDR','PGSERVICE','PGOPTIONS','PGPASSWORD','PGSSLMODE','SSL_CERT_FILE','SSL_CERT_DIR']:
            with self.subTest(key=key), patch.object(guard.Path,'read_bytes',side_effect=AssertionError('must not read approval')):
                with self.assertRaises(RuntimeError):
                    guard.validate(
                        {'VERVFY_ENVIRONMENT':'staging',key:'unsafe'},
                        operation='preflight',
                    )

    def test_missing_approval_and_environment_fail_closed(self):
        for env in [{},{'VERVFY_ENVIRONMENT':'production'},{'VERVFY_ENVIRONMENT':'staging'}]:
            with self.assertRaises(RuntimeError):
                guard.validate(env, operation='preflight')

    def test_duplicate_approval_keys_rejected(self):
        with self.assertRaises(RuntimeError):guard.unique([('hostname','staging'),('hostname','production')])

    def test_alembic_guard_precedes_database_import(self):
        source=(guard.ROOT/'alembic/env.py').read_text()
        self.assertLess(source.index('    validate(operation="upgrade")'),source.index('from db import'))
        self.assertLess(source.index('require_alembic_execution_enabled()'),
                        source.index('from db import'))

    def test_alembic_blocks_local_profile_outside_staging_before_database_import(self):
        for environment in ('development', None):
            env = {'VERVFY_STAGING_PROFILE': guard.LOCAL_PROFILE}
            if environment is not None:
                env['VERVFY_ENVIRONMENT'] = environment
            alembic_stub = types.ModuleType('alembic')
            alembic_stub.context = object()
            with self.subTest(environment=environment), \
                 patch.dict(guard.os.environ, env, clear=True), \
                 patch.dict(guard.sys.modules, {'alembic': alembic_stub, 'db': None}), \
                 self.assertRaisesRegex(RuntimeError, 'local-disposable migrations are disabled'):
                runpy.run_path(str(guard.ROOT / 'alembic' / 'env.py'))

    def test_complete_approval_validation_without_connections(self):
        import json
        files = [
            'alembic.ini', 'alembic/env.py', 'db.py', 'staging_guard.py',
            'supabase_role_memberships.py', 'requirements.lock',
            'docs/staging-alembic-preflight.sql', 'docs/staging-alembic-postflight.sql',
        ]
        files += [
            str(path.relative_to(guard.ROOT))
            for path in (guard.ROOT / 'alembic/versions').glob('*.py')
        ]
        digest = lambda data: hashlib.sha256(data).hexdigest()
        manifest = json.dumps({
            name: digest((guard.ROOT / name).read_bytes()) for name in files
        }).encode()
        ca_digest = digest(b'CA')
        issued_at = datetime.now(timezone.utc).replace(microsecond=0)
        approval = {
            **self.approval,
            'ca_sha256': ca_digest,
            'archive': '/approved/source.tar.gz',
            'archive_sha256': digest(b'archive'),
            'manifest': '/approved/manifest.json',
            'manifest_sha256': digest(manifest),
            'operation': 'preflight',
            'issued_at': issued_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'expires_at': (issued_at + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        raw = json.dumps(approval).encode()
        virtual = {
            '/approved/approval.json': raw,
            approval['ca_file']: b'CA',
            '/approved/source.tar.gz': b'archive',
            '/approved/manifest.json': manifest,
        }
        original = guard.Path.read_bytes

        def read(path):
            return virtual[str(path)] if str(path) in virtual else original(path)

        env = {
            'VERVFY_ENVIRONMENT': 'staging',
            'STAGING_APPROVAL_FILE': '/approved/approval.json',
            'STAGING_APPROVAL_SHA256': digest(raw),
        }
        env.update({
            key: self.url(role)
            for key, role in guard.ROLES.items()
        })
        with patch.object(guard, 'STAGING_CA_SHA256', ca_digest), \
             patch.object(guard.Path, 'read_bytes', read), \
             patch.object(guard.Path, 'is_file', return_value=True), \
             patch.object(guard.Path, 'is_symlink', return_value=False), \
             patch.object(guard.subprocess, 'run',
                          side_effect=AssertionError('no subprocess')):
            self.assertEqual(guard.validate(env, operation='preflight')[0], approval)
            with self.assertRaisesRegex(RuntimeError, 'approval operation'):
                guard.validate(env, operation='upgrade')
            for key in guard.ROLES:
                wrong = dict(env)
                wrong[key] = wrong[key].replace(guard.STAGING_HOST, 'production.example.test')
                with self.assertRaises(RuntimeError):
                    guard.validate(wrong, operation='preflight')
            virtual[approval['ca_file']] = b'tampered CA'
            with self.assertRaisesRegex(RuntimeError, 'approved file digest mismatch'):
                guard.validate(env, operation='preflight')
            virtual[approval['ca_file']] = b'CA'
            virtual['/approved/source.tar.gz'] = b'tampered'
            with self.assertRaisesRegex(RuntimeError, 'approved file digest mismatch'):
                guard.validate(env, operation='preflight')

    def test_operation_approval_is_explicit_unexpired_and_limited_to_24_hours(self):
        now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
        approved = {
            'operation': 'preflight',
            'issued_at': '2026-11-11T11:00:00Z',
            'expires_at': '2026-11-12T11:00:00Z',
        }
        guard._validate_operation_approval(approved, 'preflight', now)
        guard._validate_operation_approval(
            {**approved, 'operation': 'upgrade'}, 'upgrade', now
        )
        invalid = (
            ({**approved, 'operation': 'upgrade'}, 'preflight'),
            ({**approved, 'operation': 'preflight'}, 'upgrade'),
            ({key: value for key, value in approved.items() if key != 'operation'}, 'preflight'),
            ({key: value for key, value in approved.items() if key != 'issued_at'}, 'preflight'),
            ({key: value for key, value in approved.items() if key != 'expires_at'}, 'preflight'),
            ({**approved, 'issued_at': '2026-11-11'}, 'preflight'),
            ({**approved, 'expires_at': '2026-02-30T11:00:00Z'}, 'preflight'),
            ({**approved, 'expires_at': '2026-11-11T12:00:00Z'}, 'preflight'),
            ({**approved, 'issued_at': '2026-11-11T12:01:00Z'}, 'preflight'),
            ({**approved, 'expires_at': '2026-11-12T11:00:01Z'}, 'preflight'),
        )
        for approval, operation in invalid:
            with self.subTest(approval=approval, operation=operation), \
                 self.assertRaises(RuntimeError):
                guard._validate_operation_approval(approval, operation, now)


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


@unittest.skip('Replaced by strict Supabase staging guard coverage')
class RenderExceptionTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        self.approval = {
            'hostname': 'dpg-isolated-a.oregon-postgres.render.com', 'port': 5432,
            'database': 'vervfy_oauth_staging', 'resource_id': 'dpg-isolated-a',
            'ca_file': '/approved/ca.pem', 'ca_sha256': hashlib.sha256(b'CA').hexdigest(),
            'tls_exception': {
                'provider': 'render', 'isolated_staging': True, 'sslmode': 'require',
                'expected_roles': dict(guard.ROLES), 'approver': 'test release owner',
                'risk_acceptance': 'Accept missing hostname authentication for isolated staging.',
                'approved_at': (now-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'expires_at': (now+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')}}

    def url(self, role):
        params = {'sslmode': 'require', 'gssencmode': 'disable'}
        if 'ca_file' in self.approval:
            params['sslrootcert'] = self.approval['ca_file']
        return f"postgresql+psycopg://{role}:secret@{self.approval['hostname']}:5432/vervfy_oauth_staging?" + urlencode(params)

    def test_require_is_explicit_and_valid_for_each_role(self):
        for role in guard.ROLES.values():
            guard.validate_url(self.url(role), role, self.approval)
        del self.approval['tls_exception']
        with self.assertRaises(RuntimeError):
            guard.validate_url(self.url('app_runtime'), 'app_runtime', self.approval)

    def test_invalid_approval(self):
        import copy
        changes = {'provider': 'other', 'isolated_staging': False, 'sslmode': 'prefer',
                   'expected_roles': {}, 'approver': ' ', 'risk_acceptance': '',
                   'approved_at': '2099-01-01T00:00:00Z', 'expires_at': '2000-01-01T00:00:00Z'}
        for key, value in changes.items():
            a = copy.deepcopy(self.approval); a['tls_exception'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): guard.tls_mode(a)
        for key in self.approval['tls_exception']:
            a = copy.deepcopy(self.approval); del a['tls_exception'][key]
            with self.subTest(missing=key), self.assertRaises(RuntimeError): guard.tls_mode(a)
        for key, value in [('hostname','production.example.test'), ('resource_id','other'),
                           ('database','production'), ('port',5433)]:
            a = copy.deepcopy(self.approval); a[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): guard.tls_mode(a)
        for value in ['2099-01-01T00:00:00Z', '2026-11-04', None]:
            a = copy.deepcopy(self.approval); a['tls_exception']['expires_at'] = value
            with self.assertRaises(RuntimeError): guard.tls_mode(a)

    def test_unsafe_urls_for_every_role(self):
        for role in guard.ROLES.values():
            url = self.url(role)
            variants = [url.replace('dpg-isolated-a', 'dpg-production-a'),
                        url.replace(':5432', ':5433'), url.replace('/vervfy_oauth_staging', '/production'),
                        url.replace('require', 'disable'), url.replace('require', 'verify-full')]
            variants += [url+'&'+param for param in ['host=x','hostaddr=127.0.0.1','service=x',
                         'options=-crole=postgres','sslmode=require','sslrootcert=x','gssencmode=prefer']]
            for value in variants:
                with self.subTest(role=role, url=value), self.assertRaises(RuntimeError):
                    guard.validate_url(value, role, self.approval)

    def test_preflight_postflight_use_validated_mode(self):
        for mode in ['require', 'verify-full']:
            a = dict(self.approval)
            if mode == 'verify-full': del a['tls_exception']
            urls = {'MIGRATION_DATABASE_URL': guard.urlsplit(self.url(guard.ROLES['MIGRATION_DATABASE_URL']))}
            for action in ['preflight', 'postflight']:
                with patch.object(guard, 'validate', return_value=(a, urls)), patch.object(guard.sys, 'argv', ['guard', action]), patch.object(guard.subprocess, 'run') as run:
                    guard.main()
                    env = run.call_args.kwargs['env']
                    self.assertEqual(env['PGSSLMODE'], mode)
                    self.assertEqual(env['PGHOST'], a['hostname'])
                    self.assertEqual(env['PGSSLROOTCERT'], a['ca_file'])
                    self.assertEqual(env['PGGSSENCMODE'], 'disable')

    def test_ca_free_require_all_roles_and_rejects_connection_overrides(self):
        del self.approval['ca_file']; del self.approval['ca_sha256']
        for role in guard.ROLES.values():
            url = self.url(role)
            guard.validate_url(url, role, self.approval)
            for parameter in ['sslrootcert=/other.pem', 'sslrootcert=', 'sslmode=',
                              'host=', 'hostaddr=127.0.0.1', 'service=other',
                              'options=-crole=postgres', 'gssencmode=prefer', 'sslmode=require']:
                with self.subTest(parameter=parameter), self.assertRaises(RuntimeError):
                    guard.validate_url(url + '&' + parameter, role, self.approval)
        del self.approval['tls_exception']
        with self.assertRaisesRegex(RuntimeError, 'verify-full requires approved CA'):
            guard.tls_parameters(self.approval)

    def test_ca_configuration_must_be_complete_and_valid(self):
        for mode in ['require', 'verify-full']:
            a = dict(self.approval)
            if mode == 'verify-full': del a['tls_exception']
            for key in ['ca_file', 'ca_sha256']:
                partial = dict(a); del partial[key]
                with self.subTest(mode=mode, missing=key), self.assertRaisesRegex(RuntimeError, 'incomplete CA'):
                    guard.tls_parameters(partial)
            for key, value in [('ca_file', ''), ('ca_file', None), ('ca_file', 'relative.pem'),
                               ('ca_sha256', ''), ('ca_sha256', None), ('ca_sha256', 'bad')]:
                invalid = dict(a); invalid[key] = value
                with self.subTest(mode=mode, key=key, value=value), self.assertRaises(RuntimeError):
                    guard.tls_parameters(invalid)
            url = self.url('app_runtime').replace('sslmode=require', 'sslmode='+mode)
            for bad in [url.replace('&sslrootcert=%2Fapproved%2Fca.pem', ''),
                        url.replace('%2Fapproved%2Fca.pem', '%2Fother.pem')]:
                with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                    guard.validate_url(bad, 'app_runtime', a)

    def test_ca_free_psql_and_alembic_dispatch(self):
        del self.approval['ca_file']; del self.approval['ca_sha256']
        env = {'VERVFY_ENVIRONMENT': 'staging'}
        env.update({key: self.url(role) for key, role in guard.ROLES.items()})
        urls = {key: guard.validate_url(env[key], role, self.approval)
                for key, role in guard.ROLES.items()}
        for action in ['preflight', 'postflight', 'upgrade']:
            with patch.dict(guard.os.environ, env, clear=True), patch.object(guard, 'validate', return_value=(self.approval, urls)), patch.object(guard.sys, 'argv', ['guard', action]), patch.object(guard.subprocess, 'run') as run:
                guard.main()
                child = run.call_args.kwargs['env']
                self.assertNotIn('PGSSLROOTCERT', child)
                if action == 'upgrade':
                    self.assertEqual(child['MIGRATION_DATABASE_URL'], env['MIGRATION_DATABASE_URL'])
                    self.assertIn('alembic', run.call_args.args[0])
                else:
                    self.assertEqual(child['PGSSLMODE'], 'require')
                    self.assertEqual(child['PGGSSENCMODE'], 'disable')
                    self.assertEqual(child['PGHOST'], self.approval['hostname'])


class HostedSupabaseDispatchTests(unittest.TestCase):
    def setUp(self):
        self.approval = {
            'hostname': guard.STAGING_HOST,
            'port': 5432,
            'database': guard.STAGING_DATABASE,
            'resource_id': guard.STAGING_PROJECT_REF,
            'ca_file': '/approved/prod-ca-2021.crt',
            'ca_sha256': guard.STAGING_CA_SHA256,
        }

    def test_readonly_dispatch_uses_pinned_pooler_identity_and_tls(self):
        fixture = StagingGuardTests()
        fixture.setUp()
        migration_url = fixture.url('vervfy_oauth_staging_user')
        urls = {'MIGRATION_DATABASE_URL': guard.urlsplit(migration_url)}
        for action in ('preflight', 'postflight'):
            with patch.dict(guard.os.environ, {'VERVFY_ENVIRONMENT': 'staging'}, clear=True), \
                 patch.object(guard, 'validate', return_value=(self.approval, urls)) as validate, \
                 patch.object(guard.sys, 'argv', ['guard', action]), \
                 patch.object(guard.subprocess, 'run') as run:
                guard.main()
                validate.assert_called_once_with(
                    operation='preflight' if action == 'preflight' else 'postflight'
                )
                child = run.call_args.kwargs['env']
                self.assertEqual(child['PGHOST'], guard.STAGING_HOST)
                self.assertEqual(child['PGPORT'], '5432')
                self.assertEqual(child['PGDATABASE'], 'postgres')
                self.assertEqual(
                    child['PGUSER'],
                    f"vervfy_oauth_staging_user.{guard.STAGING_PROJECT_REF}",
                )
                self.assertEqual(child['PGSSLMODE'], 'verify-full')
                self.assertEqual(child['PGSSLROOTCERT'], self.approval['ca_file'])
                self.assertEqual(child['PGGSSENCMODE'], 'disable')

    def test_upgrade_dispatch_uses_pooler_url_without_bypassing_guard(self):
        fixture = StagingGuardTests()
        fixture.setUp()
        migration_url = fixture.url('vervfy_oauth_staging_user')
        urls = {'MIGRATION_DATABASE_URL': guard.urlsplit(migration_url)}
        env = {
            'VERVFY_ENVIRONMENT': 'staging',
            'MIGRATION_DATABASE_URL': migration_url,
        }
        with patch.dict(guard.os.environ, env, clear=True), \
             patch.object(guard, 'validate', return_value=(self.approval, urls)) as validate, \
             patch.object(guard.sys, 'argv', ['guard', 'upgrade']), \
             patch.object(guard.subprocess, 'run') as run:
            guard.main()
            validate.assert_called_once_with(operation='upgrade')
            child = run.call_args.kwargs['env']
            self.assertEqual(child['MIGRATION_DATABASE_URL'], migration_url)
            self.assertIn('alembic', run.call_args.args[0])
