# Local storage-cleanup verification — 2026-11-16

Status as of 2026-11-17: 159 synchronous regression tests passed; HTTP/async and
PostgreSQL integration remain blocked by sandbox socket permissions. This is not
a production physical-cleanup readiness sign-off. See the latest entry below.

## Scope and files

- `tests/isolated_storage_cleanup.py`: memory-only worker with explicit local
  database/environment checks, immutable binding validation, committed claims,
  locked pre-delete authorization, absence verification and fenced persistence.
- `tests/test_isolated_storage_cleanup.py`: 15 disposable PostgreSQL integration
  cases, including restricted real logins, concurrency and fault injection.
- `tests/test_isolated_storage_guards.py`: non-database guard and worker-ordering
  tests (21 cases including the psycopg DDL regression below).
- `docs/account-deletion-production-checklist.md`: corrected deferred cleanup
  semantics, operational limits and separate production authorization boundary.
- This verification record.

Existing README/password-reset edits and backup/draft files were preserved.
No production code, migration, production ACL, deployment setting or credential
was modified. No commit, push, merge, deployment or PR was performed.

## Security findings

Existing migrations already implement immutable namespaces, forced RLS, tenant
reservation/attachment checks, reference-trigger locking, unique claim tokens,
60-second leases, SKIP LOCKED claims, eight-attempt retry exhaustion and retained
manual-review obligations. These implementations were reused, not duplicated.

Migration 0033 revokes production claim permissions. The default cleanup worker
and audio-store deletion functions remain disabled. Namespace physical cleanup
is constrained to false. The test fixture adds wrappers only inside its newly
created disposable database; it does not grant the original claim function back
to production runtime/worker roles. No migration or CLI installs these wrappers.

The previous checklist incorrectly required physical object absence and described
Storage deletion before database commit. The account route instead commits
record deletion and trigger-created cleanup obligations together, returning
`storage_cleanup=pending`. The checklist now matches that implementation.

The rehearsal restricts storage to the exact synthetic memory adapter. Before
storage access, it checks database destination, actual login, READ COMMITTED,
namespace binding, object identity, tenant/requester ownership, reference absence,
lease and token. It holds object/job locks through memory I/O. Completion requires
an independent absence check and successful fenced SQL result. Unknown failures
abort the transaction; committed claims remain recoverable through lease expiry.

## Commands and actual results

Commands ran from `/home/sam/vervfy-latest` using `.venv/bin/python` and a cleared
environment with only PATH, HOME=/tmp, DATABASE_URL=sqlite:// (import placeholder),
VERVFY_SECRET_KEY=synthetic-test and PYTHONPATH=.:tests. No production URLs were
used. Integration fixtures create fresh Unix-socket-only PostgreSQL clusters.

Regression invocation: `python -m pytest -q` with:

- `tests/test_isolated_storage_guards.py`
- `tests/test_storage_cleanup_worker_disabled.py`
- `tests/test_storage_production_runner.py`
- `tests/test_storage_production_role_graph.py`
- `tests/test_storage_production_diagnostics.py`
- `tests/test_storage_supabase_acl.py`
- `tests/test_storage_migration_role_validation.py`
- `tests/test_security_regressions.py`
- `tests/test_provider_regression_guard.py`

Result: **71 passed, 2 setup errors, 1 warning**, 15.16 seconds.
The two setup errors are the existing SupabaseACLTests and
UnauthorizedPrivilegeTests: disposable PostgreSQL could not start. The warning
is the intentional oversized-image security test's PIL DecompressionBombWarning.
Log: `/tmp/vervfy-cleanup-regressions.log`.

New integration invocation: `python -m pytest -q tests/test_isolated_storage_cleanup.py`.
Final result: **15 setup errors**, 2.59 seconds. No integration test body ran.
The initial 11-case run also failed at the same setup step before four additional
fault/concurrency cases were added. Log: `/tmp/vervfy-isolated-cleanup-final.log`.

A disposable startup diagnostic confirmed PostgreSQL 18.7 reports:
`could not bind Unix address ... Operation not permitted`, followed by
`could not create any Unix-domain sockets`. Sandbox approval is unavailable in
this session. Tests were not skipped, weakened, or replaced with SQLite evidence.

Checks on all three new Python files:

- `ruff check`: passed after fixing import/style findings.
- `ruff format --check`: passed; three files already formatted.
- `python -m compileall -q`: passed.
- `git diff --check`: passed.

## Remaining risks and release assessment

PostgreSQL RLS, SQL execution, concurrency, claim fencing and recovery behavior
must still be verified by actually running the integration suite where private
Unix socket creation is allowed. Static checks and non-database test passes do
not establish these properties. The new integration fixture itself is therefore
not yet execution-validated beyond initialization.

The synthetic adapter intentionally does not model actual Supabase consistency,
network cancellation, provider error codes or physical-delete authorization.
Its absence check validates only the synthetic store. Real provider semantics,
remote operations continuing after lease expiry, network deadlines, credentials,
monitoring, backlog/legacy reconciliation and production canary authorization
remain separate work. Test-only definer wrappers must never be installed in a
persistent or production database.

Production physical cleanup remains disabled and is **not ready for activation**.
The existing deferred database-record deletion architecture is unchanged.

## Follow-up PostgreSQL verification — 2026-11-16

Retested startup using a freshly initialized disposable PostgreSQL 18.7 cluster.
`initdb` succeeds. Unix-socket startup fails at bind with `Operation not permitted`.
A separate loopback TCP socket probe also fails with that error. PostgreSQL with
Unix sockets disabled and `listen_addresses='127.0.0.1'` fails to create its IPv4
socket, then exits with `could not create any TCP/IP sockets`. No external host
was contacted. The temporary cluster was removed after the failed starts.

Reran the preceding regression set together with
`tests/test_isolated_storage_cleanup.py` and `tests/test_staging_migrations.py`,
using the same cleared environment. Result: **74 passed, 24 setup errors,
2 warnings in 18.73 seconds**. The errors comprise 15 cleanup tests, two ACL tests
and seven staging PostgreSQL tests (including RLS). All failed during server
startup, before test bodies. The three additional passing tests are migration
chain/SQLite checks, not PostgreSQL RLS evidence. Warnings were the existing
Alembic configuration deprecation and intentional PIL oversized-image warning.

