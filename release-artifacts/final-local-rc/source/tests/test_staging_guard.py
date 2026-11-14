"""No database imports or connections; exercise staging rejection boundaries."""
import hashlib
import unittest
from datetime import UTC
from unittest.mock import patch
from urllib.parse import urlencode

import staging_guard as guard


class StagingGuardTests(unittest.TestCase):
    def setUp(self):
        self.approval={'hostname':'staging.example.test','port':5432,'ca_file':'/approved/ca.pem','ca_sha256':hashlib.sha256(b'CA').hexdigest()}
        self.url='postgresql+psycopg://app_runtime:p%40ss@staging.example.test:5432/vervfy_oauth_staging?'+urlencode({'sslmode':'verify-full','sslrootcert':'/approved/ca.pem','gssencmode':'disable'})

    def test_valid_all_three_principals(self):
        for role in guard.ROLES.values():
            guard.validate_url(self.url.replace('app_runtime',role),role,self.approval)

    def test_production_host_rejected_for_every_principal(self):
        for role in guard.ROLES.values():
            with self.assertRaises(RuntimeError):
                guard.validate_url(self.url.replace('app_runtime',role).replace('staging.example.test','production.example.test'),role,self.approval)

    def test_mismatches_and_ambiguities(self):
        variants=[None,'',self.url.replace(':5432',''),self.url.replace(':5432',':5433'),
          self.url.replace('app_runtime','postgres'),self.url.replace('vervfy_oauth_staging','production'),
          self.url.replace('verify-full','require'),self.url+'&host=production.example.test',
          self.url+'&hostaddr=127.0.0.1',self.url+'&service=production',self.url+'&options=-crole=postgres',
          self.url.replace('gssencmode=disable','gssencmode=prefer'),self.url+'&sslmode=require',self.url+'#fragment',self.url+' ',
          self.url.replace('staging.example.test','staging.example.test.'),
          self.url.replace('staging.example.test','staging.example.test,production.example.test'),
          self.url.replace('staging.example.test','%73taging.example.test'),
          self.url.replace('p%40ss','p@ss'),self.url.replace('/approved/ca.pem','/other.pem')]
        # CA path is URL encoded; explicitly exercise changed trust root too.
        variants.append(self.url.replace('%2Fapproved%2Fca.pem','%2Fother.pem'))
        for value in variants:
            if value==self.url:
                continue
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                guard.validate_url(value,'app_runtime',self.approval)

    def test_environment_overrides_rejected_before_reading_approval(self):
        for key in ['PGHOST','PGHOSTADDR','PGSERVICE','PGOPTIONS','PGPASSWORD','PGSSLMODE','SSL_CERT_FILE','SSL_CERT_DIR']:
            with (
                self.subTest(key=key),
                patch.object(
                    guard.Path,
                    'read_bytes',
                    side_effect=AssertionError('must not read approval'),
                ),
                self.assertRaises(RuntimeError),
            ):
                guard.validate({'VERVFY_ENVIRONMENT':'staging',key:'unsafe'})

    def test_missing_approval_and_environment_fail_closed(self):
        for env in [{},{'VERVFY_ENVIRONMENT':'production'},{'VERVFY_ENVIRONMENT':'staging'}]:
            with self.assertRaises(RuntimeError): guard.validate(env)

    def test_duplicate_approval_keys_rejected(self):
        with self.assertRaises(RuntimeError):guard.unique([('hostname','staging'),('hostname','production')])

    def test_alembic_guard_precedes_database_import(self):
        source=(guard.ROOT/'alembic/env.py').read_text()
        self.assertLess(source.index('    validate()'),source.index('from db import'))

    def test_revision_argument_is_not_accepted(self):
        with patch.object(guard.sys, 'argv', ['staging_guard.py', 'upgrade', 'head']):
            with self.assertRaisesRegex(RuntimeError, 'invalid operation'):
                guard.main()

    def test_render_staging_api_requires_asgi_lifespan(self):
        proposal = (guard.ROOT / 'render.staging.proposal.yaml').read_text()
        self.assertRegex(
            proposal,
            r'(?m)^\s+startCommand: uvicorn server:app .* --lifespan on$',
        )

    def test_complete_approval_validation_without_connections(self):
        import json

        files=['alembic.ini','alembic/env.py','db.py','staging_guard.py','requirements.lock',
               'docs/staging-alembic-preflight.sql','docs/staging-alembic-postflight.sql']
        migration_dir = guard.ROOT/'alembic/versions'
        files += [str(p.relative_to(guard.ROOT)) for p in migration_dir.glob('*.py')]
        digest=lambda b:hashlib.sha256(b).hexdigest()
        manifest=json.dumps({name:digest((guard.ROOT/name).read_bytes()) for name in files}).encode()
        approval=dict(self.approval,database='vervfy_oauth_staging',resource_id='approved-test-resource',
                      ca_sha256=digest(b'CA'),archive='/approved/source.tar.gz',archive_sha256=digest(b'archive'),
                      manifest='/approved/manifest.json',manifest_sha256=digest(manifest))
        raw=json.dumps(approval).encode()
        virtual={'/approved/approval.json':raw,'/approved/ca.pem':b'CA',
                 '/approved/source.tar.gz':b'archive','/approved/manifest.json':manifest}
        original=guard.Path.read_bytes
        def read(path):
            return virtual[str(path)] if str(path) in virtual else original(path)
        env={'VERVFY_ENVIRONMENT':'staging','STAGING_APPROVAL_FILE':'/approved/approval.json',
             'STAGING_APPROVAL_SHA256':digest(raw)}
        env.update({key:self.url.replace('app_runtime',role) for key,role in guard.ROLES.items()})

        def reapprove_manifest(contents):
            manifest_bytes = json.dumps(contents).encode()
            virtual['/approved/manifest.json'] = manifest_bytes
            approval['manifest_sha256'] = digest(manifest_bytes)
            approval_bytes = json.dumps(approval).encode()
            virtual['/approved/approval.json'] = approval_bytes
            env['STAGING_APPROVAL_SHA256'] = digest(approval_bytes)

        with patch.object(guard.Path,'read_bytes',read), patch.object(guard.Path,'is_file',return_value=True), patch.object(guard.Path,'is_symlink',return_value=False), patch.object(guard.subprocess,'run',side_effect=AssertionError('no subprocess')):
            self.assertEqual(guard.validate(env)[0],approval)
            manifest_contents = json.loads(manifest)
            self.assertIn('alembic/versions/0028_storage_cleanup_leases.py', manifest_contents)
            missing_migration = dict(manifest_contents)
            missing_migration.pop('alembic/versions/0028_storage_cleanup_leases.py')
            reapprove_manifest(missing_migration)
            with self.assertRaisesRegex(RuntimeError, 'execution manifest file set mismatch'):
                guard.validate(env)
            reapprove_manifest(manifest_contents)

            extra_migration = dict(manifest_contents)
            extra_migration['alembic/versions/0029_unreviewed.py'] = digest(b'unreviewed')
            reapprove_manifest(extra_migration)
            with self.assertRaisesRegex(RuntimeError, 'execution manifest file set mismatch'):
                guard.validate(env)
            reapprove_manifest(manifest_contents)

            for key in guard.ROLES:
                wrong=dict(env);wrong[key]=wrong[key].replace('staging.example.test','production.example.test')
                with self.assertRaises(RuntimeError):guard.validate(wrong)
            fixture = RenderExceptionTests(); fixture.setUp()
            approval.update(fixture.approval)
            virtual['/approved/approval.json'] = json.dumps(approval).encode()
            env['STAGING_APPROVAL_SHA256'] = digest(virtual['/approved/approval.json'])
            env.update({key: fixture.url(role) for key, role in guard.ROLES.items()})
            self.assertEqual(guard.validate(env)[0], approval)
            virtual['/approved/ca.pem'] = b'tampered CA'
            with self.assertRaisesRegex(RuntimeError, 'digest mismatch'): guard.validate(env)
            virtual['/approved/ca.pem'] = b'CA'
            saved_ca = {key: approval.pop(key) for key in ('ca_file', 'ca_sha256')}
            virtual['/approved/approval.json'] = json.dumps(approval).encode()
            env['STAGING_APPROVAL_SHA256'] = digest(virtual['/approved/approval.json'])
            # A CA-free approval must reject URLs that still specify a CA.
            with self.assertRaisesRegex(RuntimeError, 'unsafe TLS'): guard.validate(env)
            env.update({key: value.replace('&sslrootcert=%2Fapproved%2Fca.pem', '')
                        for key, value in env.items() if key in guard.ROLES})
            self.assertEqual(guard.validate(env)[0], approval)
            approval.update(saved_ca)
            env.update({key: fixture.url(role) for key, role in guard.ROLES.items()})
            approval['tls_exception']['expires_at'] = '2000-01-01T00:00:00Z'
            virtual['/approved/approval.json'] = json.dumps(approval).encode()
            env['STAGING_APPROVAL_SHA256'] = digest(virtual['/approved/approval.json'])
            with self.assertRaisesRegex(RuntimeError, 'not active'): guard.validate(env)
            del approval['tls_exception']
            virtual['/approved/approval.json'] = json.dumps(approval).encode()
            env['STAGING_APPROVAL_SHA256'] = digest(virtual['/approved/approval.json'])
            with self.assertRaises(RuntimeError): guard.validate(env)
            env.update({key: fixture.url(role).replace('sslmode=require', 'sslmode=verify-full')
                        for key, role in guard.ROLES.items()})
            guard.validate(env)
            virtual['/approved/source.tar.gz']=b'tampered'
            with self.assertRaises(RuntimeError):guard.validate(env)

class RenderExceptionTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timedelta
        now = datetime.now(UTC)
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
