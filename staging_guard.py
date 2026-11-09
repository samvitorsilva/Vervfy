"""Fail-closed staging execution boundary. Validation never opens a connection."""
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ROLES = {'MIGRATION_DATABASE_URL': 'vervfy_oauth_staging_user',
         'DATABASE_URL': 'app_runtime',
         'GOOGLE_IDENTITY_LOOKUP_DATABASE_URL': 'google_auth_lookup'}
LOCAL_PROFILE = 'local-disposable'
LOCAL_DATABASE = 'vervfy_oauth_staging'
LOCAL_HOST = '127.0.0.1'
LOCAL_PORT = 55433
LOCAL_REDIS_PORT = 56379
LOCAL_STATE_PREFIX = 'vervfy-staging-local-'
LOCAL_PROCESS_KEYS = {
    'VERVFY_ENVIRONMENT', 'VERVFY_STAGING_PROFILE', 'VERVFY_LOCAL_STATE_DIR',
    'VERVFY_SECRET_KEY', 'VERVFY_HTTPS_ONLY', 'VERVFY_TRUSTED_PROXY_HOPS',
    'VERVFY_COOKIE_SAME_SITE', 'VERVFY_ASYNC_UPLOADS',
    'LYRICS_PROVIDER_LRCLIB', 'GOOGLE_OAUTH_ENABLED', 'DATABASE_URL',
    'MIGRATION_DATABASE_URL', 'GOOGLE_IDENTITY_LOOKUP_DATABASE_URL',
    'REDIS_URL', 'PGPASSFILE',
}


def _local_paths(env):
    home = Path(env.get('HOME', ''))
    require(home.is_absolute() and str(home) == os.path.normpath(str(home)),
            'local HOME must be an absolute canonical path')
    state = Path(env.get('VERVFY_LOCAL_STATE_DIR', ''))
    state_parent = home / '.local' / 'share'
    require(state.is_absolute() and state.parent == state_parent
            and re.fullmatch(re.escape(LOCAL_STATE_PREFIX) + r'[A-Za-z0-9]{8}',
                             state.name) is not None,
            'local state directory must be a unique managed path under HOME')
    config = home / '.config' / 'vervfy'
    return {
        'home': home,
        'state': state,
        'env_file': config / 'staging-local.env',
        'pgpass': config / 'staging-local.pgpass',
        'valkey_config': state / 'valkey' / 'valkey.conf',
        'ready_marker': state / '.local-staging-ready',
        'pg_data': state / 'postgres' / 'data',
        'pg_version': state / 'postgres' / 'data' / 'PG_VERSION',
        'pg_control': state / 'postgres' / 'data' / 'global' / 'pg_control',
    }


def _path_exists(path):
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        raise RuntimeError('Staging guard: cannot inspect local initialization state') from None


def _validate_private_file(path, home, label):
    require(path.is_absolute(), f'{label} path must be absolute')
    try:
        relative = path.relative_to(home)
    except ValueError:
        raise RuntimeError(f'Staging guard: {label} must be inside HOME') from None

    uid = os.getuid()
    components = (home, *(home / Path(*relative.parts[:index])
                           for index in range(1, len(relative.parts))))
    for directory in components:
        try:
            details = directory.lstat()
        except OSError:
            raise RuntimeError(f'Staging guard: unsafe or missing {label} directory') from None
        require(stat.S_ISDIR(details.st_mode) and not stat.S_ISLNK(details.st_mode)
                and details.st_uid == uid and stat.S_IMODE(details.st_mode) & 0o022 == 0,
                f'unsafe {label} directory')

    try:
        details = path.lstat()
    except OSError:
        raise RuntimeError(f'Staging guard: missing {label}') from None
    require(stat.S_ISREG(details.st_mode) and not stat.S_ISLNK(details.st_mode)
            and details.st_uid == uid and stat.S_IMODE(details.st_mode) == 0o600,
            f'{label} must be a regular owner-only 0600 file')


