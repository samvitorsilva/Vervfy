# Local security audit — 2026-11-17

## Scope and release decision

Source review of authentication, authorization, RLS, API controls, storage isolation,
cleanup fencing/retries, and secret exposure in the current uncommitted checkout.
Only documentation was changed during this audit. Existing fixes and security
checks were preserved. No production/staging services, credentials, or user data
were accessed; no storage deletion or PostgreSQL startup was attempted.

**Release blocked: the 16 unresolved test failures reported by the user remain
unresolved.** Their exact node IDs and failure output were not identified in the
reviewed verification report. They were not rerun, fixed, or reclassified here.
They must not be confused with the separately documented 25 PostgreSQL startup
errors or treated as passing based on older regression results.

No critical vulnerability was confirmed in this review. Two high-severity issues
and one medium-severity configuration defect are documented below. Severity is
based on the stated prerequisites; live deployment configuration was not inspected.
This is a scoped source audit, not a production security certification.

## Findings

### A1 — HIGH: password change does not revoke outstanding reset capability

References: `password_reset.py:170`, `server.py:2434`, `server.py:2518`,
`server.py:3723`, `auth.py:203`, `auth.py:389`.

Reset issuance binds the token to a user ID but supplies no credential-version
binding. The reset handler uses the claimed user ID without comparing the
credential state at issuance. An ordinary password change increments the session
version but does not invalidate an outstanding reset token. Consequently, someone
holding an unused stolen reset link can reset the account again after its owner
changes the password, until the link expires. This requires password recovery to
be enabled and possession of that link; it is not an unauthenticated token bypass.
Recovery is feature-gated and disabled by default.

Evidence: a disposable in-memory SQLite probe invoked the actual UserStore and
PasswordResetStore methods: issue token, change password with the expected hash,
claim the old token, then reset successfully (session version advanced to two).
This demonstrates the component behavior, not HTTP, Redis, or PostgreSQL behavior.
Single-use claims and session revocation do not resolve stale unused tokens.

Recommended follow-up: bind reset issuance to a credential/recovery epoch and
compare it atomically while locking the user during reset; increment that epoch
on credential/security changes. Preserve claim fencing and commit-uncertainty
handling. Add password-change/reset race regressions. No fix made in this audit.

### A2 — HIGH: live-row quota does not bound retained physical storage

References: `library.py:320`, `library.py:435`, `library.py:488`,
`server.py:3285`, `server.py:3323`, `server.py:4379`,
`storage_lifecycle.py:215`, `audio_store.py:264`.

Quota accounting sums active track rows. Removing a track immediately releases
its accounted bytes, while physical object deletion remains disabled. An
authenticated account can repeatedly upload and remove tracks, retaining storage
allocations that no longer count against its quota. Fresh managed object
reservations permit repeated allocations. Rate limits slow this process but do
not impose a cumulative retained-byte ceiling. The impact is storage cost and
resource exhaustion, not cross-account data access.

Async staging adds another unaccounted allocation: the staging object is uploaded
before the user lock/job insertion, and the final track quota check covers live
tracks rather than staging and pending/retired objects. Failed/redundant attempts
can therefore retain allocations too.

Evidence: the synthetic SQLite probe showed accounted bytes falling from 1024 to
zero after Library.remove. No provider object was created or deleted. Physical
retention and allocation order were established by source review, not a live
provider experiment or a PostgreSQL lifecycle-trigger test.

Recommended follow-up: reserve bytes before storage writes and enforce a ledger
covering pending, staging, active, failed, and retired allocations, with bounded
account/global admission. Release retained-byte charges only on verified absence
under a separately authorized cleanup policy. Keep physical deletion disabled;
enabling it is not an acceptable shortcut. No fix made in this audit.

### A3 — MEDIUM: inconsistent production detection bypasses TLS normalization

References: `db.py:53`, `server.py:166`.

The server accepts `VERVFY_ENVIRONMENT=prod` and the `ENVIRONMENT` fallback as
production. Database TLS normalization recognizes only
`VERVFY_ENVIRONMENT=production`. With the other accepted forms, an explicitly
unencrypted PostgreSQL URL remains unencrypted. Even the recognized form defaults
to `sslmode=require`, which does not mandate hostname validation as `verify-full`
does. Exploitation depends on deployment configuration and network position;
no assertion is made about the live database connection.

