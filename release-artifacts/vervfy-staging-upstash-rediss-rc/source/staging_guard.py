"""Fail-closed staging execution boundary. Validation never opens a connection."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qsl, unquote

ROOT = Path(__file__).resolve().parent
STAGING_MIGRATION_TARGET = '0027_storage_lifecycle'
STAGING_MIGRATION_COUNT = 28
APPLICATION_PERMISSIONS_ACTION = 'application-permissions'
APPLICATION_PERMISSIONS_SQL = 'docs/staging-application-permissions.sql'
APPLICATION_PERMISSIONS_STAGING_HOST = 'aws-0-us-east-1.pooler.supabase.com'
APPLICATION_PERMISSIONS_STAGING_PROJECT = 'xgqvwqogdtktgfuubzwk'
APPLICATION_PERMISSIONS_STAGING_CA_PATHS = frozenset({
    '/etc/secrets/prod-ca-2021.crt',
    '/home/sam/Downloads/prod-ca-2021.crt',
})
APPLICATION_PERMISSIONS_STAGING_CA_SHA256 = (
    '700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7'
)
APPLICATION_PERMISSIONS_COLUMNS = (
    'migration_database_create',
    'migration_public_usage',
    'migration_public_create',
    'app_runtime_role_present',
    'app_runtime_database_connect',
    'app_runtime_database_create',
    'app_runtime_database_temp',
    'app_runtime_public_usage',
    'app_runtime_public_create',
    'google_auth_lookup_role_present',
    'google_auth_lookup_database_connect',
    'google_auth_lookup_database_create',
    'google_auth_lookup_database_temp',
    'google_auth_lookup_public_usage',
    'google_auth_lookup_public_create',
)
APPLICATION_PERMISSIONS_APPROVAL_FIELDS = {
    'action', 'issued_at', 'expires_at', 'diagnostic_sql_sha256',
}
MAX_DIAGNOSTIC_APPROVAL_LIFETIME = timedelta(hours=1)
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


def validate_application_permissions_approval(approval, action):
    if action != APPLICATION_PERMISSIONS_ACTION:
        require(
            not (APPLICATION_PERMISSIONS_APPROVAL_FIELDS & approval.keys()),
            'application-permissions approval cannot authorize another action',
        )
        return

    require(
        approval.get('action') == APPLICATION_PERMISSIONS_ACTION,
        'approval action mismatch',
    )
    require(
        approval.get('hostname') == APPLICATION_PERMISSIONS_STAGING_HOST
        and approval.get('resource_id') == APPLICATION_PERMISSIONS_STAGING_PROJECT
        and approval.get('port') == 5432
        and approval.get('database') == 'postgres'
        and approval.get('ca_file') in APPLICATION_PERMISSIONS_STAGING_CA_PATHS
        and approval.get('ca_sha256') == APPLICATION_PERMISSIONS_STAGING_CA_SHA256,
        'diagnostic target or CA differs from the pinned staging identity',
    )
    for key in ('issued_at', 'expires_at'):
        require(
            isinstance(approval.get(key), str)
            and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', approval[key])
            is not None,
            'invalid diagnostic approval timestamp',
        )
    try:
        issued_at = datetime.strptime(
            approval['issued_at'], '%Y-%m-%dT%H:%M:%SZ'
        ).replace(tzinfo=timezone.utc)
        expires_at = datetime.strptime(
            approval['expires_at'], '%Y-%m-%dT%H:%M:%SZ'
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        raise RuntimeError('Staging guard: invalid diagnostic approval timestamp') from None

    now = datetime.now(timezone.utc)
    require(
        issued_at <= now < expires_at
        and expires_at - issued_at <= MAX_DIAGNOSTIC_APPROVAL_LIFETIME,
        'diagnostic approval is expired or outside its validity window',
    )
    sql_path = ROOT / APPLICATION_PERMISSIONS_SQL
    require(
        sql_path.is_file()
        and not sql_path.is_symlink()
        and isinstance(approval.get('diagnostic_sql_sha256'), str)
        and re.fullmatch(r'[0-9a-f]{64}', approval['diagnostic_sql_sha256']) is not None
        and hashlib.sha256(sql_path.read_bytes()).hexdigest()
        == approval['diagnostic_sql_sha256'],
        'diagnostic SQL digest mismatch',
    )


def validate(env=None, action=None):
    env = os.environ if env is None else env
    require(env.get('VERVFY_ENVIRONMENT') == 'staging', 'explicit staging environment required')
    require(not any(k.startswith('PG') for k in env), 'remove all PG* overrides')
    require(not any(k in env for k in ('SSL_CERT_FILE','SSL_CERT_DIR')), 'remove TLS trust overrides')
    try:
        raw = Path(env['STAGING_APPROVAL_FILE']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == env['STAGING_APPROVAL_SHA256'], 'approval digest mismatch')
        a = json.loads(raw, object_pairs_hook=unique)
        base_fields = {
            'hostname', 'port', 'database', 'resource_id', 'archive',
            'archive_sha256', 'manifest', 'manifest_sha256',
        }
        expected_fields = base_fields | (
            APPLICATION_PERMISSIONS_APPROVAL_FIELDS
            if action == APPLICATION_PERMISSIONS_ACTION
            else set()
        )
        require(
            isinstance(a, dict)
            and set(a) - {'ca_file', 'ca_sha256'} == expected_fields,
            'approval fields mismatch',
        )
        validate_application_permissions_approval(a, action)
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
        if action == APPLICATION_PERMISSIONS_ACTION:
            required.add(APPLICATION_PERMISSIONS_SQL)
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


def parse_application_permissions_output(stdout):
    reader = csv.DictReader(io.StringIO(stdout))
    require(
        reader.fieldnames == list(APPLICATION_PERMISSIONS_COLUMNS),
        'invalid diagnostic result columns',
    )
    rows = list(reader)
    require(len(rows) == 1, 'invalid diagnostic result row count')
    result = {}
    for column in APPLICATION_PERMISSIONS_COLUMNS:
        value = rows[0][column]
        require(value in ('t', 'f', ''), 'invalid diagnostic result value')
        result[column] = None if value == '' else value == 't'
    return result


def run_application_permissions_diagnostic(child):
    try:
        result = subprocess.run(
            [
                'psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1',
                '--csv', '--quiet', '-f', str(ROOT / APPLICATION_PERMISSIONS_SQL),
            ],
            env=child, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            'Read-only application-permissions diagnostic failed; database output suppressed'
        ) from None
    print(json.dumps(parse_application_permissions_output(result.stdout), sort_keys=True))


def main():
    require(
        len(sys.argv) == 2
        and sys.argv[1] in (
            'check', 'preflight', 'postflight', 'upgrade',
            APPLICATION_PERMISSIONS_ACTION,
        ),
        'invalid operation',
    )
    action=sys.argv[1]
    a, urls=validate(action=action)
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
        if action == APPLICATION_PERMISSIONS_ACTION:
            run_application_permissions_diagnostic(child)
        else:
            subprocess.run(['psql','-X','--no-password','-v','ON_ERROR_STOP=1','-f',str(ROOT/f'docs/staging-alembic-{action}.sql')],env=child,check=True)


if __name__=='__main__':
    try:
        main()
    except RuntimeError as exc:
        sys.exit(str(exc))
