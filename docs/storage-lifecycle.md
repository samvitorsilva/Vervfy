# Storage lifecycle — complete Phase 3 local implementation for review

Phase 4 and physical cleanup remain disabled. This is the isolated, uncommitted
security/confirmed-defects worktree, not the published GitHub repository or a
production-ready release. No hosted database, bucket or namespace was accessed.
All release manifests and operational approvals need fresh review of this source.

## Database boundary retained from reviewed 0027

Migration 0027 remains unchanged and depends on 0026. The private vervfy_storage
schema/tables belong to the migration principal and use ENABLE/FORCE RLS. Ten
fixed functions are owned by vervfy_storage_lifecycle_owner, a restricted NOLOGIN,
NOINHERIT role without SUPERUSER, BYPASSRLS, CREATEDB, CREATEROLE or REPLICATION.
It has narrow column SELECT for global reference verification, not passwords or
business-table UPDATE. Only the migration principal may SET it; schema CREATE
is revoked after ownership transfer. All function search paths are pinned to
pg_catalog,pg_temp and PUBLIC/deployment-default EXECUTE grants are stripped.

vervfy_storage_cleanup is inherited only by the restricted storage_cleanup_worker
login; SET/ADMIN are denied. Runtime cannot execute internal global-reference or
queue functions, inspect other tenants' objects, or mutate registry/outbox state
directly. Google OAuth roles receive no storage capabilities. Preflight rejects
unsafe effective membership, cross-schema ownership/grants/routines and defaults.
No new roles, grants, RLS policies or migration functions were added in Phase 3.

All authoritative owned-object references are public.tracks.storage_path,
public.tracks.cover_path, public.artist_photos.storage_path and
public.upload_jobs.storage_path. Their triggers take registry locks and reject
unregistered, cross-tenant, unverified, retired and incompatible new references.
Global retirement checks all four exact case-sensitive paths through narrow
SELECT-only policies. Existing ordinary tenant policies remain forced.

| Destination | New managed kind |
|---|---|
| tracks.storage_path | audio |
| tracks.cover_path | track-cover or album-cover |
| artist_photos.storage_path | artist-photo |
| upload_jobs.storage_path | staged-audio |

Namespace identity/endpoint/bucket/environment are immutable. A separate explicit
binding is required; production settings never initialize it. The explicit operator procedure is documented in
[storage-namespace-initialization.md](storage-namespace-initialization.md); tests
use disposable Unix-socket PostgreSQL and synthetic bindings only. VERVFY_STORAGE_NAMESPACE_ID and VERVFY_ENVIRONMENT must match the reviewed binding. Missing
or differing configuration fails before managed I/O. Unchanged legacy metadata
updates still need no registry insertion or namespace initialization.

## Immutable writer protocol

storage_lifecycle.py is the only active physical-object writer. Each operation:

1. Reserves a random v2/namespace/tenant/kind/UUID.ext identity and independent
   reservation token through the restricted SQL capability.
2. Creates a held cleanup obligation and commits it before network I/O.
3. Advances the reservation to uploading, validates the immutable namespace, and
   closes that validation transaction before I/O. The captured client endpoint,
   credentials and bucket cannot drift to a different process setting mid-operation.
4. Sends create-only POST (x-upsert=false), never an overwrite of a managed or
   legacy identity. It verifies complete byte count and SHA-256 with authenticated
   GET before acknowledging ready in a new short SQL transaction.
5. Attaches references transactionally through the installed guards and appropriate
   media-version/job-token checks. Success at HTTP alone is never attachment proof.

Any unknown/error/interruption leaves a held obligation and reserved/uploading/hold
state. No caller deletes a candidate after rollback, timeout, duplicate detection
or lost commit acknowledgement. A pre-commit retry may allocate another identity;
unused candidates remain durable, not guessed safe to delete.

## Complete writer and deletion inventory

