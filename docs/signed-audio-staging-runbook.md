# Signed audio staging trial

This documents the original isolated trial. The reviewed production rollout is documented in `signed-audio-production-rollout.md`; existing-object remediation remains blocked outside `staging`, `test`, or `development`.

## Prerequisites

Use a separate application service, database, private bucket and immutable namespace, with synthetic accounts/audio only. The connected Render/Supabase accounts currently expose production only; the previously mentioned staging project in repository documentation is not evidence that it is accessible or authorized. Do not substitute production credentials or endpoints. Do not copy customer audio into testing.

Keep the existing runtime roles, RLS/FORCE RLS, grants, namespace binding, retained-byte quotas, writer pause and physical deletion barriers. No Alembic revision or ACL change is part of this trial. The separately prepared 0035 ACL migration remains a separate change and is not incorporated or applied here.

Set `VERVFY_ENVIRONMENT=staging` and `VERVFY_AUDIO_SECURITY_HARDENING=1` only on that isolated application. Configure its existing approved database/storage credentials securely, with the existing TLS verification requirements. Bind `VERVFY_STORAGE_NAMESPACE_ID` to that database's immutable staging namespace. Neither application startup nor this feature creates a namespace or bucket. Do not edit production Render settings or its build command.

## Behavior

- New managed audio and staged-audio uploads request `private, no-store, max-age=0, must-revalidate`. Artwork policy is unchanged. Uploads remain create-only, reserve bytes first, verify uploaded bytes and retain failed reservations.
- `/api/tracks/{id}/playback-lease` requires the application session and owner-scoped library lookup. It returns a 900-second Storage lease, conservative expiry and server time, under a no-store response policy. Cached leases must have more than 240 seconds left to be reused.
- The client starts renewal 120 seconds before its conservative monotonic deadline, coalesces concurrent calls, aborts signing requests after 10 seconds, and rechecks on seek, foreground and online events. Healthy native audio is not replaced by a timer. New playback/recovery uses the renewed source; position and play/pause intent are preserved. Retry bursts remain bounded.
- Legacy audio receives a 409 from lease issuance and stays on the authenticated application Range endpoint. Trial reads never lazily migrate legacy storage. Authentication errors never trigger that fallback.
- Logout stops the player before waiting for the network, unloads audio, cancels pending starts/leases/downloads, clears queue/track state, revokes in-memory Blob URLs and notifies other tabs through BroadcastChannel plus a storage-event fallback. A failed logout request leaves the local player stopped; it does not falsely report server revocation. Suspended tabs process notification when JavaScript runs again.
- Completed offline downloads remain explicit account-scoped IndexedDB Blobs. Short online leases do not expire those downloads. Logout unloads them without silently erasing the saved copy. Cold offline startup is not redesigned by this change.

## Existing audio cache remediation

Do not overwrite an immutable object's bytes or use a metadata/S3 copy shortcut that bypasses reservations. Do not edit `storage.objects` rows directly. Do not delete old objects, refund retained bytes, rotate signing keys or enable cleanup.

The staging-only `audio_cache_remediation.plan(user_id, track_id)` reads an owner-scoped track, validates the immutable database binding, measures size and SHA-256, and returns a plan containing namespace, environment, media version, path hash and measurement time. It is read-only and works while writers are paused. Review the plan privately; target IDs are account data, although it contains no credentials or capability URLs.

`audio_cache_remediation.apply(approved_plan, attachment_connection=operator)` accepts that exact plan for at most 900 seconds. It requires an explicit transaction from an existing privileged **staging** operator, verifies the connection's immutable namespace, rechecks path hash, media version, size and source digest, honors writer pause, and invokes the existing lifecycle uploader through runtime permissions. The new object incurs a full additional retained-byte reservation. It must fit both tenant and global quota. It then compares-and-swaps only the unchanged owner-scoped track reference and advances its media version. The caller commits the operator transaction only after success. No privilege is granted to the application. A stale attachment does not delete or refund the new allocation; use the existing reconciliation procedures to account for it.

Run these functions only from an approved staging process with its secured environment, after synthetic rehearsals pass. There is deliberately no HTTP remediation route or automatic startup migration. Process one target at a time and record the returned new path hash. Compare the track, both objects, retained bytes and outbox state afterward.

Existing triggers can enqueue the retired identity as `pending`. The repair locks the affected object and outbox rows and preserves prior `held` states and their scheduling/claim/error fields atomically with attachment, inside a savepoint. It does not change the shared trigger functions or release existing holds. Physical cleanup must remain false, the worker must remain hard-disabled, and no cleanup claim may be executed. Stop on any `claimed`, `done`, deletion, refund, unexpected reference, quota change, binding mismatch or digest mismatch. Do not run this repair with runtime credentials or broaden their grants to make it work.

Copy-on-write prevents future normal playback from reusing the old path. It **does not revoke old signed links or bytes already cached elsewhere**. Keep a residual-exposure record for the prior browser/CDN cache lifetime. A shorter upload cache policy alone cannot certify a hard cutoff: Supabase documents that edge cache and signed-token expiry are independent. [Provider documentation](https://supabase.com/docs/guides/storage/cdn/smart-cdn)

If actual staging tests show private responses remain servable beyond the required cutoff, stop the rollout and use a session-checking application media/Range gateway for new playback. Such a gateway still cannot recall previously delivered bytes. Do not weaken TLS, CSP or storage isolation to make a test pass.

## Validation and release gates

Local checks use synthetic HTTP Storage fixtures and fresh PostgreSQL 17 clusters. The built-app browser configuration is `web/playwright.audio.config.ts`. Build with test-only loopback backend/site URLs, then run that configuration. It routes a synthetic HTTPS Storage hostname exclusively to a loopback fixture, preserving production CSP; it does not contact that hosted hostname or disable certificate verification.

Required hosted staging checks before any production proposal:

1. Verify the actual Storage API accepts the restrictive upload policy and returns it on 200/206 responses. Capture sanitized status, content-range, cache-control, age and CDN hit information; never persist signed URL query strings.
2. Issue real 900-second URLs. Test cold and warmed cache requests before expiry and after more than 900 seconds of wall time, both complete and Range requests. Do not substitute a browser clock change or mock 403 for this result.
3. Verify at least three renewals on a long synthetic track, near-expiry seeks, pause/resume, concurrent renewal, provider errors, signing timeout, revoked application session and logout during pending work. Observe audible continuity and request status; source preservation alone does not prove zero-gap playback.
4. Test real iOS Safari and Android screen lock, background audio, OS suspension, media controls, foreground recovery and intermittent connectivity. Desktop/mobile viewport and visibility simulation is only preliminary coverage.
5. Test disconnected Blob playback and seeking, completed download retention, explicit removal, quota failures and cold offline navigation. Document the existing cold-start limitations rather than claiming they are fixed.
6. Reconcile ledger bytes before/after each copy-on-write repair: old plus new charges remain, only one track pointer changes, and no object is physically deleted. Preserve all held jobs and disabled cleanup controls.

Do not propose production deployment until those hosted/device gates pass. Disabling the staging switch rolls back issuance behavior; it does not undo copy-on-write objects, refund quotas, revoke existing capabilities or purge previously cached bytes. Reverting an attached reference also requires fresh review; never use deletion as rollback.
