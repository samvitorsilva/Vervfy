"""Prepared operator runner. Default check-local cannot open a connection.

run-read-only requires a separately approved resource record/hash and private
preprovisioned inspection credential file. No credential content is read here.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).resolve().parent
RC = ROOT.parent / 'final-local-rc'
MANIFEST_SHA = '4674a05d4816aa62735cd82e11073627b0916b1dd09c4813b445d3f326981131'
ARCHIVE_SHA = '58da2d95be04aa7077c8c5b0b76965fcbb7f99f86b210b5565d5e94285e1108d'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate approval key')
        result[key] = value
    return result


def check_local():
    require(digest(RC / 'release-manifest.json') == MANIFEST_SHA, 'Release manifest mismatch')
    release = json.loads((RC / 'release-manifest.json').read_text())
    require(digest(RC / 'vervfy-release-candidate.tar.gz') == ARCHIVE_SHA, 'Candidate archive mismatch')
    procedure = json.loads((ROOT / 'procedure-manifest.json').read_text())
    for name, expected in procedure['files'].items():
        require(Path(name).name == name, 'Invalid procedure path')
        require(digest(ROOT / name) == expected, 'Procedure file mismatch')
    allowed = []
    for name, metadata in release['files'].items():
        if not name.startswith('alembic/versions/') or not name.endswith('.py'):
            continue
        path = RC / 'source' / name
        require(digest(path) == metadata['sha256'], 'Migration source mismatch')
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'revision' for t in node.targets):
                revision = ast.literal_eval(node.value)
                if int(revision[:4]) <= 27:
                    allowed.append(revision)
    require(len(allowed) == 27 and '0027_storage_lifecycle' in allowed, 'Unexpected release chain')
    return sorted(allowed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check-local', 'run-read-only'])
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--approval-sha256')
    parser.add_argument('--operator-id')
    parser.add_argument('--stage', choices=['catalogs', 'storage'])
    parser.add_argument('--passfile', type=Path)
    parser.add_argument('--reviewed-catalogs', type=Path)
    args = parser.parse_args()
    allowed = check_local()
    if args.action == 'check-local':
        print('PASS: local candidate/procedure hashes verified. No connection or SQL execution.')
        return
    require(all([args.approval, args.approval_sha256, args.operator_id, args.stage, args.passfile]),
            'STOP: approved resource record/hash, named operator, stage and private passfile required')
    require(digest(args.approval) == args.approval_sha256, 'Approval digest mismatch')
    record = json.loads(args.approval.read_text(), object_pairs_hook=unique)
    require(record['status'] == 'APPROVED' and record['scope'] == 'production_metadata_read_only', 'Scope not approved')
    for key in ('organization_id', 'project_name', 'region', 'operator_id', 'approver_id', 'approval_ticket', 'migration_role'):
        require(isinstance(record[key], str) and record[key].strip() and 'UNCONFIRMED' not in record[key], 'Unconfirmed resource/operator')
    require(record['operator_id'] == args.operator_id and record['inspection_identity_preprovisioned_and_reviewed'] is True,
            'Operator or inspection-identity approval missing')
    require(datetime.now(timezone.utc) < datetime.strptime(record['expires_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),
            'Approval expired')
    require(re.fullmatch('[a-z0-9]{20}', record['project_ref']), 'Invalid project reference')
    require(record['direct_host'] == 'db.' + record['project_ref'] + '.supabase.co' and record['port'] == 5432,
            'Unapproved direct endpoint')
    require(re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]{0,62}', record['database_name']), 'Invalid database name')
    require(re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]{0,62}', record['migration_role']), 'Invalid migration role name')
    require(record['inspection_role'] == 'vervfy_prod_inspector', 'Unapproved inspection role')
    require(record['migration_role'] not in ('vervfy_prod_inspector', 'app_runtime', 'google_auth_lookup', 'service_role'),
            'Invalid migration/inspection role separation')
    require(args.stage in record['allowed_stages'], 'Stage not approved')
    require(record['expected_current_revision'] in allowed + ['DISCOVER'], 'Unapproved current revision')
    require(record['reported_render_commit'] == 'dd22f18b92e26a59d342a98e06dfc2888c58905b', 'Baseline mismatch')
    require(digest(ROOT / 'procedure-manifest.json') == record['procedure_manifest_sha256'], 'Procedure not hash-bound')
    ca = Path(record['ca_file'])
    require(ca.is_absolute() and ca.is_file() and not ca.is_symlink() and digest(ca) == record['ca_sha256'], 'CA approval mismatch')
    require(args.passfile.is_absolute() and args.passfile.is_file() and not args.passfile.is_symlink(), 'Invalid private passfile')
    pass_stat = args.passfile.stat()
    require(pass_stat.st_uid == os.getuid() and stat.S_IMODE(pass_stat.st_mode) == 0o600, 'Private passfile must be operator-owned mode 0600')
    variables = {'inspection_role': record['inspection_role'], 'database_name': record['database_name'],
                 'migration_role': record['migration_role'], 'expected_revision': record['expected_current_revision'],
                 'allowed_revisions': ','.join(allowed)}
    if args.stage == 'storage':
        require(record['expected_current_revision'] != 'DISCOVER', 'Storage stage requires reviewed exact current revision')
        require(record['storage_project_ref'] == record['project_ref'] and
                record['storage_endpoint'] == 'https://' + record['storage_project_ref'] + '.supabase.co',
                'Separate project or custom storage domain requires revised approval/procedure')
        require(record['storage_rls_and_column_scope_reviewed'] is True and args.reviewed_catalogs,
                'Storage stage requires scoped RLS/column review and reviewed catalog output')
        require(digest(args.reviewed_catalogs) == record['catalog_review_sha256'], 'Reviewed catalog evidence mismatch')
        require(re.fullmatch('[a-z0-9][a-z0-9_-]{0,99}', record['bucket_id']) and
                re.fullmatch('[a-z0-9][a-z0-9_-]{0,99}', record['bucket_name']), 'Invalid approved bucket')
        require(uuid.UUID(record['namespace_id']).int != 0, 'Invalid namespace UUID')
        require(type(record['required_upload_bytes']) is int and record['required_upload_bytes'] > 0,
                'Approve actual application upload-byte limit')
        mime = record['required_mime_types']
        require(isinstance(mime, list) and mime and all(isinstance(x, str) and
                re.fullmatch('[a-z0-9.+-]+/[a-z0-9.+-]+', x) for x in mime), 'Approve application MIME list')
        variables.update(bucket_id=record['bucket_id'], bucket_name=record['bucket_name'],
                         namespace_id=record['namespace_id'], storage_endpoint=record['storage_endpoint'],
                         required_upload_bytes=str(record['required_upload_bytes']),
                         required_mime_types='{' + ','.join(mime) + '}')
    # No ambient database/PG/Supabase/Render variables, .psqlrc or service file.
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
           'PGHOST': record['direct_host'], 'PGPORT': '5432', 'PGDATABASE': record['database_name'],
           'PGUSER': record['inspection_role'], 'PGPASSFILE': str(args.passfile),
           'PGSSLMODE': 'verify-full', 'PGSSLROOTCERT': str(ca), 'PGGSSENCMODE': 'disable',
           'PGCONNECT_TIMEOUT': '10', 'PGAPPNAME': 'vervfy-production-metadata-preflight',
           'PGOPTIONS': '-c default_transaction_read_only=on -c search_path=pg_catalog -c statement_timeout=30s -c lock_timeout=3s'}
    command = ['/usr/bin/psql', '-X', '--no-password', '--set=ON_ERROR_STOP=1', '--set=VERBOSITY=terse']
    for key, value in variables.items():
        command += ['--set', key + '=' + value]
    command += ['--file', str(ROOT / ('01-catalogs.sql' if args.stage == 'catalogs' else '02-storage-metadata.sql'))]
    result = subprocess.run(command, env=env, check=False)
    require(result.returncode == 0, 'STOP: inspection failed; no permission changes or automatic retries')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError):
        sys.exit('STOP: local approval/integrity/inspection check failed. No automatic retry; review privately.')
