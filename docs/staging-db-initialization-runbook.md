# Render staging PostgreSQL initialization — proposal only

**Status: NOT EXECUTED.** This runbook prepares local review material only. No
Render, Supabase, hosted database, real account, or production credential was
accessed. No role SQL, migration, or hosted inspection was run. Physical object
deletion and Google OAuth remain disabled.

## Release blockers and identity conflicts

- The reported Render resource name `vervfy-oauth-staging-db` is not necessarily
  its PostgreSQL database name. Existing staging approval material is hard-coded
  to `vervfy_oauth_staging`; verify the actual database name and immutable Render
  resource ID in the dashboard before any connection. Never infer identity from
  a resource-name suffix.
- The database was previously described as unused, while
  [`staging-recreation-recovery.md`](staging-recreation-recovery.md) records a
  historical, operator-reported successful live preflight. Neither statement
  has been independently verified here. Treat staging occupancy and migration
  state as **UNKNOWN** until separately approved metadata-only inspection.
- The current source graph contains 31 linear revisions and has head
  `0031_operator_revocation`. The release guard validates all 31 migration
  file hashes but pins execution to `0027_storage_lifecycle`. Revisions
  0028–0031 are present in the source artifact but remain deferred and must
  not be applied. Older 26- or 28-revision approvals do not authorize this
  source artifact.
- The new SQL files beside this runbook are not yet in the guard's reviewed
  manifest. The existing approval artifact/manifest does not authorize them or
  the current migration chain. No hosted preflight, bootstrap, or migration
  command in this proposal is executable until a separately reviewed runner
  and artifact bind the target and file hashes.

**Stop now** if resource identity, isolation, database name, TLS, role
provisioning authority, current schema state, or an approval digest is
uncertain. Do not repair uncertainty by stamping, dropping objects, granting
SUPERUSER/BYPASSRLS, weakening guards, or running raw psql/Alembic.

## Migration dependency and order

The chain is linear; a genuinely empty database starts at base and must apply
each predecessor in order. Never stamp past a migration or assume a resource is
empty based on its name or prior report.

| Revisions | Purpose and dependency |
|---|---|
| 0001–0006 | Core PostgreSQL persistence, profile photo, track-size and session-version fields, storage path, and tenant integrity. |
| 0007 | Enables and forces tenant RLS on core tenant tables. |
| 0008–0011 | Durable upload jobs/retries, verified/pending email state, and playlist position. |
| 0012–0014 | Artist image/catalog caches and historical cover-source transition. The chain still requires these revisions even though 0014 removes earlier cache tables. |
| 0015–0017 | Artist photos, image-cache/storage metadata, and track cover support. |
| 0018–0020 | Cover lookup retry time, track listens, and playlist last-played state. |
| 0021 `provider_identities` | Makes password hashes nullable and adds provider identity storage, cascading user ownership, and forced tenant RLS. First Google identity schema. |
| 0022 `provider_identity_lookup` | Requires the restricted identity owner/executor roles and exact membership graph; creates the private SECURITY DEFINER lookup routine. No existing `vervfy_auth` schema is allowed. |
| 0023 `missing_media_columns` | Adds compatibility columns for track covers and queued artwork. |
| 0024 `provider_identity_runtime_access` | Grants the API role its narrow provider-identity operations. |
| 0025 `track_cover_sources` | Aligns the existing cover-source constraint to current application values. |
| 0026 `application_runtime_grants` | Normalizes direct application table/column grants and owned-sequence usage. |
| 0027 `storage_lifecycle` | Required by current API startup: forced-RLS lifecycle tables, immutable namespace/reference guards, role checks, and hard-disabled physical cleanup. |
| 0028 `storage_cleanup_leases` | Adds leased cleanup-claim/retry routines. Not needed for Google auth; deferred and must not be applied for this staging test. |
| 0029 `storage_cleanup_retry_limits` | Adds cleanup retry limits. Deferred; not needed for Google auth and must not be applied. |
| 0030 `operator_foundation` | Adds operator foundation objects. Deferred; not needed for Google auth and must not be applied. |
| 0031 `operator_revocation` | Adds operator revocation objects and bootstrap guards. Deferred; not needed for Google auth and must not be applied. |

