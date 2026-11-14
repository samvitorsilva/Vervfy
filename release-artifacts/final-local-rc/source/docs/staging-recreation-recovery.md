# Isolated staging recreation and migration approval packet

> Release instruction update: apply only `0027_storage_lifecycle`; keep 0028
> unapplied. Earlier audit results below are historical evidence. Current role,
> metadata and approval requirements are in `staging-db-initialization-runbook.md`;
> namespace setup is in `storage-namespace-initialization.md`. Older approval
> hashes do not authorize this candidate. No hosted execution is authorized.

> Execution update: [staging endpoint approval](staging-endpoint-approval.md) supersedes direct connection commands below. Use only its guarded entry points and verify-full TLS (or its explicitly approved, expiring isolated Render exception); the old artifact is preserved but does not authorize the new guard.

## Readiness evidence

The operator reports the live staging preflight passed on PostgreSQL 18.6 with TLS, expected identity/roles/memberships/ACLs, no assertion failures, and final ROLLBACK. This satisfies the reported database prerequisite gate, including the script's empty-relation/absent-vervfy_auth assertions. Raw catalog output was not supplied for independent review. No new connection was made for this packet.

Database is ready for the planned schema migration based on that report, subject to final artifact verification, acceptance of the empty-database recreation recovery plan below, and explicit execution approval. Confirm default ACL output was reviewed (not merely that assertions passed). Keep staging API/workers stopped and Google OAuth disabled. Production is outside this procedure.

## Recovery baseline and scope

Recreation restores an EMPTY application database, not user data. Accept this baseline explicitly before migration. If staging acquires any data that must survive, replace this procedure with a verified backup/restore plan. Record the isolated Render resource ID, database name, owner login, PostgreSQL version, region, network restrictions and secret-store references privately. Do not record password values. Recreation has not been rehearsed on Render by this review.

Prefer creating a separate replacement isolated staging resource, retaining the failed resource for diagnosis. Resource creation/deletion and endpoint changes require separate explicit approval. Have the operator provision PostgreSQL 18 with database `vervfy_oauth_staging` and owner login `vervfy_oauth_staging_user`; if these cannot be preserved, stop and review updated guards. Do not drop schemas with CASCADE or issue DROP DATABASE against an existing endpoint. Do not reuse production resources or credentials. Provider resource management is deliberately an operator step, not an automated destructive command.

Roles are cluster-wide. A replacement cluster requires recreation of custom roles; merely replacing a database on the same cluster may retain them. The SQL below is ONLY for a fresh isolated replacement where all four roles are absent. If roles already exist, stop, audit their existing memberships/ACLs and use the tested preflight; never blindly drop or replace them. The Render-created migration login must have the tested provisioning capability (CREATEROLE), database CREATE and public schema ownership/control; do not invent superuser/BYPASSRLS workarounds.

## Restore roles and baseline grants — prepared only

After separate recovery approval, use the guarded staging shell setup in [staging-alembic-review.md](staging-alembic-review.md), substituting ONLY the independently verified replacement staging hostname/password. Save the SQL block to a reviewed local file and run it with `psql -X -W -v ON_ERROR_STOP=1 -f <reviewed-file.sql>` only after recovery approval; no password belongs in SQL or command arguments. Do not paste it statement-by-statement into an interactive session. With file execution, an assertion/error stops psql before COMMIT and connection closure rolls back the transaction. If using an interactive session for diagnosis, issue ROLLBACK and stop after any error; never continue to COMMIT. Password prompts occur after the committed assertions: a password failure does not undo provisioning and requires repair of that login before proceeding.

