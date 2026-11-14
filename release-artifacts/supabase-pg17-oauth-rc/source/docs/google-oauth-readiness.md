# Google OAuth readiness

> Release instruction update: apply only `0027_storage_lifecycle`; keep 0028
> unapplied. Earlier audit results below are historical evidence. Current role,
> metadata and approval requirements are in `staging-db-initialization-runbook.md`;
> namespace setup is in `storage-namespace-initialization.md`. Older approval
> hashes do not authorize this candidate. No hosted execution is authorized.

Google OIDC login, signup onboarding, account linking, reauthentication, and
account settings are implemented. OAuth remains disabled unless
`GOOGLE_OAUTH_ENABLED=1` is explicitly configured. Existing password login and
the signed `auralis_session` cookie, Redis-backed session allowlist,
session-version checks, and session-bound CSRF tokens remain in place.

## Integration boundary

Treat Google as an additional way to prove identity, not as a replacement for
Vervfy sessions. Validate the OpenID Connect response server-side (issuer,
audience, signature, expiry, nonce, and state), use Authorization Code with
PKCE, and create a fresh Vervfy session after successful authentication. Rotate
the session ID, revoke any prior session being replaced, and set the current
database `session_version` in the new session. Keep the existing cookie flags,
session allowlist, expiration, and CSRF checks. Protect the callback against
login CSRF with one-time state and nonce values bound to the initiating browser
session; do not accept state from an untrusted redirect parameter alone.

## Linking and duplicate-account protection

Do not link accounts merely because an email string matches. Require a verified
Google email claim from the expected issuer, but also require proof of control
of the existing Vervfy account and a fresh Google authentication in the same
explicit linking flow. For password accounts, require the current password
before linking. Enforce uniqueness for `(issuer, subject)` and for any email
claim relied on by the product in the database transaction; handle conflicts
without silently merging accounts. Never let a Google identity take over an
existing password account just by presenting its email.

Represent provider identities separately from user profile email (for example,
with a provider/subject table) rather than overloading the unique email field.
Decision: Google-only accounts will have a nullable `users.password_hash`.
Preserve existing hashes and update every password-dependent path to handle
absence safely. Password login must reject accounts without a password with
the normal generic failure; do not insert dummy credentials or weaken password
verification. The local model now allows null hashes and migration 0021 prepares
the database change; production schema state has not been checked or changed.

New Google users must choose a unique username before account creation is
completed. Enforce the existing username rules and database uniqueness,
including concurrent submissions. Keep pending onboarding bound to the
validated Google identity and initiating browser with a short expiry.

Explicit Google linking requires current-password verification followed by
fresh Google authentication in the same flow. Reject identities already linked
to another account without merging users or moving their data. Email matches
never authorize linking. An existing-email conflict stops new-account creation
and requires signing into the existing account and explicitly linking Google.
Do not create a duplicate account, overwrite profile data, or reveal the existing
account's username or login methods in the conflict response. Already-linked
identities are resolved by `(issuer, subject)`, not by their current email claim.

Prevent removal of the last login method, enforcing this invariant transactionally
so concurrent credential changes cannot strand an account. Unlinking requires
fresh authentication and a remaining usable login method.

## Reauthentication for sensitive actions

Account deletion, password changes, and security-sensitive account changes
must continue to require recent proof of control. For password accounts, retain
the current-password check. For Google-only accounts, require a fresh provider
reauthentication (and validate its recent authentication time) before those
actions; do not treat an old Vervfy cookie or a previously linked identity as
fresh proof. During provider outages, users with a previously configured password
can use password authentication. Google-only users must restore provider access
or wait for service restoration; no authentication bypass is provided. There is
no automatic recovery through unverified email, and verified email alone does
not authorize recovery or linking. Additional recovery mechanisms are outside
this initial scope and require a separate security design.

Decision: Google-only users may add a password after fresh Google authentication
for their already-linked identity. Validate and hash the new password using the
existing password policy. Bind the reauthentication proof to the account,
session, and intended action, expire it promptly, and consume it once. Require
fresh authentication for deletion, email changes, password addition/change,
and provider linking/unlinking. Password-bearing accounts retain the current
password check; linking additionally requires fresh Google authentication.

Sensitive actions require authentication within five minutes (300 seconds),
tracked server-side in Redis rather than trusted from browser input or cookie
timestamps. Store the verified authentication time, method, user ID, session ID,
session version, and intended action. Check age and session validity at action
execution and atomically consume the proof. Expiry, logout, credential changes,
deletion, or missing server-side state invalidate it. Password proof starts at
successful password verification. Google proof must use validated recent
`auth_time` for the expected linked subject; callback arrival does not establish
freshness. Request fresh provider authentication with the appropriate OIDC
parameters and reject missing, stale, or implausibly future authentication times.
An account-selection screen or newly issued token alone is insufficient.
Google support for the required request/claim contract remains a verification
gate; do not weaken the five-minute requirement if it cannot be demonstrated.

