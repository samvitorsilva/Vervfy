# Staging Alembic review — 2026-11-04

> Release instruction update: apply only `0027_storage_lifecycle`; keep 0028–0031
> unapplied. Current source has 31 revisions through `0031_operator_revocation`;
> this is not approval to apply beyond 0027. Earlier audit results below are historical evidence. Current role,
> metadata and approval requirements are in `staging-db-initialization-runbook.md`;
> namespace setup is in `storage-namespace-initialization.md`. Older approval
> hashes do not authorize this candidate. No hosted execution is authorized.

> Execution update: [staging endpoint approval](staging-endpoint-approval.md) supersedes direct connection commands below. Use only its guarded entry points and verify-full TLS (or its explicitly approved, expiring isolated Render exception); the old artifact is preserved but does not authorize the new guard.

Historical status only: **conditional go for a fresh-database schema migration; live preflight was reported passed; execution remained on HOLD.** These statements describe the earlier 26-revision source and are not current hosted evidence or a current go decision. No hosted database connection, deployment, or production change is authorized by this document.

## Findings

At the time of this historical review, 26 migration files were read and the then-current head was `0026_application_runtime_grants`. That result does not describe the current graph. The current source graph has 31 revisions and head `0031_operator_revocation`; the separately approved staging/production release boundary remains `0027_storage_lifecycle`. Revisions 0028–0031 are deferred and must remain unapplied. An empty staging database must run the complete base-to-0027 prefix, not be stamped past historical migrations.

- 0001–0006 create core tables, profile/session/storage fields and tenant foreign keys/indexes. 0007 enables and forces RLS on tracks, favorites, playlists and playlist_tracks. 0008 adds forced-RLS upload_jobs; 0009–0011 add retry, email and playlist fields.
- 0012 and 0013 require `app_runtime` to exist even though their cache tables are dropped by 0014. 0014 adds the historical cover-source constraint. 0015 adds forced-RLS artist_photos and runtime CRUD. 0016/0017 add shared, non-RLS caches with runtime SELECT/INSERT/UPDATE and storage fields. 0018–0020 add cover timestamps, forced-RLS track_listens and playlist timestamps.
- 0021 makes users.password_hash nullable and creates provider_identities, composite issuer/subject primary key, user index, cascading users FK, ENABLE/FORCE RLS, and a tenant USING/WITH CHECK policy based on transaction-local app.current_user_id.
- 0022 validates both capability roles, owner membership, and the executor-role graph: only `google_auth_lookup` may inherit the executor, with no nested membership path. It creates a NEW `vervfy_auth` schema (existing schema is a blocker), a SELECT-only owner policy, and a STRICT/STABLE SECURITY DEFINER lookup function. It qualifies the identity table, pins search_path to pg_catalog, pg_temp, compares issuer/subject under C collation and restricts Google issuers/subject length. It removes schema/function default grantees, grants executor USAGE/EXECUTE BEFORE ownership transfer, then revokes owner CREATE. The function owner only receives SELECT on issuer, subject, user_id and schema USAGE; it does not own the identity table.
- 0023 conditionally adds nullable tracks.cover_url (text) and upload_jobs.cover_data (bytea). It checks presence, not compatibility of preexisting column types. Fresh staging avoids that ambiguity.
- 0024 resets direct table privileges for app_runtime and grants SELECT/INSERT/DELETE only. It does not eliminate privileges inherited from other roles, PUBLIC, or preexisting column grants. Audit effective privileges, not only this SQL.

### Execution gates

1. Recheck the **committed** role graph, effective permissions, default ACLs, empty public schema and absent vervfy_auth on the actual staging host. The rollback-only provisioning script deliberately removes its changes; do not rerun it now, because it requires the four roles to be absent.
2. Confirm the exact Render staging hostname out of band, staging-only credentials, and a documented recovery baseline (verified backup or explicitly approved recreation of this empty staging database). Keep clients/workers stopped and OAuth disabled. No backup has been verified in this review.
3. Freeze the reviewed artifact. Include the exact execution files and all 31 source migrations in the new hash-bound artifact; execution is still pinned to 0027. Revisions 0028–0031 are integrity inputs only, not approved execution. Preserve existing work and do not silently revert or stage unrelated changes.
4. Explicit approval remains required by the user's request before executing any migration.