| Runtime path | Conversion and reference handling |
|---|---|
| Library.add_upload_file / add_upload | Unique audio and embedded track-cover allocations; owner/quota/duplicate/job checks in final transaction; unused candidates held |
| server._queue_staged_upload | Unique staged-audio; guarded job reference commits before Redis enqueue; enqueue ambiguity retains the source |
| scripts/upload_worker.process | Source job-row pin during bounded read; copy to separate verified audio object; token-fenced audio/job completion atomically releases the staged reference |
| upload_worker._complete_artwork | Durable original/fence snapshot, I/O without business locks, final fenced attachment and source retirement in one transaction |
| Library.set_user_cover | Prepare outside SQL; media-version CAS in a short transaction |
| Library.set_album_user_cover | Snapshot eligible row versions; unique shared album cover; final ordered row locks and per-row version checks preserve intervening user edits |
| Library.remove_user_cover | Extract/prepare restored image outside SQL; original snapshot version fences final attachment |
| Library.set_resolved_cover / cover_art.resolve_cover | Snapshot-fenced background work; upload outside SQL; final CAS; owned Storage URLs cannot be hidden in external cover_url |
| server.upload_artist_photo / _save_artist_photo | Unique photo uploaded before SQL; bounded owner/photo update; late non-user source cannot replace user photo |
| Library.ensure_audio_storage | Copy legacy DB bytes to verified unique audio; version/null-path CAS; original DB audio bytes retained |
| Track/photo/account deletion and swaps | Database reference deletion/replacement only; trigger outbox obligations survive account cascades |

Audio is never relabeled from staged-audio to audio. The staged object remains
referenced during its source read. Permanent bytes are separately uploaded and
verified. A stale/duplicate worker cannot commit a result or replace a winner.
Legacy paths remain unchanged unless an explicit normal user edit detaches them.
Legacy/unknown objects remain held and are never destructively bulk-migrated.

The four explicit path columns are the owned-object inventory. Image caches store
external provider URLs rather than managed identities. New resolved covers reject
the configured Storage host in URL-only fields. Arbitrary operator scripts,
service-key holders and DB owners remain outside this application protocol;
unknown historical URL aliases/objects are preserved, not presumed deletable.

## Lock contention and timeout bounds

Queued artwork uses two short transactions around I/O. The first copies original
bytes and the durable expected track version; the final transaction rechecks owner,
job, original bytes, target ID and media version. It flushes/re-reads the guarded
reference before clearing the source in that same commit. No account/job/track row
or database connection is held during that upload/verification.

Regular track, album, restored and resolved covers also prepare outside SQL and
attach via short CAS transactions. Concurrent attempts may create extra held
candidates; visible attachment remains idempotent. Tests verify NOWAIT access to
all involved business rows during paused I/O, a newer user edit committing first,
unchanged final references on stale completion, and held unused candidates. The
previous duplicate test required one HTTP upload by holding rows during I/O; it
now asserts one visible attachment plus explicit retention of concurrent candidates.
This intentionally trades duplicate network work for removal of row-lock contention.

| Operation | Bound |
|---|---|
| Managed upload + full verification | Absolute cooperative network deadline 60 seconds |
| Staged download / bucket privacy query | Absolute network deadline 60 seconds |
| Async client close | Separate 5-second cleanup deadline |
| HTTP connect / pool | 5 seconds each, within overall network deadline |
| HTTP read / write inactivity | 10 seconds each, within overall network deadline |
| SQL lock wait | Transaction-local 1 second |
| SQL statement | Transaction-local 5 seconds |
| SQL idle transaction | Transaction-local 70 seconds |
| Redis queue connect / read | 5 seconds each; unsafe URL overrides rejected |
| Redis implicit command retry | Disabled; durable lease/application state decides retry |

A necessary exception to removing row locks across network I/O is the staged
source read: its job-row pin preserves the source reference until bytes are local.
It is bounded by the network deadline and SQL idle ceiling. A killed/expired pin
cannot commit a successful stale source read; retry must reload the durable job.
The transaction-local settings reset on rollback/commit and add no privilege.

The network deadline uses cancellable async HTTPX I/O behind the synchronous
worker API. It also covers response headers and trickle bodies, unlike a pure
inactivity timeout. It does not preempt local synchronous file operations, hashing,
image decoding, a hung OS or a stalled database connection establishment. Redis
socket limits likewise do not constitute an absolute system-DNS deadline.

Legacy compatibility delivery helpers in audio_store (signed URLs and range reads)
retain their pre-existing inactivity timeouts; this document does not claim the
writer's absolute deadline for those read-only delivery paths. They hold no SQL
business-row locks. Slow/trickle delivery and global signing-cache contention are
remaining availability review items, not authorizations to enable cleanup.

## Queued artwork recovery retained

A completed audio job with cover_data retains its original. processing_token means
an audio-attempt token while processing; for completed pending artwork it is the
expected track media_version. Unknown legacy fences and duplicate-track ambiguity
stay held. A completed retry resumes artwork; failed/stale work cannot overwrite
a newer cover. Clearing original bytes, clearing the fence and guarded attachment
commit atomically. After that commit, a replay performs no new artwork I/O.