Evidence: URL parsing only, with synthetic host and environment inputs, confirmed
that explicit `sslmode=disable` becomes `require` for the canonical spelling but
remains `disable` for both production aliases. No database connection was made.

Recommended follow-up: share one production-environment parser and fail closed on
insufficient database transport verification, with an explicit trusted-CA and
hostname policy. Test every supported production spelling. No configuration or
code changed in this audit.

## Security controls reviewed and limits

- Authentication: `server.py:1527` checks signed-session identity/version and the
  session allowlist; `auth.py:719` checks API CSRF. Sensitive credential changes
  use reauthentication and version changes. OAuth claim validation in
  `google_oauth.py:717` checks identity/issuer/audience/nonce rather than treating
  an email match as authority to link accounts. A1 remains a recovery exception.
- Authorization/RLS: `db.py:84` installs transaction-local tenant context;
  `alembic/versions/0007_row_level_security.py:21` forces tenant RLS. Track and
  upload-job operations use tenant-scoped lookups. Auth identity/session tables
  intentionally serve global authentication lookups; they are not independent
  tenant-RLS containment against a compromised application database role.
  No PostgreSQL ACL/RLS correctness claim is made without integration execution.
- Storage isolation: managed namespace/object ownership checks and immutable
  reservations remain intact. `audio_store.py:178` derives the tenant from a
  managed path; it relies on callers obtaining that path through authorization.
  It is not independently a caller-identity check. No externally reachable
  cross-tenant path bypass was confirmed in reviewed handlers.
- Cleanup: `alembic/versions/0029_storage_lifecycle.py:307` disallows physical
  cleanup; `alembic/versions/0033_cleanup_claims_disabled.py:70` revokes production
  claims. `scripts/storage_cleanup_worker.py:50` and `audio_store.py:264` keep
  production deletion disabled. The test-only worker in
  `tests/isolated_storage_cleanup.py` restricts storage to synthetic memory,
  checks disposable namespace/role/transaction isolation, authorizes locked
  claims, verifies absence, and uses fenced completion/retry. SQL source contains
  lease/token checks, reference checks, bounded retries and retained failures.
  Concurrent execution, grants, RLS, and rollback behavior remain unverified on
  PostgreSQL in this environment; source review is not proof of those properties.
- API controls: reviewed authentication/CSRF, request size limits, upload
  validation, throttling, and fail-closed backend-error handling remain intact.
  Active-row quota serialization does not solve A2. Signed media URLs remain
  bearer capabilities until expiry; record deletion does not revoke them or
  physically remove the referenced object.
- Secrets: a redacted Gitleaks scan of 261 tracked source/config/documentation
  files found zero findings. Only the current tracked checkout was scanned;
  environment files, credentials, data, binary files, untracked files, Git
  history, deployed bundles, and live logs were outside this scan. This is not a
  guarantee of absence of secrets. No secret values were printed. Recovery error
  diagnostics and storage error scrubbing were reviewed; general exception logs
  still merit a separate runtime redaction review before declaring logs safe.

## Actual checks in this audit

- Synthetic component probes: **3 confirmed finding scenarios**, exit 0, bounded
  to 30 seconds. Fresh in-memory SQLite only; no sockets or external services.
  Temporary script: `/tmp/vervfy-security-audit-probes.py`.
- Tracked-source Gitleaks scan: **261 files, 0 findings**, exit 0, bounded to
  40 seconds. Temporary driver: `/tmp/vervfy-audit-secret-scan.py`.
- No existing test suite was rerun and no tests were weakened or edited.
- PostgreSQL and affected HTTP/async execution remain subject to the previously
  documented sandbox socket restrictions. Those blockers are separate from the
  **16 unresolved test failures**, which remain release blockers.

Release assessment: not ready for sign-off. Triage the 16 failures with exact
node IDs/logs, remediate the findings under separate implementation scope, and
obtain isolated PostgreSQL ACL/RLS/concurrency/fencing and unrestricted HTTP/async
evidence. Production physical cleanup remains disabled and requires separate
explicit authorization and its own security verification.
