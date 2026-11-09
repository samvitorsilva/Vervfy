# Vervfy — Hosted Staging Verification

> Historical Phase 2 assessment. The staging Blueprint and local guarded
> metadata preflight have since been updated; see
> `reports/staging-configuration-remediation.md` and
> `reports/final-staging-preflight.md` for current local status. This report's
> hosted findings remain unverified: no hosted resource was accessed.

- **Assessment date:** 2026-11-07
- **Recommendation:** **NOT READY for hosted staging verification; NO-GO for staging Google OAuth**
- **Scope:** Read-only inspection of the selected worktree and its staging proposal/runbooks. No hosted service, database, Redis, Google Cloud, Storage, account, or secret store was accessed. No deployment, bootstrap, migration, or OAuth enablement was attempted.

## 1. Executive summary

The source contains substantial authentication, PostgreSQL, Redis, and OAuth
security controls, and a separate Render staging proposal exists. Those facts
do not establish that the controls work in the hosted environment. No current
resource identity, service configuration, database catalog, Redis policy,
Google client, backup, restore, browser session, or deployment log was
independently verified.

The staging proposal is not a self-contained deployable stack: it creates an
API, frontend, and free Valkey service, but deliberately omits PostgreSQL and
Storage. It depends on manual `DATABASE_URL` and `BACKEND_URL` values, a
verified existing staging database, and a region that has not been established.
The API/frontend URLs and Google callback therefore cannot yet be fixed. The
free Valkey proposal also does not meet a claim of session-key persistence
across Valkey restarts; project documentation says the free service loses keys
on restart.

Before any hosted check, reconcile the stale/inconsistent migration approval
instructions. The current source has **31 migrations** and its source head is
`0031_operator_revocation`; the guarded staging migration target is
`0027_storage_lifecycle`. Several staging documents still describe 28 files or
a 26-revision chain and/or commands the guard does not implement. Existing
artifact hashes do not approve the current worktree. Migrations `0028–0031`
must remain unchanged and unapplied for this staging exercise.

Keep `GOOGLE_OAUTH_ENABLED=0`. There is no verified staging endpoint on which
to test the exact callback, cookies, database/Redis behavior, or browser
flows. Physical Storage cleanup remains disabled.

## 2. Scope and worktree

The requested source worktree is
`/home/sam/vervfy-latest/phase4a-retry-limits`. It is a detached `HEAD` at
`dd22f18b92e26a59d342a98e06dfc2888c58905b` (`2026-10-31`, “Security updates
and terms of service”). At task start, it contained 62 modified tracked files,
57 untracked files/directories, and no deletions. The existing changes were
preserved. In particular, migrations `0028–0031` were not edited. This report
is the only file added for this task; no commit was created.

The parent directory is a separate Git worktree and was not used as the
release source.

## 3. Staging infrastructure and deployment configuration

