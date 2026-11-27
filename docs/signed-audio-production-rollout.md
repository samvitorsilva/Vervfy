# Controlled signed audio production rollout

The user authorized skipping hosted staging and new backups. Use synthetic audio first. No database migration, existing-object remediation, overwrite, deletion, quota refund, cleanup claim or privilege change is part of this release.

## Controls

`VERVFY_AUDIO_SECURITY_HARDENING=0` disables new lease issuance and returns the prior redirect behavior. `canary` enables it only for IDs in `VERVFY_AUDIO_SECURITY_CANARY_USERS`. `1` enables it globally after validation. The default is `0`; unknown modes fail closed. New audio upload cache policy is scoped through the object tenant, so canary mode leaves other accounts' uploads unchanged. Account-scoped rollout is enforced by list/upload/job/update payloads and by the lease/stream endpoints themselves.

Existing-object remediation is separately blocked in production even when leases are enabled. It is never called on startup or by HTTP. Existing references, retained-byte charges, cleanup hold fields and physical deletion barriers remain intact. New synthetic uploads incur normal retained-byte charges and are not deleted or refunded afterward.

## Order

1. Record the currently live backend deployment and frontend commit/status. These existing deployments/commits are rollback targets; do not create a backup or export production data.
2. Review the complete diff, run local authentication/ownership, quota, disabled-cleanup, lease and browser regressions. Merge only the reviewed head with a GitHub head-SHA check.
3. Deploy code with hardening disabled or account-scoped. Use one fresh synthetic account, no customer audio. Preserve the Render hashed installation/start commands, environment variables and auto-deploy policy.
4. In canary mode, upload separate synthetic warm-cache and cold-cache fixtures. Verify their actual Storage 200/206 cache headers. Record status/cache metadata only, never capability queries, cookies or credentials.
5. Issue real 900-second leases, warm one capability and leave another cold. After actual wall-clock expiry, test both normal and Range requests from fresh clients. Verify renewal obtains a new usable capability. Exercise playback/seek, logout and offline Blob behavior with synthetic audio only. Accelerated local clocks and mocks must be labeled as such.
6. Stop and retain or roll back the canary if expiry, CDN behavior, authorization, startup, quota, ledger or playback checks fail. Do not globally activate a failed cutoff. Do not fix failure by deleting objects, rotating keys, bypassing TLS, disabling RLS or releasing cleanup holds.
7. Activate global mode only after required checks pass and reconcile the existing ledger fingerprint excluding synthetic additions. Existing object cache remediation remains a separate, unapplied procedure.

## Rollback

First return the rollout switch to `0` while retaining the same canary list. Re-deploy the last known-good code if needed. Render retains the prior live deployment. The existing base commit is `8f356bce4b14656acbef067014c1418b63c47785`; the corresponding recorded backend deployment is `dep-dc4t33h7lnhs739ot7tg`. Verify these identities immediately before release; never assume they are still current.

If service-specific rollback is unavailable, revert only the new squash/merge commit on the current main branch, without a force push, and deploy that reviewed revert. Vercel's GitHub deployment should restore the frontend from the revert; trigger the Render backend deploy only after verifying the target head. Do not reset unrelated changes. Returning to old code does not revoke previously issued links, purge client caches, remove synthetic fixtures or refund their charges.