Log: `/tmp/vervfy-cleanup-verification-continuation.log`.
Ruff on the three new Python files and `git diff --check` passed again.

No application defect was established by these setup failures, so no code,
security checks, production grants or deletion controls were changed. Existing
working-tree changes remain preserved. Verification requires an execution
environment permitting a private PostgreSQL listener; neither Unix nor TCP is
permitted in this session. Sandbox escalation is unavailable. No production
access, commit, push or deployment occurred; production deletion remains disabled.

## Exact 24-test rerun — 2026-11-16

The execution environment remains restricted; no separate local-machine executor
is available in this session. A fresh disposable PostgreSQL 18.7 cluster again
initialized successfully, but both private Unix-socket startup and loopback TCP
startup exited 1 with `Operation not permitted`. No existing database was used.

Ran exactly the previously blocked tests with the cleared environment described
above:

```sh
.venv/bin/python -m pytest -q tests/test_isolated_storage_cleanup.py \
  tests/test_storage_supabase_acl.py \
  tests/test_staging_migrations.py::StagingPostgresTests
```

Result: **24 setup errors in 5.58 seconds; zero test bodies executed**.
Log: `/tmp/vervfy-postgres-24-verification.log`.
RLS, ACL, concurrent claims and cleanup fencing remain execution-unverified.
No genuine code failure could be established and no security check was relaxed.
Only this verification record was updated during this follow-up; all existing
changes were preserved. No production/staging connection, commit, push,
deployment or production deletion occurred. The remaining prerequisite is to
run the same tests on a host/session that permits a private PostgreSQL listener.

## Uncommitted implementation security review — 2026-11-16

Reviewed all three new cleanup Python files and both cleanup documents, plus the
existing namespace/storage validation and lifecycle/lease/retry/disable SQL.
No PostgreSQL process or connection was attempted during this review.

### Confirmed findings and fixes

1. **Connection validation happened too late.** Both worker entry points called
   `engine.begin()` before checking the environment and database URL. A caller
   supplying an unintended engine could therefore open a connection before being
   rejected. Two regression cases reproduced this ordering flaw: 2 failed and
   5 passed before the fix. `preflight()` now runs before checkout in both
   `claim()` and `process()`, and validation runs again inside the transaction.
   Tests cover absent opt-in and a remote engine with an otherwise valid synthetic
   local configuration, asserting that no connection checkout occurs. Storage
   adapter type is also rechecked to reject replacement after construction.
2. **Excess privilege in a test-only fault injector.** The expiry simulation
   installed a SECURITY DEFINER function as the disposable cluster administrator,
   allowed expiry by object ID alone, and retained it after the test. It now runs
   as the restricted lifecycle owner, requires the matching claim token and
   claimed state, and is dropped during test cleanup. This change is confined to
   the disposable integration fixture; no production function or grant changed.
   Its PostgreSQL execution remains unverified.

Static review found no further confirmed tenant-isolation bypass in the new
worker. Tenant/requester/path ownership, reference absence and token/lease checks
are enforced by the fixture's locked authorization wrapper. Existing forced RLS,
fixed SECURITY DEFINER search paths, reference-trigger lock ordering, committed
claims, eight-attempt exhaustion and retained manual-review jobs are preserved.
The dedicated worker is intentionally cross-tenant; application users do not
receive its wrapper permissions. No production migration, adapter or entry point
imports the rehearsal worker.

Added Python control-flow tests for false/NULL authorization, database exceptions,
provider timeout/ambiguity, an object still present after deletion, absence before
completion, rejected retry/completion, and unknown storage exceptions. These use
stubbed SQL outcomes solely to verify Python ordering and fail-closed behavior;
they do not constitute RLS, locking, SQL or lease correctness evidence.

### Verification results

- Focused cleanup guards, disabled-worker, migration-role/runner/diagnostic,
  security/provider regressions and non-PostgreSQL migration-chain tests:
  **89 passed, 2 warnings in 13.50s**.
  Log: `/tmp/vervfy-cleanup-audit-focused.log`.
- Broader synchronous test selection, excluding PostgreSQL and socket-dependent
  Redis fixtures, HTTP TestClient files and asynchronous test methods:
  **286 passed, 4 failed, 2 errors, 7 skipped, 71 deselected,
  229 subtests passed** in 23.50s.
  Log: `/tmp/vervfy-cleanup-audit-final-tests.log`.
- Additional synchronous cases from mixed HTTP/unit-test modules:
  **23 passed, 2 failed, 8 subtests passed** in 1.50s.
  Log: `/tmp/vervfy-cleanup-audit-extra-tests.log`.
- The two broad-run errors and two extra-run failures required optional passkey
  configuration. A first configuration retry correctly refused startup without
  REDIS_URL. With complete synthetic configuration and an unused Redis socket
  path inside a new temporary directory, the selected passkey suite returned
  **6 passed in 1.86s**, without starting Redis.
  Log: `/tmp/vervfy-cleanup-audit-passkey-config.log`.
- Four remaining failures reproduced in a separate invocation that does not
  import the new cleanup code: incomplete old schema fixture (media_version /
  processing_token), a test expecting head 0031 instead of existing 0033,
  the older production runner's pinned 0028 history check, and staging manifest
  file-set validation. These are in unchanged code/tests and were not weakened
  or updated to authorize newer production migrations.
  Log: `/tmp/vervfy-cleanup-audit-existing-failures.log`.
- Ruff, format check, compileall and `git diff --check`: passed on changed Python
  files / tracked diff.

Broad HTTP/async testing also stalled in existing tests, independently of cleanup:
ArtistPhotoApiTests.test_photo_data_is_isolated_between_users waited in the
TestClient/AnyIO portal, and test_production_reauth_failure_logs_only_fixed_stage
waited in asyncio with an AnyIO worker thread. Diagnostic stack dumps were
captured; the runs were interrupted/bounded, not reported as passing. Their root
cause was not established. Logs: `/tmp/vervfy-cleanup-audit-client-diagnostic.log`
and `/tmp/vervfy-cleanup-audit-no-client-tests.log`. Test selection was external
(`/tmp/vervfy-run-no-services.py`); no repository test was disabled or weakened.