| Classification | Finding |
|---|---|
| **Confirmed pass — source/config only** | `render.staging.proposal.yaml:5-59` separates the proposed API, frontend, and Valkey names from the root `render.yaml`; sets `VERVFY_ENVIRONMENT=staging`, HTTPS-only cookies, `SameSite=lax`, a generated service secret, `noeviction`, OAuth disabled, and `autoDeploy: false`; and starts Uvicorn with `--lifespan on`. The proposal does not configure production URLs or credentials. This does not prove effective hosted environment isolation. |
| **Confirmed failure — proposal incomplete** | The proposal intentionally has no PostgreSQL resource (`render.staging.proposal.yaml:39-40`; `docs/render-staging-proposal.md:27-34`). It assumes an existing database whose Render resource ID, hostname, region, database name, isolation, state, plan, and credentials are unknown. `DATABASE_URL` is a manual value, not a resource reference. Do not deploy the API until it is independently verified as staging-only. |
| **Confirmed failure — frontend requires operator input** | `BACKEND_URL` and `SITE_URL` are unset/manual in the proposal (`render.staging.proposal.yaml:56-59`). Next.js throws at build time if `BACKEND_URL` is absent (`web/next.config.ts:3-11`); `/api/*` rewrites to that configured backend (`web/next.config.ts:39-43`). The exact public HTTPS service URLs and region are not known, so a successful, correctly wired hosted build has not been established. |
| **Confirmed failure — proposed session durability is insufficient** | Both web services and the Valkey service use `plan: free` (`render.staging.proposal.yaml:7,14,47`). `noeviction` is configured, but project runbooks state Free Key Value has 25 MB and loses keys on restart (`docs/render-staging-proposal.md:215`; `docs/google-oauth-staging-runbook.md:61,104`). Since `auth.py:537-645` stores allowlisted sessions and reverse indexes in Redis, restart loss would invalidate sessions. This is not evidence that a hosted instance currently has this behavior; it means the proposed plan cannot be treated as meeting durable-session verification. Choose a suitable service or explicitly accept and test restart invalidation. |
| **Requires external authorization** | Render owner approval is required for the exact custom Blueprint path, resource creation, region, service plans/cost, public endpoint/access controls, and any secret changes. Applying a Blueprint is a hosted change even with `autoDeploy: false`; the proposal explicitly warns not to deploy without approval (`render.staging.proposal.yaml:1-3`; `docs/render-staging-proposal.md:5,48-52`). |
| **Not tested** | No Render project/resource inventory, Blueprint schema validation/change preview, hosted URL, HTTPS redirect, forwarded-header behavior, service-to-service wiring, service environment group, effective secret separation, or deployment logs were inspected. The YAML was read as a proposal only; it was not deployed or validated against Render. |

`render.yaml` is the separate root configuration and is not a staging
deployment plan: it defines free services, no PostgreSQL resource, and
externally supplied database settings (`render.yaml:2-14,33-34`). Do not use
it as a substitute for the staging proposal or attach production environment
groups to staging.

The proposal intentionally omits Supabase credentials and Storage. This is
acceptable for an auth-only test if no media/storage behavior is claimed as
verified. Do not configure production Storage. For any staging media test,
obtain approval for a separate staging Storage project/bucket and namespace.

### Required staging settings (names only)

| Service | Required settings |
|---|---|
| API, initial deployment | `VERVFY_ENVIRONMENT=staging`, unique `VERVFY_SECRET_KEY`, `VERVFY_HTTPS_ONLY=1`, `VERVFY_COOKIE_SAME_SITE=lax`, verified `VERVFY_TRUSTED_PROXY_HOPS`, `DATABASE_URL` using `app_runtime` with certificate-verified TLS, `REDIS_URL` for the dedicated staging Valkey, and `GOOGLE_OAUTH_ENABLED=0`. |
| Frontend | `BACKEND_URL` set to the staging API HTTPS origin before build; `SITE_URL` set to the staging frontend origin. |
| API, only after separate OAuth approval | `GOOGLE_CLIENT_ID`, secret-store-only `GOOGLE_CLIENT_SECRET`, exact `GOOGLE_REDIRECT_URI`, `GOOGLE_FRONTEND_ORIGIN`, and `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` using the restricted `google_auth_lookup` principal with certificate-verified TLS. |
| One-off migration runner only | `MIGRATION_DATABASE_URL` using the approved migration principal. Do not set it on the API. |

## 4. PostgreSQL, migrations, roles, and RLS

### Local/source findings

- The staging guard pins `upgrade` to `0027_storage_lifecycle`, requires a
  31-migration source manifest, and requires a fixed set of three database
  URLs before it proceeds (`staging_guard.py:13-15,99-139,141-155`). A
  read-only local AST inspection confirmed 31 migration files and source head
  `0031_operator_revocation`; this was not a database operation.
- The current API startup checks the migrated schema and the three enabled
  storage-reference triggers (`server.py:1362-1397`). The staging proposal
  explicitly enables ASGI lifespan (`render.staging.proposal.yaml:16`), so
  that check should run if this exact command is deployed.
