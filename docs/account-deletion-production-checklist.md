# Account-deletion verification — blocked for production

This checklist is not authorization to run production account deletion. Phase 4
has not enabled a production cleanup adapter, hosted migration, or erasure-status
surface. No production deletion has been performed. Use only a disposable local
PostgreSQL cluster and synthetic in-memory Storage for automated recovery tests.
Never use production or hosted staging for Phase 4 validation.

## Prepare an isolated test

1. For a future separately approved hosted verification only, use a dedicated
   test browser profile and a newly created test account. Keep the password,
   account ID, Redis session IDs, and object paths private.
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
5. Account deletion returns `storage_cleanup=pending`. The durable cleanup
   outbox survives deletion of the account row. Production deletion is not
   implemented or enabled: do not query or delete hosted Storage objects.
6. In the isolated browser profile, inspect only the synthetic account's
   `offlineTracks` records. The test account's record must be gone and the
   synthetic sentinel must remain byte-for-byte unchanged. Reopen the app and
   confirm no offline track from the deleted account is restored. Remove only
   the synthetic sentinel after recording the result.

## Failure handling and recovery

- **Session/version or Redis failure (503):** deletion must stop before database
  deletion. The session version may already have advanced, so
  reauthenticate after Redis recovers and retry only for the test account.
- **Database failure (503):** the account rows and cleanup obligations remain
  transactional. If the commit outcome is uncertain, check only
  `users.id = :test_user_id` and the exact synthetic test job IDs on the local
  disposable database before retrying. Do not infer success from a cleared
  cookie or infer failure from a client timeout.
- **Browser cleanup warning after API success:** server deletion is complete,
  but offline bytes may remain in that test browser. In the isolated profile,
  remove only `offlineTracks` records whose `accountId` equals the test
  account ID, then reopen the app and verify the synthetic sentinel remains.
  Do not clear all site storage where it could contain other accounts' data.
- **Lost response or any ambiguous result:** stop and reconcile the exact test
  account row, its recorded object paths, its recorded Redis session IDs, and
  its isolated-browser IndexedDB entries before retrying. Do not infer success
  from a cleared cookie or infer failure from a client timeout.

Deletion is not atomic across Redis, PostgreSQL, and browser IndexedDB.
Session-version advancement and Redis revocation happen before the account
transaction. References and cleanup obligations commit together; physical
Storage deletion, when separately approved and implemented, must happen later
through the fenced worker. Browser cleanup follows only after API success.
Backups and provider retention are outside this procedure.