The worker acknowledges Redis only for completed/intentional-held outcomes.
Transient failures and stale attempts leave the lease for expiry/redelivery. The
real disposable Redis regression advances its logical lease time explicitly.
Redis datastore loss/global reconciliation remains outside this implementation;
original blobs/fences remain durable in PostgreSQL for explicit recovery.

## Direct deletion and maintenance are disabled

Ordinary audio_store.upload/upload_file/delete/delete_quietly/delete_many reject
use. Active application/worker paths have no calls to those retired writers or
physical deletion helpers. New tests audit the active source inventory.

migrate.py raises before any imports/work. The main entry points of
scripts/migrate_audio_to_storage.py, scripts/move_audio_to_storage.py,
scripts/backfill_cover_storage.py, scripts/backfill_covers.py,
scripts/rebuild_covers.py and scripts/migrate_local_data.py raise before work.
Their old bodies remain for review/history, not operational use. CLI tests verify
refusal without credentials or hosted access. No old-process/mixed-writer rollout
is authorized.

## Phase 4 local cleanup protocol

The local-only forward migration 0028 adds ordered, `SKIP LOCKED` cleanup
claiming, 60-second leases, random claim tokens, stale-token fencing, bounded
exponential retry, and explicit completion. It preserves the `claim_cleanup`
stub, the namespace CHECK that forbids `physical_cleanup_enabled`, and all
existing capability roles and RLS policies. `claim_next_cleanup`,
`complete_cleanup`, and `retry_cleanup` are executable only through the
restricted cleanup capability.

Claiming locks the object before the outbox row, matching reference-trigger lock
order. In the same transaction it verifies a managed, byte-verified object and
performs the global, byte-exact check over tracks, track artwork, artist photos,
and upload jobs. It then fences the object in `deleting` before returning the
path. Reference triggers reject later attachments to that state. Shared objects
remain pending with a delay until all references are gone. Unattached,
ambiguous, legacy, and unverified reservations remain held. A successful
attachment that is later detached promotes its held obligation to pending;
rolled-back or never-attached reservations are not promoted.

The worker commits the claim before any adapter call. Storage adapters must
confirm absence and treat a missing object as success; failure codes are
allowlisted, and retries reuse the same immutable object identity. Completion
and retry both require the current unexpired token. A crash or lost response
leaves the lease to expire; retrying an ambiguous deletion is idempotent.
Database completion is committed only after the adapter confirms absence.

**Physical deletion remains disabled.** No production Storage delete client or
service configuration is provided. `scripts/storage_cleanup_worker.py` refuses
to start by default. Tests may inject an in-memory adapter or the explicitly
gated local filesystem adapter against the disposable Unix-socket PostgreSQL
fixture; filesystem deletion is confined to synthetic objects below the private
`/tmp` root. Neither adapter provides production Storage access or authorizes
production object deletion. The API continues to return
`storage_cleanup=pending` after account deletion; the durable outbox survives
the account cascade and can be inspected/recovered by test-only worker
injection. No cleanup-status UI or hosted migration is included.

## Filesystem adapter for isolated local tests

The managed lifecycle can use a create-only filesystem adapter only when
`VERVFY_ENVIRONMENT=local-test` and `VERVFY_STORAGE_BACKEND=filesystem` are both
explicitly set. `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `PG*` overrides must
be unset. `DATABASE_URL` (and any optional migration/identity database URLs)
must target the fixture's disposable PostgreSQL Unix socket under
`/tmp/vervfy-storage-pg-*`; the active SQLAlchemy session is checked again
before lifecycle SQL. There is no backend fallback. The adapter rejects
non-test database destinations, uses only synthetic managed paths, and confines
object reads, create-only writes, and injected cleanup to a private directory
directly under `/tmp`. Its default is `/tmp/vervfy-staging-storage`; configure a
different dedicated `/tmp/<name>` directory when running concurrent tests.
Upload source fixtures and download scratch files must also remain under `/tmp`.
It does not issue hosted signed URLs; signed-URL and remote-stream operations
fail closed in this backend.

Run the isolated backend/storage tests from the repository root (the tests
override database/Storage configuration for their disposable fixtures):

```sh
env -u SUPABASE_URL -u SUPABASE_SERVICE_KEY -u SUPABASE_BUCKET \
  -u PGHOST -u PGPORT -u PGDATABASE -u PGUSER -u PGPASSWORD \
  -u PGSERVICE -u PGSERVICEFILE -u PGOPTIONS \
  PYTHONPATH=tests:. DATABASE_URL=sqlite:///:memory: \
  VERVFY_ENVIRONMENT=development \
  python -m unittest -q \
    test_filesystem_storage test_storage_lifecycle test_storage_writers \
    test_storage_cleanup test_storage_boundaries test_queued_artwork \
    test_audio_store_streaming test_security_regressions \
    test_provider_regression_guard test_staging_guard test_staging_migrations
