# Final Staging Preflight & Render Validation

## 1. Executive summary

**Local preflight implementation: ready for separately authorized use.
Hosted staging: NO-GO.** A guarded, read-only PostgreSQL metadata action is
implemented and its focused tests pass against synthetic and disposable local
PostgreSQL state. The Render proposal also passes local YAML parsing and
structural checks. Neither the Render service schema nor an actual Blueprint
preview was validated, and no hosted service, database, Redis instance, or
Google OAuth client was accessed.

The source migration graph has 31 linear revisions, head
`0031_operator_revocation`. The release target remains
`0027_storage_lifecycle` (parent `0026_application_runtime_grants`); revisions
0028–0031 are deferred and must remain unapplied. No migration, deployment,
role bootstrap, OAuth enablement, or production access occurred.

The next step is **not** to run hosted commands immediately. First obtain
approval for the exact isolated Render resources, review the hosted Blueprint
change preview, verify the bootstrap login's actual PostgreSQL capabilities,
and approve the new hash-bound artifact and database procedure. The current
proposal uses Free services: the PostgreSQL plan has no managed backups and
expires after 30 days, and the Valkey plan has restart-volatile storage.

## 2. Exact files changed

- `staging_metadata_preflight.py` — read-only metadata collection and
  fail-closed phase evaluation.
- `docs/staging-db-metadata-preflight.sql` — fixed catalog-only query.
- `staging_guard.py` — approval-bound `metadata-preflight` action and manifest
  coverage.
- `tests/test_staging_metadata_preflight.py` — sanitized error, identity,
  permissions, version, and policy-evaluation tests.
- `tests/test_staging_guard.py` — guarded action and approval regressions.
- `tests/test_staging_migrations.py` — disposable PostgreSQL metadata and
  restricted-role checks.
- `render.staging.proposal.yaml` — quoted Render `"off"` values for valid YAML
  string parsing.
- `tests/test_staging_render_config.py` — local Blueprint structural checks.
- `docs/staging-db-initialization-runbook.md` — current metadata and role
  bootstrap sequence.
- `docs/staging-endpoint-approval.md` — updated artifact inventory and
  authorization requirements.
- `docs/staging-alembic-review.md` — clarified metadata-only guard boundary.
- `reports/hosted-staging-verification.md` — marked Phase 2 as historical and
  linked the current local status.
- `reports/staging-configuration-remediation.md` — marked the Phase 2.1
  preflight-gap finding as superseded.
- `reports/final-staging-preflight.md` — this report.

No migration was changed, including 0028–0031. The production `render.yaml`
was not changed. The worktree was already extensively modified; those existing
changes were preserved. Current source worktree is
`/home/sam/vervfy-latest/phase4a-retry-limits`, detached at
`dd22f18b92e26a59d342a98e06dfc2888c58905b`.

## 3. Metadata-only preflight implementation

The supported entry point is `python staging_guard.py metadata-preflight`.
It requires the existing staging approval file/digest, execution manifest,
exact approved database identity, TLS parameters, and a phase-specific
`STAGING_METADATA_DATABASE_URL`. It rejects ambient `PG*` and TLS overrides,
application/migration URLs alongside the metadata URL, unapproved roles, and
artifact/hash mismatches. Bootstrap uses `vervfy_staging_bootstrap`; the
migration and post-migration phases use `vervfy_oauth_staging_user`.

The runner uses a fresh, non-pooled connection, a 10-second connection timeout,
a 15-second statement timeout, and a `READ ONLY` transaction. It executes the
fixed catalog `SELECT`; when `public.alembic_version` exists, it reads only
that table's revision value. It does not select application account, identity,
password, session, storage-object, or user content. SQL/connection diagnostics
are suppressed; the JSON report contains curated role, privilege, ownership,
RLS, function, extension, TLS, and revision metadata. A failed check exits
nonzero. No role creation or grant operation is exposed by this action.

Phase checks include:

- **Bootstrap:** expected application roles absent; fresh database/schema;
  PostgreSQL 18; exact database and session identity; non-superuser
  `CREATEROLE` authority; database ownership and minimum database/schema
  privileges; no `CREATEDB`, replication privilege, or role memberships.