- The source migrations define forced tenant RLS for the application tables;
  migration `0022` defines the isolated identity lookup capability, and
  migration `0027` defines storage lifecycle objects. Local reports describe
  disposable PostgreSQL role/RLS tests, but these tests are not hosted
  evidence (`alembic/versions/0007_row_level_security.py`,
  `0021_provider_identities.py`, `0022_provider_identity_lookup.py`,
  `0024_provider_identity_runtime_access.py`,
  `0026_application_runtime_grants.py`, `0027_storage_lifecycle.py`).
- The intended credentials are separate: `app_runtime`,
  `google_auth_lookup`, and a one-off migration principal. Do not put
  migration credentials in the long-running API service. The staging
  endpoint procedure requires exact resource identity, artifact hashes,
  three distinct URLs, and TLS approval before it opens a connection
  (`docs/staging-endpoint-approval.md:5-47`).

### Confirmed blockers and hosted status

| Classification | Finding |
|---|---|
| **Confirmed failure — release documentation/guard mismatch** | `staging_guard.py` expects 31 migration files and pins to 0027, while `docs/staging-db-initialization-runbook.md:20` says 28 revisions through 0028. `docs/staging-endpoint-approval.md:9` still refers to a 26-revision chain and “32 files.” `staging-recreation-recovery.md` also contains older 28-file packaging instructions. Do not reuse the old approval hashes or commands. Reconcile the instructions and generate a new, independently reviewed artifact/manifest that includes the current source, while leaving 0028–0031 unchanged and unapplied. |
| **Historical Phase 2 failure — superseded locally; hosted state unknown** | At assessment time, the initialization runbook described metadata and bootstrap commands that did not exist, and the guard accepted only `check`, `preflight`, `postflight`, and `upgrade`. Phase 2.2 has since added the read-only, hash-bound `metadata-preflight` action. Role bootstrap remains a separate DBA operation; no hosted connection or current approval is implied. See `reports/final-staging-preflight.md`. |
| **Not tested — actual PostgreSQL state** | PostgreSQL version, actual resource/database identity, migration revision, ownership, runtime/migration/lookup role attributes, role memberships, effective grants, default ACLs, schema ownership, SECURITY DEFINER ownership/search paths, RLS enable/force/policies, and tenant isolation were not queried. No hosted database connection was made. |
| **Not tested — backup/recovery** | No backup or restore was inspected or rehearsed. `docs/staging-recreation-recovery.md:19-23` says the database identity and backup status are unknown and recreation has not been rehearsed. `docs/render-staging-proposal.md:215` describes no backups for the Free Postgres option, but the existing database’s actual plan is unknown. A restoration rehearsal with synthetic data is still required; an approved empty-database recreation baseline is not a substitute for a restore test if data must be retained. |
| **Requires external authorization** | First obtain independent evidence of the staging resource ID, endpoint, database, plan, data status, TLS CA/hostname validation, and absence of production links. Separately authorize the exact read-only inspection, any role bootstrap, the pinned migration to `0027_storage_lifecycle`, and postflight. Confirm backup/restore or approve a disposable empty-database recovery baseline before migration. Never apply `0028–0031` for this test. |

An earlier file records an operator-reported PostgreSQL 18.6 preflight, but
states that raw catalog output was not supplied (`docs/staging-recreation-recovery.md:13`).
Other current runbook text says database occupancy and migration state remain
unknown (`docs/staging-db-initialization-runbook.md:10-19`). This historical
claim is not independent evidence and is not counted as a pass.

## 5. Redis and sessions