## Session revocation and logout-all

Continue checking the Vervfy session ID against the server-side allowlist and
the cookie's session version against the database on every authenticated
request. Logout must revoke the current Vervfy session. Logout-all and
credential/security changes must advance `session_version` so old cookies stop
authenticating, and should remove associated server-side session entries when
possible. Provider tokens should not be retained unless a specific feature
requires them; if retained, protect, expire, and revoke them independently of
the Vervfy session.

Decision: security-sensitive account changes invalidate all other sessions.
Advance the database session version with the credential/security change and
rotate the surviving current session, revoking replaced IDs and cleaning up
other allowlist entries. Deletion and logout-all leave no surviving session.
Ensure in-flight OAuth and reauthentication transactions cannot restore access
using a stale session version after revocation or deletion.

## Implementation and release plan

1. **Finalize contracts and configuration.** The server-only settings are
   listed in `.env.example`; Google registration, deployed callback hostname,
   proxy/log redaction, and Google's `auth_time` behavior remain verification
   gates. Keep `GOOGLE_OAUTH_ENABLED=0` until those gates and the acceptance
   criteria pass.
2. **Schema and credential safety.** The worktree contains migrations 0021
   through 0024, nullable password support, and restricted `(issuer, subject)`
   lookup. Migration 0024 grants `app_runtime` only the SELECT, INSERT, and
   DELETE rights needed for tenant-scoped identity operations; forced RLS
   remains the boundary between accounts.
   Local SQLite and disposable-PostgreSQL tests cover preservation, isolation,
   and grants. No production migration has been run; review DBA roles and
   production grants before a separately authorized migration.
3. **OIDC and session integration.** The backend is implemented in
   `google_oauth.py` with disabled-by-default start/callback routes in
   `server.py`. It uses
   Authlib's lower-level client for Authorization Code + S256 PKCE, keeps
   state/nonce/verifier and browser binding in 600-second Redis transactions,
   consumes each transaction atomically, validates Google ID tokens, performs
   restricted identity lookup only after validation, and issues a fresh
   Vervfy session. Missing configuration leaves the routes disabled; Redis and
   token failures fail closed. Only already-linked identities can sign in.
4. **Account lifecycle and UI.** Username onboarding, explicit linking,
   password addition, unlink safeguards, fresh authentication, session
   invalidation, and provider-identity deletion are implemented. The login,
   signup, and account-settings UI preserve password flows. The Next.js
   `/api/:path*` rewrite proxies OAuth endpoints to FastAPI.
5. **Mocked verification and release review.** `tests/test_google_oauth.py`
   covers mocked code exchange, PKCE, signed ID-token validation, invalid
   audience/signature/nonce/expiry, browser binding, expiry/replay/concurrency,
   identity isolation, and unchanged password login/registration. No live
   Google request is made. Complete the remaining account-lifecycle, proxy,
   Google `auth_time`, and production-role checks before enablement.

## Phase 2 technical decisions

### Authlib and dependencies

Use Authlib's OAuth/OIDC client APIs. As reviewed **2026-11-02**, Authlib
**1.9.2** is published, not yanked, and latest on PyPI. Recommended dependency
constraint: **`Authlib>=1.9.2,<2`**, with the exact tested version locked and
advisories rechecked before release. PyPI metadata requires Python >=3.10,
`cryptography>=45.0.1`, and `joserfc>=1.6.8`; all resolve on Python 3.12.7.

An isolated Python 3.12.7 environment resolved Vervfy's `requirements.txt` plus
Authlib and HTTPX2 to this tested snapshot: Authlib 1.9.2, FastAPI 0.162.0,
Starlette 1.10.0, cryptography 50.0.2, joserfc 1.7.7, httpx2 2.16.0, and
httpx 0.28.1. All 43 resolved distributions installed and `uv pip check`
reported no conflicts. FastAPI `TestClient` returned 200 using this Starlette.
Authlib, Starlette OIDC, FastAPI, and both HTTP client imports succeeded.
This tests the current resolver-selected graph, not every version permitted by
the broad lower bounds in `requirements.txt`.