**Google feature schema minimum:** 0021–0026. **Minimum usable current app
startup:** the full base-to-0027 chain, because `server._require_migrated_schema`
requires the 0027 reference triggers. Do not deploy the API against a schema
stopped at 0026. Registration, login, and account linking need the 0021/0022
identity schema and lookup capability plus the 0023–0026 application
compatibility/grant revisions; session-version support begins at 0004 and is
included in the full base chain. Do not apply 0028.

No migration issues `CREATE EXTENSION`. `gen_random_uuid()` is built into
PostgreSQL 18; no extension privilege is required by this chain. PostgreSQL 18
supports the per-membership `INHERIT`, `SET`, and `ADMIN` options used by the
capability graph. Hosted compatibility is still unverified.

## RLS, ownership, and privileged-function inventory

- Tenant RLS covers `tracks`, `favorites`, `playlists`, `playlist_tracks`,
  `upload_jobs`, `artist_photos`, `track_listens`, and (from 0021)
  `provider_identities`. Each tenant policy relies on the transaction-local
  `app.current_user_id`; forced RLS prevents table-owner bypass. `users` and
  shared cache tables are not tenant-RLS tables in this chain and must not be
  described as such.
- Migration 0022 creates
  `vervfy_auth.lookup_provider_identity(text,text)` as SECURITY DEFINER,
  owned by `vervfy_identity_lookup_owner`, with a pinned
  `pg_catalog, pg_temp` search path and no PUBLIC EXECUTE. The owner receives
  only narrow SELECT on identity columns; only the lookup executor/login can
  invoke the function.
- Migration 0027 creates `vervfy_storage.namespaces`, `objects`, and
  `cleanup_jobs` with ENABLE/FORCE RLS. The migration login owns created
  tables; `vervfy_storage_lifecycle_owner` owns the privileged routines.
  Functions are `guard_namespace`, `validate_namespace`, `_has_references`,
  `_queue`, `reserve_object`, `advance_upload`, `request_cleanup`,
  `guard_references`, `retire_candidate`, and `claim_cleanup`. Their
  SECURITY DEFINER search paths are pinned and execution is restricted to the
  required migration/runtime capability roles. The `storage_owner` policy is
  capability-scoped; the runtime's object visibility is tenant-scoped. The
  three reference triggers protect `tracks`, `artist_photos`, and `upload_jobs`.
- 0027's `claim_cleanup` is deliberately a raising stub. 0028 adds
  `claim_next_cleanup`, `complete_cleanup`, and `retry_cleanup` routines under
  the restricted cleanup executor. Those are not required for OAuth and must
  not be installed or invoked in this plan.

## Role and privilege compatibility matrix

Role names below are the current migration contracts. The staging Blueprint
proposes Render's initial database login as `vervfy_staging_bootstrap`; this
provider-created identity must never be given to the API. Its ability to create
the required role graph and transfer ownership is unverified. It is not the
migration or runtime credential, and no bootstrap action is authorized here.