```sql
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'vervfy_oauth_staging'
 OR session_user <> 'vervfy_oauth_staging_user'
 OR current_user <> 'vervfy_oauth_staging_user'
 OR current_schema() IS DISTINCT FROM 'public'
 OR current_setting('server_version_num')::int / 10000 <> 18
 OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
 THEN RAISE EXCEPTION 'Wrong staging recovery target'; END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname IN
 ('app_runtime','google_auth_lookup','vervfy_identity_lookup_owner','vervfy_identity_lookup'))
 OR to_regnamespace('vervfy_auth') IS NOT NULL
 OR EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
 AND c.relkind IN ('r','p','v','m','S','f'))
 THEN RAISE EXCEPTION 'Recovery requires fresh isolated cluster/database'; END IF;
END $$;
CREATE ROLE app_runtime LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE google_auth_lookup LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_identity_lookup_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_identity_lookup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE ALL ON DATABASE vervfy_oauth_staging FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE vervfy_oauth_staging TO vervfy_oauth_staging_user;
GRANT CONNECT ON DATABASE vervfy_oauth_staging TO app_runtime, google_auth_lookup;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO vervfy_oauth_staging_user;
GRANT USAGE ON SCHEMA public TO app_runtime;
GRANT vervfy_identity_lookup_owner TO vervfy_oauth_staging_user WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT vervfy_identity_lookup TO google_auth_lookup WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
-- Assert the resulting state BEFORE committing any provisioning changes.
DO $$ BEGIN
 IF current_database() <> 'vervfy_oauth_staging'
 OR session_user <> 'vervfy_oauth_staging_user'
 OR current_user <> 'vervfy_oauth_staging_user'
 OR current_schema() IS DISTINCT FROM 'public'
 OR current_setting('server_version_num')::integer / 10000 <> 18
 OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
 THEN RAISE EXCEPTION 'Wrong staging identity/schema/version/TLS'; END IF;
 IF to_regnamespace('vervfy_auth') IS NOT NULL OR EXISTS (
 SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname NOT IN ('pg_catalog','information_schema')
 AND n.nspname !~ '^pg_' AND c.relkind IN ('r','p','v','m','S','f'))
 THEN RAISE EXCEPTION 'Expected empty staging database without private auth schema'; END IF;
 IF NOT has_database_privilege(current_user,current_database(),'CREATE')
 OR NOT has_schema_privilege(current_user,'public','USAGE')
 OR NOT has_schema_privilege(current_user,'public','CREATE')
 THEN RAISE EXCEPTION 'Missing migration schema/database permissions'; END IF;
 IF (SELECT count(*) FROM pg_roles WHERE rolname IN
 ('vervfy_identity_lookup_owner','vervfy_identity_lookup')
 AND NOT (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit)) <> 2
 THEN RAISE EXCEPTION 'Unsafe or missing capability roles'; END IF;
 IF (SELECT count(*) FROM pg_roles WHERE rolname IN ('app_runtime','google_auth_lookup')
 AND rolcanlogin AND NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit)) <> 2
 THEN RAISE EXCEPTION 'Unsafe or missing application logins'; END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls))
 THEN RAISE EXCEPTION 'Unsafe migration principal'; END IF;
 IF EXISTS (SELECT 1 FROM pg_auth_members WHERE
 member='vervfy_identity_lookup_owner'::regrole OR
 (roleid='vervfy_identity_lookup_owner'::regrole AND member<>current_user::regrole))
 OR NOT pg_has_role(current_user,'vervfy_identity_lookup_owner','SET')
 OR NOT pg_has_role(current_user,'vervfy_identity_lookup_owner','MEMBER')
 OR pg_has_role(current_user,'vervfy_identity_lookup_owner','USAGE')
 THEN RAISE EXCEPTION 'Unsafe owner membership or missing SET capability'; END IF;
 IF (SELECT count(*) FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup'::regrole) <> 1
 OR NOT EXISTS (SELECT 1 FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup'::regrole
       AND member='google_auth_lookup'::regrole
       AND inherit_option AND NOT set_option AND NOT admin_option)
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE (member='google_auth_lookup'::regrole
            AND roleid<>'vervfy_identity_lookup'::regrole)
        OR roleid='google_auth_lookup'::regrole)
 OR EXISTS (SELECT 1 FROM pg_roles r
     WHERE r.oid NOT IN ('vervfy_identity_lookup'::regrole,
                         'google_auth_lookup'::regrole)
       AND NOT r.rolsuper
       AND (pg_has_role(r.oid,'vervfy_identity_lookup','USAGE')
            OR pg_has_role(r.oid,'vervfy_identity_lookup','SET')))
 OR NOT pg_has_role('google_auth_lookup','vervfy_identity_lookup','USAGE')
 OR pg_has_role('google_auth_lookup','vervfy_identity_lookup','SET')
 OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='app_runtime'::regrole)
 OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='vervfy_identity_lookup'::regrole)
 THEN RAISE EXCEPTION 'Unsafe runtime/executor role graph'; END IF;
 IF EXISTS (SELECT 1 FROM pg_roles r WHERE rolname IN ('app_runtime','google_auth_lookup')
 AND (NOT has_database_privilege(r.oid,current_database(),'CONNECT')
 OR has_database_privilege(r.oid,current_database(),'CREATE')
 OR has_database_privilege(r.oid,current_database(),'TEMP')
 OR has_schema_privilege(r.oid,'public','CREATE')))
 OR NOT has_schema_privilege('app_runtime','public','USAGE')
 OR has_schema_privilege('google_auth_lookup','public','USAGE')
 THEN RAISE EXCEPTION 'Unexpected app database/schema permissions'; END IF;
END $$;
DO $$ BEGIN
 IF EXISTS (SELECT FROM pg_database d CROSS JOIN LATERAL
 aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) a
 WHERE d.datname=current_database() AND a.grantee=0)
 OR EXISTS (SELECT FROM pg_namespace n CROSS JOIN LATERAL
 aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a
 WHERE n.nspname='public' AND a.grantee=0)
 THEN RAISE EXCEPTION 'Unexpected PUBLIC database/schema grants'; END IF;
 IF NOT EXISTS (SELECT FROM pg_auth_members
 WHERE roleid='vervfy_identity_lookup_owner'::regrole
 AND member=current_user::regrole AND grantor=current_user::regrole
 AND set_option AND NOT inherit_option AND NOT admin_option)
 THEN RAISE EXCEPTION 'Missing restricted self-granted owner membership'; END IF;
END $$;
COMMIT;
\password app_runtime
\password google_auth_lookup
```