PostgreSQL RLS, ACL, concurrent claim and fencing integration tests remain blocked
and were explicitly not retried. Real Supabase behavior remains outside this
memory-only rehearsal. Production deletion stays disabled; all prior unrelated
changes were preserved. No commit, push, deployment or production access occurred.

## Schema/revision and HTTP/async follow-up — 2026-11-16

### Four diagnosed test defects

| Failure | Cause | Correction |
| --- | --- | --- |
| StartupSchemaTests existing-schema success case | Fixture lacked tracks/artist_photos media_version and upload_jobs processing_token required by the existing startup guard | Supply a current synthetic SQLite schema; compare the complete sqlite_master schema before/after startup and preserve row assertions. Add rejection checks for each missing lifecycle column. |
| Passkey migration graph | Expected head 0031 although the checkout already contains 0032 and 0033 | Pin the test to 0033 and assert both new parent links, retaining original additive schema checks. |
| Production migration authorization success case | Expected the legacy runner pinned to 0028 to accept a checkout at 0033 | Exercise acceptance against a disposable copy of exactly the pinned 0028 history; add explicit rejection of the newer checkout. |
| Staging approval success case | Included 33 migrations in a manifest governed by the existing 31-migration approval boundary | Exercise acceptance with a disposable pinned 0031 history and its manifest; explicitly verify rejection of the newer checkout. |

Added `tests/migration_snapshot.py` to copy, but never execute, an explicit pinned
migration history. Only tests and this report changed during this follow-up:
`tests/test_oauth_schema.py`, `tests/test_passkeys.py`,
`tests/test_production_migration.py`, and `tests/test_staging_guard.py`.
No production/staging guard constant, approval requirement, runtime schema check,
application concurrency behavior, migration or cleanup permission was changed.
The legacy deployment runners intentionally remain unusable against the newer
checkout without separately reviewed authorization.

### Confirmed async hang mechanism

Independent subprocess probes used no Vervfy imports or database connections:

- `asyncio.run(asyncio.sleep(0))`: passed.
- `asyncio.to_thread`, AnyIO thread worker, and a bare FastAPI TestClient request:
  each exceeded a five-second limit and was terminated.
- A local socketpair write raised `PermissionError: [Errno 1] Operation not permitted`.
- An asyncio debug reproduction printed `Synthetic worker completed`, followed
  by `Fail to write a null byte into the self-pipe socket` and that PermissionError
  at `asyncio/selector_events.py:_write_to_self`; it timed out after five seconds.

The thread completes but cannot wake the selector through its socketpair. Python
catches this OSError in `_write_to_self`, leaving work queued while the selector
waits. This explains both the TestClient portal hang and the OAuth callback's
thread-pool hang. It is an execution-environment restriction, not a demonstrated
Vervfy deadlock. No polling workaround, inline replacement of thread-pool work,
dependency downgrade or security-check bypass was introduced.
Evidence: `/tmp/vervfy-asyncio-wakeup-diagnostic.log`.

### Bounded verification

Final affected synchronous suite (60-second outer limit): **138 passed, 7 skipped,
5 warnings, 135 subtests passed in 5.53s**. Includes all OAuth schema tests, the
passkey graph test, production authorization and staging guard tests, cleanup
unit guards and disabled worker, storage role/runner/diagnostic tests, and the
non-PostgreSQL MigrationChainTests. The seven skips are existing deprecated
staging tests explicitly replaced by strict Supabase guard coverage. All five
warnings are Alembic's existing missing path_separator deprecation.
Log: `/tmp/vervfy-security-followup-tests.log`.

Two affected tests were run individually with faulthandler dumps at five seconds
and hard subprocess timeouts at ten seconds:

- ArtistPhotoApiTests.test_photo_data_is_isolated_between_users: timed out.
- test_production_reauth_failure_logs_only_fixed_stage
  [missing_auth_time-freshness_missing_auth_time]: timed out.

Both child processes were terminated; neither test passed or reached assertions.
Logs: `/tmp/vervfy-http-bounded.log`, `/tmp/vervfy-oauth_async-bounded.log`.

Compilation and whitespace checks passed. Ruff passed for the new helper,
passkey tests and cleanup files. The other three edited legacy test files retain
10 pre-existing Ruff findings (2/4/4 respectively); comparison with HEAD found no
new lint findings. Import ordering was corrected without wholesale formatting.

Remaining blockers: HTTP/async integration needs an environment permitting
socketpair wake-up writes; PostgreSQL RLS/ACL/concurrency verification still needs
a permitted local database listener. PostgreSQL was not retried. All existing
changes were preserved. No production/staging access, commits, pushes,
deployments or production deletion occurred.

## Release verification continuation — 2026-11-17

Read the complete prior report and preserved all implementation, test and safety
fixes. Checked prerequisites before rerunning integrations:

- Socketpair write: `PermissionError`, errno 1 (EPERM).
- Private Unix-domain bind in a newly created temporary directory: EPERM.
- Loopback TCP bind to an OS-selected port: EPERM.

No external endpoint was contacted. This session still has no permitted local
listener/wake-up mechanism and no separate execution environment available.
Consequently HTTP/async tests were not rerun into known hangs, and PostgreSQL
was not started or connected to. These prerequisites are blockers, not passing
test results; prior integration results remain unchanged and unverified.

### Regression results

Ran the following with the documented cleared synthetic environment and a
60-second outer timeout:

```text
tests/test_oauth_schema.py
tests/test_passkeys.py::test_migration_graph_is_additive
tests/test_production_migration.py
tests/test_staging_guard.py
tests/test_isolated_storage_guards.py
tests/test_storage_cleanup_worker_disabled.py
tests/test_storage_migration_role_validation.py
tests/test_storage_production_runner.py
tests/test_storage_production_role_graph.py
tests/test_storage_production_diagnostics.py
tests/test_staging_migrations.py::MigrationChainTests
tests/test_security_regressions.py
tests/test_provider_regression_guard.py
```

Result: **158 passed, 7 skipped, 6 warnings, 135 subtests passed in 10.36s**.
No test failure or new code defect was observed. Seven existing deprecated
staging tests remain skipped; warnings comprise five Alembic path_separator
deprecations and the intentional oversized-image security test warning.
Log: `/tmp/vervfy-release-20261117-regressions.log`.