| Classification | Finding |
|---|---|
| **Confirmed pass — implementation/local only** | With `REDIS_URL`, `SessionStore` uses Redis-backed session keys, a 30-day TTL, atomic create/revoke scripts, and account-wide revocation (`auth.py:48-68,537-645`). Redis errors in the session operations raise an unavailable error rather than accepting an unverified session (`auth.py:556-612`). OAuth transaction keys have a 10-minute TTL and single-use consumption (`google_oauth.py:38,249-285,506-530`). These are source properties, not hosted results. |
| **Confirmed pass — proposal only** | The staging proposal connects the API only to its named staging Valkey and sets `maxmemoryPolicy: noeviction` (`render.staging.proposal.yaml:5-9,32-37`). This setting is not evidence of the live service policy, authentication, reachability, capacity, or persistence. |
| **Not tested** | No Redis/Valkey connection or `CONFIG` inspection was performed. Hosted connectivity, actual `noeviction`, session persistence/expiry, logout/logout-all, atomic single-use and replay rejection, key survival across API/Redis restart, capacity behavior, and outage/fail-closed behavior remain unverified. |
| **Requires external authorization** | Approve a dedicated staging Key Value service and service-scoped secret, confirm it is not shared with production, and choose a plan appropriate to the desired persistence test. Then run synthetic session/OAuth replay and outage tests against staging without logging key contents or credentials. |

## 6. Google OAuth

| Classification | Finding |
|---|---|
| **Confirmed pass — source/local only** | OAuth defaults off and requires client ID/secret, callback, frontend origin, Redis, and a distinct PostgreSQL identity-lookup URL when enabled (`google_oauth.py:112-145`). The implementation uses Authorization Code + S256 PKCE, Redis transaction state, nonce and browser binding, and validates trusted Google metadata and ID-token claims (`google_oauth.py:416-504,506-629`). The current source-level checks are not a live Google integration test. |
| **Confirmed pass — safety default only** | Staging proposal sets `GOOGLE_OAUTH_ENABLED=0` and omits Google credentials (`render.staging.proposal.yaml:41-42`). Keep that state until the staged DB, service endpoints, exact callback, and test-client approval are ready. |
| **Not tested** | No staging Google OAuth client, consent/test-user configuration, authorized JavaScript origin, callback URI, client secret, or synthetic Google login was used. The hostname is not established, so the exact redirect URI cannot yet be registered. No real signature/JWKS/key-rotation, state/nonce/PKCE, expiry, auth_time, signup/login/link/unlink/password preservation/session rotation/logout test was run against Google or staging. |
| **Not tested — browser coverage** | The selected worktree has no `web/tests/google-auth.spec.ts` or `web/tests/account-isolation.spec.ts`; the configured Playwright server defaults to local services (`web/playwright.config.ts:3-37`). The previously reported three local auth smoke tests do not test staging or live Google. No browser session, console, redirect, or cookie was observed on a staging domain. |
| **Requires external authorization** | The Google Cloud owner must approve a distinct staging project/client, restricted tester audience, minimal scopes, exact HTTPS callback/origin, and secret storage on the API only. Enabling OAuth in staging is a separate approval after database and Redis postflight. Production client and production OAuth remain out of scope and disabled. |

## 7. Backup and recovery

**Not tested:** no backup inventory, point-in-time recovery setting, export,
restore, migration recovery, role/grant preservation, RLS preservation,
extension check, or Storage namespace recovery was performed. No hosted data
was accessed.

The existing staging database’s backup plan and data status are unknown.
Project runbooks say the Free Postgres option has no backups and expires; they
do not prove which plan the existing resource uses
(`docs/render-staging-proposal.md:215`; `docs/staging-recreation-recovery.md:19`).
Before migration, the database owner must provide an approved recovery plan:
either a verified backup restored to a new isolated synthetic-data database,
or explicit acceptance that the confirmed-empty staging database is disposable
and can be recreated. The requested isolated restoration rehearsal remains
blocked until the owner authorizes the target resource and test procedure.

## 8. Browser, security, and privacy results

### Test execution

