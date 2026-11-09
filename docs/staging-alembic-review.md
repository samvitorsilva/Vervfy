# Historical staging Alembic review — 2026-11-04 (26-revision checkout)

> **Superseded for the current staging candidate.** This review describes the
> older 26-file chain ending at `0026_application_runtime_grants`. The
> development artifact for the next staging preflight contains 28 migrations,
> targets `0027_storage_lifecycle`, and retains `0028_storage_cleanup_leases`
> as provenance only. Do not use the commands, approval requirements, or
> inventory checks below for that artifact; use
> [the current staging endpoint procedure](staging-endpoint-approval.md).
> The owner adopted solo-maintainer governance on 2026-11-07. It replaces
> internal independent-approver-count requirements for non-production
> operations, but does not authorize any operation or waive technical controls.

Current status: **NO-GO for hosted migrations; first read-only preflight not
yet authorized.** The endpoint identity is operator-reported; no live TLS
handshake or current database-role verification has been performed. The prior
26-revision analysis below is historical evidence only. No hosted operation
is authorized by this document.

**Readiness update — 2026-11-07:** Render Support confirmed external PostgreSQL
supports `sslmode=verify-full`, the endpoint uses Let's Encrypt certificates,
and the standard system CA store is sufficient; no Render-specific bundle or
leaf/intermediate pinning is needed. This closes the provider-support TLS
uncertainty. The release owner now reports independently verifying
`dpg-dbl7q66tlv9c73b883jg-a.oregon-postgres.render.com` against the dashboard
for resource `dpg-dbl7q66tlv9c73b883jg-a`; no live hostname/TLS handshake was
performed. The current guard requires the approved system CA file and SHA-256
digest for `verify-full`. Hosted migrations remain **NO-GO** pending role and
authorization evidence, artifact approval, and recovery-baseline acceptance.

The operator-reported dashboard identity is: resource
`dpg-dbl7q66tlv9c73b883jg-a`, external hostname
`dpg-dbl7q66tlv9c73b883jg-a.oregon-postgres.render.com`, PostgreSQL 18,
database `vervfy_oauth_staging`, port 5432, default username
`vervfy_oauth_staging_user`, status Available. The internal hostname equals
the resource ID and is not the external TLS hostname. Role/membership/ACL
authorization evidence remains outstanding.

## Findings

The historical 26-file checkout review found a base → 0001 → … → 0026 chain
ending at **0026_application_runtime_grants**. That is not the authoritative
inventory for the current Render candidate; its matching development artifact
and 35-entry execution manifest contain 28 files through 0028. For the
candidate preflight, 0027 is the migration target and 0028 remains unapplied.

- 0001–0006 create core tables, profile/session/storage fields and tenant foreign keys/indexes. 0007 enables and forces RLS on tracks, favorites, playlists and playlist_tracks. 0008 adds forced-RLS upload_jobs; 0009–0011 add retry, email and playlist fields.
- 0012 and 0013 require `app_runtime` to exist even though their cache tables are dropped by 0014. 0014 adds the historical cover-source constraint. 0015 adds forced-RLS artist_photos and runtime CRUD. 0016/0017 add shared, non-RLS caches with runtime SELECT/INSERT/UPDATE and storage fields. 0018–0020 add cover timestamps, forced-RLS track_listens and playlist timestamps.
- 0021 makes users.password_hash nullable and creates provider_identities, composite issuer/subject primary key, user index, cascading users FK, ENABLE/FORCE RLS, and a tenant USING/WITH CHECK policy based on transaction-local app.current_user_id.
- 0022 validates both capability roles, owner membership, and the executor-role graph: only `google_auth_lookup` may inherit the executor, with no nested membership path. It creates a NEW `vervfy_auth` schema (existing schema is a blocker), a SELECT-only owner policy, and a STRICT/STABLE SECURITY DEFINER lookup function. It qualifies the identity table, pins search_path to pg_catalog, pg_temp, compares issuer/subject under C collation and restricts Google issuers/subject length. It removes schema/function default grantees, grants executor USAGE/EXECUTE BEFORE ownership transfer, then revokes owner CREATE. The function owner only receives SELECT on issuer, subject, user_id and schema USAGE; it does not own the identity table.
- 0023 conditionally adds nullable tracks.cover_url (text) and upload_jobs.cover_data (bytea). It checks presence, not compatibility of preexisting column types. Fresh staging avoids that ambiguity.
- 0024 resets direct table privileges for app_runtime and grants SELECT/INSERT/DELETE only. It does not eliminate privileges inherited from other roles, PUBLIC, or preexisting column grants. Audit effective privileges, not only this SQL.

### Historical execution gates — 26-revision review only

1. Recheck the **committed** role graph, effective permissions, default ACLs, empty public schema and absent vervfy_auth on the actual staging host. The rollback-only provisioning script deliberately removes its changes; do not rerun it now, because it requires the four roles to be absent.
2. Bind the operator-reported external hostname to the resource ID in the approval record; confirm staging-only credentials and a documented recovery baseline (verified backup or explicitly approved recreation of this empty staging database). Keep clients/workers stopped and OAuth disabled. No backup has been verified in this review.
3. Freeze the reviewed artifact. The worktree has many existing changes and 0021–0026 are untracked. A clean checkout/deployed revision may not contain these migrations. Review/include the complete files and lockfile; do not silently revert or stage unrelated work.
4. The owner must explicitly authorize each hosted operation under the adopted
   solo-maintainer policy. This historic review does not supply an operation
   authorization.

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