Ruff passed for the migration snapshot helper, passkey graph tests and all three
cleanup Python files. Format checks passed for the helper and three cleanup
files. Compilation of all eight implementation/test files touched in prior
follow-ups and `git diff --check` passed. Existing legacy lint findings described
above were not claimed to be resolved.

Rechecked the disabled production worker, namespace constraint requiring
`physical_cleanup_enabled=false`, and migration 0033 claim-permission revocation.
No guard, credential, database, storage object, application code or test was
changed in this continuation; only this report was updated. No commit, push,
merge or deployment occurred.

### Remaining release blockers

HTTP/async integration still requires an environment permitting socketpair
writes. PostgreSQL integration still requires a fresh disposable local cluster
with permitted socket binding; RLS, ACL, concurrent claims, lease fencing and
cleanup recovery must actually pass there. No SQLite or mock pass substitutes
for those results. Production physical deletion remains disabled and is not
approved for activation.

## Outside-sandbox execution request — 2026-11-17

Read the report and inspected available execution capabilities. The only command
executor available in this session is sandboxed; the managed permission policy
disables sandbox escalation (`sandbox_approval=false`). No separate local or
remote test executor is connected. User authorization does not change that
execution capability.

No HTTP/async or PostgreSQL test was rerun in this continuation, and no new test
result is claimed. The latest completed regression result remains 158 passed,
7 skipped, 6 warnings, with 135 subtests passed. No code changes were justified
without new failure evidence. Only this report was updated; whitespace validation
passed and all existing changes and safety guards were preserved.

To complete verification, this checkout must be available to an authorized local
executor outside the restricted sandbox, permitting socketpair writes and a
private disposable PostgreSQL listener. The existing integration fixtures create
their own fresh cluster; do not supply an existing production or staging database.
Until that execution environment is available, HTTP/async behavior and PostgreSQL
RLS/ACL/concurrency/fencing remain unverified. No production access, physical
deletion, commit, push, merge or deployment occurred.

## psycopg 3 `%ROWTYPE` DDL correction — 2026-11-17

Confirmed the reported parser defect without a server: psycopg's query converter
rejects `objects%ROWTYPE` when given an empty parameter mapping, interpreting `%R`
as a placeholder. The fixture already used SQLAlchemy `exec_driver_sql()`, but
that API normally still supplies empty parameters to the driver.

Moved the unchanged authorization function DDL into
`_install_cleanup_authorizer()` in `tests/test_isolated_storage_cleanup.py` and
used `exec_driver_sql(..., execution_options={"no_parameters": True})` for that
static DDL only. SQLAlchemy now calls `cursor.execute(statement)` without a
parameter mapping. PostgreSQL receives literal `%ROWTYPE` unchanged. No bound
value-bearing statement, tenant/reference/token/lease condition, function owner,
search path, grant or production permission was changed.

Added `test_rowtype_ddl_reaches_psycopg_without_parameter_processing` to
`tests/test_isolated_storage_guards.py`. It exercises real SQLAlchemy psycopg
dialect dispatch into a stub DBAPI cursor and uses psycopg's actual query parser;
assertions verify no parameter argument and byte-for-byte identical SQL. A
control conversion with an empty mapping reproduces the original ProgrammingError.
This is driver-dispatch evidence, not PostgreSQL execution evidence.

The shared disposable fixture in `tests/test_staging_migrations.py` now explicitly
uses port **55432** for both startup and its SQLAlchemy URL. It still creates a
new cluster in a private temporary directory, sets `listen_addresses=''`, and
uses a private Unix socket. It never connects to an existing service on that port
or enables a TCP listener. All derived cleanup/ACL/migration tests inherit this.

### Actual rerun results

- Focused psycopg DDL regression: **1 passed in 1.00s**.
- Isolated PostgreSQL success/idempotency test: **1 setup error in 1.84s**;
  `pg_ctl` failed before the DDL or test body ran.
  Log: `/tmp/vervfy-rowtype-postgres-targeted.log`.
- Full relevant suite, bounded to 90 seconds: **159 passed, 7 skipped, 6 warnings,
  25 setup errors, 135 subtests passed in 21.71s**.
  Log: `/tmp/vervfy-rowtype-full-suite.log`.
  Selection: the latest 158-test regression selection above plus the new parser
  regression, all 15 isolated cleanup integration tests, two Supabase ACL tests,
  seven StagingPostgresTests, and the 0028-to-0031 migration boundary test.
- Both private Unix-socket and loopback TCP bind probes on port 55432 returned
  `PermissionError`, errno 1. All 25 PostgreSQL errors occurred during disposable
  server startup; no PostgreSQL test body executed. No SQL/RLS/fencing pass is
  claimed. The seven skips and six warnings are the previously documented ones.
- Ruff and formatting passed for both edited cleanup test modules. Compilation
  passed for those modules and the shared PostgreSQL fixture; whitespace checks
  passed.

The placeholder defect is fixed and verified at the driver-dispatch layer.
Real PostgreSQL verification on port 55432 remains blocked by sandbox socket
permissions. Existing fixes and guards are preserved. No production access,
physical storage deletion, commit, push, merge or deployment occurred.

## Security audit follow-up — 2026-11-17

**The 16 unresolved test failures reported by the user remain release blockers.**
They were not fixed or rerun during this audit. Exact failing node IDs and logs
were not identified in the reviewed report; do not substitute the older 25
PostgreSQL startup errors for this failure set.

See [the current security audit](security-audit-2026-11-17.md) for two high-severity
findings (stale password-reset capabilities and retained storage escaping live-row
quota) and a medium-severity production TLS configuration mismatch. Three isolated
synthetic component probes confirmed the documented behaviors; a redacted scan of
261 tracked source/config/documentation files found no secrets. These checks are
not HTTP/Redis/PostgreSQL integration evidence. No application or test code was
changed by this audit. Existing production deletion guards remain enabled, and
physical deletion remains disabled. Release sign-off remains blocked.

## Restored storage readiness work — 2026-11-21

This entry supersedes the earlier runner/inventory blockers for local code
readiness. It does not approve or describe a production operation. The user
explicitly authorized restoring storage work after the worktree was restored.
Unrelated auth/email/server edits and CSS were left untouched.

### Restored fixes and guarded migration path

- Namespace initialization explicitly accepts the current 0034 head, retaining
  administrator-only bootstrap, immutable namespace matching, savepoint rollback,
  exact-retry behavior, and physical cleanup disabled.
