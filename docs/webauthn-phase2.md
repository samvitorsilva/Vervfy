# WebAuthn Phase 2: dormant backend foundation

## Scope and dependency

This phase adds no HTTP routes, frontend changes, registration/enrollment service,
recovery authorization, or changes to Google/password account actions. Even setting
the feature flag does not wire this module into the application. No existing account
can gain a passkey or authorization proof through a new public endpoint.

`webauthn==3.0.1` (Duo Labs py_webauthn) performs assertion parsing, COSE key
interpretation and signature verification. requirements.lock includes hashes for it
and its dependencies; existing resolved versions were preserved. References:
https://pypi.org/project/webauthn/3.0.1/
https://duo-labs.github.io/py_webauthn/authentication.html

## Configuration

`Config.from_environment()` returns None unless VERVFY_WEBAUTHN_ENABLED=1.
Missing/invalid enabled configuration raises PasskeyError; AssertionService rejects
None. These are internal APIs, not application startup switches yet.

Required when constructing the enabled foundation:

- VERVFY_WEBAUTHN_RP_ID: stable lowercase DNS hostname.
- VERVFY_WEBAUTHN_RP_NAME: nonempty display name, at most 64 characters.
- VERVFY_WEBAUTHN_ORIGINS: JSON list of canonical HTTPS origins.

This phase deliberately accepts only origins exactly matching `https://<RP ID>`.
No wildcard, alternate port, parent-domain RP, request-derived origin, IP, or HTTP
origin is accepted. trycloudflare.com, ngrok.io, ngrok-free.app and their subdomains
are rejected in all environments. Production RP ownership and permanence must be
reviewed before rollout; arbitrary DNS names cannot be proven owned by validation.
Tests use synthetic app.example.com; they do not contact that host.

## Migration and privilege model

Inspected local graph: 0026_application_runtime_grants was the single head.
0027_webauthn_foundation is its direct additive successor; no release-artifact
migration assumptions were used. Its frozen schema does not import mutable models.

New tables:

- webauthn_handles: one unique, 32-byte opaque handle per user, to be generated with
  a CSPRNG during future authorized enrollment. No username/email-derived handles,
  no migration backfill, no enrollment writer in this phase.
- webauthn_credentials: unique external credential ID, owner, COSE key, algorithm,
  counter, immutable backup eligibility, current backup state, usage and revocation.
- account_action_intents: user/session-version/session-digest/action binding,
  server-validated payload digest, bounded expiry and consumption timestamp.
- account_verification_proofs: unique intent, verified credential, expiry and
  consumption timestamp. Composite owner FKs prevent cross-tenant references.
- account_recovery_codes: hashes only; no issuance or verification implementation.
- account_recovery_states: pending/cancelled/completed restricted workflow metadata;
  no state grants a normal session, proof, credential or mutation capability.

Every new table has ENABLE/FORCE RLS, using app.current_user_id for both reads and
writes, following the existing tenant_session model. Foreign keys cascade security
data on user deletion. Indexed owners and expirations support lookup and cleanup.
New-table default grants are removed, including PUBLIC, before explicit grants:

- app_runtime: read handles/credentials; update only credential counter, backup
  state and last-use timestamp; select/insert intents/proofs and update only their
  consumption timestamp.
- No runtime insert/delete/public-key/ownership/revocation update on credentials.
- No runtime recovery-table access; no Google identity lookup role access.
- No schema-wide or default grants, no new SECURITY DEFINER function or BYPASSRLS.

Downgrade locks all new tables and checks all rows as owner, including rows hidden
by FORCE RLS. It restores FORCE RLS and refuses rollback if any security data exists.
Only an empty foundation can be removed. Existing users, identities, passwords and
session data are untouched. Production migrations have not been run.

## Service contract

Use existing `db.tenant_session(user_id)` and an explicit transaction. The service
checks tenant identity, locks the user row and checks the current session version.
A Binding MUST come from server-validated current_user_row/require_api_user, never
client IDs. Live Redis session allowlist checks, CSRF and rate limits remain route
responsibilities in Phase 3. The internal API alone is not an authentication route.

1. Prepare a canonical, server-validated action payload and digest. Store no raw
   password in an intent. Password-intent persistence/hash handling and exact action
   canonicalization are not implemented; these are integration blockers.
2. create_intent inserts an expiring intent, without committing.
3. AssertionService.begin issues a 32-byte random challenge, stored under a random
   256-bit identifier in Redis/Valkey with a 120-second TTL. Record includes account,
   hashed session ID, session version, action, intent and allowed credential IDs.
4. finish atomically GET/DEL consumes the challenge before checking the response.
   Invalid/mismatched assertions burn the challenge. Outages raise errors with no
   in-memory fallback. Verification checks exact origin/RP, type, challenge,
   credential ownership, user handle when supplied, UP/UV, signature, allowed key
   algorithm and unchanged backup eligibility. Cross-origin embedding is rejected.
