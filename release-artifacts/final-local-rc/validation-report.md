# Final local release validation

Local result: PASS for all four confirmed blockers. Hosted release remains gated
on the verification and approvals below. No hosted systems were accessed; no
hosted migration, physical deletion, commit, push, merge or deployment occurred.

| Blocker | Result | Evidence |
|---|---|---|
| Explicit ASGI lifespan | PASS | Both deployment commands include `--lifespan on`; the formerly failing staging regression passes. |
| Safe namespace initialization | PASS | Explicit bootstrap-only transaction at 0027; identical retries and concurrent initializers succeed, mismatched bindings fail, rollback and revision fences pass, cleanup remains false. No storage access. |
| PostgreSQL Google integration | PASS | Real runtime-role account creation, uniqueness/atomic rollback, real lookup-role callback login, account linking, session-version rotation, duplicate ownership fencing and password preservation, on disposable private PostgreSQL. Provider exchange mocked. |
| Pinned migration instructions | PASS | Release commands and startup guidance target `0027_storage_lifecycle`; documentation scan finds no unbounded Alembic upgrade command. Release PostgreSQL fixtures stop at 0027 and verify 0028 routines absent. |

Focused regression: **174 tests PASS** on Python **3.12.7**, using hash-locked
dependencies and PostgreSQL **18.6** with private Unix sockets and synthetic data.
The same 174 tests also passed on Python 3.14. Final selected frontend TypeScript
check and lint for the two new/changed Python modules passed. Expected mocked
failure traces and image-limit/Alembic warnings appear in passing logs.

The clean source export starts at confirmed production baseline
`dd22f18b92e26a59d342a98e06dfc2888c58905b`. `release-manifest.json` lists every
source file's SHA-256, size and mode, exact added/modified paths, artifact hashes
and exclusions. The archive membership and every archived file hash were
verified. The selected frontend changes retain account isolation, account
settings navigation and OAuth dependencies; unrelated skeleton, recap, metadata,
style and developer-indicator changes were excluded. Baseline `psycopg` is
preserved; its unrelated deletion is excluded. No Git repository was mutated.
0028 is included as source provenance for the guard's 28-file inventory, remains
unapplied in this validation, and is not an authorized release migration target.

## Remaining hosted verification and approvals

- Authorize read-only inspection of the exact target identity, PostgreSQL version
  (16+ required), current migration state, roles/memberships, owners, grants,
  default ACLs and forced RLS/reference guards. Reconcile with the pinned 0027
  artifact; renew approval records and execution hashes. Existing approvals do
  not authorize these changed files or metadata scripts.
- Verify database and object-byte backup/restore and approve the forward-repair
  or restore plan. Separately approve the exact migration window through 0027,
  keeping 0028 unapplied; run approved metadata postflight before startup.
- Verify isolated storage endpoint/private bucket ownership and the immutable
  namespace tuple. Approve its binding record/hash and bootstrap administrator
  execution. Configure matching application settings; separately approve hosted
  storage smoke tests. No hosted namespace initialization occurred locally.
- Verify hosted lifespan/readiness, proxy/cookies, Redis/session availability,
  OAuth client/redirect configuration and real Google/JWKS/signup/login/linking
  flows. OAuth remains disabled by default; enablement requires approval.
- Approve the exact candidate hashes, account-deletion behavior with pending
  physical cleanup, support/erasure workflow and deployment/recovery window.
  Physical deletion and cleanup workers remain disabled; enabling deletion is
  outside this release and requires separate provider/recovery verification.