| Principal | Provisioning and intended privileges | Render compatibility |
|---|---|---|
| Provider bootstrap administrator | Must be able to create the named roles, grant memberships with PG18 options, revoke/grant database ACLs, and grant public-schema ACLs. Use only for the separately approved bootstrap transaction. | **UNKNOWN.** Render documentation reviewed establishes managed PostgreSQL availability, not these exact role/ACL/ownership powers. Verify through approved metadata inspection; stop if insufficient. |
| `vervfy_oauth_staging_user` | Dedicated LOGIN, NOINHERIT; no superuser, BYPASSRLS, CREATEDB, CREATEROLE, or replication. Database CONNECT/CREATE, `public` USAGE/CREATE; only `SET` (not inherited/admin) membership in `vervfy_identity_lookup_owner` and `vervfy_storage_lifecycle_owner`. Owns objects it creates during migrations. Secret is migration-only, never API. | Required operations are supported by local PostgreSQL tests; actual managed-provider grants/ownership behavior is **UNKNOWN**. No CREATEROLE is needed by this principal under the proposed separate bootstrap. |
| `app_runtime` | Dedicated LOGIN, NOINHERIT, no elevated attributes. Database CONNECT; `public` USAGE; migrations grant the allowlisted table/sequence privileges. No database CREATE/TEMP, schema CREATE, lookup capability, lifecycle capability, or migration access. | Local migration contract known; hosted effective grants **UNKNOWN** until reviewed. |
| `google_auth_lookup` | Dedicated LOGIN, NOINHERIT, no elevated attributes. Database CONNECT; no `public` usage or table grants. Inherits only `vervfy_identity_lookup`, with SET/ADMIN false. | Local migration contract known; hosted effective grants **UNKNOWN**. Use only for the backend's restricted lookup connection. |
| `vervfy_identity_lookup_owner` | NOLOGIN, NOINHERIT, no elevated attributes or unrelated object/default-ACL privileges. Only migration role may SET it; function owner receives narrow identity-column SELECT and private schema usage. | Role provisioning and `ALTER FUNCTION ... OWNER TO` compatibility **UNKNOWN** on Render. |
| `vervfy_identity_lookup` | NOLOGIN, NOINHERIT, no elevated attributes or unrelated privileges. Inherited only by `google_auth_lookup`; no SET/ADMIN or nested members. | **UNKNOWN** hosted. Migration 0022 fails closed on deviations. |
| `vervfy_storage_lifecycle_owner` | NOLOGIN, NOINHERIT, no elevated attributes or unrelated privileges. Only migration role may SET it; owns lifecycle routines, not business tables. | **UNKNOWN** hosted. Migration 0027 fails closed on deviations. |
| `vervfy_storage_cleanup` | NOLOGIN, NOINHERIT and no unrelated privileges. Inherited only by the cleanup-worker login, with SET/ADMIN false. | **UNKNOWN** hosted. |
| `storage_cleanup_worker` | Migration 0027 expects a restricted LOGIN. The proposal grants no database CONNECT, sets no password, and deploys no worker. Do not activate it for OAuth tests. | **UNKNOWN** hosted; capability membership must still pass 0027's strict audit. |

The proposed bootstrap SQL revokes database `PUBLIC` privileges (including
CONNECT/TEMP) and `public` schema `PUBLIC` privileges, then grants only the
listed database/schema access. This is intentionally limited to a separately
verified fresh disposable database. Do not apply it to a populated or
unverified database. The script creates roles without passwords; set only the
three required login passwords later through hidden prompts/secret storage.
Never set or distribute a cleanup-worker password for this test.

Migrations 0022 and 0027 audit effective memberships, owners, executable
routines, object grants and default ACLs. Do not pre-grant object privileges or
default privileges to capability roles. Do not “fix” a failed preflight with
SUPERUSER, BYPASSRLS, broader memberships, schema-wide grants, or a relaxed
migration check.

## Ordered initialization and migration procedure

**No hosted operation is authorized by this runbook.** The guard now provides
a hash-bound, read-only `metadata-preflight` action for the bootstrap,
migration, and post-migration phases. It does not create roles, grant
privileges, or run migrations. Each hosted phase still requires a fresh
artifact/endpoint approval. Role bootstrap remains a separate DBA operation;
do not use raw psql or unguarded Alembic without explicit approval.

1. **Freeze the local release candidate.** Review the secret-free artifact and
   manifest, including all 31 source migration files. The approved applied set
   ends at `0027_storage_lifecycle`; source head `0031_operator_revocation`
   does not change that boundary. The guard's fixed target is
   `0027_storage_lifecycle`; it rejects arbitrary revision arguments and
   missing or extra migration files. Revisions 0028–0031 are included for
   source integrity only, not for execution. Existing approvals must be renewed
   against the new hashes before hosted execution.
2. **Confirm deployment identity and recovery.** In Render dashboard inventory,
   verify the staging resource ID, region, database name, version, endpoint,
   network access, and independent credentials. Confirm no production resource
   or secret is referenced by the staging API, frontend, or workers. Determine
   whether the current staging database has backup/PITR/export coverage; do not
   assume a plan includes it. If no backup exists, use a separately approved
   empty-database recreation baseline only after metadata confirms there is no
   data to preserve. Never use real user data.
3. **Read-only bootstrap preflight.** After explicit approval, run
   `staging_guard.py metadata-preflight` with phase `bootstrap` and the
   `vervfy_staging_bootstrap` URL injected from the approved staging secret
   store. The guard validates the artifact, approval digest, endpoint, role,
   TLS, and exact database before connecting. It verifies PostgreSQL 18,
   database ownership, non-superuser `CREATEROLE` authority without
   `CREATEDB`/replication or role memberships, database/schema privileges,
   the expected public-schema owner (`vervfy_staging_bootstrap` or
   `pg_database_owner`), and absence of the expected application roles and
   relations.
   The runner uses a read-only transaction and emits catalog metadata only:
   no account rows, object paths, function bodies, passwords, connection
   strings, or raw ACLs. Require TLS and an all-pass report; otherwise stop.
