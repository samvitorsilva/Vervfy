# Vervfy — Google OAuth Production Release Gate

**Assessment date:** 2026-11-07  
**Recommendation:** **NO-GO for production Google OAuth**  
**Scope:** Source/configuration review and isolated local tests only. No production or hosted database, Storage, Redis, user account, migration, or deployment was accessed.

## 1. Executive summary

Google OIDC is implemented and defaults to disabled. The inspected flow uses
Authorization Code with S256 PKCE, Redis-backed one-time state and browser
binding, nonce checks, ID-token validation, exact configured callback
constraints, explicit subject-based linking, and session rotation. Local
PostgreSQL role/RLS and Redis tests passed.

Do not set `GOOGLE_OAUTH_ENABLED=1` yet. The code review and local tests cannot
prove the production database roles/grants, provider callback registration,
Render proxy/cookie behavior, managed Redis policy, backup restoration, or a
live Google signing-key rotation. The checked-in Render blueprint is a free
development-sized configuration, has no PostgreSQL resource, and must not be
deployed unchanged as a production topology. Keep OAuth disabled until the
blockers in section 4 are evidenced in isolated staging and approved for
production.

## 2. Verified implementation status

| Area | Source evidence and status |
|---|---|
| OAuth protocol | `google_oauth.py:416-504` validates Google discovery metadata, requests authorization-code flow with `code_challenge_method="S256"`, stores the verifier, state, nonce, purpose, issue time, and browser-binding digest. `google_oauth.py:506-602` atomically consumes the transaction, rejects expiry/replay, exchanges the code with the verifier, and validates signed ID-token claims. |
| Signature, issuer, audience, time, nonce | `google_oauth.py:416-438, 534-629` pins the expected Google issuer/endpoints and RS256, delegates ID-token parsing to Authlib, checks issuer/audience/authorized party/nonce/subject and expiry/issued-at/future timestamps, and applies clock skew. Unit tests use synthetic signed tokens and reject bad signatures and claims; they do not prove a live Google callback or key rotation. |
| Fresh authentication | Sensitive account flows request `prompt=login`, `max_age`, and essential `auth_time` (`google_oauth.py:468-480`); `google_oauth.py:645-657` requires a recent authentication. This is enforced for Google-only sensitive actions, not ordinary sign-in. |
| Callback and browser binding | `google_oauth.py:112-205` requires the callback path and frontend origin to match, requires HTTPS in production, and requires a distinct PostgreSQL lookup principal. `server.py:1520-1546, 1771-1925` binds transactions to an HttpOnly, Secure-on-HTTPS, SameSite=Lax cookie and never derives the redirect from forwarded request headers. Google Console registration of the exact production URI remains external and unverified. |
| Account linking and email | `auth.py:216-307` links by Google subject only, requires the existing account password, rejects an already-linked identity, and preserves the existing password hash. `auth.py:171-214` does not use email as an identity key; signup only stores email when Google marks it verified. No automatic email-based linking was found. |
| Passwordless and sensitive actions | `server.py:2392-2412, 2455-2520` requires the existing password for password-backed actions, and a purpose/session/version-bound, one-time fresh Google proof for Google-only password add, email change, logout-all, or deletion. Unlink requires a password and refuses to remove the last sign-in method (`auth.py:257-307`). |
| Sessions and logout | `auth.py:534-664` keeps an allowlisted session in Redis, a reverse user-session index, and fail-closed Redis errors. `server.py:1307-1339, 1820-1878, 2414-2428` checks session version and rotates sessions after authentication/linking. Logout revokes the active session (`server.py:1979-2014`); logout-all bumps the database version and revokes account sessions (`server.py:2485-2503`). |
| CSRF and throttling | `auth.py:667-688` uses a session-bound CSRF token for form and API mutations. `server.py:206-285` rate-limits auth/OAuth/mutation endpoints and returns 503 if the configured limiter is unavailable. Production startup requires `REDIS_URL` (`server.py:159-163`); no production in-memory fallback is used when configured. |
| PostgreSQL / tenant isolation | `db.py:92-107` sets transaction-local tenant context. RLS is enabled and forced for tracks/favorites/playlists/playlist tracks (`0007_row_level_security.py`), upload jobs (`0008_upload_jobs.py`), artist photos (`0015_artist_photos.py`), listening history (`0019_track_listens.py`), and provider identities (`0021_provider_identities.py`). Migration `0022_provider_identity_lookup.py` restricts pre-login lookup to a separate executor capability; `0024_provider_identity_runtime_access.py` limits normal runtime identity writes. Local disposable role/RLS tests passed; the hosted role graph is unknown. |
| Deletion and privacy | `server.py:2522-2601` confirms the account, advances session version, revokes Redis sessions, deletes tenant rows, and returns `storage_cleanup=pending`. Physical Storage deletion is intentionally not active; see deferred item C1. `render.yaml:13` disables Uvicorn access logs. No OAuth code, token, password, cookie, or session ID logging was found in the OAuth handlers; general application logs still need deployment-side redaction/retention review. |
| Frontend | `web/src/components/auth/auth-form.tsx` shows Google only when `/api/config` reports it enabled and uses the same-origin API path. `web/next.config.ts:25-34` rewrites `/api/*` to `BACKEND_URL`. `web/src/components/account-settings.tsx` implements explicit link/reauth flows and account-scoped offline cleanup. Google-specific browser tests are absent from this worktree. |

