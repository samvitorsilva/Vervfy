# Storage lifecycle and cleanup

The application writes new objects under
`v2/<namespace-uuid>/<tenant>/<kind>/<object-uuid>.<extension>`. PostgreSQL
reservations and reference triggers own attachment and cleanup state. Account
deletion removes relational references in one transaction; its Storage cleanup
obligations are asynchronous and remain durable in the PostgreSQL outbox.
Legacy paths are retained and are never eligible for automatic physical
deletion by this worker.

## Migration history

The WebAuthn chain remains `0027_webauthn_foundation` →
`0028_webauthn_enrollment`. The storage/operator chain remains
`0027_storage_lifecycle` → `0028_storage_cleanup_leases` →
`0029_cleanup_retry_limits` → `0030_operator_foundation` →
`0031_operator_revocation`. Revision `0032_merge_storage_webauthn`
joins those histories without rewriting either chain; `0033_cleanup_activation_gate`
exposes the cleanup gate only to the cleanup worker.

Before any hosted migration, an authorized operator must establish the actual
database revision, role membership/ownership prerequisites, backup recovery
readiness, and the target schema. Do not stamp, downgrade, or infer the current
revision. The lifecycle migration preserves existing path values; it does not
re-key, delete, or copy legacy objects.

## Worker boundary

The cleanup process is separate from the API and must use the
`storage_cleanup_worker` PostgreSQL login. It runs one claim at a time. Storage
requests have a 12-second absolute deadline, below the 60-second lease; failures
are rescheduled with bounded backoff, and exhausted jobs remain in
`manual_review`. Shutdown stops new claims and waits for the bounded in-flight
request. Heartbeat and failure counters are emitted to process logs; alert on
missing heartbeats, repeated worker failures, and non-empty manual-review
queues.

The entry point exits by default unless
`VERVFY_STORAGE_CLEANUP_ENABLED=1`. Even with that flag, it refuses to start
while the database reports cleanup disabled. The current schema additionally
constrains `physical_cleanup_enabled` to remain false. No production activation
migration or deployed worker is included in this change.

## Supabase identity requirements

The API's `SUPABASE_SERVICE_KEY` remains an application credential and must
never be given to the cleanup worker. Do not use a `service_role` or S3 access
key for deletion. The adapter uses a dedicated Supabase Auth user, the project's
public/anon API key, and a short-lived authenticated JWT. Required worker
settings are:

- `DATABASE_URL`: TLS PostgreSQL URL authenticated as `storage_cleanup_worker`
- `SUPABASE_URL` and `SUPABASE_BUCKET`: same immutable binding as the database
- `VERVFY_STORAGE_NAMESPACE_ID` and `VERVFY_ENVIRONMENT`: immutable namespace
- `SUPABASE_ANON_KEY`, `SUPABASE_CLEANUP_EMAIL`,
  `SUPABASE_CLEANUP_PASSWORD`, and `SUPABASE_CLEANUP_SUBJECT`: dedicated Auth
  identity credentials and expected UUID
- `VERVFY_STORAGE_CLEANUP_ENABLED`: `0` unless a separately approved release
  authorizes activation

Before activation, configure and test Storage RLS in an isolated Supabase
project. The dedicated identity must have no broader Storage policy, no upload
or read policy, and only a delete policy constrained to the configured private
bucket and the full managed-key shape for the immutable namespace. Confirm the
provider treats one `DELETE` request containing one exact key as idempotent and
does not interpret it as prefix deletion. Verify denied paths, shared objects,
legacy paths, absent objects, and ambiguous network responses. This repository
does not claim that provider behavior or the RLS policy has been verified.

## Release gates

1. On a disposable PostgreSQL cluster, provision only the documented roles,
   upgrade both migration branches to the single head, and verify existing
   synthetic legacy rows and path strings are unchanged.
2. Run lifecycle, RLS/role, writer, outbox, lease-expiry, retry-limit, and
   account-deletion tests with synthetic storage.
3. In an explicitly approved isolated Supabase project, verify the dedicated
   Auth identity, policy boundaries, exact-key deletion response semantics, and
   credential rotation. Never use production objects for this test.
4. Before a production migration, obtain a fresh backup, verify a tested restore,
   inspect the live migration revision and role graph with an authorized
   operator, and review the exact migration plan. Those hosted facts are not
   established by local tests.
5. Keep physical cleanup disabled until the separate activation migration,
   least-privilege policy, worker deployment, monitoring, recovery runbook, and
   rollback approval have all passed review.

The three legacy bulk-migration scripts are intentionally retired: they wrote
unmanaged keys or changed schema outside Alembic. A lifecycle-aware legacy
migration remains a separate project requiring an inventory of shared
references and an approved namespace-migration plan.