4. **Bootstrap roles — DBA operation, not a guard action.** After a passing
   bootstrap report, separate initialization approval, and confirmation that
   the database is fresh, execute
   [`staging-db-bootstrap-proposal.sql`](staging-db-bootstrap-proposal.sql)
   only through a separately approved DBA path as the non-superuser database
   owner/role administrator. It creates the exact eight restricted roles,
   revokes PUBLIC database/schema privileges, grants only the role-specific
   CONNECT/CREATE and schema rights, and installs the four exact capability
   memberships. It contains no password literals, user-data reads, or DROP.
   Do not execute it through the metadata action. A role-exists or SQL error is
   a stop; do not alter/reuse roles. Set passwords for the migration, runtime,
   and lookup logins separately with hidden prompts and store only in staging
   secrets. Leave the cleanup worker login password unset.
5. **Read-only migration preflight.** Repeat the guarded action using phase
   `migration` and `vervfy_oauth_staging_user`. It checks the complete role
   attribute/membership graph, exact database and schema privileges, a fresh
   schema, and revoked PUBLIC privileges. It must pass before any migration
   approval. Do not grant the identity lookup owner `public` schema access
   during bootstrap: migration 0022 grants that owner `USAGE` narrowly. The
   post-migration check must confirm the owner has `public.USAGE` but no
   `CREATE`, while `google_auth_lookup` has no `public.USAGE` and receives only
   the private `vervfy_auth` executor capability. This is the identity-lookup
   schema boundary; do not broaden it to the login role.
6. **Migrate only through the pinned guard, after migration approval.**
   Rerun the hash/identity check, then use the approved `staging_guard.py upgrade`
   operation. Its fixed Alembic target is `0027_storage_lifecycle`; it rejects
   caller-supplied revision arguments. Apply the complete linear chain through
   0027. Keep 0028–0031 unapplied, API/worker stopped, and
   `GOOGLE_OAUTH_ENABLED=0`.
   Do not use `stamp` or an unguarded migration command.
7. **Post-migration metadata gate.** After approved migration, run the guarded
   `metadata-preflight` action with phase `post-migration` and the migration
   login. It checks revision `0027_storage_lifecycle`, expected tenant/storage
   relations and forced RLS policies, SECURITY DEFINER ownership/search paths
   and exact grants, extensions/capabilities, and the identity lookup schema
   privileges. Then run the existing hash-bound `postflight` action to verify
   the reference guards and disabled 0027 cleanup stub. Keep services stopped
   on any mismatch. These metadata checks do not replace role/RLS integration
   tests or deployment isolation review.
8. **Start only the staging API after explicit approval.** Keep OAuth disabled
   until staging authentication and session test gates pass. `server.startup()`
   enforces the migrated schema only through FastAPI's ASGI lifespan. The
   current Blueprint explicitly sets `--lifespan on`; verify that exact
   command in the Render preview and reject any override using `--lifespan
   off` or another server that skips lifespan. The application cannot prevent
   an operator from changing the launch command, so deployment review must
   enforce this setting.

## Cleanup and physical-deletion boundary

Migration 0027 has a database constraint that always keeps
`physical_cleanup_enabled` false and its `claim_cleanup(uuid)` routine raises
instead of claiming an object. Migration 0028 adds lease/claim/retry functions
but is not needed for OAuth and must not be applied. The cleanup worker is
fail-closed and must not be deployed. Do not configure production or staging
storage service keys, namespace bindings, object-store deletion credentials,
or a cleanup schedule for this test. Never test physical deletion.

The API's startup guard verifies that the three 0027 reference triggers exist
and are enabled; it does not independently prove deployment isolation,
object-store isolation, or that a nonstandard launcher enables ASGI lifespan.
Those are separate release gates.

## Recovery and stop conditions

- On the first error, stop; keep API/workers stopped and OAuth disabled. Capture
  only sanitized operation, revision and SQLSTATE. Never include a connection
  URL, secret, account data, object path or raw exception that may embed one.
