# Staging Configuration Remediation

> Historical Phase 2.1 report. Its statements below that a guarded metadata
> preflight did not exist and no executable path was available were superseded
> by the Phase 2.2 local implementation in
> `reports/final-staging-preflight.md`. Role bootstrap remains a separately
> authorized DBA operation; no hosted verification or deployment is implied.

## Executive summary

**Local proposal and documentation remediation is complete; hosted staging is
not yet ready to deploy.** The staging Blueprint now defines a separate
PostgreSQL database, Valkey service, API, and frontend. OAuth remains disabled,
no production resource is referenced, and all proposed plans are Free. The
Blueprint parses and its local structure/relationships were checked.

The source migration graph has **31 revisions**, head
`0031_operator_revocation`. The only approved staging/production migration
target remains `0027_storage_lifecycle`; migrations 0028–0031 are deferred,
included only for source integrity, and must remain unapplied.

Local migration, OAuth, database-role, Redis, and synthetic backup/restore
checks passed. They do not prove Render service creation, managed PostgreSQL
privileges, TLS, backups, Redis persistence, or live Google behavior. At the
time of this Phase 2.1 report, the guard lacked metadata preflight; Phase 2.2
has since added the read-only action. Role bootstrap and hosted activity still
require separate authorization. Do not deploy, connect to hosted staging,
migrate, or enable OAuth until the remaining approvals and hosted checks pass.

No hosted or production resource was accessed. No migration, deployment,
Google Cloud change, Storage access, or OAuth enablement was performed.

## Exact files changed

- `render.staging.proposal.yaml`
- `docs/render-staging-proposal.md`
- `docs/staging-db-initialization-runbook.md`
- `docs/staging-endpoint-approval.md`
- `docs/staging-recreation-recovery.md`
- `docs/staging-alembic-review.md`
- `docs/google-oauth-staging-runbook.md`
- `reports/staging-configuration-remediation.md` (this report)

`render.yaml` and migrations 0028–0031 were not changed. Existing worktree
changes were preserved.

## Staging infrastructure assessment

### Configured in the proposal; not deployed

`render.staging.proposal.yaml` now describes four distinct resources:

| Resource | Proposal |
|---|---|
| PostgreSQL | PostgreSQL 18; direct connection (`connectionPool: none`); database `vervfy_oauth_staging`; initial provider login `vervfy_staging_bootstrap`; empty public IP allowlist |
| Valkey | Dedicated Free Key Value; `maxmemoryPolicy: noeviction`; `persistenceMode: off`; empty IP allowlist |
| API | Dedicated FastAPI web service; Free plan; staging environment; HTTPS-only cookies; explicit ASGI lifespan; OAuth disabled |
| Frontend | Dedicated Next.js web service; Free plan; manual HTTPS-only `BACKEND_URL` and `SITE_URL` inputs |

Oregon is a **proposed** common region, not an externally verified choice.
Every resource is set to the Free plan; confirm available slots, quotas, terms,
and any usage charges before creation. `DATABASE_URL`, `BACKEND_URL`, and
`SITE_URL` are deliberately unset (`sync: false`) until Render issues the
actual hosts and a staging-only app-role credential is approved. `REDIS_URL`
references only the new Valkey service. The API does not receive migration
credentials or a generated database bootstrap URL. `VERVFY_SECRET_KEY` is
generated separately for the API. No shared production environment group or
Storage credential/namespace is declared.

The production root `render.yaml` was left unchanged. Render documentation
supports the Blueprint fields used here, including top-level `databases`,
PostgreSQL `postgresMajorVersion`, `databaseName`, and `user`, Key Value
`maxmemoryPolicy`/`persistenceMode`, service references, and
`autoDeployTrigger`. Node `js-yaml` parsing and structural checks passed for
resource counts/types, region/plan alignment, datastore isolation defaults,
database identity, Valkey policy, service references, OAuth-off default, and
manual URL inputs. **No Render CLI/schema validator or Blueprint preview was
available or run**; hosted Blueprint acceptance remains untested.

