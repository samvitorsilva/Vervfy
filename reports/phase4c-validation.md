# Phase 4C — manual review and recovery validation

## Outcome and scope

The existing system has no individually authenticated operator identity or
operator authorization mechanism. Implementing privileged inspection or recovery
without that foundation would create an unsafe administrative surface. This
change therefore does **not** add an inspection endpoint, SQL function, audit
table, or recovery action. It documents the blocker and verifies that ordinary
application access cannot inspect or modify exhausted jobs. Phase 4C's
operator-workflow objective remains incomplete; this is not production
readiness.

Worktree: `/home/sam/vervfy-latest/phase4a-retry-limits`. The worktree already
contained extensive unrelated changes. They were preserved.

## Exact files changed for this task

- `tests/test_storage_cleanup.py` — add a PostgreSQL regression proving
  `app_runtime` cannot read or modify a `manual_review` job and that the cleanup
  worker leaves it unchanged.
- `docs/storage-lifecycle.md` — document why no operator action is exposed and
  define authorization, data minimization, audit, locking, fencing, and retry
  requirements for future work.
- `reports/phase4c-validation.md` — this report.

No migration was added. Migrations 0028 and 0029 remain unchanged; their
SHA-256 values match the Phase 4B preservation record:

| Migration | SHA-256 |
|---|---|
| `0028_storage_cleanup_leases.py` | `e6be5fff5326ab693222f4611144d4409885e4715543da2f27c126bbd742939f` |
| `0029_storage_cleanup_retry_limits.py` | `a8ba0312536235ebf2a87859305a78862c61ac1b362c135ba188166efb0ef76f` |

## Architecture and security decision

Migration 0027 grants tenant-scoped object visibility to `app_runtime`, which
has no direct access to the cleanup-job table. The restricted cleanup worker
receives execution of its narrowly scoped cleanup routines; lifecycle ownership
and migration principals retain privileged maintenance authority. The worker
identity is not a human identity. The `app.current_user_id` setting is ordinary
tenant context and is not an authorization credential. Reusing any of these
identities for operator access would either expose cross-tenant cleanup metadata
or grant excessive authority.

The documentation records a future safe design: individually authenticated
operator principals, a separately provisioned least-privilege boundary, a
strictly allowlisted read-only inspection, actor identity derived from the
authenticated principal, and append-only audit entries committed atomically
with serialized object-before-job changes. No credentials, signed URLs, paths,
or user content should be returned. Recovery must keep reference and token
fences and retain the original attempt count; any additional bounded retry
budget needs a separately reviewed policy/schema change.

## Authorization and audit evidence

- `test_application_runtime_cannot_inspect_or_modify_manual_review_jobs`
  verifies PostgreSQL denies direct `SELECT` and `UPDATE` through `app_runtime`
  and confirms the job remains `manual_review`, at its original attempt count,
  with the object's `deleting` fence intact.
- Existing Phase 4A/4B cleanup regressions verify that manual-review rows are
  not automatically claimed, stale tokens cannot complete or retry, leases
  fence concurrent workers, and reference checks prevent deletion/attachment
  bypasses.
- There is no operator audit relation or operator function to authorize or
  mutate. Consequently authorized inspection, operator decision auditing,
  invalid operator-action rejection, recovery retry accounting, and concurrent
  operator-action semantics are **not implemented or claimed as tested**.
- No unauthenticated administrative endpoint was added. No hosted database,
  production database, real user data, or physical Storage deletion was used.

## Tests and complete results

Executed from the target worktree against disposable local PostgreSQL fixtures
and synthetic storage objects:

```sh
env -i PATH=/usr/bin:/bin HOME=/tmp PYTHONPATH=tests:. \
  DATABASE_URL=sqlite:///:memory: VERVFY_ENVIRONMENT=development \
  VERVFY_SECRET_KEY=synthetic-phase4c \
  /home/sam/vervfy-latest/.venv/bin/python -m pytest -q \
  tests/test_storage_cleanup.py tests/test_storage_lifecycle.py \
  tests/test_storage_writers.py tests/test_storage_boundaries.py \
  tests/test_filesystem_storage.py
```

**Result: 86 passed, 88 subtests passed, 10 warnings, 11.12 seconds, no skips.**
The warnings are existing Alembic `path_separator` deprecations. Ruff lint,
Ruff format check, and `git diff --check` passed.

## Remaining blockers

- Individually authenticated operator principals and a reviewed role-membership
  / authorization provisioning procedure.
- A least-privilege inspection mechanism with tenant authorization and data
  minimization.
- An immutable, operator-attributed audit schema and authorized, serialized
  retain/provider-verification/requeue actions.
- A retry policy for post-exhaustion recovery that preserves the historical
  attempt count, plus regression tests for all authorized operator actions,
  audit immutability, invalid inputs, and concurrent decisions.
- Independent security review and hosted migration/role validation.
- Production Storage deletion remains disabled and has no production deleter.

No commit, push, merge, deployment, hosted migration, or physical deletion was
performed. These local test results do not establish production readiness.
