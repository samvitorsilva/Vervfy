# Combined release — 2026-11-09

This source combines the main checkout's website, security, and CI changes;
the Phase 4 storage lifecycle, bounded cleanup retries, and operator foundation;
and the release copy's newer Google account-action continuation flow.
The original local worktrees remain separate and unchanged by this merge.

Google-only account deletion preserves explicit DELETE confirmation across
Google verification and resumes only an unexpired continuation for the same
account and action. The backend still requires a fresh, single-use proof.
Password entry is never stored across a Google redirect. Email editing is
removed; the email address is read-only. Password-bearing accounts retain
current-password authentication for sensitive actions.

## Migration and deployment boundary

The repository includes 31 linear migrations, with source head
`0031_operator_revocation`. The guarded rollout target remains
`0027_storage_lifecycle`. Revisions 0028–0031 are included for review and
future rollout; publishing this source does not authorize or apply them.
Do not substitute `alembic upgrade head` for the pinned rollout operation.

OAuth remains disabled by default. Production still needs its configured
Google client/callback, restricted application and identity-lookup database
connections, Redis, backup/restore verification, and migration pre/postflight.
Storage cleanup is not enabled by this release publication. Local-disposable
staging validation remains available and rejects migration execution.

The earlier reports are historical evidence for their original source copies.
Their file counts, manifests, and approval hashes do not approve this combined
source. Generate a fresh execution manifest for any deployment. The user
reported successful local staging Google login, signup, and logout through
Cloudflare; live account deletion and hosted production behavior remain
unverified.

The frontend requires `BACKEND_URL` and a production `SITE_URL` (or Render's
`RENDER_EXTERNAL_URL`) at build/runtime. CI now supplies an explicit local site
origin for its production build. Temporary tunnel hostnames, private settings,
test output, dependency directories, and nested checkout copies are excluded.

## Merge verification

Python sources compile and contain no duplicate top-level/class definitions.
The migration graph has one head. TypeScript and the production frontend build
pass. Frontend lint reports zero errors and 17 existing warnings.

The first Python 3.14 run passed 394 tests and 381 subtests. Two test issues
were corrected: the filesystem test now uses an explicitly non-temporary file
instead of assuming the repository is outside /tmp, and the runtime-provider
scan excludes historical reports just as it excludes documentation. All 14
tests in the affected modules passed on rerun.

Final deployment-version verification: Python 3.12 unittest discovery passed
all 396 tests, including disposable PostgreSQL/Redis integration coverage.
The Google/account browser suite passed 16 checks on its first production-server
run; the remaining unlink check depended on a separate login mock. After making
that fixture self-contained, its targeted rerun passed. All 17 checks therefore
passed across these runs. Account deletion continuation and its confirmation,
expiry, and wrong-account rejection cases are included. Real-provider browser
authentication was not performed during this publication.

The separate real-API account-isolation Playwright spec was not exercised in
this browser run because its synthetic backend was not started. Backend tenant
isolation tests did run in the full suite. The full frontend smoke/readiness
suite remains for GitHub CI; no hosted deployment is claimed by these checks.