- **Migration:** expected eight restricted roles, exact capability memberships
  including PostgreSQL membership flags, database/schema privilege contract,
  fresh database, and revoked PUBLIC database/schema privileges.
- **Post-migration:** exact revision 0027; expected application/storage
  relations, owners, forced RLS and policies; SECURITY DEFINER function set,
  owners, pinned search paths and execute grants; identity lookup schema and
  column grants.

The identity lookup schema boundary is deliberate: migration 0022 grants
`public.USAGE` to `vervfy_identity_lookup_owner` (not `CREATE`); the
`google_auth_lookup` login must not receive `public.USAGE` or direct identity
table reads, and receives only `vervfy_auth` access through the restricted
executor. Do not pre-grant public schema access to the lookup login to address
a failure.

The public schema owner is accepted only as the designated bootstrap role or
PostgreSQL's `pg_database_owner`; an unrecognized owner fails the phase check.

The query inventories installed extensions and checks the PostgreSQL 18
`gen_random_uuid()` capability. The migration source does not require adding a
non-default extension. The metadata action does not replace the existing
guarded `preflight` SQL, which separately reviews default ACLs and broader
object grants, or the existing `postflight` action. It also does not prove
application-level tenant isolation; that requires separate synthetic RLS and
application tests.

The metadata command itself does not connect during `staging_guard.py check`.
An actual metadata run remains a hosted database operation and therefore
requires explicit approval. The existing approval hashes are stale for these
changes; no new artifact, approval JSON, credentials, or hosted execution was
created.

## 4. Authorized role-bootstrap instructions

Role bootstrap is a separately approved DBA operation, not a guard action.
Only after a passing, authorized bootstrap metadata report and confirmation of
a fresh disposable staging database may the reviewed
`docs/staging-db-bootstrap-proposal.sql` be executed.

The bootstrap connection must be the non-superuser
`vervfy_staging_bootstrap` login, with `CREATEROLE` and ownership of the
staging database, and without `CREATEDB`, replication privilege, or role
memberships. If Render does not provide exactly those capabilities,
stop and obtain a provider-supported, explicitly approved alternative; do not
use a superuser or grant `BYPASSRLS`. The script rejects pre-existing roles
instead of altering or reusing them. It creates:

- Login roles `vervfy_oauth_staging_user`, `app_runtime`,
  `google_auth_lookup`, and `storage_cleanup_worker`.
- No-login roles `vervfy_identity_lookup_owner`,
  `vervfy_identity_lookup`, `vervfy_storage_lifecycle_owner`, and
  `vervfy_storage_cleanup`.

All roles except the bootstrap authority must be non-superuser, non-BYPASSRLS,
and lack database/role creation and replication privileges. The migration
login receives database CONNECT/CREATE and `public` USAGE/CREATE; it receives
restricted SET membership in the identity and storage owners. `app_runtime`
receives CONNECT and `public` USAGE only at bootstrap; migrations grant the
reviewed table/function privileges. `google_auth_lookup` receives CONNECT and
inherits only the identity executor, with SET and ADMIN disabled. The storage
cleanup worker role is created for schema compatibility but gets no password
or deployed worker for this OAuth-only staging test. Bootstrap revokes PUBLIC
database/schema privileges and does not install broad default privileges.

Set the migration, runtime, and lookup login passwords separately through
hidden prompts and the staging secret store after the approved role
transaction. Never put passwords in SQL, command arguments, or logs. Keep the
migration URL out of the API service. Then, as a separate guarded read-only
phase, use the migration login to confirm the exact role graph and privileges.
Run the existing guarded `preflight` as required to review default ACLs and
object grants before any separately approved migration. Execute migrations
only through the hash-bound guard, pinned to `0027_storage_lifecycle`.

## 5. Render Blueprint validation

`render.staging.proposal.yaml` describes four isolated Free-plan resources in
Oregon:

