# Production account-deletion verification

This is a manual checklist only. No production deletion has been performed.
Run it only with explicit authorization, in an approved window, using a newly
created, dedicated test account and synthetic test-owned files. Do not use a
maintainer's or customer's account. Never run broad Redis scans, bucket listings,
unfiltered SQL queries, or commands that read or change another account's data.

## Current deferred-cleanup architecture

Account deletion revokes sessions, then deletes account records and queues storage
cleanup obligations in one PostgreSQL transaction. A successful API response is
`{"ok": true, "storage_cleanup": "pending"}`. It does **not** confirm physical
Supabase object deletion. Browser offline cleanup follows API success.

Physical production deletion remains disabled:

- `scripts/storage_cleanup_worker.py` refuses to run; there is no authorized
  production storage deleter.
- Migration 0033 revokes `claim_next_cleanup()` execution from the runtime,
  cleanup capability and worker roles. Do not restore those grants.
- The immutable namespace has `physical_cleanup_enabled=false`, enforced by a
  database constraint. Do not alter that constraint or binding.
- `audio_store.delete`, `delete_quietly`, and nonempty `delete_many` refuse
  physical deletion. Legacy and unverified objects remain held for review.

Cleanup obligations intentionally survive account-record deletion. Do not purge
those obligations or mistake their presence for an incomplete account-row delete.

## Prepare an isolated test

1. Use a dedicated test browser profile with no personal Vervfy data. Create a
   test account through the normal production registration flow. Record its
   exact account ID from that account's authenticated `/api/me` response. Keep
   the password, account ID, Redis session IDs, and object paths private.
2. Generate a short synthetic audio file and a simple test image locally. Do
   not use commercial music, real profile photos, or files owned by another
   person. Upload the audio, a track cover, and an artist photo to the test
   account. Add a playlist, favorite, and listening-history entry using only
   that test track.
3. In the isolated browser profile, download the test track for offline use.
   Add a synthetic IndexedDB sentinel record with a distinct fake account ID
   and harmless generated audio. This is test data, not another real account;
   it checks that the cleanup targets only the deleted account ID.
4. Open a second isolated browser context and sign in to the same test account.
   This creates two test sessions. Before deletion, record the members of only
   `vervfy:user-sessions:<test-account-id>` from the configured Redis database.
   Do not inspect other Redis keys or values. Record the exact playlist IDs,
   test-owned Storage paths, and any staging paths from rows filtered by the
   test account ID only.
5. Confirm the test account ID, session IDs, object paths, and synthetic test
   files are documented in a private test record before proceeding.

## Delete and verify

1. In the first browser context, use Account settings → Delete account, enter
   the test account's current password, and type `DELETE`. Do not call the
   endpoint with another account's cookie or identifier.
2. Expect the deletion request to succeed and the browser to navigate to the
   deleted-account confirmation page. The second context's next authenticated
   API request must be unauthorized; it must not load account or offline
   content for the deleted account.
3. In Redis, check only the previously recorded test session IDs:
   `vervfy:session:<test-session-id>` must not exist, and
   `vervfy:user-sessions:<test-account-id>` must be empty or absent. Do not
   enumerate the global session keyspace. Legacy-session sweeping is covered
   by isolated automated tests because reproducing pre-index production
   sessions is unnecessary for this test.
4. Run read-only database checks parameterized with the exact test account ID.
   Every count below must be zero:

   ```sql
   SELECT count(*) FROM users WHERE id = :test_user_id;
   SELECT count(*) FROM tracks WHERE user_id = :test_user_id;
   SELECT count(*) FROM artist_photos WHERE user_id = :test_user_id;
   SELECT count(*) FROM track_listens WHERE user_id = :test_user_id;
   SELECT count(*) FROM favorites WHERE user_id = :test_user_id;
   SELECT count(*) FROM playlists WHERE user_id = :test_user_id;
   SELECT count(*) FROM upload_jobs WHERE user_id = :test_user_id;
   SELECT count(*) FROM playlist_tracks
   WHERE playlist_id IN (:test_playlist_id_1, :test_playlist_id_2);
   ```

   Bind the ID as a query parameter; do not replace these with unfiltered
   listings or queries. Include only playlist IDs recorded for this test
   account; omit the last query if it had no playlists. This direct child-row
   check remains meaningful after the parent playlist rows are deleted.