```

The PostgreSQL fixture creates a temporary cluster with a private Unix socket,
no TCP listener, synthetic rows, and stops it during test teardown. Do not set
hosted database or Supabase variables, use the staging approval workflow, or
run hosted migrations for these tests. To stop, interrupt/exit the test runner;
the fixture stops its temporary database. The default filesystem directory is
deliberately retained for inspection and repeatability. Do not point it inside
the repository. Physical cleanup remains disabled: the worker entry point
refuses to start, and deletion/retry tests must explicitly inject the local
filesystem adapter against synthetic lifecycle rows.

## Validation and review limits

The durable reports directory contains the full cumulative Phase 3 diff relative
to the approved Phase 2 checkpoint, manifests, commands and final results. Only
disposable PostgreSQL/Redis and synthetic in-process Storage/loopback browser
fixtures are used. SQLite browser tests are functional API evidence, not RLS proof.
No production/staging migration, deployment, push, commit, merge, OAuth enablement
or original-worktree edit is authorized by these local results.

Independent review is required before any hosted migration or physical cleanup
enablement. Hosted create-only/provider
semantics, hosted role provisioning, persistence configuration and production
backup/object restore verification remain unverified. Held artwork/candidates can
consume storage and require explicit recovery. No production-ready claim is made.
The Phase 4 test-only adapter, absence of an operational production deleter,
unapplied hosted migration, missing hosted role review, and lack of an erasure
status surface remain release blockers. Production deletion requires separate
approval and a later reviewed implementation.

## Phase 4A bounded cleanup attempts (local only)

Forward-only revision `0029_cleanup_retry_limits` follows unchanged
`0028_storage_cleanup_leases`. Each issued claim increments the same durable
`attempts` counter, including a replacement after lease expiry. At most eight
claims are issued per object. Reference deferrals and unsafe-state holds do not
consume claims. Attempts 1–7 retain the existing exponential backoff (5 seconds
initially, capped at one hour); attempt 8 may still complete successfully.

An eighth reported provider failure enters `manual_review` immediately. An
expired eighth lease enters `manual_review` when the claim scanner next visits
it, without returning a new token or invoking an adapter. Existing pending or
expired jobs already at/above eight are also stopped when scanned; historical
counts are not reset. A live lease is never revoked early by this migration.
Manual-review rows are excluded from automatic claims and held-job promotion.
Their tokens and lease timestamps are cleared; the cleanup obligation and
`deleting` object remain durable, so new references remain forbidden.

`error_code` retains the latest allowlisted provider failure across reclamations.
`exhaustion_reason` records `attempt_limit_provider_failure`,
`attempt_limit_lease_expired`, or `attempt_limit_reached` (pre-existing exhausted
pending job). A crash without a reported provider failure may have a NULL
`error_code`; the explicit exhaustion reason still explains why work stopped.
All existing token/expiry checks, object-before-job locks, reference checks,
restricted function ACLs and RLS remain in force.

### Safe operator recovery requirements

Manual review is not proof of absence and must not be reported as erased.
There is deliberately no automatic reset or privileged recovery endpoint.
Before any separately reviewed recovery, an operator must:

1. Preserve the job, attempt count, diagnostics, namespace and immutable object
   identity in an audit record; investigate the provider failure or crash.
2. Quiesce all workers that could still be performing I/O, including expired
   claim holders. Database token fencing cannot cancel an in-flight provider call.
3. Verify the exact namespace/bucket/path, managed classification and byte
   verification, and recheck all authoritative references. Keep `deleting` in
   place; never restore `ready`/`live` or create a replacement identity to retry.
4. Use a separately approved, audited reconciliation procedure with the same
   object-before-job lock order and restricted privileges. Mark completion only
   after authoritative absence verification; keep obligations on ambiguity.
   Do not reset attempts, requeue, reuse old tokens, or delete the outbox row to
   bypass this eight-claim limit. Additional retries require a separately reviewed
   policy/schema change that preserves history and fencing.

This remediation does not provide or enable production deletion, hosted
migration, operator tooling, monitoring, or an erasure-status surface. Provider
semantics, role provisioning, backup/restore and independent release review
remain outstanding Phase 4 gates.

## Phase 4C manual review: operator access is not available

The current application has no authenticated operator identity or authorization
model. `app.current_user_id` is tenant context supplied to ordinary application
transactions; it is not evidence of operator authority. The cleanup worker is a
single-purpose capability for claiming, completing, and retrying jobs, not an
operator identity. The lifecycle owner and migration principal are privileged
maintenance principals, not a human-review role. None is safe to reuse for
investigation or recovery.

Accordingly, no administrative HTTP endpoint, manual-review SQL function, audit
writer, or recovery action is exposed. Migration 0030 adds a private operator
identity/audit schema, but ordinary `app_runtime` access cannot read or write
it, and no operator identity has been provisioned. The cleanup worker cannot
claim manual-review rows. This intentionally leaves exhausted obligations for
a future reviewed implementation instead of treating an unauthenticated caller,
a caller-supplied actor string, or a shared database credential as an operator.

A future implementation requires individually authenticated operator
principals and an independently provisioned, least-privilege authorization
boundary. Its read-only inspection must return only job/object IDs, authorized
tenant identity, classification and lifecycle state, attempts, last allowlisted
failure code, exhaustion reason, relevant timestamps, and lease/claim validity;
it must never return paths, credentials, signed URLs, or user content. The
operator identity must come from the authenticated database principal, not a
request parameter. Every mutation must be serialized using the established
object-before-job lock order and atomically append an immutable audit record
containing actor, timestamp, reason, action, and provider-verification outcome.

Recovery must preserve the deleting/reference fence and old token fencing. A
requeue cannot reset `attempts`: the existing eight-claim limit means a
separately reviewed schema/policy is required to authorize any additional,
bounded recovery claims while retaining the original history. A retain decision
must not restore an attachable lifecycle state. Provider verification must not
be represented as deletion completion without an authorized, fenced transition.
Until authentication, role-graph validation, audited functions, and disposable
PostgreSQL regression coverage for those transitions exist, inspection and
recovery remain unavailable and production readiness must not be inferred.

## Phase 4C.2.1 operator identity database foundation

Forward-only migration `0030_operator_foundation` follows the verified
`0029_cleanup_retry_limits` head. Forward-only migration
`0031_operator_revocation` extends it without changing historical migrations.
It creates isolated tables in the
`vervfy_operator` schema. The migration requires the separately provisioned
`vervfy_operator_foundation_owner` role to be NOLOGIN, NOINHERIT, non-privileged,
and SETtable only by the restricted migration login. The migration rejects
unsafe ownership, effective memberships, grants, or default ACLs on that role.
There are no grants to `app_runtime`, `storage_cleanup_worker`, or
`google_auth_lookup`; all five tables use ENABLE/FORCE RLS with an owner-only
policy. The owner role's schema CREATE grant is revoked after migration.

The schema keeps operator identifiers, passkey credential identifiers and
public keys, explicit role assignments, independent session-token digests, and
storage audit events separate from `public.users`, provider identities, and
ordinary session cookies/Redis keys. No private authenticator key or raw
session token is stored. Role assignments have no implicit default; the
database guard permits a bootstrap `operator_admin` assignment only when no
active administrator exists and an external reference is present, disallows
self-grants, and checks that subsequent grants/revocations come from an active
operator administrator. Migration `0031` makes the bootstrap assignment and
its reference single-use across revocation; it fails closed if multiple
historical bootstrap assignments already exist. Credential revocation now
revokes all sessions using that credential and cannot be undone through
UPDATE. Session rows require an active operator and unrevoked owned
credential; suspending or revoking an operator revokes existing sessions.
The token digest and session identity cannot be rewritten or unrevoked.

Audit UPDATE/DELETE/TRUNCATE triggers reject ordinary DML, including direct
DML performed as the foundation owner. This is not tamper-proof against that
owner or the migration login: either can alter/drop triggers or schema
objects. No independent audit sink exists, so audit history must not be
represented as tamper-resistant against database maintenance principals. No
WebAuthn authentication, session validation endpoint, credential enrollment,
operator HTTP authorization, or audit-writing service is enabled yet.

The current deployment has no independent, individually authenticated operator
provisioner or approved break-glass ceremony. Therefore the migration creates
the database foundation but deliberately does not provide production operator
account provisioning. The fixture's synthetic database administrator exercises
owner-only table operations solely to test constraints. A production bootstrap
must be a separately approved, dual-controlled process using an individual
non-application principal, recording an external change reference and never
placing credentials or secrets in SQL/logs. Until that process and subsequent
WebAuthn/session code are independently reviewed, do not provision real
operators or claim operator authentication is available.
