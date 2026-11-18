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