| Check | Result |
|---|---|
| Current source migration graph | **Passed, local/read-only only:** 31 migration files, source head `0031_operator_revocation`; no database was contacted. |
| Backend, PostgreSQL, Redis, frontend, TypeScript, lint, production build | **Not run in this task.** Earlier local results in the prior release-gate report predate this staging assessment and do not establish the current hosted behavior. |
| Playwright against staging | **Not run:** no approved staging URL, deployment, or synthetic test account was available. |
| Google OAuth browser flow | **Not run:** no staging Google client, callback registration, or approved tester was available; no matching Google/account-isolation Playwright spec exists in this selected worktree. |
| Render blueprint/schema validation | **Not run:** no Render schema validator or dashboard preview was used. |
| Hosted PostgreSQL, Redis, backup/restore, logs | **Not run:** no external authorization or endpoint evidence was supplied. |

| Classification | Finding |
|---|---|
| **Confirmed pass — source/config only** | Same-origin `/api/*` proxying is present; the proposal uses HTTPS-only cookies, `SameSite=lax`, a dedicated staging secret, OAuth off, and `noeviction`. Its API command disables access logs and explicitly runs lifespan (`render.staging.proposal.yaml:16,22-37`; `web/next.config.ts:16-43`). These facts do not verify deployed headers/cookies or logs. |
| **Confirmed failure — staging exposure is unspecified** | The proposed web services are public Render web services, and no tester-only access control is configured in the YAML. The proposal asks operators to enable available staging access controls (`docs/render-staging-proposal.md:111-112`) but does not define or verify one. Before adding credentials or synthetic accounts, approve a compatible restriction/tester plan; Google’s callback must remain reachable by the approved test flow. |
| **Not tested** | HTTPS redirect/certificate, Secure/HttpOnly/SameSite cookies, CSRF, CORS, trusted proxy hop/IP behavior, rate limiting, auth error handling, redirects, sensitive-data redaction, browser console, API/frontend integration, account isolation, and cross-account requests were not exercised on a hosted endpoint. No logs were read. |
| **Not tested — runtime database TLS** | The staging runtime must receive PostgreSQL URLs with the approved TLS mode and CA. The migration guard validates URLs for its own guarded operations, but the live API/Google lookup URLs and the database’s TLS status were not inspected (`staging_guard.py:99-139`; `db.py:54-75`; `google_oauth.py:178-207`; `docs/render-staging-proposal.md:68,75`). |
| **Confirmed pass — cleanup disabled in source** | Migration 0027 constrains `physical_cleanup_enabled` to false and installs a raising `claim_cleanup` stub (`alembic/versions/0027_storage_lifecycle.py:190,484-487`). The staging proposal has no worker or Storage credentials. This is source/config evidence only; no hosted catalog was checked. |

## 9. Findings by severity

| Severity | Classification | Finding |
|---|---|---|
| **High** | Confirmed failure | The proposed stack has no PostgreSQL resource and lacks verified database/API endpoints; `DATABASE_URL` and `BACKEND_URL` are manual values. It cannot be treated as deployable until isolated resource identity and service wiring are approved. |
| **High** | Confirmed failure | Approval/runbook instructions conflict with the current 31-file source and guard. A fresh artifact/manifest and corrected executable procedure are required; old hashes and commands are not valid authorization. |
| **High** | Not tested | Hosted PostgreSQL role/RLS/tenant isolation, migration revision, TLS, and backup/recovery are unverified. The prior operator-reported preflight has no inspectable raw evidence. |
| **High** | Confirmed failure in proposed plan | Free Valkey is documented as restart-volatile, so the proposed plan cannot demonstrate durable sessions across Valkey restart. Use a suitable plan or explicitly test/document expected session invalidation. |
| **High** | Not tested | No hosted Google client/callback or browser flow exists in evidence. OAuth must remain disabled. |
| **Medium** | Confirmed failure | No staging-only access restriction is specified for public web endpoints. Approve a tester restriction before adding test credentials/accounts. |
| **Medium** | Not tested | Runtime database TLS, Redis transport/authentication, cookies, CSRF/CORS, rate limits, logging redaction, and fail-closed behavior have not been verified on the provider. |
| **Informational** | Confirmed pass in source | Physical Storage cleanup remains hard-disabled. No cleanup worker, Storage namespace, or Storage credentials should be added for this authentication-only test. |

