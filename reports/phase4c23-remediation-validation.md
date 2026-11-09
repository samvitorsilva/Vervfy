# Phase 4C.2.3 — Operator Foundation Remediation Validation

## Scope

Implemented the selected database-foundation follow-ups from the Phase 4C.2.2
audit: single-use first-administrator bootstrap history and monotonic
credential revocation that invalidates existing sessions. Reassessed the audit
owner-tampering concern and documented why it cannot be solved inside the same
database trust boundary.

No hosted or production database, real identity, or Storage service was
accessed. PostgreSQL validation used test-created Unix-socket clusters and
synthetic identities/objects only.

## Exact files changed

- `alembic/versions/0031_operator_revocation_bootstrap_guards.py` — new
  forward-only revision after `0030_operator_foundation`.
- `tests/test_operator_identity_foundation.py` — regression tests for
  credential-driven session revocation, prevention of credential restoration,
  and bootstrap replay after revocation; updated migration head assertions.
- `tests/test_staging_migrations.py` — updated linear-chain head/count and
  downgrade-refusal checks.
- `docs/storage-lifecycle.md` — documented migration 0031 and the audit-owner
  trust boundary.
- `reports/phase4c22-security-audit.md` — appended follow-up disposition and
  unresolved findings.
- `reports/phase4c23-remediation-validation.md` — this report.

Migrations 0028, 0029, and 0030 were not modified.

## Schema and security changes

Revision `0031_operator_revocation` depends on `0030_operator_foundation`.
It replaces the active-only bootstrap index with a lifetime uniqueness
constraint for the initial `operator_admin` assignment, uniquely indexes its
bootstrap reference, and updates the role-assignment trigger to reject any
second bootstrap after the first assignment has been revoked. Upgrade fails
closed if it encounters multiple historical bootstrap administrators.

Credential UPDATE is guarded by a SECURITY INVOKER trigger with fixed
`search_path=pg_catalog,pg_temp`. Once revoked, a credential cannot be updated
again, including to clear `revoked_at`. The transition to revoked atomically
revokes all extant sessions tied to that credential. The trigger function has
no PUBLIC or application-role execute grant. No SECURITY DEFINER function,
new runtime grant, or administrative endpoint was added.

First-admin creation is still not an independently authenticated provisioning
process. The migration-owner capability remains the database write boundary;
the reference is replay-resistant history, not proof of human authorization.
Do not provision production operators until a separate, individually
authenticated and reviewed bootstrap ceremony exists.

Audit records are protected from direct UPDATE/DELETE/TRUNCATE DML, but not
tamper-proof against the table owner or migration login, which can alter
same-database triggers/schema objects. No independent audit sink is available.
This is explicitly documented as an unresolved trust-boundary limitation.

## Validation results

All commands used Python 3.12.7 in a temporary environment and disposable
local PostgreSQL fixtures:

| Suite | Result |
|---|---:|
| `test_operator_identity_foundation.py` | 10 tests passed |
| `test_staging_migrations.py` | 9 tests passed |
| `test_storage_cleanup.py` | 20 tests passed |
| `test_storage_lifecycle.py` | 23 tests passed |
| Ruff check, Ruff format check, `git diff --check` | Passed |

Total: **62 tests passed**, no skips in the reported suites. Existing Alembic
`path_separator` deprecation warnings remain.

The operator regressions specifically confirm credential revocation revokes
its session, credential revocation cannot be cleared, and a revoked first
administrator cannot be replaced by replaying the same or a new reference.
Two concurrent first-administrator provisioning transactions also produce
exactly one active bootstrap assignment.
The existing storage lifecycle/cleanup suites continue to pass against the
new migration head, including retry and lease-fencing behavior.

## Remaining blockers

- No safe production first-operator bootstrap or individual operator
  authentication exists.
- No WebAuthn ceremonies, administrative sessions/API, recovery endpoints, or
  audit-writing service exist.
- A separately controlled append-only audit sink is required to resist
  database-owner tampering.
- Future authorization must check current identity status and current
  unrevoked role assignments; role assignments are not automatically revoked
  when an operator is suspended/revoked.
- No production readiness is claimed. Physical Storage deletion remains
  disabled.

No commit, push, merge, or deployment was performed.