- Read-only ACL inventory recognizes only 0034's exact lifecycle-owner quota
  privileges/functions. It grants nothing and still rejects extra capabilities.
- `scripts/storage_production_migration.py` now pins the complete, linear
  34-migration history through `0034_storage_byte_reservations`. The only
  accepted starting states are `0031_cleanup_retry_limits` (the default) and
  `0033_cleanup_claims_disabled` (explicitly selected through
  `VERVFY_PRODUCTION_START_REVISION`). Revision 0032, arbitrary future heads,
  and already-upgraded databases do not qualify as starting states.
- The command's `--authorize-production-migration` must match the configured
  start-to-target boundary exactly, and the existing 15-minute expiry is still
  required. Existing project, CA/verify-full TLS, restricted-login ownership,
  grantor-aware role graph, namespace, and cleanup privilege checks remain.
- Starting-state checks distinguish the expected presence of auth_sessions and
  cleanup-claim revocation. Postflight checks 0034, default installation quotas,
  forced quota RLS, sized-reservation/retained-byte permissions, denial of
  unsized reservations, and unchanged namespace/cleanup restrictions.
- Upgrade and postflight share one outer transaction. A final verification
  rejection rolls back the schema, version stamp, and grants together. No
  existing migration was rewritten, stamped manually, or skipped.

### Evidence-based reconciliation

`storage_inventory.py` implements plan validation and atomic accounting.
`scripts/storage_inventory_reconcile.py` exposes separate `plan` and `apply`
operations. Neither operation writes or deletes provider objects.

Prerequisites for any future authorized use:

1. Verify the actual database revision and choose the corresponding approved
   migration boundary. Use the existing production target configuration and
   restricted migration credentials/CA; never change host or role guards to
   make a different target pass. This work did not connect to production.
2. Pause **all** storage writers: uploads, processing/artwork workers, retries,
   and out-of-band provider changes. Drain active I/O before measuring. Keep
   writers paused through evidence review and database commit. The required
   `--confirm-uploads-paused` flag records this operator prerequisite; the tool
   cannot establish that external writers are actually paused.
3. After the guarded upgrade to 0034, run the separately authorized inventory
   `plan` operation with `--plan-file`, `--confirm-project-ref`, and
   `--confirm-uploads-paused`. It rechecks real connection TLS/identity, role
   graph, exact head, forced RLS, positive existing quotas, immutable binding,
   and revoked cleanup claims. It does not run any migrations.
4. The plan transaction is explicitly read-only. Snapshot SQL closes before
   provider I/O. For each NULL-size ledger row, the observer uses authenticated
   GETs for two complete matching reads, measuring bytes and SHA-256 and
   requiring a stable strong ETag. It never trusts provider size metadata as
   byte evidence. Redirects, unsafe paths, unsupported encodings, incomplete or
   changing reads, missing/empty objects, and active upload/deletion states
   block the whole plan. Both reads share an absolute 60-second network deadline
   with an additional bounded five-second client close and a 10-GiB per-object
   read ceiling. There are no provider POST/PUT/PATCH/DELETE requests.
5. Review the private (0600), exclusively created plan and independently record
   its SHA-256. The plan contains object paths and tenant identifiers: keep it
   private. Do not edit sizes or fabricate evidence. The SHA-256 is an approval
   binding, not a provider signature or a substitute for reviewing provenance.
6. A separately authorized `apply` requires `--approved-sha256` and
   `--authorization-expires-at`, in addition to the same target/paused-writer
   flags. Expiry must be active and within 15 minutes; measurement must also be
   no older than 15 minutes from the start of collection. Apply requires no
   provider credentials and performs no provider I/O.
7. Apply rechecks guards on its actual transaction, validates every observation,
   locks the quota-policy row in admission order and the object table, and
   compares the complete ledger snapshot. It updates only `reserved_bytes IS
   NULL`. All fields, known charges, object identities, ownership, states,
   references, jobs, quotas, RLS policies, and grants remain unchanged. Missing
   evidence, wrong binding, stale approval, ledger drift, or any SQL failure
   rolls back all changes. Exact replay without ledger drift returns zero.

The existing reservation function still blocks on any remaining NULL charge.
After successful complete reconciliation, global and tenant admission checks
continue to apply; if measured retained usage exceeds capacity, new admission
stays blocked. Deletion, marking an object deleted, or reconciliation never
refunds a known retained charge. Shared/legacy NULL ownership is preserved, not
inferred or reassigned; these bytes are charged globally, while existing tenant
accounting semantics are unchanged.

### Verification and remaining limits

Tests use fresh disposable PostgreSQL, isolated SQLite, generated local TLS
certificates, and mocked/synthetic provider responses only. Both migration
boundaries exercise real TLS, role, revision, namespace and postflight guards;
only synthetic final rejection is injected to prove rollback. Synthetic role
grantor topology is provisioned in the new fixture, not relaxed in the runner.
Tests also cover concurrent/idempotent reconciliation, mid-update database
failure rollback, caller rollback, runtime denial, snapshot drift, no known-charge
reduction, read-only collection, absolute header/body deadlines, unsafe paths,
and account/track deletion preserving retained charges and cleanup obligations.

**No production readiness sign-off or physical deletion approval:**

- No live revision, bucket, object, role, quota, or credentials were inspected.
  The future rollout and actual measured reconciliation still require separate
  authorization and verification.
- Missing, empty, unstable, oversized, actively written or otherwise unmeasurable
  unknown objects remain blocked for manual investigation. Evidence collection
  that cannot finish within the freshness window must not bypass or extend it
  without a separately reviewed design.
- This tool reconciles registered ledger rows. It does not enumerate or adopt
  provider-only orphan objects. Full bucket-to-ledger inventory and legacy/shared
  ownership review remain separate readiness work; global ledger caps are not
  proof of the provider's complete billable inventory.
- Stable strong-ETag/read behavior must be rehearsed against a disposable provider
  project before a production run. Synthetic HTTP tests do not prove provider
  behavior. External writer quiescence is an operational prerequisite.
- Capacity, backups/recovery and any outstanding unrelated security findings
  still need release review. All physical deletion entrypoints and claim gates
  remain disabled; no new deleter or cleanup grant was added.

