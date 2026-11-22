# Production ACL and legacy-inventory preparation

These are separate, explicit plan/apply operations, updated from the
read-only audit on 2026-11-22. They do not run migrations or call provider
write/delete endpoints. No production write, migration, or deployment has been
run.

## Required execution order

After an explicitly approved release of the pause-capable application, pause
and drain every storage writer and cleanup worker. Keep them paused through
these separately planned and approved stages: (1) ACL repair, (2) stale-audio
detachment, (3) legacy registration, (4) migration through 0034, (5) historical
size charges, and (6) byte reconciliation. Each stage requires a fresh plan
digest, explicit approval before its production write, and successful
postflight before proceeding. Stop on any mismatch or failure. This runbook
does not authorize a deployment or production write.

## ACL repair

The repair is limited to `public.auth_sessions`, `public.alembic_version`,
`public.artist_images`, and `public.track_cover_cache`. It requires the
restricted migration login, verified TLS/project/revision, a maintenance-window
confirmation, an independently approved plan digest, and an authorization
expiry within 15 minutes. It rejects unexpected owners, RLS state, privileges,
column ACLs, or role grants.

It preserves the intended `app_runtime` grants: `SELECT, INSERT, DELETE` on
`auth_sessions`; `SELECT, INSERT, UPDATE` on both cache tables; and no
`app_runtime` grant on `alembic_version`. It removes direct grants to
`anon`, `authenticated`, and `service_role` from those four internal tables,
and preserves the existing `postgres` grants on the two cache tables.
It does not enable or disable RLS, change tenant-table grants/policies, alter
rows, or change Supabase-wide default privileges.
Before approval, confirm no deployed component depends on Supabase
`anon`, `authenticated`, or `service_role` Data API access to these tables.
The latest read-only audit found the four target tables have no RLS, and those
roles currently have broad table privileges. Repository code accesses
`auth_sessions`, `artist_images`, and `track_cover_cache` through `app_runtime`;
the ACL repair preserves those intended grants. The service key is used by the
repository's Storage API adapter, not for these table queries.
The fresh 2026-11-22 read-only snapshot confirms all four tables are owned by
`vervfy_prod_migrator`, have RLS and FORCE RLS disabled, and have no
column-level ACLs. Current `app_runtime` grants match the intended auth/cache
privileges but also grant `SELECT, INSERT, UPDATE, DELETE` on
`alembic_version`; the repair removes that overgrant. All three exposed roles
have the full direct table privilege set on each target, including `MAINTAIN`
on PostgreSQL 17. The repair removes those grants, preserves the existing
`postgres` grants on the two cache tables, and leaves table ownership and RLS
unchanged. Local preparation tests verify that auth-session data and tenant
RLS state survive repair.

The database has active PostgREST 14.18 connections. Cumulative
`pg_stat_statements` data (reset 2026-10-20 20:22 UTC) showed 10,991 target-table
calls under `app_runtime`, but none under `authenticator`, `anon`,
`authenticated`, or `service_role`. The latest connection snapshot had two
idle PostgREST connections and five idle `app_runtime` connections; no
`storage_cleanup_worker` connection. The PostgREST schema configuration was
not visible in database role/database settings. `authenticator` can SET ROLE
to `anon`, `authenticated`, and `service_role`, and each has `public` schema
USAGE. Thus these un-RLS-protected tables are Data API-reachable if `public`
is in PostgREST's exposed schema list; that configuration remains unverified.
The query history is evidence, not proof that no external client depends on
these grants: activity history and idle connections cannot identify every
consumer. Obtain API/service-owner confirmation before revoking.

The MCP audit connection negotiated TLS 1.3, but it connected as
`supabase_read_only_user`, not `vervfy_prod_migrator`; this does not verify the
production runner's `sslmode=verify-full`, CA binding, or client TLS. SQL
metadata checks matched the migration role's expected attributes, database and
schema privileges, and ownership of all 12 required application tables. The
strict runner preflight and its read-only plan-file generation were not run:
the local `VERVFY_PRODUCTION_*` connection and CA settings are unset. Do not
treat the MCP session or this ACL snapshot as the runner's signed plan/digest.

The current inventory query reconfirmed 196 `songs` catalog objects, eight
lifecycle rows, 188 unregistered catalog objects, and two missing audio
references with no inline audio. All eight cleanup jobs are held; at revision
0032 the cleanup owner, executor, and worker still have claim permission, while
`app_runtime` does not. Current database sessions were idle, but this does not
prove that external services are paused. Before any apply, stop uploads,
processing/artwork workers, retries/schedulers, out-of-band object writers,
and the cleanup worker at their control planes; wait for in-flight database
transactions and Storage requests to drain; then recheck for zero active
claims and stable inventory. Keep them paused through all approved changes.
The repair does not alter grants or policies on the six tenant-RLS tables or
the other `service_role`-accessible tables; it is not a general API hardening.

The live ACL snapshot above is not a signed runner plan. Do not generate an
apply authorization from it. After configuring the restricted migration URL
and CA in the approved environment, obtain external API-owner approval and
pause/drain writers. Then generate a fresh guarded read-only plan:
Use `docs/storage-production-runner.env.example` as the placeholder-only
template; keep any populated copy outside the repository with owner-only
permissions.

