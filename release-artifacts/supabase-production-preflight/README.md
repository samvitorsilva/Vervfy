# Supabase production read-only preflight — review only

**NOT AUTHORIZED TO CONNECT.** Project reference, exact production resource and
named operator are unconfirmed. No hosted connection or SQL execution has occurred.
This package supplements the existing candidate; it does not change or reprepare it.

## Operator checklist

1. **Identify and authorize before connecting.** A project owner records the Supabase
   organization ID, production project name/reference, region, primary database
   name, exact direct endpoint/5432, named operator, approving owner, ticket and
   UTC expiry in a copy of `approved-resource.template.json`. Verify the project is
   production, not a branch, staging or replica. Obtain these nonsecret identifiers
   from existing inventory and the authorized Supabase project owner; do not send
   credentials or connection strings to the agent. Record reported Render commit
   `dd22f18b92e26a59d342a98e06dfc2888c58905b` as reported, not independently verified.
   Bind this procedure manifest and approved resource-record hashes in the ticket.
   Initially authorize **catalogs only**. The supplied template is not an approval.
2. **Confirm the inspection identity is already provisioned.** Use only
   `vervfy_prod_inspector` under the contract below, with an existing operator-owned
   private passfile supplied through the organization's credential process. Never
   use the application login, `postgres`, a Supabase API/service-role key, or the
   dashboard SQL Editor. If the identity/access does not exist, STOP: creating a
   role, grants or an RLS policy is a production modification requiring a separate
   provisioning proposal and approval. No provisioning SQL is included here.
3. **Check local hashes, then run catalog SQL only after separate authorization.**
   Use the commands below. Review all results against the frozen candidate and
   the revision actually installed; do not interpret pending future schema as an
   existing security failure. Missing expected existing objects/permissions is STOP.
4. **Approve metadata visibility before stage 02.** A DBA reviews the catalog output,
   inspector column grants, all applicable bucket/namespace policies and their
   fingerprints, including permissive and restrictive combinations. Require simple,
   reviewed metadata-only SELECT policies with complete visibility of the approved
   bucket and namespace singleton; no custom function/subquery reading user data.
   A fingerprint is not proof unless it matches reviewed policy evidence. All
   inspector excessive-scope counts must be zero. Unknown policy behavior is STOP.
   Record the catalog output SHA-256, exact observed revision, bucket/configuration
   values and desired/existing immutable namespace in a newly approved resource
   record; allow `storage` and set the visibility-review flag only after signoff.
5. **Run bucket/namespace metadata stage after that approval.** This package assumes
   the database and Storage belong to the **same confirmed Supabase project** and
   use its standard project endpoint. A different Storage project/custom domain
   requires separately scoped inspection and an amended reviewed procedure.
   Both bucket identity checks, privacy and configured upload limits must pass.
   Derive required bytes from the reviewed Render setting `VERVFY_MAX_UPLOAD_MB`
   (candidate default 50 MiB) and MIME types from supported uploads and image
   writers in the candidate; do not guess or expose other environment values.
   MIME wildcard/provider matching rules require manual comparison if the exact
   allowlist-subset check fails; no automatic compatibility approval.
   Compare the namespace to the nonsecret approved configuration:
   `VERVFY_ENVIRONMENT=production`, `SUPABASE_URL`, `SUPABASE_BUCKET`, and
   `VERVFY_STORAGE_NAMESPACE_ID`. Do not view/export keys or full environment dumps.
   Namespace UUID/environment/endpoint/bucket must match; cleanup must be false.
   An absent namespace table before 0027 means pending migration/initialization,
   not permission to initialize. An existing table with no visible row is UNKNOWN
   until complete visibility is proven. A different immutable tuple is STOP.
6. **Inspect existing recovery evidence only.** In the exact project's Supabase
   Dashboard Database → Backups, an authorized operator views status, successful
   backup timestamps/IDs, retention and PITR recovery window if enabled. Record
   metadata and owner attestation only; do not download dumps, trigger backups,
   click Restore, enable PITR or alter retention. Inspect existing backup-system
   reports for music bytes separately: covered bucket, backup-set identifier/time,
   retention, integrity totals, encryption/key-recovery availability and access owner.
   Inspect a prior successful restore-rehearsal report: date, isolated destination,
   schema/role/RLS restoration and database-to-audio integrity/playback results,
   with compatible database/object recovery points, RPO/RTO and approver. Summaries
   must omit accounts, file/object names, paths, signed URLs, keys and raw dumps.
   Missing byte backups, expired recovery points, or no credible restore evidence
   is STOP for release. Request a separately approved nonproduction recovery
   rehearsal if needed; perform no backup/restore operation under this procedure.

## Inspection identity contract (specification only; no grants authorized)

- Dedicated LOGIN, NOINHERIT, NOSUPERUSER, NOBYPASSRLS, NOCREATEDB,
  NOCREATEROLE, NOREPLICATION. No inbound/outbound memberships, role ownership,
  application/capability ownership, schema CREATE, database CREATE/TEMP, write
  privileges, sequence rights or callable non-catalog routines. No `pg_read_all_data`,
  `pg_monitor`, settings/stats/file-reading roles or lifecycle/lookup memberships.