Enter different strong passwords in the hidden prompts; store them only in the staging secret store. No password is assigned to capability roles. Preserve/audit provider-created membership rows; the preflight checks effective owner SET without inheritance. Do not grant lookup capability to app_runtime. Set no broad default privileges.

Repeat the read-only preflight and both application-login TLS/identity checks. Password prompt failure or an unexpected role/default ACL is a stop condition. Restore schema by running the complete approved migration artifact from base to `0027_storage_lifecycle`, keeping 0028 unapplied, then postflight. Migrations restore table/function ownership, policies and object grants: migration login owns tables/version/private schema; lookup-owner owns only the helper function. 0026 handles runtime table and owned-sequence grants. Do not restore a fabricated alembic_version or manually create application tables.

## Freeze and verify the execution artifact

Do not use `git archive HEAD`: 0021–0026 are untracked. The approved checkout must contain the actual reviewed working files, alembic.ini, alembic/env.py, db.py, requirements.lock, and all 28 version files. To prepare an explicit secret-free source bundle locally (no Git changes):

```bash
cd /home/sam/vervfy-latest
python - <<'PY'
import ast, hashlib, json, tarfile
from pathlib import Path
versions = sorted(Path('alembic/versions').glob('*.py'))
def require(condition, message):
    if not condition:
        raise SystemExit(message)

parents = {}
for p in versions:
    require(p.is_file() and not p.is_symlink(), f'Unsafe file: {p}')
    values = {}
    for n in ast.parse(p.read_text(), filename=str(p)).body:
        targets = n.targets if isinstance(n, ast.Assign) else ([n.target] if isinstance(n, ast.AnnAssign) else [])
        names = {x.id for target in targets for x in ast.walk(target) if isinstance(x, ast.Name)}
        relevant = names & {'revision', 'down_revision', 'branch_labels', 'depends_on'}
        if not relevant:
            continue
        require(len(targets) == 1 and isinstance(targets[0], ast.Name), f'Ambiguous assignment: {p}')
        key = targets[0].id
        require(key not in values, f'Duplicate {key}: {p}')
        try:
            values[key] = ast.literal_eval(n.value)
        except (ValueError, TypeError, SyntaxError):
            raise SystemExit(f'Nonliteral {key}: {p}')
    require(set(values) == {'revision','down_revision','branch_labels','depends_on'}, f'Missing metadata: {p}')
    revision, parent = values['revision'], values['down_revision']
    require(isinstance(revision, str) and isinstance(parent, (str, type(None))), f'Invalid revision types: {p}')
    require(values['branch_labels'] is None and values['depends_on'] is None, f'Unexpected branch/dependency: {p}')
    require(revision not in parents, f'Duplicate revision: {revision}')
    parents[revision] = parent
require(len(parents) == 28, 'Expected 28 source migrations; apply only through 0027')
require(set(parents) - set(parents.values()) == {'0028_storage_cleanup_leases'}, 'Unexpected source head')
seen = set(); r = '0028_storage_cleanup_leases'
while r is not None:
    require(r in parents and r not in seen, 'Missing parent or cycle')
    seen.add(r); r = parents[r]
require(seen == set(parents), 'Disconnected revisions')
require(all(len(r) > 5 and r[:4].isdigit() and r[4] == '_' for r in seen), 'Invalid revision names')
require({int(r[:4]) for r in seen} == set(range(1,29)), 'Missing numbered migrations')
files = [Path(x) for x in ('alembic.ini','alembic/env.py','db.py','staging_guard.py','requirements.lock',
         'docs/staging-alembic-preflight.sql','docs/staging-alembic-postflight.sql')] + versions
require(all(p.is_file() and not p.is_symlink() for p in files), 'Missing file or symlink')
contents = {str(p): p.read_bytes() for p in files}
manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
out = Path('/tmp/vervfy-staging-guarded-artifact')
out.mkdir(mode=0o700, exist_ok=False)
(out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
with tarfile.open(out/'source.tar.gz','w:gz') as archive:
    import io
    for name, data in contents.items():
        info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
        archive.addfile(info, io.BytesIO(data))
print('Approval manifest SHA-256:', hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest())
print('Verified 28 source revisions; execution pinned to 0027; bundle:', out)
PY
```

