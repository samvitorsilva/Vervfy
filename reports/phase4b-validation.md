# Phase 4B — PostgreSQL completion failure recovery

Worktree: `/home/sam/vervfy-latest/phase4a-retry-limits`.

## Exact files changed in this task

- Modified `tests/test_storage_cleanup.py`: three regression tests and test-only fault/fencing helpers.
- Added `reports/phase4b-tests.log`: passing suite output.
- Added `reports/phase4b-preservation.json`: preservation check and migration hashes.
- Added `reports/phase4b-validation.md`: this report.

A pre-edit SHA-256 inventory of existing worktree files was compared after the
change. Only `tests/test_storage_cleanup.py` changed (generated caches excluded).
Migrations 0028 and 0029 and all existing Phase 4A artifacts remain unchanged.
No production implementation, adapter, configuration, or frozen RC was edited.
No commit, push, merge, deployment, hosted database connection, or physical
cleanup enablement was performed.

## Failure evidence

1. `test_completion_transaction_failure_rolls_back_and_recovers`:
   the worker commits its claim and deletes the synthetic object. The real
   `complete_cleanup` SQL returns true inside the completion transaction.
   An independent database connection still sees claimed/deleting before commit.
   PostgreSQL division-by-zero (SQLSTATE 22012) then aborts that transaction.
   Independent reads verify claimed/deleting, attempt 1, retained token/lease,
   and absent synthetic bytes. A worker cannot reclaim the live lease; attaching
   a reference fails. After explicit lease expiry the old token cannot complete.
   Another worker deletes the already-missing object successfully and commits
   done/deleted at attempt 2 with token/lease cleared. Subsequent completion
   and claim attempts cannot change that result or cause additional deletion.

2. `test_lost_completion_commit_acknowledgement_keeps_durable_done`:
   real PostgreSQL completion and commit succeed, then a test-only session
   context wrapper raises ConnectionError before returning to the worker.
   This models the application-visible lost acknowledgement, not a network
   packet fault. Independent reads see done/deleted at attempt 1, no token or
   lease, and absent bytes. The prior token cannot complete again; three fresh
   workers find no claimable work. Exactly one deletion call occurs.

3. `test_eighth_completion_failure_requires_manual_review_without_redelete`:
   the same real SQL failure on claim 8 rolls completion back to claimed/deleting.
   The live lease remains protected. After expiry the scanner preserves the
   deleting fence and obligation in manual_review at attempt 8 with
   attempt_limit_lease_expired, clearing token/lease. No ninth adapter call,
   stale completion, reference attachment, or automatic retry is permitted.
   The synthetic object is absent; manual reconciliation remains necessary.

Existing tests also pass for concurrent claims, stale-token fencing, lease
expiry, referenced audio/covers/photos/uploads, eight provider failures, eight
crashes, mixed failures, and successful completion on the eighth claim.

## Validation

Executed from the worktree:

```sh
env -i PATH=/usr/bin:/bin HOME=/tmp PYTHONPATH=tests:. \
  DATABASE_URL=sqlite:///:memory: VERVFY_ENVIRONMENT=development \
  VERVFY_SECRET_KEY=synthetic-phase4b \
  /home/sam/vervfy-latest/.venv/bin/python -m pytest -q \
  tests/test_storage_cleanup.py tests/test_storage_lifecycle.py \
  tests/test_storage_writers.py tests/test_storage_boundaries.py \
  tests/test_filesystem_storage.py
```

**85 passed; 88 subtests passed; 10 existing Alembic path_separator warnings;
11.17 seconds; no skips.** Ruff lint, Ruff format check, and git diff --check pass.
The only subsequent test-file edit was line wrapping for formatting.

The initial sandbox run could not start disposable PostgreSQL (9 passed,
76 setup errors). The approved run outside the sandbox passed. The existing
fixture creates temporary private Unix-socket PostgreSQL clusters with TCP
listeners disabled, uses restricted worker roles, and stops clusters at teardown.
Storage objects are synthetic; filesystem tests use temporary synthetic files.

## Remaining Phase 4 blockers

- Production Storage adapter and provider absence/idempotency semantics remain
  unimplemented/unverified; physical cleanup remains disabled.
- Hosted migrations, role/ACL provisioning, independent security review, and
  previously identified hosted catalog findings remain outstanding.
- Manual-review monitoring, audited reconciliation tooling, and an erasure-status
  surface are still required, including absent-object exhaustion reconciliation.
- Provider retention, backups/restoration, and operational rollout/recovery
  verification remain outstanding. Real transport-level lost-ack behavior was
  not exercised by the deterministic application-boundary simulation.

This is local regression evidence, not production readiness.