## 10. Exact unresolved blockers and required external approvals

1. **Render/resource owner:** identify the exact staging project/resource IDs,
   region, database name/host/plan/data status, Valkey and service resources;
   verify no production database, Redis, Storage, environment group, or secret
   is referenced. Approve the exact service plan, region, cost, public URL and
   staging access-control approach.
2. **Release/DBA owners:** reconcile current runbook/guard/migration inventory;
   review the exact guarded runner and fresh artifact/manifest hashes; approve
   metadata-only inspection and verify TLS/hostname identity. Separately
   approve any role bootstrap, the migration pinned to
   `0027_storage_lifecycle`, and postflight. Preserve migrations `0028–0031`
   unchanged and unapplied.
3. **Database owner:** establish an approved backup/restore or disposable-empty
   recovery baseline and perform the synthetic restoration rehearsal before
   migration or application startup.
4. **Render operator:** create or approve the isolated API, frontend, and
   Valkey services; set unique staging-only service secrets; provide the
   verified HTTPS `BACKEND_URL`; verify the API’s `DATABASE_URL` and
   `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` use restricted staging principals
   and certificate-verified TLS. Do not set migration credentials on the API.
5. **Google Cloud owner:** create/approve a distinct staging OAuth Web client
   and restricted test-user audience. Only after hostnames are fixed, register
   the exact frontend callback
   `https://<staging-frontend-host>/api/auth/google/callback` and matching
   origin; store its secret only in the staging API. Approve staging OAuth
   enablement separately after postflight.
6. **Test owner:** provide designated synthetic accounts and authorize the
   staging-only browser, cross-account, outage, expiry, replay, and restore
   checks. Do not use real user data.

These are authorization prerequisites, not actions taken in this assessment.
No hosted command should be run until the exact approval and artifact
requirements in `docs/staging-endpoint-approval.md` are satisfied and the
documented procedure matches the current guard.

## 11. Recommended next actions

1. Correct the stale migration counts, artifact instructions, and command
   descriptions; validate the updated guard without connecting to a database.
   Keep the target pinned to 0027 and hash all 31 source migrations while
   leaving 0028–0031 unapplied.
2. Obtain owner-supplied staging resource identity, region, database plan,
   data status, backup evidence, TLS CA/hostname evidence, and separate-service
   inventory. Do not infer identity from resource names.
3. Approve the exact staging Blueprint/change preview and provision only
   dedicated resources. Keep `GOOGLE_OAUTH_ENABLED=0` and Storage/cleanup
   disabled.
4. After separate read-only approval, run the reviewed guarded preflight and
   inspect sanitized role, ACL, RLS, ownership, SECURITY DEFINER/search-path,
   and migration output. Stop on any mismatch.
5. After backup/recovery approval, migrate only to
   `0027_storage_lifecycle`, then run postflight. Deploy API/frontend only
   after this evidence and verify effective environment separation.
6. Test Redis/session behavior, HTTPS/proxy/cookies/CSRF, rate limits,
   fail-closed outages, and tenant isolation with synthetic accounts. Then
   configure the separate Google client and run the complete staging browser
   flow before any staging OAuth enablement approval.
7. Record actual artifacts, revisions, sanitized outputs, test identities by
   synthetic labels only, and the final staging go/no-go. Reassess production
   separately; this report authorizes no production action.

## 12. Go / no-go

**NO-GO for hosted staging execution and staging Google OAuth at this time.**
The proposed topology is incomplete, the current approval/runbook set is
internally inconsistent, and no current hosted identity or recovery evidence
is available. Proceed only after the external approvals above and a corrected,
hash-bound execution procedure. Keep production Google OAuth disabled.
Physical Storage cleanup remains disabled.