The GitHub advisory feed for PyPI/Authlib was checked on this date. The listed
affected ranges are below 1.9.2, including:
[CVE-2026-114616](https://github.com/advisories/GHSA-8m4g-j4wp-wgcg) (empty
HMAC verification key; fixed 1.9.1),
[CVE-2026-114620](https://github.com/advisories/GHSA-x4rv-c3wx-4cr8) (unsafe
JAR `request_uri`; fixed 1.9.0),
[CVE-2026-114617](https://github.com/advisories/GHSA-c5mf-xmp2-59rc) (ID-token
`nonce_supported` can disable nonce validation; fixed 1.9.0),
[CVE-2026-116672](https://github.com/advisories/GHSA-c73q-w75p-j82v)
(unsafe RFC 7592 examples; fixed 1.9.1), and
[CVE-2026-27962](https://github.com/advisories/GHSA-wvwj-cvrp-7pv5) (JWS
JWK-header injection; fixed 1.6.9). Other older `alg=none` and asymmetric
algorithm-confusion advisories are also fixed before 1.9.2. The patched version
does not make arbitrary JWT usage safe: pin a trusted asymmetric algorithm,
resolve keys only from trusted Google JWKS, reject unresolved keys and
token-supplied JWKs, and explicitly enforce all product-required claims. Do not
use Authlib's authorization-server, JAR, or dynamic-registration APIs for
sign-in.

Authlib's official FastAPI/Starlette client documentation covers Google OIDC
discovery, Authorization Code, S256 PKCE, nonce, and ID-token parsing.
Isolated smoke tests created a Google authorization URL with fixed state and
nonce and an S256 challenge, verified the verifier stayed out of the URL and
was sent in a mocked token exchange, and validated a locally signed RS256 ID
token (signature, issuer, audience, expiry, nonce). A wrong nonce was rejected.
`email_verified` is surfaced but not enforced as Vervfy's account policy; the
application must check it explicitly. No live Google request was made.
The test also confirmed an ID-token `nonce_supported=false` claim cannot disable
nonce validation in 1.9.2 (CVE-2026-114617).

Do not use Authlib's Starlette `authorize_redirect` /
`authorize_access_token` state flow for these routes: its implementation reads
and clears `request.session`, and its cache option still depends on a
session-bound marker rather than Vervfy's atomic Redis consumption. The tested
lower-level `AsyncOAuth2Client` creates the authorization URL and fetches the
token without accessing a Starlette request/session; supply the Redis-stored
state, nonce, and PKCE verifier explicitly, then invoke ID-token validation
with the expected nonce and trusted metadata/JWKS. This preserves the designed
Redis transaction boundary.

Authlib 1.9.2 has a deprecated fallback to `httpx`; `requirements.txt`
explicitly includes `httpx2>=2,<3` and the hashed Python 3.12.7
`requirements.lock` pins the tested dependency graph. CI and Render install
from the hash-verified lock. Keep FastAPI/Starlette's tested compatible pair
locked and recheck advisories when refreshing it.

References: [Authlib 1.9.2 on PyPI](https://pypi.org/project/Authlib/1.9.2/),
[v1.9.2 release](https://github.com/authlib/authlib/releases/tag/v1.9.2),
[Authlib FastAPI integration](https://docs.authlib.org/en/stable/oauth2/client/web/fastapi.html),
[Starlette OIDC integration](https://docs.authlib.org/en/stable/oauth2/client/web/starlette.html),
[Authlib HTTPX2 client](https://docs.authlib.org/en/stable/oauth2/client/http/httpx.html),
[Authlib advisories](https://api.github.com/advisories?ecosystem=pip&affects=authlib&per_page=100).

### Redis OAuth transactions and replay

Create random 256-bit state, nonce, PKCE verifier, and browser-binding values;
send S256 PKCE. Store only a hash of state in a namespaced Redis key and keep
the verifier, nonce, purpose, issue time, browser-binding digest, and (for
link/reauth) user ID, session ID, and session version in its value. Set the key
with `NX` and a **600-second TTL**. Keep the opaque browser-binding cookie
HttpOnly and host-only for at most 600 seconds. Bind state to that cookie and
the initiating authenticated session for link/reauth; bind purpose and any
post-login destination server-side, never from callback parameters.

On callback, an atomic Redis Lua operation compares the binding and deletes the
transaction before exchanging the code; exactly one concurrent callback may
consume it. Then validate the ID-token nonce and PKCE exchange. Expired,
missing, mismatched, already-consumed, or backend-unavailable transactions
fail closed and require a new attempt; there is no process-memory fallback in
production. Recheck session validity/version before accepting a link or
reauthentication result. A 600-second login transaction does not extend the
separate 300-second sensitive-action proof.

### `auth_time` and safe reauthentication

Google's OIDC documentation says `auth_time` is returned when explicitly
requested as an essential ID-token claim and enabled in Google sign-in security
settings. For reauthentication request both `max_age=300` and
`claims={"id_token":{"auth_time":{"essential":true}}}`.
The claim reports when Google last authenticated the user; it is not guaranteed
merely by a fresh code/token exchange. `prompt=select_account` selects an
account, and `prompt=consent` re-consents; neither proves fresh credential
entry. Enable the Google setting and demonstrate a recent claim after a
reauthentication request before enabling Google-only sensitive actions. OIDC
Core defines `max_age`; Google deployment testing must demonstrate it honors
the request. If Google omits or does not refresh the claim, do not substitute
`iat`, callback time, account selection, or the Vervfy session.

Accept only a validated integer `auth_time` no older than **300 seconds** and
no more than **60 seconds in the future**; use the same 60-second maximum skew
for ID-token time validation. A timestamp within future skew counts as age zero.
Missing, stale, malformed, or implausibly future values reject the action.
Password accounts may use their current-password path. Google-only accounts
receive no bypass: deny the action and require
successful provider reauthentication or a separately designed recovery
mechanism. OIDC Core requires `auth_time` when `max_age` is requested; the
claim remains the server-validated evidence and `max_age` is not accepted as a
substitute for a fresh timestamp.

References: [Google OIDC claims and request parameters](https://developers.google.com/identity/openid-connect/openid-connect),
[OpenID Connect Core `auth_time`](https://openid.net/specs/openid-connect-core-1_0.html#IDToken).

### Callback URL, proxy, and cookies

The exact public callback **path** is
`/api/auth/google/callback` (HTTPS GET, authorization-code query response).
The public URI is
`https://<configured-public-frontend-origin>/api/auth/google/callback`; its
hostname is a per-environment deployment value not present in the worktree and
must be explicitly set and registered in Google Cloud. Local development may
use `http://localhost:3000/api/auth/google/callback`. Configure one
`GOOGLE_REDIRECT_URI` per environment and use that identical value for both
authorization and token exchange. FastAPI must serve the same `/api/...` path:
the existing Next.js `/api/:path*` rewrite proxies it to `BACKEND_URL`. Never
construct the URI from Host/forwarded headers or use the API service's private
origin. The configured frontend `SITE_URL`/public origin and callback host must
match.

Keep the browser flow same-origin through Next.js. Use a host-only
`__Host-`-prefixed browser-binding cookie with `Secure`, `HttpOnly`,
`SameSite=Lax`, `Path=/`, and no `Domain`; leave the existing
`auralis_session` cookie defaults (`HttpOnly`, HTTPS-dependent `Secure`,
`SameSite=Lax`, 30-day lifetime) unchanged. Use a top-level GET callback, not
`form_post`, so Lax cookies are sent; OAuth-enabled deployments must use
`VERVFY_COOKIE_SAME_SITE=lax` (Strict would omit the session cookie on callback,
and None is unnecessary). Local HTTP development needs a separate
non-`__Host-` cookie; production must use HTTPS. Verify the Next rewrite
preserves callback query parameters and `Set-Cookie` headers. Callback
responses must use `Cache-Control: no-store`, avoid referrers, redirect to a
clean allowlisted frontend path, and redact authorization codes/tokens from
application and proxy logs. Never return provider tokens to browser JavaScript.

Deployment configuration belongs only on FastAPI: server-side
`GOOGLE_CLIENT_ID`, secret-store `GOOGLE_CLIENT_SECRET`, exact
`GOOGLE_REDIRECT_URI`, and the public frontend origin. Do not add provider
secrets to Next.js public/build-time variables. Production requires Redis; an
evicted or lost transaction is a failed login, never a successful fallback.

### Migration 0022 deployment roles

Provision `vervfy_identity_lookup_owner` and `vervfy_identity_lookup` before
migration 0022, both `NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB
NOCREATEROLE NOREPLICATION`. The owner role must have no memberships; only the
migration principal may be its member. Run the migration transactionally in the
application schema with a current role that owns `provider_identities` and is a
member of the lookup-owner role (or `SET ROLE` to a table-owner role with those
same conditions). That principal needs `CREATE` on the database for
`vervfy_auth`. Migration 0022 grants the owner only
schema `USAGE` and column `SELECT` on `issuer`, `subject`, and `user_id`, adds
its SELECT-only RLS policy, transfers function ownership, and removes the
owner's temporary schema `CREATE`.

The executor role receives only private-schema `USAGE` and function `EXECUTE`;
it gets no table access. Its only membership must be the dedicated
`google_auth_lookup` login with `INHERIT TRUE`, `SET FALSE`, and `ADMIN FALSE`.
That login must have no other memberships and no nested members, so other roles
cannot inherit or SET into the lookup capability. Migration 0022 and the
staging preflight reject any additional direct or transitive executor access.
Do not grant it to the general `app_runtime`, browser, or tenant roles. Keep
migration, function-owner,
executor, and ordinary runtime credentials separate; no runtime login is
superuser, `BYPASSRLS`, or a member of the migration/owner role. Provisioning
and runtime grants are DBA/deployment responsibilities; the migration creates
neither roles nor login grants. Confirm the deployed schema/search path and
role memberships before running 0022. Migration 0024 grants only
tenant-scoped table operations to `app_runtime`; it does not grant lookup
function execution or executor membership. Existing disposable-PostgreSQL
tests do not verify production grants or the full historical migration chain.

### Migration 0023 and the isolated schema discrepancy

The complete Alembic chain through 0024 passes on a fresh disposable
PostgreSQL database, including both 0023 columns, forced RLS, restricted roles,
and tenant-scoped runtime grants. Migration 0023 also handles the reproduced
partial-schema case where `tracks.cover_url` already exists but
`upload_jobs.cover_data` does not: it preserves the existing column and adds
only the missing one. Neither test establishes a deployed database's recorded
revision or schema state.

The prior non-production `server.startup()` called
`Base.metadata.create_all()` before compatibility column additions.
`create_all()` creates a missing table from current ORM metadata but does not
add columns to an existing table. Thus, if it created `tracks` while an older
`upload_jobs` table already existed, the schema could have `tracks.cover_url`
but lack `upload_jobs.cover_data`. This sequence was reproduced in a
disposable database. Migration 0023 now inspects each table independently and
adds only a missing column, avoiding the duplicate-column failure and retaining
existing data. Startup no longer creates or repairs persistent schema; it
checks for the tables and 0023 columns and requires explicit migration. This
does not establish the live isolated database's state: its Alembic revision
was not readable using the available runtime role. Production startup behavior
is unchanged; the development-only drift does not establish production schema
state.

Development startup now performs no persistent-schema creation or repair. It
checks that the users, tracks, and upload_jobs tables exist and that the 0023
media columns are present; it intentionally does not query `alembic_version`
with the application role. Initialize or update a development database
explicitly with `alembic upgrade 0027_storage_lifecycle` using its authorized migration
connection; startup never runs migrations itself. Existing development
databases with missing required schema must be reviewed and migrated explicitly.
Production startup behavior is unchanged.

When authorized migration credentials are available, do not point them anywhere
except the intended isolated database. First run read-only checks as the
authorized migration principal:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
SELECT current_schema(), current_schemas(true);
SELECT version_num FROM alembic_version;
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND ((table_name = 'tracks' AND column_name = 'cover_url')
    OR (table_name = 'upload_jobs' AND column_name = 'cover_data'))
ORDER BY table_name, column_name;
SELECT relrowsecurity, relforcerowsecurity
FROM pg_class WHERE oid = 'public.provider_identities'::regclass;
SELECT has_table_privilege('app_runtime', 'public.provider_identities', 'SELECT'),
       has_table_privilege('app_runtime', 'public.provider_identities', 'INSERT'),
       has_table_privilege('app_runtime', 'public.provider_identities', 'DELETE'),
       has_table_privilege('app_runtime', 'public.provider_identities', 'UPDATE');
SELECT has_function_privilege('app_runtime',
         'vervfy_auth.lookup_provider_identity(text,text)', 'EXECUTE'),
       has_function_privilege('vervfy_identity_lookup',
         'vervfy_auth.lookup_provider_identity(text,text)', 'EXECUTE');
SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
       rolcreaterole, rolreplication, rolinherit
FROM pg_roles
WHERE rolname IN ('vervfy_identity_lookup_owner', 'vervfy_identity_lookup');
```

Compare the recorded revision and schema before acting. When 0023 is pending and
one of its columns already exists, the migration preserves it and adds only
the missing column. Still take and verify a restorable backup, and test the
upgrade on a disposable copy matching the observed revision/schema before
applying it to a shared database. If 0023 or 0024 is recorded while
`upload_jobs.cover_data` is absent, investigate partial/nonstandard migration
execution or later schema changes before repair; do not assume normal
PostgreSQL Alembic execution left a half-applied 0023.

Before any production migration, the DBA must separately establish the
production database identity, recorded revision, both column states, role
preflight, RLS/grants, and a verified backup. Rehearse the same migration path
against a production-schema copy. The isolated discrepancy is not evidence of
production drift. No production database was accessed for this review.

References: [migration 0022 role preflight and lookup grants](../alembic/versions/0022_provider_identity_lookup.py),
[migration 0024 runtime table grants](../alembic/versions/0024_provider_identity_runtime_access.py).

## Phase 1 acceptance criteria

Phase 1 is complete only when the following are documented and reviewed;
unchecked items remain verification gates, not unresolved product defaults:

- [x] Credential, onboarding, no-auto-linking, existing-email conflicts,
  last-login-method, recovery, five-minute fresh-authentication, and session
  invalidation policies are recorded above.
- [x] Decision: use the public HTTPS frontend and one exact configured URI per
  environment; Authlib is selected subject to the >=1.9.2 minimum.
- [x] Define the exact callback path, per-environment URI configuration,
  Next.js rewrite, and secure Lax-cookie behavior. Concrete public hostnames,
  Google registration evidence, and live proxy/cookie behavior remain
  deployment gates.
- [x] Document Google's `auth_time` opt-in, `max_age` request, 300-second rule,
  60-second clock skew, and fail-closed fallback. Live provider verification is
  still required before enabling sensitive actions for Google-only users.
- [x] Review Authlib compatibility, required packages, and current advisories;
  require Authlib >=1.9.2,<2 and httpx2>=2,<3. `requirements.lock` pins the
  Python 3.12.7 resolution with hashes and is used by CI and Render builds;
  compatibility tests ran in an isolated environment.
- [x] Specify 600-second Redis transactions, atomic single-use consumption,
  browser/session/purpose binding, concurrent callback handling, and fail-closed
  behavior. Sensitive-action proofs remain capped at 300 seconds.
- [ ] Review the migration and API/UI contracts, email normalization/uniqueness,
  deletion ownership constraints, null-password handling, and rollback limits.
  Map each security requirement to mocked tests before feature enablement.

## Phase 2 acceptance criteria

Do not enable Google login until all are met:

- [x] Resolve and lock the Python 3.12.7 FastAPI/Starlette/Authlib dependency
  graph with hashes; require Authlib >=1.9.2,<2 and httpx2>=2,<3.
- [ ] Before enablement, exercise JWKS cache/key rotation and recheck current
  security advisories in the deployment release review.
- [ ] Set and register the exact HTTPS callback URI for each deployed frontend;
  verify the Next rewrite, callback query, cookies, log redaction, and no-store
  behavior end to end. Development uses only the documented localhost URI.
- [ ] Enable Google's `auth_time` claim setting and demonstrate that a
  `max_age=300` reauthentication returns a validated timestamp within 300
  seconds. Prove missing/stale/future claims deny sensitive actions; verify
  password fallback and Google-only denial behavior.
- [ ] Test Redis expiry, eviction/missing state, backend outage, parallel
  callbacks, state/nonce/browser/session mismatch, one-time consumption, and
  invalidation after logout, session-version change, or deletion. Every failure
  must deny the flow without memory fallback.
- [ ] Provision and review migration 0022's separate migration, function-owner,
  executor, and runtime roles/grants in the deployment database. Run migrations
  only after DBA preflight; verify `app_runtime` can operate only on its tenant's
  identity rows and cannot execute the lookup function. Only the dedicated
  trusted auth connection may execute that function.
- [ ] Complete the existing mocked OIDC, account lifecycle, isolation, migration,
  and deployment acceptance plan before onboarding Google-only users.

## Verification limits

### Schema review (2026-11-02)

The implementation request called the schema/credential slice "Phase 1"; it
corresponds to item 2 of the phased plan above. Completing that slice does not
complete the broader Phase 1 acceptance checklist or authorize OAuth routes.

Migration 0021 was tested on a disposable PostgreSQL 18.6 cluster using a
non-superuser table owner without BYPASSRLS and a separate application role.
Tests cover upgrade/data preservation, null credentials, guarded downgrade,
identity uniqueness, foreign keys, deletion cascade, and tenant read/write
isolation. Downgrade now takes exclusive locks before checking credentials and
identities and temporarily removes FORCE RLS for the owning migration role's
identity check, restoring it before refusing a populated downgrade. This fixes
the previous empty-table downgrade failure under an ordinary owner. Run this
transactional DDL only in a maintenance window; exclusive locks can block traffic.
The tests do not validate the deployed database role/grant setup or the entire
historical migration chain. SQLite batch-migration restrictions still apply.

The PostgreSQL 18.6 result above is historical and does not establish
Supabase compatibility. The separate Supabase PG17.11 candidate has its own
disposable full-chain, role-catalog, TLS-guard, API-role denial, forced-RLS,
tenant-isolation, lookup-boundary, storage-lifecycle, and temporary namespace
grant/revoke tests. See `supabase-staging-compatibility.md` and the candidate
checksums; neither artifact authorizes hosted migration or enables OAuth.

### Restricted pre-login lookup

Migration `0022_provider_identity_lookup.py` adds
`vervfy_auth.lookup_provider_identity(text, text)`. It returns only a user ID or
NULL for an exact Google `(issuer, subject)`, with case-sensitive comparisons,
no normalization, no email fallback, no wildcard/list operation, and no writes.
`provider_identity_lookup.py` exposes the internal Python helper using bound
parameters. The Google callback calls it only after consuming the browser-bound
transaction and validating the ID token; it has no route and no SQLite fallback.

The caller MUST validate the Google token (including issuer, signature, audience,
expiry, nonce, and verified-email requirement) and consume the browser-bound
OAuth transaction before calling the helper. A function name or Python argument
is not proof of verification. The database trusts the dedicated authentication
capability; it cannot independently establish that Google verified the subject.
The helper's result alone must never issue a session without those checks.
The two accepted Google issuer spellings remain distinct exact database keys;
no automatic aliasing or linking is performed.

Privilege boundary:

- `vervfy_identity_lookup_owner` owns only the lookup function. It receives schema
  USAGE and SELECT on only the identity table's issuer, subject, and user_id
  columns. A SELECT-only RLS policy scoped to that role permits its lookup;
  ENABLE/FORCE RLS and the existing tenant policy stay intact. It receives no
  identity writes, user/profile/library reads, or broad BYPASSRLS privilege.
- `vervfy_identity_lookup` receives only private-schema USAGE and function
  EXECUTE from this migration. It receives no table SELECT and cannot become
  the function owner. PUBLIC and deployment-default schema/function grants
  are removed. The function has a fixed `pg_catalog, pg_temp` search path and
  references the fully qualified identity table with no dynamic runtime SQL.
- Ordinary application/browser roles must not receive the executor capability.
  Only the trusted authentication backend connection may receive it. Authorized
  backend code can query arbitrary exact pairs; protection against unverified
  callers therefore depends on keeping this capability private and performing
  verification first. Never expose the helper as a raw lookup API. Tenant
  context likewise remains trusted backend state, never a client-supplied ID.

Migration/provisioning contract (not executed on any shared database):

- A DBA must reserve both capability roles with NOLOGIN, NOINHERIT,
  NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE, and NOREPLICATION. Use
  dedicated roles without preexisting object grants; audit PUBLIC grants too.
  Migration 0022 fails closed if role attributes are unsafe or roles are absent.
- The owner role must have no other role memberships, and only the migration
  role may hold membership in it. The migration role requires ownership of the
  identity table, membership permitting function ownership transfer, and CREATE
  on the database for the new private schema. Runtime logins must never inherit
  migration/owner privileges. Review these prerequisites with the deployed role
  topology before migration; no automatic login grants are made here.
- Run 0022 transactionally under the same trusted application schema/search_path
  used for earlier migrations. It creates a fresh private schema and fails on
  name collisions rather than replacing existing objects. It does not rewrite
  users or identities. It temporarily grants schema CREATE to the function owner
  for ownership transfer, then revokes it within the transaction.
- Downgrade removes only its function, policy, grants, and empty private schema,
  preserving identities, users, tenant RLS, and externally provisioned roles.
  It deliberately avoids CASCADE. Stop lookup callers before downgrade. The
  subsequent 0021 downgrade still refuses existing identities/passwordless users.
- SQLite skips 0022; deployed lookup requires PostgreSQL. Configure the
  restricted lookup URL only on the trusted backend.

PostgreSQL tests use a disposable private cluster. Coverage includes allowed
exact lookups, unknown/incorrect-case subjects, email-like/wildcard/injection
inputs, missing issuer matches, denied application EXECUTE and SET ROLE, denied
executor table reads, restricted owner privileges, unsafe default grants,
search-path shadowing, deleted identities, unsafe role preflight rejection,
partial-column migration compatibility, and downgrade/data/RLS preservation.
The complete migration chain and local role/grant behavior have now been
verified on a fresh disposable PostgreSQL cluster; deployed provider grants
remain a DBA/staging verification gate.

## Phase 3 implementation status

The backend and UI lifecycle is implemented: Google-only username onboarding,
explicit non-email-based linking, fresh Google reauthentication, password
creation, last-login-method-safe unlinking, sensitive-action checks, session
version changes/rotation, and localized login/signup/account controls. Existing
password login and registration remain available. OAuth remains disabled by
default; keep `GOOGLE_OAUTH_ENABLED=0` until the unchecked Phase 1/2 release
gates below are independently reviewed and verified.

Local verification on the locked Python 3.12.7 dependency set: 63
OAuth/schema/PostgreSQL tests and 19 password/auth regression tests pass; all 3
Google-auth Playwright tests pass. The frontend production build passed and
lint reported 0 errors (17 warnings). A fresh disposable PostgreSQL database
reached Alembic head `0024_provider_identity_access`; forced RLS, tenant
isolation, capability-role attributes, and restricted `app_runtime`/lookup
grants were checked. No live Google callback or production database was used.

## Production rollout procedure

Do not run these steps until the isolated staging runbook is complete and the
DBA and release owner approve production. Keep `GOOGLE_OAUTH_ENABLED=0` during
the code deployment and migration.

1. **Approve and prepare.** Confirm the production database, schema, current
   Alembic revision, and the `tracks.cover_url`/`upload_jobs.cover_data` states
   using the read-only checks above. Verify a restorable backup. Provision the
   separate lookup-owner and executor roles, membership, migration principal,
   and runtime grants exactly as specified under “Migration 0022 deployment
   roles.” Never give the API runtime credentials the migration principal.
2. **Configure server-side settings.** Use the production API service for
   `DATABASE_URL` (least-privilege app role), `REDIS_URL`, `VERVFY_SECRET_KEY`,
   `VERVFY_ENVIRONMENT=production`, `VERVFY_HTTPS_ONLY=1`,
   `VERVFY_COOKIE_SAME_SITE=lax`, and `VERVFY_TRUSTED_PROXY_HOPS` matching the
   verified Render proxy topology. Add `GOOGLE_OAUTH_ENABLED=0`,
   `GOOGLE_CLIENT_ID`, secret-store-only `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_FRONTEND_ORIGIN=https://<production-frontend-host>`,
   `GOOGLE_REDIRECT_URI=https://<production-frontend-host>/api/auth/google/callback`,
   and secret-store-only `GOOGLE_IDENTITY_LOOKUP_DATABASE_URL` for the
   dedicated lookup-executor login. Register that exact callback in the
   production Google Web client. Keep all Google secrets API-side; never use
   `NEXT_PUBLIC_*`, frontend build arguments, or logs. Set frontend `BACKEND_URL`
   to the production API origin and `SITE_URL` to the canonical frontend origin
   if Render's `RENDER_EXTERNAL_URL` is not the canonical URL.
3. **Deploy with OAuth disabled and migrate.** Deploy the reviewed code and
   frontend while the feature flag remains off. Run Alembic once from an
   approved one-off migration runner, injecting `MIGRATION_DATABASE_URL` from
   the secret manager for that process only. It must identify the intended
   production database and use the DBA-approved migration principal:

   ```sh
   DATABASE_URL="$MIGRATION_DATABASE_URL" \
     MIGRATION_DATABASE_URL="$MIGRATION_DATABASE_URL" \
     python -m alembic upgrade 0027_storage_lifecycle
   DATABASE_URL="$MIGRATION_DATABASE_URL" \
     MIGRATION_DATABASE_URL="$MIGRATION_DATABASE_URL" \
     python -m alembic current
   ```

   Do not persist the migration URL in the API service environment or shell
   history. Stop on any revision/schema mismatch or failed role preflight; do
   not stamp revisions or grant superuser/BYPASSRLS as a workaround.
4. **Verify before enabling.** Confirm the applied revision is exactly
   `0027_storage_lifecycle` and 0028 is unapplied; `provider_identities` has ENABLE and FORCE
   RLS; `app_runtime` has SELECT/INSERT/DELETE but not UPDATE; only the
   executor can execute `vervfy_auth.lookup_provider_identity(text,text)`; and
   both capability roles are NOLOGIN, NOINHERIT, NOSUPERUSER, NOBYPASSRLS,
   NOCREATEDB, NOCREATEROLE, and NOREPLICATION. Exercise a synthetic password
   login and verify `/healthz`, the frontend API proxy, disabled Google UI, and
   production logs contain no OAuth codes, tokens, cookies, or database URLs.
   Enable Google only after staging has demonstrated live Google signature,
   JWKS rotation, `auth_time`, callback/cookie/proxy, Redis-failure, and account
   lifecycle behavior. Then set `GOOGLE_OAUTH_ENABLED=1` and verify one approved
   canary login/signup, linking, unlink safeguards, and password login.
5. **Rollback.** For an OAuth incident, set `GOOGLE_OAUTH_ENABLED=0` and
   redeploy/restart the API; this disables Google flows while preserving
   password authentication, but also prevents existing Google-only users from
   signing in until Google is restored. Keep migrations applied: 0023/0024 are
   forward-only, and 0021 refuses downgrade when identities or passwordless
   accounts exist. Do not downgrade or drop provider data. Roll application
   code back only to a version that tolerates nullable password hashes and
   provider identities; a pre-0021 password-only version is unsafe after
   Google-only accounts exist. If a database migration fails, leave OAuth
   disabled and have the DBA choose a tested forward repair or an explicitly
   approved backup restore.

Production is **not ready to enable** until all live-provider, staging,
database-role, and release-approval gates above are evidenced. No production
credentials, migrations, or deployment were used for this work.