## Current controlled execution

Use only the operation-scoped procedure in
[staging-endpoint-approval.md](staging-endpoint-approval.md) and its matching
28-file development artifact. Do not use the historical `sslmode=require`
setup, direct psql/Alembic commands, or migration commands in this review.
The first authorized operation must be `preflight`; it is read-only and does
not authorize a migration. The local `check` has not passed because no
per-operation approval record or staging URLs have been provided.

Runtime grants are applied by 0026. Inspect postflight output: CRUD for the eight application tables, SELECT/INSERT/UPDATE only for shared caches, SELECT/INSERT/DELETE only for provider_identities, and no runtime access to alembic_version or lookup execution. Lookup owner has column SELECT only; lookup executor/login have no direct identity table access. Only USAGE is allowed for owned serial/identity sequences, if any.

Verify actual login identity/TLS again with passwords entered at the psql prompt (no URL arguments):

```bash
PGUSER=app_runtime psql -X -W -v ON_ERROR_STOP=1 -c "SELECT current_database(),session_user,current_user,(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls;"
PGUSER=google_auth_lookup psql -X -W -v ON_ERROR_STOP=1 -c "SELECT current_database(),session_user,current_user,(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls; SELECT vervfy_auth.lookup_provider_identity('https://accounts.google.com','staging-nonexistent-probe') IS NULL AS missing_identity_returns_null;"
unset DATABASE_URL MIGRATION_DATABASE_URL PGPASSWORD PGOPTIONS
```

The second statement is expected to return true on empty staging. After approved hosted migration, separately authorize rollback-only synthetic two-tenant tests: no-context SELECT returns no identity rows, cross-tenant INSERT/DELETE are denied/affect zero rows, own-tenant INSERT/SELECT/DELETE works, UPDATE denied, runtime function execution denied, executor direct table reads denied, exact lookup succeeds and wrong-case subject returns null. Catalog checks alone do not prove application isolation. Keep Google disabled until those tests pass.

## Historical failure recovery notes — 26-revision candidate only

- Stop on the first error. Keep staging clients stopped and OAuth disabled. Do not deploy, stamp, retry blindly, weaken RLS or grant superuser/BYPASSRLS. Capture only sanitized revision/error/SQLSTATE; do not publish connection exceptions containing URLs.
- Normal PostgreSQL DDL failure in this env.py transaction should roll back all pending revisions from this invocation, including the version table on a fresh database. Provisioned roles/ACLs from earlier committed transactions remain. No migration contains explicit COMMIT, concurrent-index DDL, or autocommit blocks.
- A lost connection near COMMIT leaves the outcome uncertain. Reconnect with the same identity/TLS guard and inspect `to_regclass('public.alembic_version')`, tables, vervfy_auth, and (only if present) SELECT version_num FROM public.alembic_version. Empty base means rollback; 0026 means commit. Unexpected partial state/revision requires investigation, not a stamp or automatic rerun. Do not rerun the empty-database preflight on successful head and interpret its deliberate rejection as migration failure.
- Fix the specific role/ACL/lock/schema cause through separate approval, repeat preflight, then rerun only if the original empty state is confirmed. The lock/statement timeouts above abort instead of waiting indefinitely; investigate before increasing them.
- After successful head, keep schema in place during feature rollback. 0026, 0025, 0024 and 0023 explicitly refuse downgrade; therefore `alembic downgrade 0022` is not a recovery path from head. 0021 also refuses identities/passwordless users. Do not delete user data to force downgrade. Use a reviewed forward repair or explicitly approved staging-only restore/recreation; roles are cluster objects and require their own restore plan.

## Local verification of the fixes

Verified on disposable PostgreSQL 18.6 with a private Unix socket and TCP listening disabled:

- `DATABASE_URL=sqlite:// .venv/bin/python -m unittest discover -s tests -p test_staging_migrations.py -v`: **6 passed**. Covers the complete 26-revision chain including 0021–0024, upgrade with existing historical cover rows, generated/current values, invalid-value rejection, SQLite batch compatibility, forward-only guards, exact table grants, owned-sequence USAGE without setval/unrelated-sequence access, forced tenant RLS, and restricted lookup behavior.
- `DATABASE_URL=sqlite:// .venv/bin/python -m unittest discover -s tests -p test_oauth_postgres.py -v`: **17 passed**. Existing identity/lookup security and migration regressions remain green.
- `alembic heads`: sole head `0026_application_runtime_grants`. Python compilation and `git diff --check` passed.

The sandbox initially prevented local PostgreSQL startup; tests succeeded outside it using only disposable local clusters. One new test initially used an administrator session to assert SET ROLE denial; it was corrected to authenticate as the restricted lookup login. Alembic emits an existing nonfatal path_separator deprecation warning. No hosted checks were run, and no files were committed or staged. Migrations 0021–0026 remain present but untracked and must be included in the eventual reviewed release artifact.

## Current preflight and recovery status

No read-only preflight has been run with the current 28-file development
artifact, and no catalog output is available to establish hosted role or ACL
state. The previously documented report was not independently evidenced and
must not be treated as a current pass. The
[recreation and execution packet](staging-recreation-recovery.md) is historical
for the 26-file candidate; do not execute its SQL or migration commands.
