# Phase 4A bounded cleanup retries — local validation

Implementation worktree: `/home/sam/vervfy-latest/phase4a-retry-limits`.
Created detached at `dd22f18`; `git status --porcelain` was empty before copying
`release-artifacts/final-local-rc/source` as the approved baseline. The frozen
source is untracked in the original checkout, so Git HEAD alone is not the RC
baseline. No commit, push, merge, deployment or hosted migration was performed.
Existing checkout and existing Phase 4 worktree changes were left untouched.

## Exact implementation delta from frozen source

- Added `alembic/versions/0029_storage_cleanup_retry_limits.py`.
- Changed `tests/test_storage_cleanup.py`.
- Changed `docs/storage-lifecycle.md`.

Evidence files added in this worktree:

- `reports/phase4a-baseline.json`: SHA-256 hashes of the copied frozen source.
- `reports/phase4a-tests.log`: final focused-suite output.
- `reports/phase4a-validation.md`: this report.

All baseline source hashes were rechecked against the frozen source after tests;
none changed. Worktree migration 0028 remains byte-identical to the frozen copy.
Only the two listed existing source files differ from the copied baseline.
Generated Python/pytest caches are not implementation artifacts.

## Migration and behavior

Revision: `0029_cleanup_retry_limits` (fits Alembic's varchar(32) version column).
Parent: `0028_storage_cleanup_leases`.
The requested migration filename is retained. Downgrade raises explicitly.

Ordinary claims and expired-lease reclamations increment the same counter.
Eight claims maximum; an eighth success can complete. An eighth provider failure
enters manual review immediately; an expired eighth claim enters manual review
on the next scanner visit, without another adapter call. Existing exhausted
pending/expired rows cannot obtain a ninth claim; historical counts are retained.
Live claims retain their lease. Manual review clears token/lease, retains the
outbox and deleting fence, and records an explicit exhaustion reason alongside
the last provider error. No automatic reclaim/reset capability is supplied.

Object-before-job locking, SKIP LOCKED, reference protection, restricted ACLs,
RLS, token/expiry fencing and pre-exhaustion backoff remain intact. Neither a
production delete adapter nor physical cleanup enablement was introduced.
Operator documentation requires audit preservation, quiescing in-flight workers,
namespace/reference verification, retaining deletion fences, and separately
reviewed reconciliation; resetting attempts to bypass the limit is prohibited.

## Validation

Run from this worktree using a sanitized environment:

```sh
env -i PATH=/usr/bin:/bin HOME=/tmp PYTHONPATH=tests:. \
  DATABASE_URL=sqlite:///:memory: VERVFY_ENVIRONMENT=development \
  VERVFY_SECRET_KEY=synthetic-phase4a \
  /home/sam/vervfy-latest/.venv/bin/python -m pytest -q \
  tests/test_storage_cleanup.py tests/test_storage_lifecycle.py \
  tests/test_storage_writers.py tests/test_storage_boundaries.py \
  tests/test_filesystem_storage.py
```

**82 passed; 88 subtests passed; 10 warnings; 11.28 seconds.**
Warnings are the existing Alembic `path_separator` deprecation. No tests skipped.
Ruff lint passed for the migration and cleanup test file; `git diff --check`
passed. PostgreSQL fixtures create private temporary Unix-socket clusters with
TCP disabled and synthetic objects only; teardown stops those clusters.

The initial sandbox run could not start PostgreSQL (9 passed, 73 setup errors).
The authorized unsandboxed run exposed the initial 33-character revision name
(9 passed, 73 setup errors). Shortening the revision resolved that defect; the
final run above passed. No unresolved regression was observed in these suites.
No hosted connection, real user data, production deletion or hosted migration
was used. Local filesystem deletion tests operate only on synthetic /tmp data.

## Remaining Phase 4 gates

- Production Storage adapter/provider absence and idempotency semantics remain
  unimplemented/unverified; physical cleanup stays disabled.
- Hosted migration, role/ACL provisioning and independent security review remain
  outstanding. This task does not resolve earlier hosted catalog findings.
- Manual-review monitoring, audited operator recovery tooling and an erasure-status
  surface are not supplied by this migration.
- Provider retention, backups/object restoration and operational rollout/recovery
  verification remain outstanding.

These results establish local regression coverage, not production readiness.
