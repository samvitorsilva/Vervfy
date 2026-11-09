# Google OAuth controlled staging runbook

This runbook is for an isolated, non-production verification deployment. It does
not authorize enabling OAuth in production, migrating a shared database, or
using production credentials or user data. Follow
[`google-oauth-readiness.md`](google-oauth-readiness.md) for the security
contract; record actual hostnames, test evidence, operator, and date in the
staging change ticket (never record secret values).

> **Staging database update — 2026-11-07:** The owner adopted the
> solo-maintainer policy. The earlier 26-revision/0026 instructions and
> internal DBA/security approver-count requirements below are superseded for
> staging. The current development artifact contains 28 migrations, targets
> 0027, and keeps 0028 unapplied. No operation is authorized until the
> per-operation owner record, private staging URLs, and local guard check pass.
> Frozen release artifacts remain unchanged.

## Current configuration and unknowns

`render.yaml` currently describes one API (`vervfy-api`), one frontend
(`vervfy-next`), and one Redis service (`vervfy-redis`); the API is configured
as `VERVFY_ENVIRONMENT=production`. The Redis declaration uses
`maxmemoryPolicy: allkeys-lru`. An isolated staging PostgreSQL resource is now
reported as available in the Render dashboard; its external hostname is
reported as independently matched by the operator, with no live TLS/database
check yet. Identity evidence is recorded in
[`staging-endpoint-approval.md`](staging-endpoint-approval.md). No staging
frontend/API/Redis deployment or staging OAuth client is confirmed. The
frontend service declares `BACKEND_URL`; its actual
value and public origin are deployment settings. `.env.example` documents
OAuth settings but leaves client credentials, callback, frontend origin, and
restricted lookup database URL unset. **Do not copy production resources or
guess hostnames.**

Fill these placeholders from the approved staging deployment before proceeding:

| Value | Staging value (operator fills in) |
|---|---|
| Frontend origin, no path | `https://<STAGING_FRONTEND_HOST>` |
| Exact callback URI | `https://<STAGING_FRONTEND_HOST>/api/auth/google/callback` |
| API service URL used by frontend `BACKEND_URL` | `<STAGING_API_ORIGIN>` |
| Staging PostgreSQL database/project | `<STAGING_DATABASE>` |
| Migration principal | `<STAGING_MIGRATION_ROLE>` |
| Ordinary application DB role | `<STAGING_APP_RUNTIME_ROLE>` |
| Dedicated lookup executor login | `<STAGING_AUTH_LOOKUP_LOGIN>` |
| Isolated staging Redis endpoint | `<STAGING_REDIS_ENDPOINT>` |
| Google OAuth client ID label | `<STAGING_GOOGLE_CLIENT_ID>` |

Do not substitute a production hostname, DB, Redis, service key, or OAuth
client. Keep the staging client, users, and provider identities distinct from
production. Use synthetic test accounts and no production data.

## Recommended low-cost Render layout

The current `render.yaml` is **not a staging blueprint**: it names the current
services `vervfy-api` and `vervfy-next`, sets the API environment to
`production`, and connects it to the declared `vervfy-redis`. Do not create a
second environment by deploying this file unchanged. Create separately named
staging resources manually (or use a reviewed staging-specific blueprint in a
later change) and verify every service URL before adding credentials.

For one short verification window, Render Hobby/free resources may be adequate
if the workspace has capacity:

| Resource | Free option and constraints |
|---|---|
| FastAPI and Next.js | Separate Free web services. They spin down after 15 minutes idle; first request can take about a minute. Their aggregate free runtime uses the workspace's 750 free instance hours/month. |
| PostgreSQL | One Free database per workspace; 1 GB; expires after 30 days, then has a 14-day upgrade grace period before deletion; no backups or managed pooling. |
| Key Value | One Free instance per workspace; 25 MB; no durable persistence and service restarts lose all keys. |
| Hostnames/TLS | Render service subdomains and managed TLS; verify Google accepts the actual chosen public hostname. Hobby includes two custom domains if using a domain already owned. Domain registration/DNS may have a separate charge. |

These are suitable only for synthetic, disposable tests. A free Valkey restart
also clears Vervfy sessions and OAuth transactions, which should fail closed
but can interrupt the test. Do not rely on free Postgres for retained staging
data. Check workspace usage, service-count limits, free database/Key Value
slots, build minutes, bandwidth, and current plan terms before creating
anything.