The public IP allowlists are empty by default. `staging_guard.py` accepts only
an approved direct Render PostgreSQL hostname, so any future external guarded
runner would need an individually approved, temporary source CIDR and removal
afterward. Never open `0.0.0.0/0`. The current guard does not accept an
internal Render database hostname.

Render Key Value internal connections are unauthenticated by default. The
proposal does not encode the dashboard-only internal-auth toggle; require it
after creation, then confirm the `REDIS_URL` service reference resolves to the
authenticated staging URL before starting the API. Enabling internal auth
restarts Valkey, so perform it before synthetic session/OAuth tests.

### Migration graph and approved target

Alembic inspection confirmed one linear graph of 31 revisions through
`0031_operator_revocation`. The source includes `0027_storage_lifecycle` and
the four deferred revisions `0028_storage_cleanup_leases`,
`0029_storage_cleanup_retry_limits`, `0030_operator_foundation`, and
`0031_operator_revocation`. Staging must execute only the base-to-0027 prefix.
The guard pins `0027_storage_lifecycle` and validates a manifest containing
all 31 source migration files; presence in the artifact does not approve their
execution.

Relevant docs now distinguish the current graph, the 0027 boundary, deferred
revisions, and historical 26-/28-revision reports. No migrations were run
during this remediation.

### Database role and initialization findings

Local disposable PostgreSQL 18.6 tests validate the role, table-grant, RLS,
and Google identity lookup contracts. Hosted PostgreSQL ownership, role
creation/membership options, effective grants, default privileges, TLS CA,
and resource identity are **not tested**.

The Blueprint's initial login, `vervfy_staging_bootstrap`, is distinct from
the required migration login (`vervfy_oauth_staging_user`), application login
(`app_runtime`), and lookup login (`google_auth_lookup`). The provider login's
ability to create the reviewed role graph and transfer schema ownership is
unknown. `docs/staging-db-bootstrap-proposal.sql` remains a proposal and was
not executed.

**Blocking finding:** `staging_guard.py` currently accepts `check`,
`preflight`, `upgrade`, and `postflight`; it does not implement the proposed
metadata-only preflight or role-bootstrap actions. The guarded database
preflight expects roles to exist, so it cannot initialize a fresh Blueprint
database. Existing docs explicitly prohibit substituting raw psql/Alembic.
Resolve this with a separately reviewed, hash-bound guarded bootstrap path or
an explicitly approved DBA procedure before any hosted database operation.
The old approval/artifact hashes do not authorize the current source.

## Redis and session assessment

The proposed Valkey is isolated and uses `noeviction`, but the Free plan's
`persistenceMode: off` is restart-volatile. A restart loses active session
allowlists, user-to-session indexes, rate-limit counters, and pending OAuth
transactions. Lost sessions and OAuth callbacks should fail closed; users may
need to sign in again. At capacity, writes fail rather than silently evicting
authentication state. This is disposable-staging behavior, not production
session durability.

Code evidence: `auth.py` sets a 30-day session TTL and propagates Redis
failures; `google_oauth.py` uses a 600-second OAuth transaction TTL and an
atomic, browser-bound single-use consume operation. Local Unix-socket Redis
tests passed for atomic consumption/replay rejection, expiration, missing
state, and outage behavior. No hosted Valkey restart, persistence, eviction,
or outage test was run. Before production, select an appropriately persistent
service and verify capacity, `noeviction`, restart behavior, and session
revocation.

## Google OAuth staging configuration

OAuth remains disabled by the checked-in proposal (`GOOGLE_OAUTH_ENABLED=0`);
Google credentials and lookup URL are absent. When separately authorized:

- Use a distinct Google Web application client and explicitly designated test
  users. Do not use the production client or real user data.
- Register exactly
  `https://<STAGING_FRONTEND_HOST>/api/auth/google/callback`. Add only
  `https://<STAGING_FRONTEND_HOST>` as an authorized JavaScript origin if the
  chosen client flow requires it.