def _validate_local_artifacts(paths):
    artifacts = (
        paths['env_file'], paths['pgpass'], paths['valkey_config'],
        paths['pg_version'], paths['pg_control'], paths['ready_marker'],
    )
    present = [_path_exists(path) for path in artifacts]
    if not any(present) and not _path_exists(paths['state']):
        raise RuntimeError('Staging guard: local staging initialization has not started')
    require(all(present),
            'partial local staging initialization; preserve files and inspect before continuing')

    state_dirs = (
        paths['state'], paths['state'] / 'postgres',
        paths['pg_data'], paths['state'] / 'postgres' / 'socket',
        paths['pg_data'] / 'global',
        paths['state'] / 'valkey', paths['state'] / 'valkey' / 'data',
    )
    uid = os.getuid()
    for directory in state_dirs:
        try:
            details = directory.lstat()
        except OSError:
            raise RuntimeError('Staging guard: incomplete local state directory') from None
        require(stat.S_ISDIR(details.st_mode) and not stat.S_ISLNK(details.st_mode)
                and details.st_uid == uid and stat.S_IMODE(details.st_mode) == 0o700,
                'local state directories must be owner-only 0700 directories')

    _validate_private_file(paths['env_file'], paths['home'], 'local environment file')
    _validate_private_file(paths['pgpass'], paths['home'], 'PGPASSFILE')
    _validate_private_file(paths['valkey_config'], paths['home'], 'Valkey config')
    _validate_private_file(paths['ready_marker'], paths['home'], 'local readiness marker')
    for path in (paths['pg_version'], paths['pg_control']):
        try:
            details = path.lstat()
        except OSError:
            raise RuntimeError('Staging guard: incomplete PostgreSQL cluster files') from None
        require(stat.S_ISREG(details.st_mode) and not stat.S_ISLNK(details.st_mode)
                and details.st_uid == uid,
                'unsafe PostgreSQL cluster file')
    try:
        version = paths['pg_version'].read_text(encoding='ascii').strip()
    except (OSError, UnicodeError):
        raise RuntimeError('Staging guard: cannot read local PostgreSQL version') from None
    require(version == '18', 'local PostgreSQL cluster must be version 18')
    try:
        marker = paths['ready_marker'].read_text(encoding='ascii')
    except (OSError, UnicodeError):
        raise RuntimeError('Staging guard: invalid local readiness marker') from None
    require(marker == 'local-disposable-v1\n',
            'local staging readiness marker is incomplete or invalid')


def _validate_local_env_file(path, env):
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        raise RuntimeError('Staging guard: invalid local environment file') from None
    values = {}
    for line in lines:
        match = re.fullmatch(r'export ([A-Z][A-Z0-9_]*)=(.*)', line)
        require(match is not None, 'local environment file contains unsupported syntax')
        key, raw_value = match.groups()
        require(key in LOCAL_PROCESS_KEYS and key not in values,
                'local environment file contains an unapproved or duplicate variable')
        try:
            parts = shlex.split(raw_value)
        except ValueError:
            raise RuntimeError('Staging guard: invalid local environment value') from None
        require(len(parts) == 1, 'local environment file contains an invalid value')
        require(raw_value == shlex.quote(parts[0]),
                'local environment file value is not canonically quoted')
        values[key] = parts[0]
    require(set(values) == LOCAL_PROCESS_KEYS,
            'local environment file does not match the reviewed allowlist')
    require(all(env.get(key) == value for key, value in values.items()),
            'local environment file does not match the validated process environment')


def _validate_local_pgpass(path, home):
    expected = home / '.config' / 'vervfy' / 'staging-local.pgpass'
    require(path == str(expected), 'PGPASSFILE must use the dedicated local credential path')
    _validate_private_file(expected, home, 'PGPASSFILE')
    try:
        lines = expected.read_text(encoding='ascii').splitlines()
    except (OSError, UnicodeError):
        raise RuntimeError('Staging guard: invalid PGPASSFILE') from None
    require(len(lines) == len(ROLES), 'PGPASSFILE must contain exactly the three staging logins')
    seen = set()
    for line in lines:
        fields = line.split(':')
        require(len(fields) == 5, 'PGPASSFILE contains an unexpected entry')
        host, port, database, role, password = fields
        require((host, port, database) == (LOCAL_HOST, str(LOCAL_PORT), LOCAL_DATABASE)
                and role in ROLES.values()
                and re.fullmatch(r'[0-9a-f]{64}', password) is not None
                and role not in seen,
                'PGPASSFILE contains an unexpected or duplicate entry')
        seen.add(role)
    require(seen == set(ROLES.values()), 'PGPASSFILE is missing a staging login')