- Database CONNECT; ordinary catalog visibility, without protected `pg_authid` or
  role-password access. USAGE only on schemas needed by the following metadata
  reads. Do not grant application table access or change PUBLIC/provider ACLs.
- Column SELECT only: `public.alembic_version(version_num)`;
  `storage.buckets(id,name,public,file_size_limit,allowed_mime_types)`;
  if present, `vervfy_storage.namespaces(id,namespace_id,environment,endpoint,bucket,
  physical_cleanup_enabled)`. No broader table SELECT. No `storage.objects` rows,
  application-user rows or provider-identity rows. Catalog inspection of those
  relations' ACLs, policies and structure is permitted.
- Existing, explicitly reviewed, SELECT-only RLS visibility restricted to the
  approved bucket and singleton namespace. Forced RLS is retained. Never use
  BYPASSRLS or membership in lifecycle-owner to obtain metadata. Permission errors
  and RLS-hidden rows are not a clean/empty database. Supabase PUBLIC grants can
  defeat a custom role's narrow direct grants: treat excessive scope as STOP and
  obtain a separate access design, not blanket revocations or privilege escalation.
- A role-level read-only default is desirable but is not a security boundary. The
  runner additionally enforces read-only transactions and a sanitized environment.

## Exact commands

**Local verification now; no connection and no SQL execution:**

```bash
cd /home/sam/vervfy-latest
python3 release-artifacts/supabase-production-preflight/preflight.py check-local
sha256sum release-artifacts/supabase-production-preflight/procedure-manifest.json
```

Review the package. Populate a **copy** of the template using nonsecret resource
metadata. An approving owner must bind the record SHA-256 and procedure-manifest
SHA-256 in the authorization ticket, set `status=APPROVED`, confirm the operator
and existing identity, and set a future UTC expiry. Authentication remains in an
existing local mode-0600 passfile, never in this JSON or a command-line URL. The CA
must come from the exact project's approved certificate record and its hash must
be bound in the resource record. Direct endpoint connectivity and `verify-full`
are mandatory; no automatic pooler/TLS fallback or default credential fallback.

**Do not run until the corresponding stage is explicitly authorized.** Replace
only the bracketed nonsecret approval/operator/path placeholders:

```bash
install -d -m 0700 /tmp/vervfy-production-preflight-evidence
python3 release-artifacts/supabase-production-preflight/preflight.py run-read-only \
  --stage catalogs \
  --approval /absolute/path/approved-production-resource.json \
  --approval-sha256 '<HASH_FROM_AUTHORIZATION_TICKET>' \
  --operator-id '<AUTHORIZED_OPERATOR_ID>' \
  --passfile /absolute/private/path/inspection.pgpass \
  > /tmp/vervfy-production-preflight-evidence/catalogs.txt \
  2> /tmp/vervfy-production-preflight-evidence/catalogs.errors.txt
```

A nonzero exit or STOP ends the procedure; inspect errors privately, do not widen
permissions or retry automatically. Do not share raw diagnostic files. Stage 02
requires a new approval record/hash binding the **reviewed** catalog output:

```bash
sha256sum /tmp/vervfy-production-preflight-evidence/catalogs.txt
python3 release-artifacts/supabase-production-preflight/preflight.py run-read-only \
  --stage storage \
  --approval /absolute/path/approved-storage-metadata-resource.json \
  --approval-sha256 '<HASH_FROM_STORAGE_STAGE_AUTHORIZATION_TICKET>' \
  --operator-id '<AUTHORIZED_OPERATOR_ID>' \
  --passfile /absolute/private/path/inspection.pgpass \
  --reviewed-catalogs /tmp/vervfy-production-preflight-evidence/catalogs.txt \
  > /tmp/vervfy-production-preflight-evidence/storage-metadata.txt \
  2> /tmp/vervfy-production-preflight-evidence/storage-metadata.errors.txt
```

Before stage 02, freeze applicable ACL/policy/config changes for this inspection
window by operational coordination, not SQL locks. If concurrent changes occur,
STOP and reapprove catalog evidence. The runner pins the revision again, but a
catalog snapshot cannot prove that privileges/policies stayed unchanged afterward.

## Acceptance and migration STOP conditions

- PostgreSQL below **16** is unsupported by these migrations. This procedure gates
  catalog inspection to majors **16–18**; any other major requires a revised
  review. Local migration evidence is **18.6 only**. A different hosted version
  needs explicit compatibility signoff before migration, not an automatic pass.
- Exactly one known candidate revision through 0027; missing, multiple, unrecognized,
  branch/partial state or any 0028 revision/routine is STOP. `DISCOVER` permits
  stage 01 to discover a known revision; stage 02 requires its reviewed exact value.
  Already at 0027: verify postflight; do not schedule a new migration as an assumption.