Final restored-worktree verification: **225 tests passed, 53 subtests passed,
0 failures/skips** in the 23-file storage-readiness suite. The 37 warnings are
existing Alembic configuration deprecations and deliberately oversized image
fixtures. Ruff passed for every changed Python file and `git diff --check`
passed. Additional read-only TLS connection verification is included in the
runner fixture. No production access, physical deletion, commits, pushes, PRs,
or deployment occurred.

## Explicit disposable Supabase 0034 workflow — 2026-11-21

The new entrypoint is `scripts/storage_rehearsal.py`. It is separate from both
production CLIs. Production target loading, namespaces, reconciliation helpers,
migration files, and Alembic environment guards were not changed for this work.
No hosted project was contacted. Existing unrelated edits remain untouched.

### Configuration and provisioning boundary

The workflow intentionally starts with a **separately provisioned disposable
project** at reviewed revision 0031 or 0033. It does not create hosted projects,
roles, grants, namespaces or synthetic provider objects, and does not bootstrap
an arbitrary database. Missing prerequisites block execution. Do not point the
production provisioner at another project or bypass staging/Alembic guards to
prepare a rehearsal; use a separately reviewed project-specific provisioning
procedure. That hosted preparation remains required before running this workflow.

Required preparation, on the disposable project only:

- Restricted `vervfy_rehearsal_migrator` login with application/Alembic table
  ownership and the reviewed lifecycle-owner SET membership. Runtime and cleanup
  roles must match the existing grantor-aware role graph. No SUPERUSER,
  BYPASSRLS, CREATEROLE or CREATEDB capability is accepted for the migration login.
- A fresh, immutable namespace with environment `disposable-rehearsal`, a new
  nonzero UUID, the disposable project's exact HTTPS storage endpoint, a bucket
  named `vervfy-rehearsal-...`, and `physical_cleanup_enabled=false`. Bootstrap
  must use its existing separately privileged authorization; the workflow
  cannot grant that privilege or modify an existing binding.
- Only synthetic application tenants `a` and `b`. Populate both with tracks,
  covers, artist photos, playlists/favorites/listens as appropriate, staged
  upload jobs with original artwork bytes, managed objects, shared legacy
  references, and pending cleanup obligations. The snapshot step rejects an
  empty ledger or missing two-tenant/legacy/outbox coverage. Load only generated
  fixture bytes into a private bucket through a separately authorized setup
  procedure. Verify that the bucket contains only the intended fixture inventory.
- A project approval table owned by `vervfy_rehearsal_migrator` at
  `vervfy_rehearsal.approval`, containing exactly one row with columns
  `project_ref text`, `run_id uuid`, `config_sha256 text`, `disposable boolean`.
  Pin its values to the reviewed configuration and true disposable assertion.
  Restrict schema/table access to that migration login. This is an extra
  project-side approval marker, not proof supplied by Supabase that a project is
  disposable; the administrator remains responsible for project selection.

Create an owner-only 0600 regular JSON configuration file, using this shape
(replace every placeholder and review the canonical digest independently):

```json
{
  "purpose": "vervfy-0034-disposable-rehearsal-v1",
  "project_ref": "<new 20-character project ref>",
  "namespace_id": "<fresh namespace UUID>",
  "bucket": "vervfy-rehearsal-<unique fixture suffix>",
  "start_revision": "0031_cleanup_retry_limits",
  "run_id": "<fresh run UUID>",
  "ca_sha256": "<SHA-256 of approved CA bundle>",
  "history_sha256": "<reviewed migration/environment history digest>"
}
```

The other approved start is `0033_cleanup_claims_disabled`. The workflow refuses
production's project reference/namespace, the existing staging project, wrong
bucket prefixes, different migration history, insecure/symlink configuration,
and mixed target URLs. Direct Supabase PostgreSQL only is supported here;
Session Pooler rehearsal remains outside this entrypoint's claims.

Use a clean process environment containing only the required system paths and
these reviewed settings, populated from the disposable project's secret store:

- `VERVFY_ENVIRONMENT=disposable-storage-rehearsal`
- `VERVFY_REHEARSAL_CA_FILE`: absolute path to the pinned readable CA bundle.
- `VERVFY_REHEARSAL_DATABASE_URL`: `postgresql+psycopg` direct project host on
  port 5432, database `postgres`, login `vervfy_rehearsal_migrator`.
- `VERVFY_REHEARSAL_RUNTIME_URL`: the same host/database/CA, login `app_runtime`.
- Both URLs require exactly `sslmode=verify-full` and `sslrootcert=<absolute CA
  path>` query parameters. No hostaddr, options or alternate connection routes.
- `VERVFY_REHEARSAL_STORAGE_KEY`: disposable-project credential for plan reads
  only. Never reuse a production provider key.

Inherited `PG*`, DATABASE_URL/MIGRATION_DATABASE_URL, generic Supabase credentials,
production variables, staging profile, or ambiguous ENVIRONMENT selectors are
rejected before engine construction. HTTP environment proxies and redirects are
not used. Configuration validation itself never opens a connection.

Offline helpers (no database/provider access): import `history_digest()` from
`scripts.storage_rehearsal` to obtain the reviewed source digest; use
`plan_digest(read_private(config_path))` for the canonical configuration digest.
A digest binds an independently reviewed artifact; it is not a digital signature
or a substitute for reviewing the target and evidence provenance.

### Authorized operation sequence

Every operation requires `--config`, `--config-sha256`,
`--confirm-disposable-project`, `--confirm-writers-paused`, and
`--authorization-expires-at` (fresh UTC RFC3339 expiry within 15 minutes).
Pause and drain all application, background and external provider writers for
the whole rehearsal. The confirmation flag does not stop external writers.
Run with the dedicated environment above; do not run these against production.

1. **snapshot**: add `--receipt-file <new-private-file>`. The operation is
   transactionally read-only and writes an exclusive local 0600 baseline receipt.
   Record/review the printed baseline SHA-256. It hashes every field of every
   pre-existing public table under each tenant's RLS context, plus all namespace,
   object and cleanup-job fields. Receipts contain digests/counts, not row values.