Render Support confirmed external PostgreSQL URLs support `sslmode=verify-full`
with the standard system CA store and Let's Encrypt endpoint certificates; no
Render-specific CA bundle is needed. External PostgreSQL connections from
Render web services use outbound IP addresses and may incur outbound bandwidth
costs. This does not confirm a staging resource, role configuration, or
endpoint-specific TLS handshake.

If predictable uptime is required, Render's published starting compute prices
at review time were **$7/month per 0.5 CPU/512 MB web service**, **$6/month for
the smallest Postgres plan (256 MB RAM)**, and **$10/month for 256 MB Key
Value**. Two always-on web services plus those smallest data plans are
approximately **$30/month**, before usage/overages, taxes, optional domain
registration, or plan changes. This is a cost illustration, not a quote.
Render Hobby includes 5 GB monthly bandwidth and 500 build minutes; its
published overage rates are $0.15/GB and $5/1,000 build minutes. Set billing
alerts/spend controls before provisioning and remove staging resources after
the test window. Prices and quotas can change; confirm in the dashboard.

An alternative is one separate Supabase Free project for PostgreSQL, if the
organization has a free project slot. Published Free limits include 500 MB
database, at most two active projects, and pausing after one week of inactivity.
It may reduce cost, but must first pass DBA preflight for role creation,
membership, ownership transfer, RLS, and migration 0022; local PostgreSQL
success does not prove a managed provider permits these operations. Avoid
upgrading the entire organization just for OAuth verification without an
approved budget.

