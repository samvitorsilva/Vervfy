# Phase 3: dormant registration and restricted recovery internals

## Status and boundaries

Registration, enrollment authorization, recovery-code primitives and isolated
transaction helpers are implemented. They have no HTTP routes, UI activation or
startup wiring. The existing WebAuthn configuration is still disabled by default;
passing None to the registration/recovery services fails closed. Setting the flag
alone does not expose these services. Existing Google login/signup/linking and
password account-action routes remain in place; no passkey proof is accepted there.

This is not production readiness. Successful local tests cannot establish trust
in an enrollment policy, deployment roles, domain ownership or recovery operations.

## Migration graph and storage integration

The active directory had one head: 0027_webauthn_foundation, descending from
0026_application_runtime_grants. The new additive revision is
0028_webauthn_enrollment -> 0027_webauthn_foundation.

The separate archived phase4-cleanup-remediation, phase4a-retry-limits and
release-artifacts/final-local-rc/source trees contain another branch:
0026_application_runtime_grants -> 0027_storage_lifecycle ->
0028_storage_cleanup_leases (plus 0029_cleanup_retry_limits in the retry tree).
The full revision IDs do not collide, but combining those migration trees would
create multiple heads. A reviewed merge revision with both actual final branch
heads is required before integrating/deploying them. No archived tree was edited,
no branch was imported, and no release-candidate head was assumed or migrated.

0028 adds webauthn_enrollments with tenant FK, session digest/version, source method,
optional unique original signup transaction, bounded expiry and consumed timestamp.
A partial unique index permits only one Google-signup authorization per account,
even after use/expiration. There is no account backfill.

The new table uses ENABLE/FORCE RLS and the existing app.current_user_id policy.
Default ACLs and PUBLIC access are removed. app_runtime gets select/insert and only
consumed_at updates on authorizations; INSERT on handles/credentials; select/insert
on recovery tables and only consumed_at updates on recovery codes. Existing key,
owner, expiry and source fields cannot be modified by app_runtime; no credential
DELETE permission or recovery-state completion permission is granted. Provider
lookup roles remain excluded. These permissions trust backend authorization logic,
as the existing tenant-role model does; they are not protection against arbitrary
SQL execution by a compromised app_runtime principal.

Downgrade refuses any retained enrollment, handle, credential, recovery-code or
recovery-state data, including owner-hidden rows. An empty downgrade restores Phase
2 grants. No production or application database migration has been run.

## Enrollment authorization

### New Google-only accounts

GoogleOAuthService.store_pending_signup now records a random server-side signup
transaction identifier and verification time alongside the existing pending signup.
The original receipt survives username-conflict retries; retries cannot renew its
enrollment lifetime. Older pending records without a receipt still work with the
existing signup route but cannot authorize the new enrollment service.

RegistrationService.create_google_signup is an unwired alternative transaction:

1. Require a fresh explicit database transaction; validate the username.
2. Atomically consume the actual server-side Google pending-signup record, bound to
   the original browser cookie. Require the original receipt to be under 300 seconds.
3. Recheck canonical/legacy Google identity lookup. Reject an existing identity.
4. Choose a fresh UUID tenant; insert a new User and canonical ProviderIdentity.
   Unique constraints reject concurrent/existing identity or username ownership.
5. Create a server session ID and insert the enrollment authorization in this SAME
   database transaction, bound to that user, session ID digest and session version.
   Authorization expires no later than original signup verification + 300 seconds.
6. Only after commit may a future route expose the session cookie and grant ID.

There is no authorize_signup(existing_user_id) API. A normal login does not create
pending signup data or a durable enrollment grant. Re-login creates another session
and cannot reuse the original grant. Existing Google-only accounts remain blocked
from password enrollment. Failed signup transactions consume the pending receipt
and require a new Google signup flow; they cannot grant access to an existing user.

A failure after Redis session creation but before SQL commit may leave an orphan
allowlist entry until its TTL. It cannot authenticate because current_user_row also
requires a committed matching User. Phase 4 must arrange rollback cleanup and never
publish the cookie before successful commit. No existing route calls this method.

### Existing password accounts

RegistrationService.authorize_password checks the live session, current database
session version and password hash. It uses the existing current-password limiter
key, ten-attempt/900-second window and successful reset, plus a Redis-only enrollment
attempt budget before expensive hashing. No client-supplied password_verified flag
is accepted. Passwordless users cannot obtain this authorization.

Each authorization permits exactly one new credential. Password accounts can obtain
another authorization and register another credential. Signup authorization allows
one initial credential; adding further credentials to a Google-only account via an
existing passkey requires a separately integrated passkey_add proof path in Phase 4.
No session-only or email-only bootstrap was implemented.

## Registration verification

begin and finish both check the live allowlisted session, account version, account
and authorization ownership. They use the Phase 2 Redis atomic single-use challenge
store, with a registration ceremony discriminator, authorization ID and stable user
handle. Challenges expire in at most 120 seconds, bounded by authorization expiry.

The maintained webauthn library generates options and verifies challenge, exact
configured origin, RP hash, credential ID consistency, user presence, required user
verification and supported public-key algorithm. Cross-origin/embedded responses
are rejected. All account ownership comes from server bindings, not response fields.

The first authorized begin creates a cryptographically random 32-byte user handle.
Subsequent ceremonies preserve it. Credential IDs are globally unique; multiple
credentials per account are allowed (maximum ten retained credential rows). The user
row lock serializes concurrent enrollment. Credential insertion and authorization
consumption share a database transaction; any error must roll back the entire
transaction. Challenges are already burned on failed verification or DB failure.
Key/backup/counter parsing is performed by the library, not custom cryptography.