This is source plus a dependency lock, not a self-contained Python environment. Use the tested runner/dependency environment. Verify SHA-256 entries against the actual extracted files or reviewed working files immediately before execution; reject missing/additional version files or changed hashes. Preserve this artifact for recovery. If the output directory already exists, stop and inspect it rather than overwrite the previous approved artifact.

## Preparation and approval: verify the exact execution files

Record the packaging command's manifest SHA-256 in the approval record through a trusted channel. A manifest supplied alongside a changed archive is not an independent trust anchor. The bundle prepared before this correction must be revalidated or rebuilt under separate local preparation; do not overwrite it silently.

Run this from the actual execution checkout (or extracted artifact directory), immediately before execution, with the approved manifest path and digest. It does not import migration code or connect to a database. Keep this directory unchanged afterward; any edit requires verification again. Dependencies must match the reviewed lockfile and tested runner.

```bash
read -r -p 'Approved manifest SHA-256: ' APPROVED_MANIFEST_SHA256
export APPROVED_MANIFEST_SHA256
export MIGRATION_MANIFEST=/tmp/vervfy-staging-guarded-artifact/manifest.json
python - <<'PYVERIFY'
import hashlib, json, os, re
from pathlib import Path

def require(ok, message):
    if not ok:
        raise SystemExit(message)

def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate manifest path')
        result[key] = value
    return result

raw = Path(os.environ['MIGRATION_MANIFEST']).read_bytes()
expected = os.environ['APPROVED_MANIFEST_SHA256']
require(re.fullmatch(r'[0-9a-f]{64}', expected) is not None, 'Invalid approved digest')
require(hashlib.sha256(raw).hexdigest() == expected, 'Unapproved manifest')
manifest = json.loads(raw, object_pairs_hook=unique_pairs)
require(isinstance(manifest, dict), 'Invalid manifest')
fixed = {'alembic.ini','alembic/env.py','db.py','staging_guard.py','requirements.lock',
         'docs/staging-alembic-preflight.sql','docs/staging-alembic-postflight.sql'}
versions = {str(p) for p in Path('alembic/versions').glob('*.py')}
require(len(versions) == 26 and set(manifest) == fixed | versions, 'Missing/extra execution files')
for name, digest in manifest.items():
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts, 'Unsafe manifest path')
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'Symlink in execution path')
    require(path.is_file() and isinstance(digest,str) and re.fullmatch(r'[0-9a-f]{64}',digest), 'Invalid file/digest')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Hash mismatch: {name}')
print('PASS: exact approved execution files, including all 26 migrations')
PYVERIFY
```