### Local fixes prepared; hosted execution remains gated

- 0025_track_cover_sources replaces the historical constraint with all current model values (embedded, upload, user, musicbrainz, audiodb, generated, placeholder, unknown), permits NULL to match the model, and preserves existing data. It refuses downgrade.
- 0026_application_runtime_grants grants public/application-schema USAGE and explicit CRUD on users, tracks, favorites, playlists, playlist_tracks, upload_jobs, track_listens and artist_photos. Shared artist_images/track_cover_cache receive SELECT/INSERT/UPDATE only. It normalizes direct runtime table/column ACLs, grants only USAGE on serial/identity sequences owned by those allowlisted tables, and refuses downgrade. Fresh installs have no such sequences. It adds no default privileges, database CREATE/TEMP, schema CREATE, arbitrary function access, Alembic access, or lookup capabilities. Provider identity grants and all RLS policies remain unchanged.
- Inherited/PUBLIC grants still require preflight review; the migration deliberately does not rewrite other principals' access. Core runtime grants are now migration-owned: do not apply the previous manual grant recipe.
- db.py declares uq_tracks_user_id_id while migrations rely on the existing composite primary key; this is not a fresh-chain FK blocker.

## Role and ownership contract

| Principal | Expected capability |
|---|---|
| vervfy_oauth_staging_user | Existing migration login; owns application tables/version table and new private schema; public USAGE/CREATE; database CONNECT/CREATE; effective SET to lookup owner without inherited owner access. Never used by API. |
| app_runtime | LOGIN, NOINHERIT, no superuser/BYPASSRLS/CREATEDB/CREATEROLE/REPLICATION; CONNECT, public USAGE; no CREATE/TEMP or membership in migration, owner, executor, lookup login. |
| google_auth_lookup | Same restricted login attributes; CONNECT; executor membership INHERIT TRUE, SET FALSE, ADMIN FALSE; no public USAGE or table grants. |
| vervfy_identity_lookup_owner | NOLOGIN NOINHERIT; all privileged attributes false; no memberships of its own; only migration login may be its member. Owns function only. |
| vervfy_identity_lookup | Same restricted capability attributes; only trusted lookup login inherits executor capability. No table access. |

PostgreSQL 18 membership INHERIT/SET flags matter independently of a login's NOINHERIT attribute. Inspect all grantors: creator-generated membership and self-granted membership may coexist. Migration 0022 only checks MEMBER, not effective SET; preflight must check both. Existing Render migration login CREATEROLE is used by provisioning but is not required by the migration chain; do not give it to runtime logins or expand privileges to make migration pass. [PostgreSQL 18 membership documentation](https://www.postgresql.org/docs/18/role-membership.html).