| Resource | Configured relationship | Limitation |
|---|---|---|
| PostgreSQL | Dedicated PostgreSQL 18 database `vervfy_oauth_staging`, initial user `vervfy_staging_bootstrap`, direct connection, empty IP allowlist. | Provider role attributes, TLS, backup policy, and actual endpoint unverified. |
| Key Value | Dedicated `vervfy-staging-valkey`, `noeviction`, persistence `"off"`, empty IP allowlist. | Restart loses sessions, rate limits, and OAuth transaction state. |
| API | Dedicated FastAPI service; dedicated generated secret; `DATABASE_URL` manual and intended only for `app_runtime`; `REDIS_URL` references staging Key Value. | Host, forwarded-header behavior, and environment isolation unverified. |
| Frontend | Dedicated Next.js service; manual `BACKEND_URL` and `SITE_URL` inputs for the issued staging HTTPS origins. | Both exact URLs must be supplied before a successful first build/deploy. |

Google OAuth is explicitly disabled (`GOOGLE_OAUTH_ENABLED=0`); client ID,
client secret, and identity lookup URL are absent. API cookies are configured
HTTPS-only with `SameSite=lax`; one trusted proxy hop is proposed but must be
confirmed against Render's actual topology. Service start/build commands,
health paths, same-region placement, Valkey reference, and OAuth-off default
were checked locally. No production service names or production datastore
references are present in the proposal. `autoDeployTrigger: "off"` parses as a
string, not a YAML boolean.

**Local validation passed:** PyYAML parsed both Render files and all three
tests in `test_staging_render_config.py` passed. These checks cover resource
types/counts, service-name isolation, plan/region alignment, database identity,
Key Value policy, service references, commands/health checks, manual URL
inputs (unset until the actual HTTPS hosts are issued), and OAuth disabled by
default.

**Not validated:** Render's official JSON schema or hosted Blueprint preview.
The Render CLI and Python `jsonschema` validator are unavailable locally. The
local parser/test is not a substitute for Render validation. After authorization
and before applying the Blueprint, use Render CLI v2.7+ with
`render blueprints validate render.staging.proposal.yaml` if available, then
create a Blueprint from this custom path in the authorized Render account.
Review the full change preview, service plans, generated URLs, secret prompts,
network settings, and absence of production resources. Stop before Apply/Deploy
unless resource creation has separate explicit approval.

The local YAML test uses PyYAML from the locked environment; PyYAML is not a
direct dependency in `requirements.txt`, so the test class skips when it is
unavailable in another test environment. No application dependency was added.

The proposal selects no paid resources, but that is not a billing guarantee.
Confirm current quotas, plan terms, and dashboard pricing before creation.
The expected incremental cost is potentially $0 only if all Free-plan slots,
hours, and quotas are available. Free PostgreSQL is 1 GB, expires after 30
days, and has no managed backups; Free Key Value is 25 MB and has no
persistence. An earlier, dated pricing snapshot in
`docs/render-staging-proposal.md` estimated about $30/month for always-on
frontend/API, Key Value, and PostgreSQL; that was not selected and is not a
current quote. Confirm dashboard pricing and obtain explicit budget approval
before choosing paid/persistent services. If test criteria require persistence
or retained recovery points, use an approved service rather than weakening
session guarantees.

## 6. Migration safety gate

Local Alembic inspection and the focused graph test confirm:

- 31 linear source revisions; current head `0031_operator_revocation`.
- Approved release target `0027_storage_lifecycle`, parent
  `0026_application_runtime_grants`.
- Deferred chain: `0028_storage_cleanup_leases` ->
  `0029_cleanup_retry_limits` -> `0030_operator_foundation` ->
  `0031_operator_revocation`.
- The existing guard's execution target remains fixed at 0027. Deferred
  migrations are integrity inputs only and must not be applied or stamped.

Before any hosted migration, require exact staging resource/host/database
identity, the newly reviewed hash-bound artifact and approval, fresh database
and role preflight, a separately approved recovery baseline, and successful
default-ACL/object-grant checks. Keep API/workers stopped and OAuth disabled.
Run only the complete base-to-0027 chain through `staging_guard.py upgrade`.
Then run the post-migration metadata action and existing guarded postflight;
verify roles, ownership, forced RLS/policies, grants, reference guards, and the
disabled 0027 cleanup stub. No migration or database operation was executed
for this report.

## 7. Backup and restore readiness