- Set API `GOOGLE_REDIRECT_URI` and `GOOGLE_FRONTEND_ORIGIN` to those exact
  HTTPS values. Code in `google_oauth.py` requires the callback path and
  origin to match and rejects non-HTTPS except localhost.
- Set frontend `BACKEND_URL` to the staging API's public HTTPS origin and
  `SITE_URL` to the staging frontend origin. Render Free web services cannot
  receive private-network traffic; browser requests should remain same-origin
  through the frontend rewrite.
- Keep `GOOGLE_CLIENT_SECRET` and
  `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` only in the staging API's secret
  store. The lookup login must remain distinct from `app_runtime`; do not
  expose secrets in frontend build variables, responses, or logs.
- Keep `VERVFY_HTTPS_ONLY=1` and `VERVFY_COOKIE_SAME_SITE=lax`. The proposed
  `VERVFY_TRUSTED_PROXY_HOPS=1` is tentative; verify Render's actual proxy
  topology and forwarded-header behavior before use.
- Code evidence in `google_oauth.py` includes S256 PKCE, state and nonce,
  pinned Google OIDC metadata/JWKS URI and RS256, issuer/audience checks,
  expiration/issued-at checks, and fresh `auth_time` enforcement for
  sensitive operations. The browser binding and state are stored in Redis.
  These local implementation checks do not prove Google Console configuration
  or a live hosted callback.

## Backup, restore, and Storage

The updated recovery runbook documents a custom-format PostgreSQL dump,
password-hash-free global-role inventory, isolated PostgreSQL 18 restore,
post-restore checks for migration state, ownership, grants, extensions, RLS,
and synthetic-account preservation. Database recovery is explicitly
separate from object Storage recovery. The proposed Free database expires
after 30 days and has no managed backups; no hosted backup or restore is
available as evidence.

A local synthetic backup/restore rehearsal passed across fresh
Unix-socket-only PostgreSQL 18.6 clusters. It preserved the 0027 revision,
synthetic accounts/password hashes, role graph (recreated using the existing
disposable fixture), database/schema/table/function ownership, grants, RLS
policies, and extensions.

An initial attempt to replay `pg_dumpall --globals-only` directly failed on
PostgreSQL 18 role-membership grantor/ADMIN semantics. The final rehearsal
recreated roles and memberships using the reviewed local fixture before
restoring the custom archive. Do not blindly replay provider-wide global-role
dumps; restore only the reviewed application roles and memberships, then
verify their effective privileges. This remains a hosted recovery
prerequisite. No Storage service or namespace was accessed; media recovery
requires a separate staging-only bucket and object-store procedure.

## Local validation evidence

| Check | Result |
|---|---|
| Render YAML parser and structural/relationship assertions | **PASS**; no Render-hosted preview/schema validator |
| Alembic graph inspection | **PASS**; 31 linear revisions, head `0031_operator_revocation`, target `0027_storage_lifecycle` present |
| `test_staging_guard.py` | **17 passed** |
| `test_staging_migrations.py` | **9 passed** on disposable PostgreSQL; graph check and migration execution stopped at 0027 |
| `test_google_oauth.py` | **23 passed** |
| `test_oauth_postgres.py` | **21 passed** on disposable PostgreSQL |
| `test_google_oauth_redis_integration.py` | **4 passed** using a private Unix-socket Redis process |
| `test_db_config.py` | **3 passed** |
| Synthetic PostgreSQL backup/restore rehearsal | **PASS**, with the role-dump limitation described above |

The standalone `staging_guard.py check` was **blocked as expected** with
`missing or invalid approval material`: no approved JSON/digest or hosted
database role URLs exist. The guard validates before opening a connection.

The Alembic tests emit an existing non-fatal `path_separator` deprecation
warning. No focused test in the final runs failed; no mocked failure case
was counted as a pass. Browser tests against staging, live Google login,
Render deployment/preview, hosted database/role checks, hosted Redis, and
hosted backup/restore were **not run** because no staging environment exists
or is authorized. Frontend build/TypeScript checks were not rerun because no
frontend code changed.