5. The credential update and unique proof insertion occur in the caller's database
   transaction. A DB rollback loses the consumed Redis challenge (safe failure),
   so the user starts another ceremony. Proof expiry never exceeds intent expiry.
6. consume_proof locks and validates the account, intent, proof and active credential,
   checks the exact payload digest, then conditionally marks proof and intent used.
   It never commits. The actual sensitive mutation MUST use this same transaction.
   If the mutation fails, roll back the entire transaction. Do not catch the error
   and commit. Existing UserStore mutators commit internally and therefore must be
   refactored or given transaction-aware variants before integration.

Synced/backup-eligible credentials can report zero or nonmonotonic counters: the
library receives a baseline of zero, while the stored counter retains its high-water
mark. Signature/UV/challenge checks remain mandatory. Non-backup credentials retain
strict increasing-counter checks when a nonzero counter exists. No counter replaces
the single-use challenge. Credential counters are updated under database locks.

## Local validation

Dependencies must already be installed from requirements.lock in the project's
virtual environment. The commands below do not download packages or read .env.
PostgreSQL initdb/pg_ctl and Redis/Valkey binaries must be on PATH; run as a non-root
user. Socket restrictions in a sandbox may require permission to run local daemons.

```sh
cd /home/sam/vervfy-latest
env -i PATH="$PATH" HOME=/tmp DATABASE_URL=sqlite:///:memory: \
  VERVFY_SECRET_KEY=isolated-test REDIS_URL= GOOGLE_OAUTH_ENABLED=0 \
  VERVFY_ENVIRONMENT=test timeout 120 .venv/bin/python -m pytest -q \
  tests/test_passkeys.py tests/test_passkeys_postgres.py \
  tests/test_google_oauth.py tests/test_google_oauth_diagnostics.py \
  tests/test_google_oauth_redis_integration.py \
  tests/test_security_regressions.py tests/test_oauth_schema.py
.venv/bin/alembic heads
.venv/bin/ruff check --no-cache passkeys.py passkey_schema.py \
  alembic/versions/0027_webauthn_foundation.py \
  tests/test_passkeys.py tests/test_passkeys_postgres.py
git diff --check
```

Tests create their own private temporary PostgreSQL cluster and Redis/Valkey Unix
sockets, with TCP listeners disabled. They never use application DB/Redis URLs.
Migration upgrade/downgrade tests invoke the new migration only on disposable
schemas. No global cleanup/reset or production migration commands are needed.

Coverage includes real synthetic ECDSA assertions, invalid signatures/RP/origin/UV,
wrong owner/session/action/credential/user handle, revocation, counter policies,
challenge TTL/replay/concurrency, DB/Redis outages, proof rollback/replay/payload
binding/expiry, PostgreSQL concurrent proof consumption, owner-hidden downgrade
guards, RLS, malicious default ACLs, FK ownership and disposable cascade deletion.
Existing Google and password regression suites remain in the validation command.

## Release blockers and Phase 3

Keep the foundation disconnected until all are resolved:

1. Approve existing-account enrollment trust anchors and lost-credential recovery.
   No current-session-only enrollment, Google iat fallback or recovery bypass.
2. Add and review registration verification before granting narrowly scoped
   enrollment capability. Store immutable handle/key/ownership/backup eligibility.
3. Build authenticated, CSRF-protected, rate-limited ceremony endpoints; validate
   current session allowlist on begin, finish and mutation. Set body/credential
   count limits and distributed throttles; fail closed on infrastructure outages.
4. Define action canonicalization and transaction-aware mutations. Integrate proof
   consumption atomically with password/email/logout-all/deletion changes. Recheck
   eligibility under locks. Version/revoke/rotate sessions and refresh CSRF tokens.
5. Implement recovery codes, notifications and restricted recovery policy separately;
   schema existence does not authorize recovery. Add credential-management policy.
6. Review stable production RP ID, origins, tenant-role deployment, cleanup/retention,
   dependency advisories and a full migration-chain deployment rehearsal. This phase
   tests the additive migration against the existing local role/schema fixture, not
   a hosted release candidate. Do not infer release deployment readiness from it.
7. Add browser/virtual-authenticator tests and independent security review. Preserve
   Google login/signup/linking and password behavior. Google linking's existing
   freshness limitation remains unchanged and needs separate review.

No UI flows, production credentials, hosted services, or live Google requests were
used or modified. Logs must never include assertions, challenges, session IDs,
recovery codes, private keys or OAuth callback parameters.

## Recorded validation result

Final local run: 142 passed, 13 subtests passed, no skips (22.13 seconds).
Two warnings: existing Alembic path_separator deprecation and the intentional
oversized-image security test's Pillow warning. Ruff and git diff --check passed;
pip check reported no broken requirements. Local graph now has one head:
0027_webauthn_foundation. No deployment database was migrated.