The existing recovery runbook specifies a custom-format `pg_dump`, a
password-hash-free `pg_dumpall --globals-only --no-role-passwords` inventory,
checksums, and restoration only into a new isolated disposable PostgreSQL 18
cluster. Recreate only reviewed application roles and memberships; do not
blindly replay provider-managed globals. Before accepting a restore, verify
database/schema/table/function ownership, grants, role attributes and
memberships, RLS ENABLE and FORCE plus policies, extensions, exact revision
0027, and designated synthetic account/password-hash preservation. Keep
services and OAuth disabled.

A synthetic local PostgreSQL backup/restore rehearsal was reported as passed
in the preceding Phase 2.1 report. It is not a hosted recovery test and was
not repeated during this preflight. The proposed Free hosted database has no
managed backups; a verified backup or explicitly approved empty-database
recreation baseline is required before migrations. Database backups do not
restore object storage. No staging Storage namespace is configured, no Storage
recovery was tested, and physical cleanup remains disabled.

## 8. Focused test results

Executed locally from the specified worktree with synthetic/disposable state:

| Check | Result |
|---|---|
| `test_staging_metadata_preflight.py` | **12 passed** — evaluator failures, version/database/role/schema-owner mismatch, schema privilege boundary, and sanitized SQL/connection errors. |
| `test_staging_guard.py` | **19 passed** — approval binding, endpoint/role validation, and metadata action. |
| `test_staging_migrations.py` | **10 passed** — complete 31-revision graph, migration regressions, and disposable Unix-socket PostgreSQL catalog/identity-schema checks. The restricted `app_runtime` permission-denied case also passed with sanitized diagnostics. |
| `test_staging_render_config.py` | **3 passed** — local YAML parse and structural assertions. |
| `py_compile` on changed Python implementation/tests | **Passed.** |
| `git diff --check` | **Passed** for tracked diff; newly added files were reviewed by tests and compile checks. |
| Alembic graph inspection | **Passed:** 31 revisions, head 0031, target 0027, parent 0026. |

The local PostgreSQL test is Unix-socket-only; its TLS result is expected to be
false and does not validate hosted TLS. Alembic emitted an existing
non-fatal `path_separator` deprecation warning. The full suite, Redis
integration, browser tests, and hosted checks were not rerun for this phase.
Earlier local Redis and browser results remain historical evidence only. No
focused local test was skipped or failed. The evaluator's wrong-role,
wrong-database, permission-denied, and bad-version cases are deliberate
synthetic failure inputs; their tests passed. Render schema/preview validation
was unavailable, not a failed test.

## 9. Remaining hosted prerequisites and approvals

**Requires user/owner authorization:** approve the exact custom Blueprint,
resource names/region/plans, current billing exposure, resource creation, and
staging-only secrets. No resources are created by this report.

**Requires Render-hosted validation:** verify the service preview and actual
HTTPS hosts; confirm frontend/backend URL rewrites, proxy headers, secure
cookies, API environment isolation, database identity/TLS/role attributes,
Valkey `noeviction` and outage/restart behavior, service health checks, and
logs with synthetic accounts only. Confirm the bootstrap login is a
non-superuser database owner with `CREATEROLE`; otherwise the documented
bootstrap preflight must fail and the provider-supported alternative needs
separate review.

**Requires database-owner/DBA approval:** authorize metadata reads, role
bootstrap SQL, password setup, backup/recreation baseline, and—later—a
separate migration approval pinned to 0027. Do not run hosted migrations as
part of this preflight.

**Requires Google Cloud owner approval:** create a distinct staging OAuth
client/project, configure only the exact HTTPS callback
`https://<STAGING_FRONTEND_HOST>/api/auth/google/callback` and, if required,
the exact frontend JavaScript origin, restrict test users, and inject the
secret into the API service only. After all staging checks, enabling staging
OAuth still requires a separate go/no-go. Production OAuth remains disabled.

## 10. Decision

**Staging GO/NO-GO: NO-GO for hosted deployment, migration, or OAuth testing
today.** The local preflight and proposal are ready for a controlled,
authorized validation sequence, but missing Render schema/preview evidence,
actual resource identity, role capabilities, recovery baseline, Valkey
behavior, and live OAuth verification are release gates. Local tests do not
resolve those hosted blockers. No production system was accessed or modified.