Result classification: local code/config checks are **confirmed pass**;
direct replay of the PostgreSQL 18 global-role dump is a **confirmed failure**
and is not an approved restore method; all hosted behavior is **not tested**;
resource creation, hosted database operations, client creation, secret
injection, migration, and staging OAuth enablement **require external
authorization**.

## Security, privacy, and remaining blockers

| Severity / status | Finding and evidence |
|---|---|
| **Historical Phase 2.1 blocker — superseded locally** | At that time, a fresh database lacked a guarded metadata preflight. Phase 2.2 added a read-only metadata action; role DDL remains separate and requires DBA approval. See `reports/final-staging-preflight.md` and `docs/staging-db-initialization-runbook.md`. |
| **High — requires hosted authorization** | Render identity, PostgreSQL 18 role/ownership capability, TLS CA, allowlist access, and effective grants remain unverified. See `render.staging.proposal.yaml` and `docs/staging-endpoint-approval.md`. |
| **High — dashboard action and verification required** | Render Key Value internal authentication is off by default and is not set by the Blueprint. Enable it before API use and verify the referenced connection string. See `docs/render-staging-proposal.md` and the Render Key Value documentation. |
| **High for production; configured but untested in staging** | Free Valkey is restart-volatile; the proposal sets `noeviction` and persistence off. See `render.staging.proposal.yaml`, `auth.py`, and `google_oauth.py`. |
| **High — not tested hosted** | No staging Google client, test users, callback, HTTPS/proxy/cookie behavior, or live OIDC flow exists yet. Local flow validation is in `google_oauth.py`; deployment inputs are in `docs/google-oauth-staging-runbook.md`. |
| **Medium — local pass, hosted unknown** | Synthetic PostgreSQL restore passed locally; the Free hosted database has no managed backup and hosted restore is untested. See `docs/staging-recreation-recovery.md`. |
| **Deferred / not an auth blocker** | No Storage service or namespace is configured and physical cleanup remains disabled. Operator control plane, trustee bootstrap, and independent audit infrastructure remain deferred. |

Confirmed locally: separate resource names/references, no production URLs or
environment groups in the proposal, OAuth off, secret inputs unpopulated, no
Storage credentials, local fail-closed Redis behavior, and local PostgreSQL
role/RLS regressions. Hosted isolation, Render plan acceptance, PostgreSQL
capabilities/TLS, Redis persistence/restart, proxy/cookie behavior, live OAuth,
hosted logs/redaction, and managed-provider restore remain untested.

## External approvals and next action

1. Owner approval of the exact custom Blueprint path, four resource names,
   Oregon (or a consistently changed region), Free plans, workspace quota and
   billing exposure, and the decision to create a new disposable database.
2. Render access/billing approval to create the resources and set separate
   staging secrets; confirm generated HTTPS origins and no production
   environment groups or connections.
3. DBA/security approval of the database resource identity, PostgreSQL 18
   compatibility, TLS CA, temporary exact-source allowlist if needed, bootstrap
   role capabilities, role/grant contract, and a tested recovery decision.
4. Separate approval to resolve the guarded metadata/bootstrap gap and create
   a new hash-bound artifact. Only then may a new migration approval target
   `0027_storage_lifecycle`; never apply 0028–0031 under this release boundary.
5. Google Cloud owner approval for the staging client, exact callback/origin,
   consent/test-user policy, and API-only secret injection. Enable staging
   OAuth only after migration, role/RLS, session, and browser checks pass.
6. If media testing is later required, obtain separate approval for an isolated
   staging Storage project/bucket/namespace and recovery procedure.

**Recommendation: NO-GO for hosted deployment, migration, and Google OAuth
activation at this time.** The shortest safe next step is owner review of this
four-resource Blueprint and a decision on the missing guarded database
bootstrap path. No production action is part of that approval.