- Reconcile roles and effective grants with migrations 0022/0024/0026/0027 and the
  existing runbook. Only the production migration role may SET capability owners;
  owner roles have no login/elevated attributes. Only `google_auth_lookup` inherits
  the lookup executor; only the restricted cleanup login inherits cleanup executor,
  both without SET/ADMIN. No extra/nested holders. All required roles must exist
  before a separately approved migration. Do not substitute the staging migration
  identity or use the staging guard/bootstrap SQL on production.
- **Supabase-specific 0027 prerequisite:** before 0027, each storage capability's
  final four inventory counts must be zero, exactly matching `_fresh_privileges`
  across all non-system schemas/default ACLs. Supabase-managed PUBLIC execution
  or default privileges may conflict. Any count or unsafe role graph is STOP;
  provider-managed roles are not exempt from the migration's checks. If already
  at 0027, intended storage ownership/grants naturally exist: reconcile with the
  installed target, rather than applying the fresh-capability zero rule again.
- Expected tenant RLS tables: tracks, favorites, playlists, playlist_tracks,
  upload_jobs, artist_photos, track_listens, and provider_identities when introduced
  by the installed revision. Require ENABLE and FORCE plus reviewed policy
  semantics. `users` and shared caches are not tenant-RLS tables in this chain.
  At 0027, storage tables require forced RLS and exactly the three enabled,
  correctly bound `storage_reference_guard` triggers. Fingerprints require a
  trusted comparison; they alone do not certify policy/function behavior.
- Lack of migration-role object ownership/schema authority, unknown effective
  grants, missing metadata permissions, unsafe inspection access, unreviewed RLS,
  storage mismatch or inadequate recovery evidence means STOP. Do not probe
  privileges by writing, executing capability functions, or running migrations.
- This read-only procedure cannot prove live object existence/playability,
  reference-path consistency, write authority, restore success or Google flows.
  Those need existing credible evidence or separate authorization. No object
  listing, signed URL, playback or OAuth test is included here.
- Later approval must bind the unchanged candidate hash, production-specific
  migration executor/identity, exact current→`0027_storage_lifecycle` path, recovery
  plan and window. Keep 0028 unapplied and physical cleanup/worker disabled.
  Namespace initialization, provisioning, configuration, migrations and deployment
  are separate modifications and are **not authorized by a read-only signoff**.

## Query/privacy review and sources

`01-catalogs.sql` reads only PostgreSQL catalogs and the release revision column.
`02-storage-metadata.sql` reads only that column and the expressly listed bucket
and namespace metadata columns, producing booleans/counts. Neither reads user
records, provider identities, object metadata rows or bytes. Policy/function/
constraint literals are hashed rather than exported; unknown role names are
classified. No password catalogs, connection strings, tokens, function invocation,
function definitions, activity-query text or raw environment dumps are selected.
Both files use REPEATABLE READ / READ ONLY, session-local timeouts/search path,
SELECT/CTEs/built-in introspection and final ROLLBACK. The permitted psql meta
commands only format output, set variables, branch, stop or capture query flags.
A SELECT can invoke side effects through a function/RLS policy; this is why
custom routines are never called and stage 02 requires prior policy review.

Preparation verification is **static only**: local hashes, Python syntax, a
restrictive SQL keyword/meta-command scan and manual query review. No SQL parser,
database execution or hosted result has been used; SQL runtime/permission checks
remain pending authorized inspection. The local check is not production approval. `verify-preparation.py` reproduces
the static scan without executing SQL; `static-review.json` records its result.

Provider references (public documentation only):

- [Supabase connections and verified TLS](https://supabase.com/docs/guides/database/connecting-to-postgres): use the confirmed project's direct endpoint and CA; custom direct-login name, no API key.
- [Supabase platform access control](https://supabase.com/docs/guides/platform/access-control): dashboard Read-Only SQL uses `supabase_read_only_user` with `pg_read_all_data`, which exceeds this scope.
- [Storage schema](https://supabase.com/docs/guides/storage/schema/design) and [private buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals): bucket configuration is metadata; storage-object rows/bytes are excluded here.
- [Database backups](https://supabase.com/docs/guides/platform/backups): database backups exclude Storage bytes; custom-role passwords also need a separate recovery process.
- [Supabase managed-role limits](https://supabase.com/docs/guides/database/postgres/roles-superuser): do not assume managed operator authority meets migration/namespace prerequisites.
- [PostgreSQL role membership](https://www.postgresql.org/docs/18/role-membership.html), [read-only transactions](https://www.postgresql.org/docs/18/sql-set-transaction.html), and [libpq authentication environment](https://www.postgresql.org/docs/18/libpq-envars.html).

**Exact next action:** the production project owner identifies the resource and
operator, reviews this package and the existing inspection-identity evidence,
and approves only the catalog-stage record/hash/time window. If no compliant
inspection identity exists, stop for a separate provisioning/access-design approval.
Do not connect before that authorization.