def _validate_local_database_url(raw, role):
    require(isinstance(raw, str) and raw
            and not any(c.isspace() or ord(c) < 32 for c in raw),
            'missing/invalid local database URL')
    try:
        u = urlsplit(raw)
        port = u.port
        query = parse_qsl(u.query, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        raise RuntimeError('Staging guard: malformed local database URL') from None
    require(u.scheme == 'postgresql+psycopg'
            and u.netloc == f'{role}@{LOCAL_HOST}:{LOCAL_PORT}'
            and u.hostname == LOCAL_HOST and port == LOCAL_PORT
            and u.username == role and u.password is None
            and u.path == f'/{LOCAL_DATABASE}' and not u.fragment,
            'local database endpoint, role, or database mismatch')
    expected = {'sslmode': 'disable', 'gssencmode': 'disable'}
    require(len(query) == len(expected) and len(dict(query)) == len(query)
            and dict(query) == expected,
            'local database URL has unexpected connection parameters')
    return u


def _validate_local_redis_url(raw, valkey_config, state):
    require(isinstance(raw, str) and raw
            and not any(c.isspace() or ord(c) < 32 for c in raw),
            'missing/invalid local REDIS_URL')
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        raise RuntimeError('Staging guard: malformed local REDIS_URL') from None
    require(u.scheme == 'redis' and u.hostname == LOCAL_HOST
            and port == LOCAL_REDIS_PORT and u.username in (None, '')
            and re.fullmatch(r'[0-9a-f]{64}', u.password or '') is not None
            and u.path == '/0' and not u.query and not u.fragment,
            'REDIS_URL must target only the authenticated local Valkey database')

    try:
        rows = [shlex.split(line, comments=True) for line in
                valkey_config.read_text(encoding='utf-8').splitlines()]
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError('Staging guard: invalid local Valkey config') from None
    directives = {}
    allowed = {'bind', 'protected-mode', 'port', 'dir', 'pidfile', 'logfile',
               'daemonize', 'save', 'appendonly', 'maxmemory',
               'maxmemory-policy', 'requirepass'}
    for row in rows:
        if not row:
            continue
        require(row[0] in allowed, 'local Valkey config contains an unapproved directive')
        directives.setdefault(row[0], []).append(row[1:])
    expected = {
        'bind': [[LOCAL_HOST]], 'protected-mode': [['yes']],
        'port': [[str(LOCAL_REDIS_PORT)]],
        'dir': [[str(state / 'valkey' / 'data')]],
        'pidfile': [[str(state / 'valkey' / 'valkey.pid')]],
        'logfile': [[str(state / 'valkey' / 'valkey.log')]],
        'daemonize': [['yes']], 'save': [['']],
        'appendonly': [['no']], 'maxmemory': [['256mb']],
        'maxmemory-policy': [['noeviction']],
        'requirepass': [[u.password]],
    }
    require(directives == expected, 'local Valkey config does not match isolated REDIS_URL')
    return u


def _reject_local_provider_environment(env):
    blocked_exact = {
        'SUPABASE_URL', 'SUPABASE_KEY', 'SUPABASE_SERVICE_KEY',
        'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI',
        'GOOGLE_FRONTEND_ORIGIN',
    }
    allowed_google = {'GOOGLE_OAUTH_ENABLED', 'GOOGLE_IDENTITY_LOOKUP_DATABASE_URL'}
    credential_suffix = re.compile(
        r'(?:^|_)(?:API_KEY|SECRET|SECRET_KEY|CLIENT_SECRET|SERVICE_KEY|'
        r'ACCESS_TOKEN|REFRESH_TOKEN|TOKEN|ACCESS_KEY|ACCESS_KEY_ID|PRIVATE_KEY|'
        r'PASSWORD|CREDENTIALS)$'
    )
    for key in env:
        require(key not in blocked_exact, f'unapproved provider variable: {key}')
        require(not key.startswith(('SUPABASE_', 'RENDER_', 'CLOUDFLARE_', 'CF_')),
                f'unapproved provider variable: {key}')
        if key.startswith('GOOGLE_'):
            require(key in allowed_google, f'unapproved Google variable: {key}')
        require(not key.startswith(('OAUTH_', 'OIDC_')),
                f'unapproved OAuth variable: {key}')
        require(not re.search(r'(?:^|_)(?:PROD|PRODUCTION)(?:_|$)', key),
                f'production variable is forbidden: {key}')
        if credential_suffix.search(key):
            require(key == 'VERVFY_SECRET_KEY',
                    f'unapproved provider credential variable: {key}')


def _validate_local(env):
    require(env.get('VERVFY_ENVIRONMENT') == 'staging',
            'explicit staging environment required')
    require(env.get('VERVFY_STAGING_PROFILE') == LOCAL_PROFILE,
            'explicit local-disposable profile required')
    _reject_local_provider_environment(env)
    require(env.get('GOOGLE_OAUTH_ENABLED') == '0',
            'Google OAuth must remain explicitly disabled')
    require(env.get('VERVFY_HTTPS_ONLY') == '0'
            and env.get('VERVFY_TRUSTED_PROXY_HOPS') == '0'
            and env.get('VERVFY_COOKIE_SAME_SITE') == 'lax'
            and env.get('VERVFY_ASYNC_UPLOADS') == '0'
            and env.get('LYRICS_PROVIDER_LRCLIB') == '0',
            'local-only runtime settings are incomplete')
    require(re.fullmatch(r'[0-9a-f]{64}', env.get('VERVFY_SECRET_KEY', '')) is not None,
            'local VERVFY_SECRET_KEY must be a generated 256-bit value')

    pg_keys = [key for key in env if key.startswith('PG') and key != 'PGPASSFILE']
    require(not pg_keys, 'remove all PostgreSQL overrides except PGPASSFILE')
    require(not any(key in env for key in ('SSL_CERT_FILE', 'SSL_CERT_DIR')),
            'remove TLS trust overrides')

    paths = _local_paths(env)
    _validate_local_artifacts(paths)
    _validate_local_env_file(paths['env_file'], env)
    _validate_local_pgpass(env.get('PGPASSFILE', ''), paths['home'])
    urls = {
        key: _validate_local_database_url(env.get(key), role)
        for key, role in ROLES.items()
    }
    lookup = urls['GOOGLE_IDENTITY_LOOKUP_DATABASE_URL']
    application = urls['DATABASE_URL']
    require((lookup.hostname, lookup.port, lookup.username, lookup.path)
            != (application.hostname, application.port, application.username,
                application.path),
            'restricted lookup connection must be independent from DATABASE_URL')
    _validate_local_redis_url(env.get('REDIS_URL'), paths['valkey_config'], paths['state'])
    return {
        'hostname': LOCAL_HOST, 'port': LOCAL_PORT,
        'database': LOCAL_DATABASE, 'profile': LOCAL_PROFILE,
    }, urls


def local_child_environment(env=None):
    """Return only reviewed local settings; never forward ambient provider secrets."""
    env = os.environ if env is None else env
    _validate_local(env)
    child = {'PATH': os.defpath, 'LC_ALL': 'C.UTF-8', 'HOME': env['HOME']}
    for key in LOCAL_PROCESS_KEYS:
        if key in env:
            child[key] = env[key]
    child['PYTHONNOUSERSITE'] = '1'
    return child


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
    """Default to authenticated TLS; a bounded approval permits Render staging only."""
    if 'tls_exception' not in approval:
        return 'verify-full'
    e = approval['tls_exception']
    require(isinstance(e, dict) and set(e) == {
        'provider', 'isolated_staging', 'sslmode', 'expected_roles', 'approver',
        'risk_acceptance', 'approved_at', 'expires_at'}, 'invalid TLS exception fields')
    require(e['provider'] == 'render' and e['isolated_staging'] is True
            and e['sslmode'] == 'require', 'exception is only for isolated Render staging')
    require(re.fullmatch(r'dpg-[a-z0-9-]+', approval['resource_id']) is not None
            and re.fullmatch(r'dpg-[a-z0-9-]+\.[a-z0-9-]+-postgres\.render\.com',
                             approval['hostname']) is not None,
            'exception requires a direct Render PostgreSQL resource')
    require(approval['database'] == 'vervfy_oauth_staging' and approval['port'] == 5432
            and e['expected_roles'] == ROLES, 'exception identity/roles mismatch')
    require(all(isinstance(e[k], str) and e[k].strip()
                for k in ('approver', 'risk_acceptance')), 'approver and risk acceptance required')
    try:
        times = [datetime.strptime(e[k], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                 for k in ('approved_at', 'expires_at')]
    except (ValueError, TypeError):
        raise RuntimeError('Staging guard: invalid exception UTC timestamps') from None
    start, end = times
    require(start <= datetime.now(timezone.utc) < end and end - start <= timedelta(days=7),
            'TLS exception not active or exceeds seven days')
    return 'require'


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
    require(port == approval['port'] and u.username == role and u.password, 'port/login/password mismatch')
    require(u.path == '/vervfy_oauth_staging', 'database mismatch')
    expected = tls_parameters(approval)
    require(len(query) == len(expected) and dict(query) == expected, 'unsafe TLS/connection parameters')
    require('\x00' not in unquote(u.password), 'invalid password encoding')
    return u


def _validate_hosted(env):
    require(env.get('VERVFY_ENVIRONMENT') == 'staging', 'explicit staging environment required')
    require(not any(k.startswith('PG') for k in env), 'remove all PG* overrides')
    require(not any(k in env for k in ('SSL_CERT_FILE','SSL_CERT_DIR')), 'remove TLS trust overrides')
    try:
        raw = Path(env['STAGING_APPROVAL_FILE']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == env['STAGING_APPROVAL_SHA256'], 'approval digest mismatch')
        a = json.loads(raw, object_pairs_hook=unique)
        require(isinstance(a, dict) and set(a) - {'tls_exception','ca_file','ca_sha256'} == {'hostname','port','database','resource_id','archive','archive_sha256','manifest','manifest_sha256'}, 'approval fields mismatch')
        require(isinstance(a['hostname'],str) and re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+',a['hostname']), 'invalid approved hostname')
        require(type(a['port']) is int and a['port'] == 5432 and a['database']=='vervfy_oauth_staging' and isinstance(a['resource_id'], str) and a['resource_id'].strip(), 'invalid approved identity')
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
        required={'alembic.ini','alembic/env.py','db.py','staging_guard.py','requirements.lock',
                  'docs/staging-alembic-preflight.sql','docs/staging-alembic-postflight.sql'} | versions
        require(len(versions)==26 and set(manifest)==required, 'execution manifest file set mismatch')
        for name,digest in manifest.items():
            p=ROOT/name
            require(not any(x.is_symlink() for x in [p,*p.parents]), 'symlink execution path')
            require(hashlib.sha256(p.read_bytes()).hexdigest()==digest, 'execution file digest mismatch')
        urls={key:validate_url(env.get(key),role,a) for key,role in ROLES.items()}
        return a,urls
    except (KeyError, OSError, ValueError, TypeError):
        raise RuntimeError('Staging guard: missing or invalid approval material') from None


def validate(env=None):
    env = os.environ if env is None else env
    profile = env.get('VERVFY_STAGING_PROFILE')
    if profile == LOCAL_PROFILE:
        return _validate_local(env)
    require(profile is None or profile == 'hosted',
            'unknown staging profile')
    return _validate_hosted(env)


def require_alembic_execution_enabled(env=None):
    env = os.environ if env is None else env
    require(env.get('VERVFY_STAGING_PROFILE') != LOCAL_PROFILE,
            'local-disposable migrations are disabled until separately approved')


def main():
    require(len(sys.argv)==2 and sys.argv[1] in ('check','preflight','postflight','upgrade'), 'invalid operation')
    a, urls=validate()
    action=sys.argv[1]
    if action=='check':
        if a.get('profile') == LOCAL_PROFILE:
            print('PASS: local-disposable profile validated (no connection)')
            return
        print('PASS: approved staging endpoint and execution files validated (no connection)')
        return
    require(a.get('profile') != LOCAL_PROFILE,
            'local-disposable profile is validation-only in this phase')
    child=dict(os.environ)
    if action=='upgrade':
        subprocess.run([sys.executable,'-m','alembic','-c',str(ROOT/'alembic.ini'),'upgrade','head'],cwd=ROOT,env=child,check=True)
    else:
        u=urls['MIGRATION_DATABASE_URL']
        child.update(PGHOST=a['hostname'], PGPORT=str(a['port']), PGDATABASE=a['database'],
                     PGUSER=ROLES['MIGRATION_DATABASE_URL'], PGPASSWORD=unquote(u.password),
                     PGCONNECT_TIMEOUT='10',
                     PGOPTIONS='-c search_path=public -c default_transaction_read_only=on -c statement_timeout=30s')
        child.update({'PG' + key.upper(): value for key, value in tls_parameters(a).items()})
        subprocess.run(['psql','-X','--no-password','-v','ON_ERROR_STOP=1','-f',str(ROOT/f'docs/staging-alembic-{action}.sql')],env=child,check=True)


if __name__=='__main__':
    try:
        main()
    except RuntimeError as exc:
        sys.exit(str(exc))