Enrollment does not itself issue a sensitive-action proof or recovery codes.

## Recovery foundations

RecoveryCodes.issue_initial requires a live session and an existing passkey assertion
proof bound to recovery_rotate and the fixed initial-code intent digest. Registration
alone, a Google session, or a current password cannot issue codes. The proof is
consumed in the same transaction as issuance. A second issuance is rejected: code
rotation and independent recovery authorization are not enabled.

Ten codes are generated with 256 bits of CSPRNG entropy each. Only domain-separated,
account-bound SHA-256 digests are stored; this high-entropy token design is not a
password-hashing scheme. Plaintext codes are returned once to the internal caller,
which must not deliver them until database commit or log/persist them elsewhere.

Consumption requires a live account session and shared Redis account rate limiting
(five attempts per 900 seconds, including invalid inputs). A conditional UPDATE and
creation of pending restricted state share one transaction; concurrent/replayed
consumption has one winner. Database rollback restores both operations. Pending
state is session/version-bound and expires in 300 seconds. It cannot authorize
replacement credentials, ordinary login, enrollment grants, email changes or account
deletion. There is no workflow that advances it to an authorizing state.

Signed-out recovery, notifications, cooling-off, credential replacement, revocation,
code rotation and support-assisted recovery remain disabled pending security review.

## Transaction preparation

account_transactions.py provides unwired password-add, email-change and logout-version
helpers. They require a caller-owned tenant transaction, lock/check the account and
session version, flush constraints and never commit. They are mutations, not
verification APIs: callers must first consume the appropriate exact-action proof in
the same transaction. Tests demonstrate rollback and committed password creation
with real passkey proof consumption.

Existing UserStore methods and routes remain unchanged. Deletion is intentionally
not refactored: object storage removal and session revocation cannot be made atomic
with SQL by wrapping them in a database transaction. A reviewed tombstone/outbox and
retry plan must be reconciled with the storage-lifecycle branch.

## Exact local validation

Use the already installed virtual environment and local PostgreSQL initdb/pg_ctl and
Valkey/Redis binaries, as a non-root user. The tests create private temporary Unix
sockets with TCP disabled; no application URLs, .env, hosted databases or Google
endpoints are used. A sandbox may require permission for local daemons.

```sh
cd /home/sam/vervfy-latest
env -i PATH="$PATH" HOME=/tmp DATABASE_URL=sqlite:///:memory: \
  VERVFY_SECRET_KEY=isolated-test REDIS_URL= GOOGLE_OAUTH_ENABLED=0 \
  VERVFY_ENVIRONMENT=test timeout 180 .venv/bin/python -m pytest -q \
  tests/test_passkey_enrollment.py tests/test_passkey_enrollment_postgres.py \
  tests/test_passkeys.py tests/test_passkeys_postgres.py \
  tests/test_google_oauth.py tests/test_google_oauth_diagnostics.py \
  tests/test_google_oauth_redis_integration.py tests/test_security_regressions.py \
  tests/test_oauth_schema.py
.venv/bin/ruff check --no-cache passkey_enrollment.py account_transactions.py \
  passkey_schema.py alembic/versions/0028_webauthn_enrollment.py \
  tests/test_passkey_enrollment.py tests/test_passkey_enrollment_postgres.py \
  tests/test_passkeys.py
.venv/bin/alembic heads
env -i PATH="$PATH" HOME=/tmp .venv/bin/python -m pip check
git diff --check
```

## Phase 4 prerequisites (all required before enabling routes)

1. Reconcile actual storage/WebAuthn branches with a reviewed merge revision and
   rehearse the full combined migration chain under deployment roles.
2. Approve signup enrollment UX and eligibility, and explicitly keep existing
   Google-only bootstrap unavailable absent an approved independent trust anchor.
3. Integrate the new signup transaction with existing signup throttles, CSRF and
   username-conflict behavior. Publish cookies/grants only after commit; handle
   orphan session cleanup and post-commit failures without authorization renewal.
4. Add gated registration endpoints with request limits, CSRF, trusted origins,
   live-session checks and network/account rate limits. Require session rotation,
   version invalidation, credential notifications and audit events after enrollment.
5. Add reviewed passkey_add proof authorization for subsequent Google-only credentials.
   Do not reuse the original signup grant or derive authorization from session age.
6. Define exact canonical action payloads, and integrate proof consumption with the
   mutation helpers in a single transaction. Handle Redis revocation/rotation errors
   using durable session-version invalidation; refresh CSRF after rotation.
7. Review recovery threat model, second credential/recovery-code UX, notifications,
   retention, code rotation and restricted-state transitions. Keep email-only and
   session-only replacement unavailable. Add audit events with no secret payloads.
8. Reconcile account deletion with storage outbox/tombstone/retry semantics.
9. Complete browser/virtual-authenticator and fault-injection tests, review production
   RP ownership/stability and perform independent security review. Local unit and
   PostgreSQL tests do not substitute for these gates.

## Recorded validation

Final expanded suite: 192 passed, 13 subtests passed, no skips (55.85 seconds).
Warnings were the existing Alembic path_separator deprecation and the intentional
Pillow oversized-image regression warning. Ruff, pip dependency checks and
`git diff --check` passed. Active migration graph: single head
0028_webauthn_enrollment. Only disposable local schemas were upgraded/downgraded.
