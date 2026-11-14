import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

import staging_guard as guard


class ApplicationPermissionsDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_path = Path(self.temp.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.approval = self.make_approval()

    @staticmethod
    def timestamp(value):
        return value.strftime('%Y-%m-%dT%H:%M:%SZ')

    def make_approval(self):
        ca_path = self.temp_path / 'staging-ca.pem'
        ca_path.write_bytes(b'synthetic staging CA')
        archive_path = self.temp_path / 'approved-source.tar.gz'
        archive_path.write_bytes(b'synthetic source archive')

        versions = {
            str(path.relative_to(guard.ROOT))
            for path in (guard.ROOT / 'alembic/versions').glob('*.py')
        }
        source_files = {
            'alembic.ini',
            'alembic/env.py',
            'db.py',
            'staging_guard.py',
            'supabase_role_memberships.py',
            'requirements.lock',
            'docs/staging-alembic-preflight.sql',
            'docs/staging-alembic-postflight.sql',
            'docs/staging-migration-default-privileges.sql',
            'docs/staging-namespace-bootstrap-grant.sql',
            'docs/staging-namespace-bootstrap-revoke.sql',
            guard.APPLICATION_PERMISSIONS_SQL,
        } | versions
        manifest = {
            name: hashlib.sha256((guard.ROOT / name).read_bytes()).hexdigest()
            for name in sorted(source_files)
        }
        manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
        manifest_path = self.temp_path / 'execution-manifest.json'
        manifest_path.write_bytes(manifest_bytes)

        return {
            'hostname': 'aws-0-us-east-1.pooler.supabase.com',
            'port': 5432,
            'database': 'postgres',
            'resource_id': 'xgqvwqogdtktgfuubzwk',
            'archive': str(archive_path),
            'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            'manifest': str(manifest_path),
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'ca_file': str(ca_path),
            'ca_sha256': hashlib.sha256(ca_path.read_bytes()).hexdigest(),
            'action': guard.APPLICATION_PERMISSIONS_ACTION,
            'issued_at': self.timestamp(self.now),
            'expires_at': self.timestamp(self.now + timedelta(minutes=30)),
            'diagnostic_sql_sha256': hashlib.sha256(
                (guard.ROOT / guard.APPLICATION_PERMISSIONS_SQL).read_bytes()
            ).hexdigest(),
        }

    def environment(self, approval=None):
        approval_path = self.temp_path / 'approval.json'
        approval_bytes = json.dumps(
            self.approval if approval is None else approval,
            sort_keys=True,
        ).encode()
        approval_path.write_bytes(approval_bytes)
        env = {
            'VERVFY_ENVIRONMENT': 'staging',
            'STAGING_APPROVAL_FILE': str(approval_path),
            'STAGING_APPROVAL_SHA256': hashlib.sha256(approval_bytes).hexdigest(),
        }
        for key, role in guard.ROLES.items():
            env[key] = self.url(role)
        return env

    def validate(self, env, action):
        with (
            patch.object(
                guard,
                'APPLICATION_PERMISSIONS_STAGING_CA_PATHS',
                guard.APPLICATION_PERMISSIONS_STAGING_CA_PATHS
                | {self.approval['ca_file']},
            ),
            patch.object(
                guard,
                'APPLICATION_PERMISSIONS_STAGING_CA_SHA256',
                self.approval['ca_sha256'],
            ),
        ):
            return guard.validate(env, action=action)

    def url(self, role):
        approval = self.approval
        query = urlencode({
            'sslmode': 'verify-full',
            'sslrootcert': approval['ca_file'],
            'gssencmode': 'disable',
        })
        return (
            f"postgresql+psycopg://{role}.{approval['resource_id']}:synthetic-secret"
            f"@{approval['hostname']}:{approval['port']}/postgres?{query}"
        )

    def test_valid_diagnostic_approval_is_checked_without_connecting(self):
        approval, _ = self.validate(
            self.environment(), guard.APPLICATION_PERMISSIONS_ACTION
        )
        self.assertEqual(approval, self.approval)

    def test_missing_approval_and_missing_diagnostic_binding_are_rejected(self):
        with self.assertRaises(RuntimeError):
            self.validate(
                {'VERVFY_ENVIRONMENT': 'staging'},
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

        approval = dict(self.approval)
        del approval['diagnostic_sql_sha256']
        with self.assertRaisesRegex(RuntimeError, 'approval fields mismatch'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

    def test_expired_diagnostic_approval_is_rejected(self):
        approval = dict(self.approval)
        approval['issued_at'] = self.timestamp(self.now - timedelta(hours=2))
        approval['expires_at'] = self.timestamp(self.now - timedelta(hours=1))
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

    def test_mismatched_diagnostic_sql_digest_is_rejected(self):
        approval = dict(self.approval)
        approval['diagnostic_sql_sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'diagnostic SQL digest mismatch'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

    def test_pinned_staging_identity_and_ca_are_reused(self):
        approval = dict(self.approval)
        approval['resource_id'] = 'aaaaaaaaaaaaaaaaaaaa'
        with self.assertRaisesRegex(RuntimeError, 'pinned staging identity'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

        approval = dict(self.approval)
        approval['ca_sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'pinned staging identity'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

        approval = dict(self.approval)
        approval['ca_file'] = '/tmp/unapproved-ca.pem'
        with self.assertRaisesRegex(RuntimeError, 'pinned staging identity'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

        source = (guard.ROOT / 'staging_database_guard.py').read_text()
        self.assertIn(guard.APPLICATION_PERMISSIONS_STAGING_HOST, source)
        self.assertIn(guard.APPLICATION_PERMISSIONS_STAGING_PROJECT, source)
        self.assertIn(guard.APPLICATION_PERMISSIONS_STAGING_CA_SHA256, source)

    def test_sql_checks_identity_and_uses_a_read_only_transaction(self):
        sql = (guard.ROOT / guard.APPLICATION_PERMISSIONS_SQL).read_text()
        self.assertIn('BEGIN TRANSACTION READ ONLY;', sql)
        self.assertIn('ROLLBACK;', sql)
        self.assertIn("session_user <> 'vervfy_oauth_staging_user'", sql)
        self.assertIn("current_user <> 'vervfy_oauth_staging_user'", sql)
        self.assertIn("current_setting('server_version_num')::integer < 170011", sql)
        for column in guard.APPLICATION_PERMISSIONS_COLUMNS:
            with self.subTest(column=column):
                self.assertIn(f'AS {column}', sql)
        self.assertNotRegex(
            sql,
            r'(?im)^\s*(?:INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALTER|DROP|GRANT|REVOKE)\b',
        )

    def test_wrong_action_and_diagnostic_approval_reuse_are_rejected(self):
        approval = dict(self.approval)
        approval['action'] = 'preflight'
        with self.assertRaisesRegex(RuntimeError, 'approval action mismatch'):
            self.validate(
                self.environment(approval),
                guard.APPLICATION_PERMISSIONS_ACTION,
            )

        env = self.environment()
        for action in ('preflight', 'upgrade'):
            with self.subTest(action=action), self.assertRaises(RuntimeError):
                self.validate(env, action=action)

    def test_dispatch_runs_only_diagnostic_and_prints_boolean_results(self):
        headers = ','.join(guard.APPLICATION_PERMISSIONS_COLUMNS)
        values = 't,f,t,t,t,f,f,t,f,f,,,,,'  # Absent role privileges are SQL NULL.
        completed = guard.subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f'{headers}\n{values}\n', stderr='',
        )
        migration_key = 'MIGRATION_DATABASE_URL'
        urls = {migration_key: urlsplit(self.url(guard.ROLES[migration_key]))}
        output = io.StringIO()
        with (
            patch.dict(guard.os.environ, {'VERVFY_ENVIRONMENT': 'staging'}, clear=True),
            patch.object(
                guard.sys, 'argv',
                ['staging_guard.py', guard.APPLICATION_PERMISSIONS_ACTION],
            ),
            patch.object(guard, 'validate', return_value=(self.approval, urls)),
            patch.object(guard.subprocess, 'run', return_value=completed) as run,
            contextlib.redirect_stdout(output),
        ):
            guard.main()

        results = json.loads(output.getvalue())
        self.assertIs(results['migration_database_create'], True)
        self.assertIs(results['migration_public_usage'], False)
        self.assertIs(results['google_auth_lookup_database_connect'], None)
        command = run.call_args.args[0]
        self.assertEqual(command[-1], str(guard.ROOT / guard.APPLICATION_PERMISSIONS_SQL))
        self.assertIn('--csv', command)
        self.assertIn('--no-password', command)
        self.assertNotIn(self.url(guard.ROLES[migration_key]), command)
        self.assertEqual(
            run.call_args.kwargs['env']['PGPASSWORD'], 'synthetic-secret'
        )
        self.assertNotIn('synthetic-secret', output.getvalue())

    def test_database_failure_output_is_suppressed(self):
        error = guard.subprocess.CalledProcessError(
            1, ['psql'], output='secret connection string', stderr='driver details',
        )
        with patch.object(guard.subprocess, 'run', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'database output suppressed') as raised:
                guard.run_application_permissions_diagnostic({})
        self.assertNotIn('secret connection string', str(raised.exception))
        self.assertNotIn('driver details', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
