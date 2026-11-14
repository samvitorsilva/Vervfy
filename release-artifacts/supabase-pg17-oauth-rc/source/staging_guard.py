"""Fail-closed staging execution boundary. Validation never opens a connection."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit, parse_qsl, unquote

ROOT = Path(__file__).resolve().parent
STAGING_MIGRATION_TARGET = '0027_storage_lifecycle'
STAGING_MIGRATION_COUNT = 28
ROLES = {'MIGRATION_DATABASE_URL': 'vervfy_oauth_staging_user',
         'DATABASE_URL': 'app_runtime',
         'GOOGLE_IDENTITY_LOOKUP_DATABASE_URL': 'google_auth_lookup'}


def require(ok, message):
    if not ok:
        raise RuntimeError('Staging guard: ' + message)


def unique(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, 'duplicate approval/manifest key')
        result[k] = v
    return result


def tls_mode(approval):
    """Supabase staging requires certificate and hostname verification."""
    require('tls_exception' not in approval, 'TLS exceptions are not permitted')
    return 'verify-full'


def tls_parameters(approval):
    """One exact TLS parameter set for URLs and psql, with no partial CA approval."""
    mode = tls_mode(approval)
    ca_keys = {'ca_file', 'ca_sha256'} & approval.keys()
    require(ca_keys in (set(), {'ca_file', 'ca_sha256'}), 'incomplete CA approval')
    require(mode == 'require' or bool(ca_keys), 'verify-full requires approved CA')
    params = {'sslmode': mode, 'gssencmode': 'disable'}
    if ca_keys:
        require(isinstance(approval['ca_file'], str) and approval['ca_file']
                and Path(approval['ca_file']).is_absolute(), 'invalid approved CA path')
        require(isinstance(approval['ca_sha256'], str)
                and re.fullmatch(r'[0-9a-f]{64}', approval['ca_sha256']) is not None,
                'invalid approved CA digest')
        params['sslrootcert'] = approval['ca_file']
    return params


def validate_url(raw, role, approval):
    # Only password may be percent encoded. Reject whitespace and URI fragments.
    require(isinstance(raw, str) and raw and not any(c.isspace() or ord(c)<32 for c in raw), 'missing/invalid URL')
    try:
        u = urlsplit(raw)
        port = u.port
        query = parse_qsl(u.query, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        raise RuntimeError('Staging guard: malformed URL') from None
    require(u.scheme in ('postgresql', 'postgresql+psycopg'), 'unsupported driver')
    require(not u.fragment and u.netloc.count('@') == 1, 'ambiguous authority/fragment')
    require(u.hostname == approval['hostname'] and u.netloc.rsplit('@',1)[1] == f"{approval['hostname']}:{approval['port']}", 'endpoint mismatch')
    expected_user = f"{role}.{approval['resource_id']}"
    require(port == approval['port'] and u.username == expected_user and u.password, 'port/login/password mismatch')
    require(u.path == '/postgres', 'database mismatch')
    expected = tls_parameters(approval)
    require(len(query) == len(expected) and dict(query) == expected, 'unsafe TLS/connection parameters')
    require('\x00' not in unquote(u.password), 'invalid password encoding')
    return u


def validate(env=None):
    env = os.environ if env is None else env
    require(env.get('VERVFY_ENVIRONMENT') == 'staging', 'explicit staging environment required')
    require(not any(k.startswith('PG') for k in env), 'remove all PG* overrides')
    require(not any(k in env for k in ('SSL_CERT_FILE','SSL_CERT_DIR')), 'remove TLS trust overrides')
    try:
        raw = Path(env['STAGING_APPROVAL_FILE']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == env['STAGING_APPROVAL_SHA256'], 'approval digest mismatch')
        a = json.loads(raw, object_pairs_hook=unique)
        require(isinstance(a, dict) and set(a) - {'ca_file','ca_sha256'} == {'hostname','port','database','resource_id','archive','archive_sha256','manifest','manifest_sha256'}, 'approval fields mismatch')
        require(isinstance(a['hostname'],str) and re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+',a['hostname']), 'invalid approved hostname')
        require(
            type(a['port']) is int
            and a['port'] == 5432
            and a['database'] == 'postgres'
            and isinstance(a['resource_id'], str)
            and re.fullmatch(r'[a-z0-9]{20}', a['resource_id']) is not None
            and re.fullmatch(
                r'[a-z0-9-]+\.pooler\.supabase\.com', a['hostname']
            ) is not None,
            'invalid Supabase session-pooler identity',
        )
        tls = tls_parameters(a)
        approved_files = [('archive','archive_sha256'),('manifest','manifest_sha256')]
        if 'sslrootcert' in tls:
            approved_files.append(('ca_file','ca_sha256'))
        for pathkey, hashkey in approved_files:
            p = Path(a[pathkey])
            require(p.is_absolute() and p.is_file() and not p.is_symlink(), 'invalid approved file')
            require(hashlib.sha256(p.read_bytes()).hexdigest() == a[hashkey], 'approved file digest mismatch')
        manifest=json.loads(Path(a['manifest']).read_bytes(), object_pairs_hook=unique)
        versions={str(p.relative_to(ROOT)) for p in (ROOT/'alembic/versions').glob('*.py')}
        required={'alembic.ini','alembic/env.py','db.py','staging_guard.py',
                  'supabase_role_memberships.py','requirements.lock',
                  'docs/staging-alembic-preflight.sql',
                  'docs/staging-alembic-postflight.sql',
                  'docs/staging-migration-default-privileges.sql',
                  'docs/staging-namespace-bootstrap-grant.sql',
                  'docs/staging-namespace-bootstrap-revoke.sql'} | versions
        require(
            len(versions) == STAGING_MIGRATION_COUNT
            and f'alembic/versions/{STAGING_MIGRATION_TARGET}.py' in versions
            and 'alembic/versions/0028_storage_cleanup_leases.py' in versions
            and set(manifest) == required,
            'execution manifest file set mismatch',
        )
        for name,digest in manifest.items():
            p=ROOT/name
            require(not any(x.is_symlink() for x in [p,*p.parents]), 'symlink execution path')
            require(hashlib.sha256(p.read_bytes()).hexdigest()==digest, 'execution file digest mismatch')
        urls={key:validate_url(env.get(key),role,a) for key,role in ROLES.items()}
        return a,urls
    except (KeyError, OSError, ValueError, TypeError):
        raise RuntimeError('Staging guard: missing or invalid approval material') from None


def main():
    require(len(sys.argv)==2 and sys.argv[1] in ('check','preflight','postflight','upgrade'), 'invalid operation')
    a, urls=validate()
    action=sys.argv[1]
    if action=='check':
        print('PASS: approved staging endpoint and execution files validated (no connection)')
        return
    child=dict(os.environ)
    if action=='upgrade':
        subprocess.run(
            [
                sys.executable, '-m', 'alembic', '-c', str(ROOT/'alembic.ini'),
                'upgrade', STAGING_MIGRATION_TARGET,
            ],
            cwd=ROOT, env=child, check=True,
        )
    else:
        u=urls['MIGRATION_DATABASE_URL']
        child.update(PGHOST=a['hostname'], PGPORT=str(a['port']), PGDATABASE=a['database'],
                     PGUSER=u.username, PGPASSWORD=unquote(u.password),
                     PGCONNECT_TIMEOUT='10',
                     PGOPTIONS='-c search_path=public -c default_transaction_read_only=on -c statement_timeout=30s')
        child.update({'PG' + key.upper(): value for key, value in tls_parameters(a).items()})
        subprocess.run(['psql','-X','--no-password','-v','ON_ERROR_STOP=1','-f',str(ROOT/f'docs/staging-alembic-{action}.sql')],env=child,check=True)


if __name__=='__main__':
    try:
        main()
    except RuntimeError as exc:
        sys.exit(str(exc))