RLS protects eight final tables: tracks, favorites, playlists, playlist_tracks, upload_jobs, artist_photos, track_listens, provider_identities. users and shared caches are intentionally not tenant-RLS tables in this chain. Runtime is a trusted backend principal, never a browser/database client. The lookup SELECT policy allows its dedicated owner all identity rows; the function narrows access to an exact pair. FORCE RLS applies to table owners; superuser/BYPASSRLS bypasses it. [PostgreSQL RLS documentation](https://www.postgresql.org/docs/18/ddl-rowsecurity.html).

## Legacy direct-command example — historical, do not execute

The shell, psql, and direct Alembic commands in this section predate the
current endpoint-approval guard and are retained only as historical reference.
They are not authorized, even if an old approval or artifact is available.
Use only the current instructions in
[`staging-endpoint-approval.md`](staging-endpoint-approval.md). The present
guard still cannot initialize a fresh database; do not substitute these
commands for role bootstrap. The guard has a separate, read-only
`metadata-preflight` action; it validates catalog state but does not create
roles, grant privileges, or initialize a database.

The former procedure used a private interactive Bash session, hidden password
prompts, and an independently checked staging hostname. No commands from that
procedure should be run now.

```bash
cd /home/sam/vervfy-latest
set +x
set -euo pipefail
unset DATABASE_URL MIGRATION_DATABASE_URL GOOGLE_IDENTITY_LOOKUP_DATABASE_URL
unset PGSERVICE PGSERVICEFILE PGOPTIONS PGPASSWORD PGHOSTADDR
read -r -p 'Verified isolated Render staging hostname: ' PGHOST
export PGHOST
export PGPORT=5432 PGDATABASE=vervfy_oauth_staging
export PGUSER=vervfy_oauth_staging_user PGSSLMODE=require PGCONNECT_TIMEOUT=10
read -r -s -p 'Staging migration password: ' PGPASSWORD
printf '\n'
export PGPASSWORD
export PGOPTIONS='-c search_path=public -c lock_timeout=10s -c statement_timeout=300s'
export VERVFY_ENVIRONMENT=staging GOOGLE_OAUTH_ENABLED=0
export MIGRATION_DATABASE_URL="$(.venv/bin/python - <<'PY'
import os
from sqlalchemy import URL
print(URL.create('postgresql+psycopg', username=os.environ['PGUSER'],
    password=os.environ['PGPASSWORD'], host=os.environ['PGHOST'],
    port=int(os.environ['PGPORT']), database=os.environ['PGDATABASE'],
    query={'sslmode': 'require', 'connect_timeout': '10',
           'options': os.environ['PGOPTIONS']}).render_as_string(hide_password=False))
PY
)"
export DATABASE_URL="$MIGRATION_DATABASE_URL"
.venv/bin/python -m alembic heads
.venv/bin/python -m alembic history
psql -X --no-password -v ON_ERROR_STOP=1 -f docs/staging-alembic-preflight.sql
```

`sslmode=require` enforces encryption; use verify-full with the correct provider CA if that is your approved connection standard. Staging does not get db.py's production-only TLS injection. Explicitly set BOTH URLs: alembic/env.py prefers MIGRATION_DATABASE_URL but imports db.py, which requires DATABASE_URL, and otherwise falls back to it. No dotenv file is loaded by this migration path. Alembic uses NullPool and one PostgreSQL transaction around the full run; it does not share the app engine's prepare_threshold setting. Use a direct database endpoint, not a transaction pooler.

Review preflight output against the contract above. Stop on unexpected ACLs, memberships, owners, database settings, nonempty state, or TLS mismatch. Do not run the following merely because the command block exists.

**Legacy example below — do not execute.** The current approved release boundary is `0027_storage_lifecycle`; 0028–0031 remain unapplied. Hosted execution requires the current guard and a fresh approval, neither of which is supplied here.

```bash
.venv/bin/python -m alembic upgrade 0027_storage_lifecycle
.venv/bin/python -m alembic current
psql -X --no-password -v ON_ERROR_STOP=1 -f docs/staging-alembic-postflight.sql
```

Do not use `--sql` as a dry run: several revisions inspect/query the live bind and are not offline-renderable. Do not run migrate.py (it is an unrelated storage/data migration), app startup schema shims, create_all, or alembic stamp.

Runtime grants are applied by 0026. Inspect postflight output: CRUD for the eight application tables, SELECT/INSERT/UPDATE only for shared caches, SELECT/INSERT/DELETE only for provider_identities, and no runtime access to alembic_version or lookup execution. Lookup owner has column SELECT only; lookup executor/login have no direct identity table access. Only USAGE is allowed for owned serial/identity sequences, if any.

Verify actual login identity/TLS again with passwords entered at the psql prompt (no URL arguments):

```bash
PGUSER=app_runtime psql -X -W -v ON_ERROR_STOP=1 -c "SELECT current_database(),session_user,current_user,(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls;"
PGUSER=google_auth_lookup psql -X -W -v ON_ERROR_STOP=1 -c "SELECT current_database(),session_user,current_user,(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls; SELECT vervfy_auth.lookup_provider_identity('https://accounts.google.com','staging-nonexistent-probe') IS NULL AS missing_identity_returns_null;"
unset DATABASE_URL MIGRATION_DATABASE_URL PGPASSWORD PGOPTIONS
```

The second statement is expected to return true on empty staging. After approved hosted migration, separately authorize rollback-only synthetic two-tenant tests: no-context SELECT returns no identity rows, cross-tenant INSERT/DELETE are denied/affect zero rows, own-tenant INSERT/SELECT/DELETE works, UPDATE denied, runtime function execution denied, executor direct table reads denied, exact lookup succeeds and wrong-case subject returns null. Catalog checks alone do not prove application isolation. Keep Google disabled until those tests pass.

## Failure recovery

- Stop on the first error. Keep staging clients stopped and OAuth disabled. Do not deploy, stamp, retry blindly, weaken RLS or grant superuser/BYPASSRLS. Capture only sanitized revision/error/SQLSTATE; do not publish connection exceptions containing URLs.
- Normal PostgreSQL DDL failure in this env.py transaction should roll back all pending revisions from this invocation, including the version table on a fresh database. Provisioned roles/ACLs from earlier committed transactions remain. No migration contains explicit COMMIT, concurrent-index DDL, or autocommit blocks.
- A lost connection near COMMIT leaves the outcome uncertain. Reconnect with the same identity/TLS guard and inspect `to_regclass('public.alembic_version')`, tables, vervfy_auth, and (only if present) SELECT version_num FROM public.alembic_version. Empty base means rollback; 0027 means commit. Unexpected partial state/revision requires investigation, not a stamp or automatic rerun. Do not rerun the empty-database preflight on successful head and interpret its deliberate rejection as migration failure.
- Fix the specific role/ACL/lock/schema cause through separate approval, repeat preflight, then rerun only if the original empty state is confirmed. The lock/statement timeouts above abort instead of waiting indefinitely; investigate before increasing them.
- After successful head, keep schema in place during feature rollback. 0026, 0025, 0024 and 0023 explicitly refuse downgrade; therefore `alembic downgrade 0022` is not a recovery path from head. 0021 also refuses identities/passwordless users. Do not delete user data to force downgrade. Use a reviewed forward repair or explicitly approved staging-only restore/recreation; roles are cluster objects and require their own restore plan.

## Local verification of the fixes

Verified on disposable PostgreSQL 18.6 with a private Unix socket and TCP listening disabled:

- Historical local result only: `test_staging_migrations.py` reported **6 passed** against the then-current 26-revision source and 0026 head. It is not evidence for the current 31-revision graph or a hosted database. Current local checks are reported separately in `reports/staging-configuration-remediation.md`.
- `DATABASE_URL=sqlite:// .venv/bin/python -m unittest discover -s tests -p test_oauth_postgres.py -v`: **17 passed**. Existing identity/lookup security and migration regressions remain green.
- `alembic heads`: sole head `0026_application_runtime_grants`. Python compilation and `git diff --check` passed.

The sandbox initially prevented local PostgreSQL startup; tests succeeded outside it using only disposable local clusters. One new test initially used an administrator session to assert SET ROLE denial; it was corrected to authenticate as the restricted lookup login. Alembic emits an existing nonfatal path_separator deprecation warning. No hosted checks were run, and no files were committed or staged. Migrations 0021–0026 remain present but untracked and must be included in the eventual reviewed release artifact.

## Reported live preflight and recovery packet

The operator reports PostgreSQL 18.6 staging preflight passed with TLS, expected identities/roles/memberships/ACLs, no assertion failures and final ROLLBACK. Raw catalog output was not supplied for independent review. See [the recreation and execution packet](staging-recreation-recovery.md) for the empty-database recovery baseline, guarded role provisioning, artifact inclusion checks and postflight acceptance criteria. This report does not authorize migration or recreation.