5. Verify cleanup obligations for only the previously recorded test-owned
   object paths using an appropriately authorized read-only database check.
   Expect pending or held obligations, not physical absence. Supabase objects
   may remain indefinitely while cleanup is disabled. Do not delete them,
   restore claim grants, browse the bucket, or run a production cleanup worker.
   A profile photo is stored in the account row, not a Supabase object.
6. In the isolated browser profile, inspect only the synthetic account's
   `offlineTracks` records. The test account's record must be gone and the
   synthetic sentinel must remain byte-for-byte unchanged. Reopen the app and
   confirm no offline track from the deleted account is restored. Remove only
   the synthetic sentinel after recording the result.

## Failure handling and recovery

- **Session/version or Redis failure (503):** account-record deletion stops.
  Session version may already have advanced; reauthenticate after recovery.
- **Database failure (503):** account-row deletion and queued obligations roll
  back together. No physical Storage deletion occurs. Sessions may already be
  revoked. If commit outcome is ambiguous, reconcile only the exact test account
  and recorded paths before retrying; do not infer failure from a timeout.
- **Browser cleanup warning after API success:** database deletion succeeded,
  but offline bytes may remain. Remove only records for the synthetic account
  in its isolated browser profile, preserving the synthetic sentinel.
- **Future cleanup failure:** timeout, ambiguous deletion, failed absence checks,
  or persistence failure must never imply completion. Preserve the obligation.
  Exhausted retries require manual review, not automatic job removal or reset.

Redis revocation, PostgreSQL commits, and browser IndexedDB cleanup are not one
atomic transaction. Physical Supabase cleanup is a separate, currently disabled
operation. Backups and provider retention are outside this procedure.

## Disposable cleanup rehearsal

`tests/isolated_storage_cleanup.py` implements a memory-only synthetic worker;
`tests/test_isolated_storage_cleanup.py` creates a fresh PostgreSQL cluster with
no TCP listener and a private `/tmp/vervfy-storage-pg-*` Unix socket. It applies
the existing migration chain only to that empty disposable database. Test-only
`cleanup_rehearsal` wrappers reuse the existing claim function as its owner;
the original production claim ACL remains revoked throughout. Never install
these wrappers in a persistent environment. No Supabase or filesystem deletion
adapter is accepted by the rehearsal worker.

The worker validates disposable-only configuration before opening a database
connection and revalidates after checkout. Claims commit before storage access.
Before synthetic deletion the worker checks
the immutable namespace, path identity, tenant/requester ownership, reference
absence, token and lease, holding object/job locks through the memory operation.
Reference triggers prevent reattachment of deleting objects. Absence is checked
before completion. Existing SQL implements unique fencing tokens, eight maximum
attempts, bounded exponential backoff, and retained manual-review obligations.
After an ambiguous completion commit, replay/reclaim checks the object again;
already absent objects are safe to process. Unknown errors abort the transaction.

Run from the repository with an empty environment (no `.env` sourcing):

```sh
env -i PATH="$PATH" HOME=/tmp DATABASE_URL=sqlite:// \
  VERVFY_SECRET_KEY=synthetic-test PYTHONPATH=.:tests \
  .venv/bin/python -m pytest -q tests/test_isolated_storage_cleanup.py \
  tests/test_isolated_storage_guards.py tests/test_storage_cleanup_worker_disabled.py
```

The bootstrap placeholder URL does not supply PostgreSQL evidence: the integration
fixture creates its own PostgreSQL URLs. PostgreSQL binaries, a non-root user,
and permission to bind a local Unix socket are required. Setup errors or skips
mean PostgreSQL behavior is **unverified**, never passing RLS evidence.

## Separate production authorization required

This rehearsal is not a production cleanup release. Production activation needs
separate review and explicit authorization for provider deletion semantics,
bounded network deadlines, independent absence confirmation, lease expiry during
remote I/O, credentials and effective ACLs, monitoring, retained manual-review
jobs, legacy ownership reconciliation, and a narrowly scoped synthetic canary.
PostgreSQL concurrency/RLS tests must actually pass first. A remote provider
cannot participate atomically in the database transaction; an expired request
must not be treated as confirmed completion. Do not add a production adapter,
change grants/constraints, migrate production, or enable a worker as part of this
local rehearsal.