## 3. Production configuration requirements

Set values only in the appropriate provider secret store; this report lists
names, not values.

| Service | Required settings |
|---|---|
| API auth/runtime | `VERVFY_ENVIRONMENT=production`, `VERVFY_SECRET_KEY`, `VERVFY_HTTPS_ONLY=1`, `VERVFY_COOKIE_SAME_SITE=lax`, verified `VERVFY_TRUSTED_PROXY_HOPS`, `DATABASE_URL` using the restricted `app_runtime` principal, and a production-grade `REDIS_URL`. |
| Google OAuth (API only) | `GOOGLE_OAUTH_ENABLED=0` through deployment and pre-enable checks; then `GOOGLE_CLIENT_ID`, secret-store-only `GOOGLE_CLIENT_SECRET`, exact `GOOGLE_REDIRECT_URI`, matching `GOOGLE_FRONTEND_ORIGIN`, and secret-store-only `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` using the dedicated lookup-executor login. Keep all Google credentials off the frontend and out of `NEXT_PUBLIC_*` variables. |
| Database operations | `MIGRATION_DATABASE_URL` only in an approved one-off migration process; never in the API runtime environment. Run the reviewed target `0027_storage_lifecycle`, not `head`, unless a separately approved release explicitly changes that target. |
| Storage | `SUPABASE_URL`, secret-store-only `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`, and the reviewed `VERVFY_STORAGE_NAMESPACE_ID`; confirm the bucket is private and staging/production credentials and namespaces are separate. |
| Frontend | `BACKEND_URL` for the production API. Set `SITE_URL` when the provider URL is not the canonical frontend origin. `FRONTEND_URL` is only needed if direct cross-origin browser-to-API requests are deliberately enabled; the normal same-origin rewrite does not require it. |

The `.env.example` placeholder now names `app_runtime`, not a database-owner
login. The Render Key Value policy was changed from `allkeys-lru` to
`noeviction`: silent eviction could clear session, rate-limit, or OAuth
transaction keys. `noeviction` turns memory exhaustion into write failures;
the application must still be given adequate capacity and monitored.

## 4. A. Launch blockers

| Severity | Finding and required evidence |
|---|---|
| **HIGH** | **Production database and authorization are unverified.** Local PostgreSQL tests do not establish production ownership, role membership, grants, forced RLS, or whether the deployed `DATABASE_URL` is actually `app_runtime`. Before launch, an authorized DBA must review the production role graph, run read-only preflight, confirm `app_runtime` is non-owner/non-superuser/non-BYPASSRLS, verify only the dedicated lookup login has lookup execution, apply only the approved migration target, and run postflight checks. Evidence: `alembic/versions/0022_provider_identity_lookup.py`, `0024_provider_identity_runtime_access.py`, `0026_application_runtime_grants.py`, `0027_storage_lifecycle.py`, `staging_guard.py:13-17, 120-160`. |
| **HIGH** | **No live isolated-staging sign-off exists in this assessment.** No production Google client or hosted callback was used. Complete staging with a separate Google client and synthetic accounts; verify S256, state/nonce/replay rejection, real signature verification, key rotation, `auth_time`, callback/cookie/proxy behavior, login/signup/link/unlink/passwordless actions, and Redis/DB outages. Register the exact frontend callback in Google Cloud. Only then can the production release owner authorize the flag change. Evidence: `google_oauth.py:416-657`, `docs/google-oauth-staging-runbook.md`, `docs/google-oauth-readiness.md:594-648`. |
| **HIGH** | **Current Render blueprint is not production-ready.** `render.yaml:1-66` declares free API, web, and Redis services, has no PostgreSQL resource, and leaves externally supplied connection URLs unset. The free Key Value service is documented as restart-volatile and unsuitable for retained production sessions; `noeviction` prevents LRU eviction but not restarts, outages, or exhaustion. Provision and verify production-grade API/web/database/Redis/Storage resources, capacity, alerting, and private networking before OAuth enablement. Do not deploy this blueprint unchanged. |
| **HIGH** | **Backup and restoration are not evidenced.** Before migration, create a provider-supported, access-controlled backup and test restoration to an isolated non-production database. No backup, restore, or production recovery test was attempted. Evidence: `docs/google-oauth-readiness.md:594-640`; this is an operational gate, not something source tests can prove. |
| **HIGH** | **Feature toggle must remain off until all above gates pass.** The code and Render default set OAuth disabled (`google_oauth.py:112-119`, `render.yaml:41-42`); retain `GOOGLE_OAUTH_ENABLED=0` during deploy and migration. No approval or enablement was performed. |