2. **upgrade**: add the original `--receipt-file`, `--receipt-sha256`, and exact
   `--authorize-upgrade 0031_cleanup_retry_limits..0034_storage_byte_reservations`
   (use the 0033 start string if configured). A bounded transaction advisory lock
   precedes start-state checks. TLS, restricted identity/ownership, role graph,
   marker, forced RLS, namespace, claims and matching populated baseline are
   checked. Migration, postflight and preservation verification share one
   transaction. Authorization is rechecked before DDL and before commit.
3. **recover**: after any uncertain result, reconnect with original receipt and
   digest. Recovery is read-only. It returns `at_baseline` or `committed_0034`
   only after matching data and guards. Other revisions, changed rows or failed
   guards block investigation. It never automatically retries, stamps,
   downgrades, refunds or deletes. Retain the pinned checkout, configuration,
   CA and receipt to make recovery reproducible.
4. **verify**: at 0034, runtime probes use a separate verified-TLS `app_runtime`
   connection. They check populated two-tenant reads, cross-tenant UPDATE/INSERT
   denial, storage RLS, accounting-write denial, and blocked unknown-size or
   oversized reservations. Probe transactions always roll back.
5. **plan**: add `--plan-file <new-private-file>`. SQL is read-only and closes
   before provider I/O. The disposable bucket must report the exact ID and
   `public=false`. Only bounded GETs are sent. The existing observer performs
   two complete matching versioned reads for every unknown-size ledger object.
   Review the exclusive private plan and independently approve its printed SHA.
6. **apply**: add original `--plan-file` and `--plan-sha256`. Recheck head and all
   guards, then use existing atomic NULL-only reconciliation. Freshness, snapshot
   drift, quota locking, known-charge preservation and replay protection remain.
   Missing/empty/changing objects remain blocked. No provider credential or
   provider I/O is needed for apply.
7. Repeat **verify** and read-only **recover**. Confirm retained bytes include all
   intended ledger objects, tenant isolation holds, original artwork and other
   row fields are preserved, and physical cleanup remains false. Logical
   deletion and shared/global quota behavior must not release retained charges.

There is no cleanup or reset operation. Project disposal, if later desired,
requires its own explicit authorization outside this workflow. Neither worker
claims nor provider deletion are enabled at any stage.

### Local proof and hosted blockers

`tests/test_storage_rehearsal.py` runs the full CLI against fresh local PostgreSQL
with generated verify-full TLS and mocked provider reads. Only the network
engine destination is substituted; all configuration and SQL/TLS guards execute.
Both start revisions use a populated two-tenant fixture with nine pre-existing
managed/legacy objects, staged cover bytes, live references and cleanup jobs.
Tests prove full-field preservation, unknown-size admission blocking, measured
reconciliation and replay, forbidden runtime mutations, shared global quota,
marker/RLS drift denial, bounded advisory locking, and false cleanup state.

The test injects a rejecting postflight to prove DDL/version/data rollback. It
also commits successfully and then raises a simulated lost acknowledgement;
reconnecting recovery must identify the committed head without another upgrade.
Changed-row recovery is rejected. Configuration tests refuse unsafe targets,
credentials/routes, CA/history/digest mismatches, public/wrong buckets and
inherited overrides before network execution.

Remaining hosted requirements: separately reviewed disposable project baseline,
roles/marker/namespace and fixture provisioning; dedicated credentials and CA;
actual Supabase grantor/extension behavior, private bucket and ETag/streaming
behavior; complete bucket-to-ledger orphan/shared-ownership inventory; maintenance
window and capacity review. Local commit-state recovery is not a backup/PITR
restore drill: restoration into a fresh disposable project and production
operational recovery planning remain separate requirements. No hosted rehearsal,
production access, physical deletion, commit or push occurred during this work.

Focused verification for this addition: **80 tests passed and 10 subtests passed**
across the new workflow/target guards and existing quota, reconciliation,
production-runner and disabled-cleanup tests, in about 17 seconds. Ruff and
`git diff --check` passed. After adding the explicit PostgreSQL >=16 gate, both
populated paths were rechecked. Warnings are existing Alembic `path_separator`
deprecations. Hash comparisons confirmed the production runner, production
reconciliation CLI, shared reconciliation code, Alembic environment, unrelated
user auth/email/server edits, and CSS are byte-for-byte unchanged from the start
of this task. All changes remain local and uncommitted.

## Local review and storage commit checkpoint — 2026-11-21

Reviewed the uncommitted storage changes as a unit before the requested local
commit. Shared Storage headers now send modern `sb_secret_*` credentials only as
`apikey`, retaining both headers for legacy credentials across synchronous,
lifecycle, inventory, and disposable-rehearsal clients. Mocked request tests
verify key rotation, redirects/rejections, namespace mismatch, and redaction.
No RLS, namespace, quota, deletion, or production target guard was weakened.

Checkpoint verification: **226 tests passed, 25 subtests passed** in the scoped
21-file storage/deletion/isolation suite, in about 35 seconds. Ruff and diff
checks passed. Warnings were existing Alembic configuration deprecations and an
intentional oversized-image fixture. Local PostgreSQL used fresh disposable
clusters with generated test TLS; provider traffic was mocked. No hosted or
production connection occurred.

The requested commit contains storage implementation, storage-focused tests and
this report only. Existing auth/email/password-reset/server edits and CSS are
excluded. Hosted baseline provisioning and backup/restore readiness remain
separate follow-up work; physical deletion stays disabled. No push or deployment
is authorized or performed.

## Disposable 0031/0033 baseline preparation bundle — 2026-11-21

The reviewed storage changes were committed locally as `9f81dd7`; nothing was
pushed. Unrelated auth/email/password-reset/server edits and CSS were excluded.
Baseline preparation is a subsequent, uncommitted review artifact.

`scripts/prepare_storage_rehearsal_baseline.py` creates a private **offline**
provisioning review bundle. It has no database/client construction or execution
mode and never creates hosted resources, roles or provider objects. It reuses the
existing disposable target, configuration digest, CA pin and 34-migration history
checks with internal validation-only dummy URLs. It does not read inherited
production credentials. No dummy URL/password is written into the bundle.

After obtaining an independently verified new disposable project reference,
approved CA file and private 0600 rehearsal configuration, prepare with:

```bash
.venv/bin/python scripts/prepare_storage_rehearsal_baseline.py \
  --config /private/rehearsal.json \
  --config-sha256 "$APPROVED_CONFIG_SHA256" \
  --ca-file /private/approved-ca.pem \
  --confirm-disposable-project "$DISPOSABLE_PROJECT_REF" \
  --output-dir /private/new-baseline-review
```