```sh
python scripts/storage_production_acl_repair.py plan \
  --plan-file /secure/path/internal-acl-plan.json \
  --confirm-project-ref llxmskxxchpmeavorusj \
  --confirm-maintenance-window
```

Review the private plan and its printed SHA-256. Only after independent
approval, run `apply` with the same arguments plus
`--approved-sha256 <approved-digest>` and
`--authorization-expires-at <UTC-expiry-within-15-minutes>`. The command runs
the normal strict production preflight after repair. If that check fails, stop;
do not continue to stale-reference detachment, registration, or migration.

## Legacy registration and size verification

At revision 0032 or 0033, the registration tool snapshots all non-null storage
references in `tracks.storage_path`, `tracks.cover_path`,
`artist_photos.storage_path`, and `upload_jobs.storage_path`, plus the complete
existing lifecycle ledger. It only plans missing non-`v2/` references.
Unregistered `v2/` paths, incompatible existing ledger rows, drift, unsafe
paths, or a count other than the approved count block the operation.

Each new row gets a stable UUIDv5 derived from the immutable namespace and
path, with `tenant_id=NULL`, `kind/classification='legacy'`, `state='hold'`,
and no reservation token. The latest audit found eight existing ledger rows:
six managed and two held legacy rows, all with matching catalog objects. They
are preserved. The apply transaction locks reference tables and the ledger,
rechecks the plan snapshot, inserts only those rows, and creates no cleanup
jobs. Replaying the same plan is a no-op.

The latest audit found 196 objects in the private `songs` bucket, eight
ledger matches, and 188 unledgered catalog objects. The reference audit found
196 distinct paths: six already ledgered, 188 catalog-backed paths to register,
and two stale audio references with no Storage object, ledger row, or inline
audio. Their approved hashes and recorded sizes are:

| Path hash | Historical bytes |
|---|---:|
| `120ed875180f5a7c090e34f1d89cf286` | 30,780,168 |
| `9f964fb1a025533f6df8bb931ac4b3ff` | 5,759,110 |

Before legacy registration,
detach them through the guarded stale-audio tool at revision 0032 or 0033. This
uses the `app_runtime` tenant-scoped update and normal lifecycle trigger to
create two held legacy tombstones. It preserves the track rows, playlists, and
history, and does not delete storage data. The tombstones remain uncharged
until after migration 0034.

Plan and independently approve the detach stage separately:

```sh
python scripts/storage_production_stale_audio_repair.py plan --stage detach \
  --plan-file /secure/path/stale-audio-detach.json \
  --confirm-project-ref llxmskxxchpmeavorusj \
  --target 120ed875180f5a7c090e34f1d89cf286:30780168 \
  --target 9f964fb1a025533f6df8bb931ac4b3ff:5759110 \
  --confirm-storage-writers-paused \
  --confirm-no-alternative-copies
```

Apply with the same arguments plus `apply`, the reviewed
`--approved-sha256 <digest>`, and
`--authorization-expires-at <UTC-expiry-within-15-minutes>`. This is a separate
authorization from registration and migration. Then rerun the read-only
reference and catalog audits. If unchanged, registration should now see 188
unregistered catalog-backed paths, matching the 188 objects without ledger
rows. Stop if the new audit differs; the CLI count is not a way to override it.

```sh
python scripts/storage_production_legacy_registration.py plan \
  --plan-file /secure/path/legacy-registration-plan.json \
  --confirm-project-ref llxmskxxchpmeavorusj \
  --confirm-uploads-paused \
  --expected-unregistered-count 188
```

Review the private plan (it contains object paths) and its SHA-256. Independently
approve it, then use the same arguments with `apply`,
`--approved-sha256 <approved-digest>`, and
`--authorization-expires-at <UTC-expiry-within-15-minutes>`. Keep all storage
writers paused. The expected lifecycle inventory after detachment and
registration is eight existing rows, two trigger-created stale tombstones,
and 188 catalog-backed registrations: 198 rows total. Do not change the
expected count to make a mismatched plan pass. The registration tool does not
verify provider object existence itself; compare its paths to a fresh,
read-only storage catalog inventory before approving any plan.

After separate approval, run the guarded 0032→0034 migration. The migration
sets existing `reserved_bytes` to NULL, so new reservations remain blocked.
At 0034, freshly plan and independently approve the stale-audio `charge`
stage, then apply it. This records the positive historical `tracks.size_bytes`
values against the two held tombstones (30,780,168 and 5,759,110 bytes); it
does not claim the files exist or permit cleanup. This is a new digest and
approval from the pre-migration detach stage.

Before resuming writers, use `scripts/storage_inventory_reconcile.py` at 0034:
its read-only plan streams every unknown object twice, requires matching
positive byte counts, SHA-256 and strong ETag, and covers the complete unknown
ledger set. Review and independently approve that plan; apply fills only NULL
charges. The reconciliation should cover 196 physical objects (eight existing
catalog-backed rows plus 188 registrations). The two stale tombstones are
positively charged separately and are excluded from object reads.
Missing, unreadable, changing, or active objects block reconciliation; leave
writers paused and preserve the fail-closed quota gate until resolved. The
byte-read phase transfers object data and can incur provider egress charges;
approve its cost and duration separately. It performs no provider writes or
deletions.

The repair intentionally leaves owner-specific default privileges unchanged.
Review the observed `postgres`/`supabase_admin` defaults separately before
changing them; do not broaden this repair or alter Supabase-managed defaults
without explicit approval.