The reviewed release migration target remains `0027_storage_lifecycle`.
Migrations `0028`–`0031` were not edited or applied; keep them outside this
OAuth rollout unless separately approved. The local staging source-manifest
guard expected 28 files while this worktree contains 31 migrations; its count
was aligned to 31 without changing the guarded migration target. The manifest
and guard tests now pass.

## 5. Security findings

| Severity | Finding | Source evidence / disposition |
|---|---|---|
| **MEDIUM** | **Redis availability is a shared authentication dependency.** Sessions, throttles, OAuth transactions, and reauthentication proofs share Redis. Redis errors fail closed, but capacity exhaustion/restart can deny sign-in, erase limiter state, and invalidate sessions. The blueprint now uses `noeviction`; production capacity, restart behavior, persistence, alerting, and recovery still require staging/provider verification. | `auth.py:73-126, 534-664`; `google_oauth.py:236-378`; `render.yaml:1-6`. |
| **MEDIUM** | **Deletion does not physically erase Storage objects yet.** The database deletion commits cleanup obligations and reports pending; the account-deletion checklist explicitly says no production cleanup adapter or erasure-status surface exists. Treat this as deferred only if the published privacy/retention commitments permit it and the cleanup obligation is monitored. If those commitments promise immediate physical erasure, this becomes a launch blocker. | `server.py:2522-2601`; `docs/account-deletion-production-checklist.md:4-6, 66-100`; `storage_lifecycle.py`. |
| **MEDIUM** | **Logging and retention policy need operator confirmation.** Uvicorn access logging is disabled, and no OAuth handler logs secrets. Other application paths log track identifiers, artist names, and exception traces; verify provider log access/retention and redact personal data and connection details. | `render.yaml:13`; `server.py` application log calls; `cover_art.py` lookup logs; `storage_lifecycle.py:182` avoids provider messages/credential-bearing exception chains. |
| **LOW** | **Readiness endpoint is liveness-only.** Render checks `/healthz`, which returns a constant “ok” and does not check PostgreSQL or Redis. Add dependency-aware monitoring/alerts or an external synthetic check; do not make a dependency outage look like a healthy customer experience. | `render.yaml:14`; `server.py:2604-2612`. |
| **LOW** | **CI does not mirror the locked production backend install.** Render installs `requirements.lock` with hashes, while CI installs `requirements.txt` and sets SQLite; PostgreSQL/Redis integration coverage is therefore not guaranteed on every CI runner. The local test run below used the lock and disposable services. Consider making CI use the lock and provision explicit isolated PostgreSQL/Redis services. | `.github/workflows/ci.yml:10-22`; `render.yaml:13`; `requirements.lock`. |

## 6. Test results

Executed locally on Python 3.12.7 with the hash-locked backend dependencies,
sanitized environment, synthetic data, disposable Unix-socket PostgreSQL
clusters (TCP disabled), and a private Unix-socket Redis process:

| Check | Result |
|---|---|
| Full backend pytest suite | **360 passed**, **319 subtests passed**, **0 skipped**, **0 failing**; 24 warnings (existing Alembic `path_separator` deprecations and deliberate Pillow decompression-boundary warnings). Includes Google OAuth/security, PostgreSQL roles/RLS/migrations, Redis atomic replay/expiry/outage, session/account regressions, and storage isolation tests. |
| Mocked OAuth rejection cases | Passed: bad signature, nonce/audience/issuer/time checks, replay, invalid/unlinked identity, and stale/missing `auth_time` are expected-denial test cases, not test failures. |
| Frontend lint | **0 errors**, 17 existing Next.js/style warnings. |
| TypeScript | `npx tsc --noEmit`: **passed**. |
| Frontend production build | **passed** with synthetic `BACKEND_URL` and `SITE_URL`. |
| Playwright authentication smoke | **3 passed** against the built local frontend and synthetic mock backend: CSRF-token load, login error display, and registration password guidance. |
| Google-specific Playwright / account-isolation browser tests | **Not run**: no Google-auth or account-isolation Playwright spec exists in this selected worktree. No live Google credentials were used. |
| Render blueprint | YAML parsed; asserted OAuth default is disabled and Redis policy is `noeviction`. |
| Ruff | Changed staging/test files pass with the existing `I001` and `UP017` diagnostics in `staging_guard.py` excluded. A normal Ruff check reports those three pre-existing import-order/UTC-style findings; they were not broadened into this release task. |
| GitHub Actions / hosted tests | Not run. No CI workflow, hosted callback, production database, production Storage, migration, or deployment was invoked. |

