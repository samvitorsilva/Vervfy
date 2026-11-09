# Phase 4C.2.1 — operator identity database foundation

## Outcome

Added a private PostgreSQL schema for future independent operator identities,
WebAuthn credential metadata, explicit role assignments, administrative session
metadata, and storage audit records. No ordinary application role can access
the schema. No WebAuthn ceremony, application authentication, administrative
endpoint, recovery endpoint, or production provisioning flow was added.

The worktree already contained extensive Phase 4A–4C changes. They were
preserved. No hosted/production database, real account, production Storage,
frozen release candidate, or physical deletion was accessed or changed.

## Exact files changed

- `alembic/versions/0030_operator_foundation.py` — new forward-only migration.
- `tests/storage_lifecycle_fixture.py` — provision the restricted foundation
  owner only in the disposable PostgreSQL fixture.
- `tests/test_operator_identity_foundation.py` — new schema, role, audit, and
  privilege tests using synthetic identities.
- `tests/test_staging_migrations.py` — recognize the actual new head and test
  downgrade refusal for revisions 0029 and 0030.
- `docs/storage-lifecycle.md` — record schema boundaries and the provisioning
  limitation.
- `reports/phase4c21-validation.md` — this report.

Migrations 0028 and 0029 were not edited. Their current hashes match the Phase
4B preservation record:

| Migration | SHA-256 |
|---|---|
| `0028_storage_cleanup_leases.py` | `e6be5fff5326ab693222f4611144d4409885e4715543da2f27c126bbd742939f` |
| `0029_storage_cleanup_retry_limits.py` | `a8ba0312536235ebf2a87859305a78862c61ac1b362c135ba188166efb0ef76f` |

## Migration graph and schema design

Before changes, the verified single Alembic head was
`0029_cleanup_retry_limits`. Migration `0030_operator_foundation` has
`down_revision = "0029_cleanup_retry_limits"` and is forward-only. No historical
migration was rewritten.

The migration creates five tables under private schema `vervfy_operator`:

- `operator_identities`: UUID identity, unique lowercase ASCII identifier,
  pending/active/suspended/revoked status, timestamps, suspension/revocation
  markers, and required provisioning method/reason/reference metadata. It has
  no foreign key to `public.users` or provider identities and creates no rows.
- `operator_credentials`: globally unique credential ID, owning operator,
  public-key bytes, allowlisted non-secret metadata, signature counter, backup
  flags, timestamps, and revocation state. No private-key column exists;
  metadata keys are constrained to `aaguid`, `transports`, `device_type`, and
  `discoverable`.
- `operator_role_assignments`: explicit `operator_admin` /
  `storage_reviewer` grants, grantor, grant/revocation times, reason, and
  bootstrap reference. A partial unique index permits one active assignment
  per operator and role.
- `operator_sessions`: operator/credential ownership, UUID, SHA-256-sized
  token digest, authentication/use/expiry timestamps, and revocation marker.
  Raw session tokens are not stored, and this is separate from the existing
  user cookie/Redis sessions.
- `storage_operator_audit`: actor, action, resource type/ID, prior/resulting
  state, reason, timestamp, and request UUID. Triggers reject update, delete,
  and truncate, including when invoked by the foundation owner.

Tables use ENABLE/FORCE RLS and an owner-only policy. No ordinary runtime role
gets schema usage or table privileges. Trigger functions are SECURITY INVOKER,
have fixed `search_path=pg_catalog,pg_temp`, and receive no PUBLIC EXECUTE.
There are no SECURITY DEFINER functions.

The migration requires a separately provisioned
`vervfy_operator_foundation_owner` role with NOLOGIN, NOINHERIT, and no elevated
attributes or pre-existing object privileges. Only the restricted migration
login may SET it, with inheritance and ADMIN denied. Preflight rejects other
effective memberships and unsafe role ownership/default privileges. The
temporary schema CREATE grant is revoked after creation. `app_runtime`,
`storage_cleanup_worker`, and `google_auth_lookup` cannot access the schema or
join the owner role.

## Provisioning and authorization model

There is no public registration path, ordinary-user promotion, or Google OAuth
link. New identities default to `pending`, and no administrator row is seeded.
The database guard only permits a first `operator_admin` bootstrap assignment
when no active administrator exists and an external provisioning reference is
provided. It disallows self-grants, requires active operators, and requires
later grants/revocations to be made by an active operator administrator.
Revoked assignments and audit history cannot be deleted or rewritten.
Suspended/revoked operators cannot receive new sessions, and changing an
operator to either status revokes existing sessions; session ownership must
match an unrevoked credential, and revoked sessions cannot be restored.

This is a constrained database model, not an operator-authentication system.
The migration login can SET the owner role and remains a privileged maintenance
principal; it is not suitable as a daily operator credential. There is no
individually authenticated production bootstrap/provisioner or approved
two-person break-glass ceremony in the existing architecture. Consequently,
the migration does not expose a production account-creation operation.
Disposable tests exercise owner-only inserts with synthetic data. Production
bootstrap still requires a separately approved, dual-controlled process using
an individual non-application principal and external change evidence; secrets
must not be put in SQL, metadata, or logs.

## Tests and results

Executed from the target worktree with sanitized environment and disposable
Unix-socket PostgreSQL fixtures:

```sh
env -i PATH=/usr/bin:/bin HOME=/tmp PYTHONPATH=tests:. \
  DATABASE_URL=sqlite:///:memory: VERVFY_ENVIRONMENT=development \
  VERVFY_SECRET_KEY=synthetic-phase4c21 \
  /home/sam/vervfy-latest/.venv/bin/python -m pytest -q \
  tests/test_operator_identity_foundation.py tests/test_storage_cleanup.py \
  tests/test_storage_lifecycle.py tests/test_storage_writers.py \
  tests/test_storage_boundaries.py tests/test_filesystem_storage.py \
  tests/test_security_regressions.py tests/test_staging_migrations.py \
  tests/test_oauth_postgres.py tests/test_oauth_schema.py \
  tests/test_google_oauth.py
```

**Result: 186 passed, 98 subtests passed, 16 warnings, 28.58 seconds, no skips.**
Fifteen warnings are existing Alembic `path_separator` deprecations; one is the
existing Pillow decompression-bomb warning from its boundary test. Ruff lint,
Ruff format check, and `git diff --check` passed.

Coverage includes identity creation/uniqueness and provisioning metadata,
credential ownership and metadata constraints, role grant/revocation and
bootstrap guardrails, suspended/revoked session rejection, session fencing,
runtime access denial, audit immutability, tenant RLS preservation, migration
head/upgrade/downgrade safety, and the Phase 4A–4C storage regressions.

## Remaining limitations

- Operator authentication and WebAuthn enrollment/verification are not
  implemented.
- No independent administrative session issuance, validation, or HTTP surface
  exists; the session table is metadata only.
- No production identity bootstrap or independent operator provisioning
  principal/ceremony exists.
- There is no application audit writer or production audit-retention/monitoring
  process.
- The database cannot validate that future `public_key` bytes are a valid
  public-only COSE key; future credential ingestion must parse and reject
  private key material before persistence.
- Role checks in table triggers are not a substitute for application-level
  session authentication, CSRF protection, authorization, or reviewed audit
  transactions.
- Hosted role provisioning, migration execution, and independent security
  review remain outstanding. Physical Storage deletion remains disabled.

No commit, push, merge, deployment, hosted migration, or physical deletion was
performed. This establishes a local database foundation, not completed or
production-ready operator authentication.