- Bootstrap DDL is transactional. If connection outcome around COMMIT is
  ambiguous, do not replay it; obtain new approval for metadata-only state
  inspection. If any role already exists, preserve it and audit before deciding
  whether a separate repair is approved.
- Alembic's PostgreSQL environment runs a transactional chain. A lost
  connection near commit is still ambiguous: use the guarded metadata path to
  establish the exact revision. If revision is 0027, do not replay. If no
  migration exists and the DB is otherwise still verified empty, a retry needs
  a fresh execution approval. Any partial/unexpected state means stop; never
  stamp or downgrade to force progress.
- Do not `DROP`, `CASCADE`, restore over, or recreate the current resource
  automatically. Prefer a separately approved new isolated replacement. A
  restore/recreation must have a verified target identity and an explicit
  backup/recovery decision; hosted backup availability is currently unknown.
- If role creation, membership options, grants, ownership transfer, RLS,
  default-ACL cleanup, or guard checks cannot be satisfied with provider
  privileges, abandon this staging DB path and report the limitation. Never
  grant SUPERUSER/BYPASSRLS or weaken policies/guards.

## Guarded metadata command and DBA boundary

The metadata runner is read-only and available only through the staging guard.
Inject a single phase-appropriate database URL through the approved secret
store; never place it in command arguments, a shell command, or history. Keep
`VERVFY_ENVIRONMENT=staging`, the approved JSON/digest, and the expected phase
set. The guard rejects ambient PostgreSQL/TLS overrides and validates the
endpoint, role, artifact hashes, and TLS approval before opening a connection.
It emits sanitized JSON and suppresses raw driver diagnostics.

```text
# After separate hosted read-only approval; use the approved bootstrap login.
STAGING_METADATA_PHASE=bootstrap
python staging_guard.py metadata-preflight

# After approved role bootstrap; use the migration login before migration.
STAGING_METADATA_PHASE=migration
python staging_guard.py metadata-preflight

# After the separately approved migration pinned to 0027.
STAGING_METADATA_PHASE=post-migration
python staging_guard.py metadata-preflight
```

`metadata-preflight` never creates roles, grants permissions, or changes the
database. There is intentionally no `bootstrap-roles` action. The DBA must
review and separately authorize the role SQL; the migration action remains
hash-bound and pinned to `0027_storage_lifecycle`. Never use an arbitrary
revision, `stamp`, or unguarded migration command.

## Approval gates

| Gate | Separate approval required | This proposal does not authorize |
|---|---|---|
| 1. Hosted read-only inventory/preflight | Confirm exact Render resource ID, database name, host/TLS method, isolated credentials, and exact metadata-only query/artifact. | Any connection or user-data query now. |
| 2. Database role/bootstrap initialization | Confirm empty disposable state, provider bootstrap authority, exact SQL/hash, recovery baseline, and allowed ACL changes. | Executing role DDL, changing ACLs, or setting credentials now. |
| 3. Hosted migration | Approve exact artifact/manifest, reviewed guard pinned to 0027, exact resource identity, backup/recreation baseline, and migration window. | Running any hosted migration without fresh artifact approval; applying 0028. |
| 4. API/OAuth enablement | Separate approval after postflight and isolated app-secret review. | Deploying/starting services, enabling Google OAuth, or enabling cleanup. |

## Validation performed for this proposal

Validation is local-only and must not be interpreted as hosted compatibility.
The metadata preflight ran successfully against a fresh disposable local
PostgreSQL 18.6 database and returned no application relations, schemas, or
migration table. As expected on that local Unix-socket connection, TLS was
false; this says nothing about Render TLS. PostgreSQL's fresh local database
reported PUBLIC CONNECT and TEMP, confirming why the bootstrap proposal
explicitly revokes those defaults before granting named connections.

The postflight ran successfully against a disposable synthetic catalog fixture
(empty metadata-only tables, no account/object rows, and three synthetic
reference triggers). It reported revision 0027, all 11 expected RLS flags
enabled/forced, three enabled reference guards, the 0027 disabled-cleanup stub
present, and the 0028 claim function absent. This validates query behavior,
not the migrations or hosted catalog.

All three SQL files also passed an offline PostgreSQL SQL grammar parse after
substituting the documented psql identifier variable and removing psql control
lines. The bootstrap proposal was **not executed**, including on the local
fixture; no migrations were run. No hosted query or connection was attempted.