Pricing/limit references (checked 2026-11-03): [Render pricing](https://render.com/pricing),
[Render free-instance limits](https://render.com/docs/free),
[Render Key Value/Valkey](https://render.com/docs/key-value),
[Render custom domains and TLS](https://render.com/docs/custom-domains),
[Supabase pricing](https://supabase.com/pricing), and
[Google OAuth app verification](https://support.google.com/cloud/answer/13463073).

## Verification options and recommendation

| Option | Google callback and browser boundary | PostgreSQL 0022 | Redis/Valkey and live OIDC | Isolation, limits, and cost |
|---|---|---|---|---|
| **1. Local PostgreSQL + Valkey + HTTPS tunnel** | Can exercise a real HTTPS browser callback, Secure/Lax cookies, CSRF, same-origin Next rewrite, and live Google redirects if the exact tunnel URI is accepted and registered. It exercises the tunnel and local Next/FastAPI path, not Render's proxy/TLS implementation or headers. | Strong low-cost verification against local PostgreSQL using disposable roles and the real migration SQL. Does not prove a managed DB provider's role, ownership, or grant restrictions. | Real local Valkey tests cover atomic consume/replay, TTL, and outage; live Google can exercise ID-token/JWKS/`auth_time`. No managed Valkey eviction policy or hosted failure mode is covered. | **$0** with locally installed software and Cloudflare Quick Tunnel. Quick Tunnel generates a changing public URL, has no uptime guarantee, and anyone with the URL can reach the app. Use only synthetic data, start it for the test window, and stop it immediately afterward. Google Console must accept the exact URL; re-register and reconfigure when it changes. |
| **2. Temporary isolated Render free-tier services** | Best direct check of Render TLS, public hostname, hosted Next rewrite, FastAPI callback, cookies, and deployed proxy behavior. Register the exact public frontend HTTPS callback. Free web services cannot receive private-network traffic, so the Next service's `BACKEND_URL` must use the staging API's public HTTPS URL (not an internal URL); keep all browser traffic through the frontend rewrite. | Tests real managed Postgres behavior only if migration preflight succeeds. Do not assume Render Postgres permits required role creation/ownership changes; prove this before applying migrations. | Tests managed Render Valkey service/restarts and live Google OIDC. Free Key Value has 25 MB and loses all keys on restart; free Postgres is 1 GB, expires after 30 days, and has no backups. | **$0 if workspace slots/quotas are available**, but one free Postgres and one free Key Value per workspace, idle web spin-down, shared monthly hours/build/bandwidth, and possible usage charges/suspension. Use no production data; resource loss is expected. |
| **3. Minimal paid Render staging** | Same hosted callback/proxy fidelity as option 2, with less sleep/restart uncertainty. Use exact registered HTTPS frontend URI and same-origin rewrite. | Same managed-role compatibility uncertainty; paid compute does not guarantee a role capability. DBA must verify migration permissions before running 0021/0022. | Managed Valkey and live Google tests without free-tier size/expiry limits; still verify actual eviction/persistence and outage behavior. | Published smallest compute snapshot: two web services at $7 each, Postgres $6, Key Value $10—about **$30/month** plus taxes, bandwidth/build overages, storage, and optional domain. Confirm current dashboard prices and budget before provisioning. |

**Recommendation: start with option 1, then use option 2 only for hosted parity.**
It is the cheapest way to verify the most independently testable gates: real
local Redis semantics, PostgreSQL migration/role behavior, password/account
regressions, and live Google authorization, ID-token signatures/JWKS and
`auth_time` through a real HTTPS browser callback. A Quick Tunnel is not a
stable hostname: check Google's registered redirect URI validator before
relying on a generated `trycloudflare.com` hostname, and keep the tunnel open
only for an approved test. If Google rejects it or any Render-specific
proxy/cookie behavior remains uncertain, use temporary free Render resources
if slots are available. Pay for option 3 only if free limits prevent reliable
completion and the owner approves the spend.

Do not treat option 1 as complete staging sign-off: local PostgreSQL cannot
prove managed-provider permissions, and a tunnel cannot prove Render routing,
forwarded-header, deployment secret, or provider-specific Redis behavior. Do
not enable OAuth in production based on either local or free-tier evidence.

Local release-candidate checks completed 2026-11-03: 63 OAuth/schema/PostgreSQL
tests and 19 password/auth regression tests passed on the locked Python 3.12.7
dependencies; all 3 Google-auth browser tests passed; the complete Alembic
chain reached `0024_provider_identity_access` on a fresh disposable PostgreSQL
cluster with tenant RLS and role/grant checks; and the frontend production
build passed. These checks cover local behavior only. No live Google callback,
production Google client, hosted Render proxy, or production database has been
verified; keep production OAuth disabled.

Before using a Quick Tunnel, make both local services available only on
loopback, route the public tunnel to the local Next.js frontend, and configure
Next.js to proxy `/api/*` to loopback FastAPI. Use the actual generated HTTPS
frontend URL as `GOOGLE_FRONTEND_ORIGIN`, and append exactly
`/api/auth/google/callback` for `GOOGLE_REDIRECT_URI` and Google Console. The
random hostname changes when the tunnel restarts, so re-register and restart
the application with the new URL. The tunnel URL is public to anyone who gets
it; use synthetic accounts/data, do not add an incompatible outer access/login
gate in front of the OAuth callback, and stop the tunnel and local services
immediately after the test. This validates browser behavior through that
tunnel, not Render.

For free Render, confirm the workspace's free database and Key Value slots are
actually available. `render.yaml` already declares `vervfy-redis`; whether
that resource currently exists and consumes the workspace slot is unknown.
Never reuse it unless its ownership and isolation are positively established.
Render documents that Free web services cannot receive private-network
traffic: for this option set frontend `BACKEND_URL` to the staging API's
public HTTPS service URL, not an internal service address. Keep the frontend
browser-facing requests same-origin through its rewrite.

Official references: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/),
[Google Web OAuth client and redirect rules](https://developers.google.com/identity/protocols/oauth2/web-server),
[Render free services and limitations](https://render.com/docs/free),
[Render private networking for Key Value](https://render.com/docs/key-value),
and [Render Postgres connectivity](https://render.com/docs/postgresql-creating-connecting).

### Staging environment variable map

Obtain each URI from the staging provider dashboard's **internal** connection
details where possible. Store credentials as service-level secret variables;
never commit them, put them in a frontend build variable, paste them in logs,
or copy a production value.

| Service | Variable | Required staging value |
|---|---|---|
| API | `PYTHON_VERSION` | `3.12.7` |
| API | `VERVFY_ENVIRONMENT` | `staging` (not the current blueprint's `production`) |
| API | `VERVFY_HTTPS_ONLY` | `1` |
| API | `VERVFY_TRUSTED_PROXY_HOPS` | Actual verified Render proxy topology; current example is `1`, verify before using |
| API | `VERVFY_SECRET_KEY` | Independently generated staging-only random secret |
| API | `VERVFY_COOKIE_SAME_SITE` | `lax` when OAuth is enabled; fail closed otherwise |
| API | `DATABASE_URL` | Staging app-role PostgreSQL URL only |
| API | `REDIS_URL` | Staging Key Value internal URL only; it is shared by session/rate-limit/OAuth transaction features, so restart/eviction affects all of them |
| API | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` | Staging-only storage project/key/bucket if needed by the running app; do not reuse production storage credentials |
| API | `GOOGLE_OAUTH_ENABLED` | `0` until all staging pre-enable checks pass; then `1` only for the isolated staging API |
| API secret | `GOOGLE_CLIENT_ID` | Staging Web application client ID |
| API secret | `GOOGLE_CLIENT_SECRET` | Staging client secret |
| API | `GOOGLE_REDIRECT_URI` | Exact public frontend URI below; identical to Google Console registration |
| API | `GOOGLE_FRONTEND_ORIGIN` | Exact public frontend origin, no path or trailing slash |
| API secret | `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` | Dedicated TLS DB login granted only the lookup executor capability; must differ from `DATABASE_URL` by host/port/user/database |
| Frontend | `BACKEND_URL` | Staging API origin only; for two Render Free web services use the API's public HTTPS URL because Free web services cannot receive private-network traffic. For local testing, use the local FastAPI origin. Never production. |
| Frontend | `SITE_URL` | Staging frontend public origin if using a custom domain; otherwise verify the provider-supplied `RENDER_EXTERNAL_URL` is correct |

Do not set provider credentials as `NEXT_PUBLIC_*`. `FRONTEND_URL` is only
needed if direct cross-origin browser-to-API requests are deliberately used;
the normal `/api/:path*` same-origin rewrite does not require it. Keep
`GOOGLE_OAUTH_ENABLED=0` while creating services, setting secrets, and running
migrations. The only approved callback template is:

```text
https://<STAGING_FRONTEND_HOST>/api/auth/google/callback
```

Use the actual verified frontend host in both `GOOGLE_REDIRECT_URI` and the
Google Console. Do not use the backend/private service hostname. If using a
Render-provided hostname, test that Google Console accepts it before depending
on it; otherwise use a verified custom domain and account for its registration
cost.

The implementation requests only OIDC `openid email profile`; it does not
call paid Google APIs or request Gmail/Drive scopes. No per-auth Google charge
is expected from this setup, but verify the current Google Cloud project
billing/consent requirements and scope classification before creating the
client. Google may require app/brand verification depending on the consent
screen and requested scopes; do not broaden scopes to solve a verification
issue.

## Safest verification order

### 1. Provision and isolate staging

- [ ] Create separate staging frontend/API services, a staging-only PostgreSQL
  project/database, a staging-only Redis instance, and a distinct Google OAuth
  client. Restrict access to the staging environment and test users.
- [ ] Verify network and credential isolation: staging API cannot connect to
  production DB/Redis/storage; staging credentials cannot authenticate to
  production; staging logs and backups are access-controlled.
- [ ] Configure the frontend's `BACKEND_URL` to the staging API origin and
  `SITE_URL` (if a custom origin is used) to the exact staging frontend origin.
  Verify the frontend build uses no OAuth client secret or other provider
  secret.
- [ ] Set API environment values from the secret manager/deployment settings:
  `VERVFY_ENVIRONMENT=staging`, `VERVFY_HTTPS_ONLY=1`,
  `VERVFY_TRUSTED_PROXY_HOPS=<verified proxy hop count>`,
  `VERVFY_COOKIE_SAME_SITE=lax`, and a unique staging
  `VERVFY_SECRET_KEY`. Keep `GOOGLE_OAUTH_ENABLED=0` throughout provisioning.
- [ ] Configure `DATABASE_URL` for the staging application role and
  `REDIS_URL` for staging Redis. Do not reuse the production `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, storage bucket, DB, or Redis. Only configure OAuth
  credentials after migrations and the pre-enable checks below pass.
- [ ] Confirm backup/snapshot and restore procedures for the staging DB.
  Confirm staging Redis can be isolated, paused, and tested without affecting
  any other service. Do not use `FLUSHALL` or induce memory pressure on shared
  Redis.

### 2. Register the staging Google client

- [ ] Create a distinct OAuth 2.0 **Web application** client in the approved
  Google Cloud project. Use the approved consent-screen audience/test-user
  policy; do not add real users beyond the authorized staging testers.
- [ ] Register this exact authorized redirect URI, replacing the placeholder
  with the verified frontend origin:
  `https://<STAGING_FRONTEND_HOST>/api/auth/google/callback`
- [ ] Do not use wildcards, path variants, trailing-slash alternatives, the
  API's private hostname, or the production URI. If Google requires an
  authorized JavaScript origin for the selected client configuration, add
  only `https://<STAGING_FRONTEND_HOST>`; never add a broad origin.
- [ ] Enable the Google OIDC `auth_time` behavior described in the readiness
  document for the staging client/project. Record the setting and verify the
  actual returned claim during step 6; configuration alone is not evidence.
- [ ] Store the client ID and secret only in the staging API secret store as
  `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Set
  `GOOGLE_REDIRECT_URI=https://<STAGING_FRONTEND_HOST>/api/auth/google/callback`
  and `GOOGLE_FRONTEND_ORIGIN=https://<STAGING_FRONTEND_HOST>`. Do not expose
  the secret through `NEXT_PUBLIC_*`, frontend build arguments, browser
  responses, or logs.

### 3. Prepare the staging database and apply migrations

The current candidate is a **28-file** migration inventory. The target for a
future, separately authorized migration is `0027_storage_lifecycle`;
`0028_storage_cleanup_leases` is provenance only and must remain unapplied.
The first operation is the authorized, read-only preflight—not a migration.
Use the development artifact referenced by
[the staging endpoint procedure](staging-endpoint-approval.md), never the
26-file checkout guard or the frozen guard.

- [ ] Prepare one owner-attributed authorization with `operation: preflight`,
  a unique ID, reason, active UTC window of at most 24 hours, exact Render
  resource/hostname/database/version, reviewed archive/manifest hashes, and
  the confirmed system CA path/hash. Adoption of the policy is not operation
  authorization.
- [ ] Load all three staging-only database URLs from the private staging
  secret store: migration login `vervfy_oauth_staging_user`, application login
  `app_runtime`, and lookup login `google_auth_lookup`. Do not paste or log
  passwords or full URLs. This local `check` validates URL identities and
  artifact hashes without connecting.
- [ ] Run `staging_guard.py check` from the exact 28-file development
  artifact. Only after it passes and the owner explicitly authorizes the
  hosted operation, run `staging_guard.py preflight` once. The SQL uses
  `BEGIN READ ONLY` and ends with `ROLLBACK`; review every catalog report.
- [ ] The expected role contract is enforced/reported by the preflight SQL:
  no runtime superuser or `BYPASSRLS`; no runtime schema/database creation;
  isolated `NOLOGIN` identity capability roles; `google_auth_lookup` alone
  inherits the restricted identity executor without `SET`/`ADMIN`; and the
  migration login has only the reviewed schema work and owner `SET` capability.
  The SQL also reports effective memberships, object/default ACLs, owners, and
  role/database settings. These are source expectations, not evidence that
  hosted roles already satisfy them. Stop on any mismatch.
- [ ] Do not migrate after preflight by implication. A separate `upgrade`
  authorization requires reviewed preflight output and a tested backup/restore
  or approved staging-recreation recovery path. Production OAuth stays off.

### 4. Verify Redis transaction behavior before live login

Use only staging API and its dedicated staging Redis. Record Redis service,
memory limit, eviction policy, and whether the provider permits observing or
changing those settings. Current `render.yaml` uses `allkeys-lru`; do not
assume staging has the same policy. Redis loss/eviction must deny an OAuth
attempt, never complete it from process memory.

- [ ] With OAuth still disabled, verify API can reach staging Redis and that
  staging sessions/rate limits use only that endpoint.
- [ ] Enable OAuth only for the isolated staging API/test group after sections
  1–3 are signed off; initiate a test flow and verify one transaction is
  created with the documented 600-second TTL, NX semantics, hashed state key,
  PKCE verifier/nonce, and browser binding. Do not put raw state, cookies, or
  tokens in tickets or logs.
- [ ] Complete the callback once; replay the same callback and submit two
  concurrent copies. Exactly one may consume the transaction; all others must
  fail closed and must not create another session/account or repeat linking.
- [ ] Start a flow in one browser profile and finish in another; try a changed
  browser-binding cookie and changed/missing state. Each attempt must fail
  closed. For link/reauth flows also test stale session ID/version and logout
  during the flow.
- [ ] Verify expiry: wait until the transaction's Redis TTL reaches zero (600
  seconds from creation), then submit the callback. It must fail. Do not edit
  TTLs in production-like code to shorten this test.
- [ ] On this isolated Redis only, test loss/eviction: remove or expire a
  test transaction through an approved method, then exercise the callback.
  It must fail closed with no identity lookup/session issuance. If testing
  memory pressure, use disposable staging resources and confirm effects on
  sessions are contained; never use shared Redis or `FLUSHALL`.
- [ ] During a test-only Redis outage, initiate/finish OAuth and verify the
  request returns a generic failure, leaks no infrastructure detail, and
  issues no session. Restore Redis and verify ordinary password login/session
  behavior recovers. Record exact response class/status without secret data.

### 5. Verify live Google OIDC and account lifecycle

- [ ] Use only an authorized staging test account and the exact callback URI.
  Verify successful login for an already-linked synthetic identity and a
  fresh Vervfy session. Confirm PKCE S256, state, nonce, issuer, signature,
  audience, expiry, subject, and verified-email policy are enforced by the
  backend. Do not log or copy authorization codes, ID/access tokens, nonce, or
  PKCE values.
- [ ] Test an unlinked Google identity: login must not auto-link by email.
  Signup must require username selection; an email conflict must stop account
  creation without revealing the existing account or silently merging data.
- [ ] Test explicit link from a password account: wrong/missing password fails;
  correct password plus fresh Google authentication links only the verified
  `(issuer, subject)` to that account. An identity already linked elsewhere
  must be rejected without moving data.
- [ ] Test unlink and password lifecycle: unlink is refused if it would remove
  the last usable login method; Google-only account password creation requires
  fresh provider authentication. Confirm credential changes rotate the active
  session, invalidate other sessions/proofs, and do not leave old sessions
  usable.
- [ ] For sensitive actions, capture only non-secret test evidence that Google
  returned a validated `auth_time` within 300 seconds after the configured
  `max_age=300`/essential claim request. Verify missing, stale, malformed, and
  more-than-60-seconds-future values are rejected. Do not substitute `iat`,
  callback time, account selection, or an old Vervfy session.
- [ ] Exercise JWKS key rotation with Google's live key set in staging. Confirm
  a valid token signed by a newly published trusted key succeeds after refresh;
  unknown key IDs, unsupported algorithms, bad signatures, and unavailable
  JWKS fail closed. Record key IDs and timing only if approved; never retain
  token material.
- [ ] Recheck current Authlib/dependency security advisories immediately before
  staging sign-off. Confirm the tested lockfile is the exact artifact deployed.

### 6. Verify proxy, cookies, CSRF, redirects, and logging

- [ ] Confirm the public frontend has HTTPS and `/api/:path*` reaches only the
  staging FastAPI origin. Verify callback query parameters pass through the
  Next.js rewrite unchanged, response status/Location and `Set-Cookie` headers
  are preserved, and no redirect uses an API/private origin or untrusted
  `Host`/forwarded header.
- [ ] Confirm `GOOGLE_REDIRECT_URI` exactly matches the Google Console value
  and the callback's public scheme/host/path. Use a top-level GET callback.
- [ ] Inspect browser cookie attributes: the browser-binding cookie is
  host-only `__Host-` with `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, no
  `Domain`, and short lifetime; `auralis_session` retains its existing secure,
  HttpOnly, Lax, 30-day policy. Confirm OAuth fails closed if SameSite is not
  Lax. Never expose session or binding cookies to JavaScript.
- [ ] Verify CSRF tokens are required for onboarding/account mutations, tied
  to the session, and rejected when missing/invalid. Test callback state and
  browser binding independently of CSRF.
- [ ] Confirm callback and account-action responses use `Cache-Control:
  no-store`, callback uses `Referrer-Policy: no-referrer`, and post-callback
  redirects go only to the clean configured frontend origin/path. Check
  browser history and referrer behavior after callback.
- [ ] Inspect API, Next.js, hosting, and reverse-proxy access/error logs with
  synthetic test requests. Query strings on callback may contain `code` and
  `state`: ensure those values, authorization headers, secrets, cookies,
  tokens, passwords, and CSRF values are redacted or excluded. If any appear,
  disable OAuth, restrict/delete the affected staging logs under the retention
  policy, and fix redaction before resuming.
- [ ] Verify proxy trust-hop count against the actual staging topology; do not
  trust arbitrary forwarded headers. Confirm generic user-facing errors do
  not reveal Redis, PostgreSQL, client secret, token validation, or account
  existence details.

### 7. Run password-auth and regression checks

- [ ] Verify existing username/password login and registration remain available
  while Google is enabled in staging. Test valid and invalid credentials,
  generic unknown-user/password errors, CSRF enforcement, rate limiting, and
  session creation.
- [ ] Verify password login rejects Google-only accounts without changing
  account state or revealing whether a password exists. Confirm password
  accounts can still use password paths for supported sensitive actions.
- [ ] Run the backend suite, OAuth/schema/security tests, disposable PostgreSQL
  privilege tests, frontend lint/type checks, and Google/account Playwright
  tests against the intended staging artifact. Track skipped tests explicitly;
  a mocked test is not evidence of live Google, Redis, proxy, or production
  role behavior.
- [ ] Exercise logout, logout-all, account deletion, and session-version change
  during and after an OAuth transaction. Confirm old cookies, in-flight
  transactions, and one-time reauthentication proofs cannot restore access.

## Rollback and containment

1. If any check fails or secrets/logs are exposed, immediately set
   `GOOGLE_OAUTH_ENABLED=0` on the **staging API**, restart/redeploy that API,
   and confirm `/api/config` advertises Google disabled and OAuth start routes
   no longer start a flow. This also prevents existing Google-only users from
   signing in until OAuth is restored. Do not change production settings.
2. Revoke/rotate the staging Google client secret if exposure is suspected.
   Remove staging OAuth secrets after the test window; never copy them into
   source or tickets. Preserve sanitized logs and evidence under the approved
   retention policy.
3. Keep migrations applied by default during feature rollback. Disabling OAuth
   does not require dropping schema. Do not downgrade 0021 while any provider
   identity or passwordless user exists: its downgrade takes exclusive locks
   and explicitly refuses those records. Do not drop data to force rollback.
4. A 0022 downgrade is a DBA-only staging action after OAuth is disabled, all
   lookup callers are stopped, and a verified snapshot exists. It removes the
   lookup function/policy/grants/schema but preserves identities; it must not
   use `CASCADE`. Recheck role state before any later downgrade. Restore only
   through the approved staging backup process.
5. Migration 0023 is forward-only because dropping its media columns can destroy
    data. Keep the migration applied during rollback; restore from an approved
    snapshot only if a database rollback is required.
6. Migration 0024 is forward-only because revoking runtime identity operations
   would break Google account flows. Keep it applied during feature rollback.
6. After containment, document the failure and owner, rotate only affected
   staging credentials, repeat the affected verification from the safest
   earlier step, and obtain a new operation-scoped owner authorization before
   resuming staging activity. Any external independence requirement still
   takes precedence.

## Production release gates

Staging success is not production approval. Keep production
`GOOGLE_OAUTH_ENABLED=0` until all are separately reviewed and evidenced:

- [ ] Production frontend origin and exact callback are approved, registered
  in the production Google client, and verified end to end.
- [ ] Production has isolated OAuth secrets, Redis, database credentials, and
  a reviewed capacity/eviction policy; no staging credentials or identities
  are reused.
- [ ] DBA approves production migration-chain state, backup/restore, 0021-0024
  role preflight, ownership, RLS, executor membership, TLS, and rollback plan.
  Apply migrations only in a separately authorized release window; this
  runbook does not authorize them.
- [ ] Live Google `auth_time`, JWKS refresh/rotation, exact issuer/audience,
  browser callback cookies, CSRF, no-store/referrer policy, log redaction,
  session invalidation, and provider/Redis outage behavior pass in the approved
  production-like staging environment.
- [ ] Password login/registration, account isolation, onboarding/link/unlink,
  email conflicts, passwordless account controls, and account deletion pass
  regression review.
- [ ] Security, product, operations, and DBA owners sign off; a monitored
  enablement/disable procedure, incident owner, support/recovery guidance,
  and rollback decision are documented.

**Safest sequence:** isolate staging → register a distinct Google client →
preflight and migrate staging DB → verify role boundaries → test Redis failure
semantics → enable OAuth only in staging → verify live Google and HTTP boundary
→ run password/account regressions → obtain sign-offs. Production enablement is
a separate later decision.