All command variables above are public target/digest metadata, not credentials.
No database password or provider key is needed for preparation. The output path
must not exist; reruns cannot overwrite an approved artifact. Review and record
the printed manifest SHA-256 independently.

The 0700 bundle directory contains exclusively created 0600 files:

- `manifest.json`: target/config binding, file sizes and SHA-256 digests,
  baseline, run identity, explicit remaining blockers, and
  `ready_for_hosted_execution=false`.
- `config.json`: reviewed public configuration only; no connection URLs or keys.
- `01-preflight.sql`: a transactionally read-only DBA check for the fresh
  disposable application schema, PostgreSQL >=16, TLS, exact restricted role
  attributes, fresh-public ownership and pre-existing bootstrap capability. It
  requires exactly one independently DBA-owned approval row at
  `vervfy_rehearsal.provisioning_approval(project_ref text, run_id uuid,
  config_sha256 text, disposable boolean)`, bound to this exact profile.
  Missing or mismatched identity, existing application/storage/auth schema,
  wrong principal or missing capability blocks. It grants and repairs nothing.
- `02-role-requirements.json`: exact restricted login/capability attributes and
  required migration/worker/login membership options, plus only the optional
  postgres ADMIN-only owner/executor memberships accepted by the migrations.
  Passwords are left to the dedicated secret-management process.
  Provider-managed grants must satisfy the existing reviewed exceptions; no
  catalog edits, blind revokes or privilege workarounds are proposed.
- `03-baseline-phases.json`: reviewed execution order and immutable namespace.
- `04-fixtures.json` and `fixtures/`: nine tiny valid WAV/JPEG synthetic assets,
  ownership/reference intent, sizes and SHA-256 checksums. Managed paths are
  allocator-issued UUID patterns, not preselected object IDs. There is no
  `upload_verified=true` assignment or fabricated provider evidence.

The SQL file alone cannot authenticate a Supabase project by network identity.
Any future execution still requires a separately reviewed direct-host,
verify-full, configuration-bound disposable connection before SQL is submitted.
The private approval marker must be created only after that independent target
check. Do not run this SQL through a production console or treat the marker as
an alternative to TLS/project validation.

Provisioning phases are deliberately explicit:

1. Independently approve the new project, prepare restricted roles/memberships,
   fresh public-schema ownership, DBA approval marker and migration capabilities.
   Check the read-only preflight through a reviewed disposable connection.
2. A target-bound baseline executor applies unchanged migrations through 0028.
   Seed synthetic tenants and shared legacy references under their tenant
   contexts before lifecycle reference triggers are installed.
3. Apply unchanged 0029-0031 with every role/ACL guard intact. Stop rather than
   modifying provider-managed grantors if the graph does not satisfy the guards.
4. At **exactly 0031**, a separately authorized privileged DBA invokes existing
   `initialize_namespace` with the new disposable binding and cleanup false.
   The existing helper intentionally does not accept 0033 initialization.
5. At exactly 0031, `scripts/upload_storage_rehearsal_fixtures.py` can reserve and
   upload the eight managed assets using the restricted `app_runtime` role,
   create-only requests and full matching readbacks. It validates the migrator
   guard, runtime identity, immutable namespace, private bucket and exact fixture
   hashes. It refuses pre-existing managed rows, never retries, attaches
   references, or deletes objects, and marks uncertain reservations held. The
   shared legacy identity and tenant-scoped attachment rows still require a
   separately reviewed seeder. Do not set verification flags directly or enable
   cleanup to make the setup pass.
6. For the 0033 variant only, apply unchanged 0032/0033 after namespace bootstrap.
   Create the separate runtime `vervfy_rehearsal.approval` marker owned by the
   restricted migrator, then use the existing snapshot/upgrade/recover/verify/
   plan/apply rehearsal workflow.

For upload execution, provide only the explicit rehearsal variables
`VERVFY_REHEARSAL_DATABASE_URL`, `VERVFY_REHEARSAL_RUNTIME_URL`, and
`VERVFY_REHEARSAL_STORAGE_KEY` through an approved secret manager, plus
`VERVFY_ENVIRONMENT=disposable-storage-rehearsal`; do not set generic database or
Supabase variables. The command also requires the independently recorded bundle
digest:

```bash
.venv/bin/python scripts/upload_storage_rehearsal_fixtures.py \
  --config /private/rehearsal.json \
  --config-sha256 "$APPROVED_CONFIG_SHA256" \
  --ca-file /private/approved-ca.pem \
  --confirm-disposable-project "$DISPOSABLE_PROJECT_REF" \
  --bundle-dir /private/new-baseline-review \
  --bundle-sha256 "$APPROVED_BUNDLE_SHA256"
```

**Remaining hosted rehearsal blockers:** there is no hosted DBA/role bootstrap
executor, guarded empty-schema baseline executor, legacy registration/attachment
seeder, or confirmed Free project/credentials/CA connectivity/provider response.
The uploader is covered by local mock-provider tests only and must be reviewed
and exercised on a separately approved disposable Free project before it is
considered hosted-verified. Cross-project restore/immutable-namespace policy
and backup restoration also remain separate readiness requirements. Do not use
bare Alembic, change a production target constant, stamp revisions or grant
BYPASSRLS to bypass any gap.

The preparation tests validate both baselines, deterministic private artifacts,
no engine construction or ambient-secret copying, refusal of unsafe targets and
configuration drift, valid fixture hashes and sizes, and no output overwrites.
Generated SQL is exercised only in fresh local PostgreSQL with test TLS. It
accepts an attested empty candidate and rejects wrong identity, existing data,
non-DBA marker ownership and missing bootstrap capability without modifying
existing data or restoring privileges. No hosted provisioning, push, deployment,
provider deletion or production access occurred.

Baseline preparation and uploader verification: the preparation/preflight tests
and local mock-provider tests passed; generated SQL ran only on fresh local
PostgreSQL with test TLS. Hosted project, credentials, provider operations and
physical deletion were not accessed. Existing Alembic configuration warnings
remain. Only verified preparation files are eligible for the local commit;
unrelated auth/email/server changes remain untouched.