Two initial backend test failures were resolved narrowly before the final
360-test pass: the staging execution-manifest count was stale, and the provider
host regression guard treated three documentation citation hosts as runtime
providers. The guard still pins staging migration execution to `0027`.

## 7. Exact deployment prerequisites

1. Select and freeze the reviewed source artifact; confirm its migration
   manifest and current production revision. Keep `0028`–`0031` unapplied for
   this release.
2. Obtain DBA and release-owner approval. Use separate migration, `app_runtime`,
   and `google_auth_lookup` principals; verify role attributes, memberships,
   table/function grants, RLS, TLS, and the exact database identity. Do not use
   the migration principal or database owner as API credentials.
3. Verify a restorable backup and retention/access controls before migration.
4. Provision production-grade Render/API/frontend, PostgreSQL, Redis, and
   private Storage resources; use adequate Redis memory with `noeviction` and
   provider-appropriate durability/monitoring. Confirm the trusted proxy hop
   count rather than copying the example blindly.
5. Configure the variable names in section 3 in their correct service scopes.
   Keep Google secrets and lookup credentials on the API only; keep `BACKEND_URL`
   and optional canonical `SITE_URL` on the frontend.
6. Deploy with OAuth disabled. Run the authorized one-off Alembic operation to
   `0027_storage_lifecycle`; verify the resulting revision and postflight role,
   RLS, schema, and lookup-function checks. Do not use `alembic upgrade head`.
7. Verify HTTPS, Secure/HttpOnly/Lax host cookies, same-origin rewrite,
   forwarded-client-IP behavior, API/Redis/database health, private Storage,
   no access logs containing auth query strings, and log redaction.
8. Complete live staging verification with synthetic accounts, including
   password login preservation, Google signup, no email-based linking, explicit
   linking, unlink safeguards, passwordless sensitive actions, logout/logout-all,
   deletion behavior, Redis/DB outage fail-closed behavior, and key rotation.
9. Obtain explicit release approval to set `GOOGLE_OAUTH_ENABLED=1`; perform a
   single synthetic canary login and signup, then verify password login,
   linking, revocation, and logs. Keep a rollback ready to set the flag back to
   `0`; do not downgrade identity migrations or deploy password-only code after
   Google-only accounts exist.

## 8. Post-deployment verification plan

After an approved deployment, use only a newly created synthetic canary
account. Verify the exact callback, Secure/HttpOnly/SameSite=Lax cookies,
session rotation, stable login across restart, logout and logout-all revocation,
password login, signup, link/unlink guards, and fresh Google proofs for
sensitive actions. Verify the API runtime cannot execute the pre-login lookup,
cannot access another tenant's rows, and cannot bypass forced RLS. Confirm
Redis/database failure produces controlled denial rather than fallback
authentication. Review provider and application logs for OAuth codes, tokens,
cookies, passwords, database URLs, session identifiers, or unnecessary personal
data. Check backup/restore monitoring and the deletion cleanup queue without
enumerating or accessing unrelated user records.

## 9. C. Deferred features

These are not launch blockers by themselves: an operator control plane,
trustee/bootstrap workflow, independent audit infrastructure, and physical
Storage cleanup. No operator endpoint or bootstrap identity is required by the
Google OAuth flow. Physical cleanup is different only where a specific privacy
promise or legal requirement requires it before launch; see the conditional
medium finding above. Do not apply migrations `0028`–`0031` as part of this
OAuth release.

## 10. Go / no-go

**NO-GO today.** The shortest safe path is: complete isolated live staging;
provision and independently verify production PostgreSQL roles/RLS, backup,
Redis, proxy, and secret configuration; deploy with OAuth disabled; apply only
the approved migration target; obtain explicit release approval; then enable
OAuth for a canary and verify the flows. No hosted verification is authorized
by this assessment. No commit, push, merge, production change, or frozen
candidate modification was performed.