**Approval boundary:** preparation and verification do not authorize provisioning, migration, replacement resource creation, or deletion. Obtain explicit approval for the intended staging operation and acceptance of the empty-data recovery baseline. Stop on any verification failure.

## Exact migration and postflight sequence — approval required

Use the exact staging-only shell setup in [staging-alembic-review.md](staging-alembic-review.md), which explicitly sets both database URLs from hidden-password input, TLS, public search_path and timeouts. Do not carry over `default_transaction_read_only=on` from the manual preflight session. After verifying artifact hashes and the independently confirmed staging host:

```bash
psql -X --no-password -v ON_ERROR_STOP=1 -f docs/staging-alembic-preflight.sql
# STOP HERE until explicit migration approval and recovery-baseline acceptance.
.venv/bin/python -m alembic upgrade 0027_storage_lifecycle
.venv/bin/python -m alembic current
psql -X --no-password -v ON_ERROR_STOP=1 -f docs/staging-alembic-postflight.sql
```

## Postflight verification — after approved execution

Required postflight evidence:

1. Exactly one applied revision: `0027_storage_lifecycle` (0028 unapplied); expected table ownership by migration login.
2. ENABLE/FORCE RLS on all eight tenant tables with unchanged tenant predicates; users/shared caches intentionally lack tenant RLS.
3. Runtime CRUD on the eight allowlisted application tables, SELECT/INSERT/UPDATE only on shared caches, SELECT/INSERT/DELETE only on provider_identities. No identity UPDATE/TRUNCATE, Alembic access, private-schema CREATE or lookup EXECUTE. No new broad PUBLIC/default privileges.
4. Lookup function remains STRICT/STABLE/SECURITY DEFINER, owned by vervfy_identity_lookup_owner with pinned search_path; owner receives only identity-column SELECT plus its SELECT policy. Executor/login receive private-schema USAGE/function EXECUTE and no direct table access.
5. Cover-source constraint includes all eight supported values and NULL; cover_url is nullable text, upload cover_data nullable bytea, users.password_hash nullable. Fresh schema has no sequences; any adopted owned sequences grant runtime USAGE only.
6. Repeat actual app/lookup login identity and TLS checks from the review. Empty-database exact lookup returns NULL. Separately approve synthetic rollback-only tenant isolation tests before enabling application traffic/OAuth.

Postflight is largely a catalog report, so exit status alone is not sign-off. On migration failure stop; normal transaction failure rolls back pending DDL, while a disconnect near COMMIT requires inspecting actual revision/schema before retrying. Do not downgrade forward-only migrations or stamp state. Preserve failed resource for diagnosis, then seek separate recovery approval if recreation is needed.
