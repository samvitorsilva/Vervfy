# One-time owner catalog inspection — prepared for review

Use `production-catalog.sql` in the Supabase SQL Editor for project
`llxmskxxchpmeavorusj`, as the authorized project owner using the existing `postgres`
role. Verify the project reference in the dashboard before execution: SQL checks
cannot independently authenticate a Supabase project reference. The script requires
actual database `postgres`, effective role `postgres`, and PostgreSQL 17.11.
The reported deployed baseline remains `dd22f18b92e26a59d342a98e06dfc2888c58905b`;
this SQL does not verify Render deployment state.

Review the exact script and SHA-256 first. When authorized to perform the manual
inspection, run the entire file once, including BEGIN and ROLLBACK. Do not select
individual statements. It produces one `catalog_report` JSON result containing
all report sections. Any error/timeout means STOP; if the editor retains an open
transaction, issue only `ROLLBACK;`. Do not repair missing objects or broaden
privileges within this inspection. No production execution has occurred here.

The anonymous DO guard only reads catalogs and raises exceptions; it creates no
persistent function, executes no application function and writes no data. It
requires Alembic metadata to be an ordinary, non-RLS table with a built-in text or
varchar revision column. Missing metadata, views or incompatible types abort
before the revision read. The sole non-catalog relation read is
`ONLY public.alembic_version(version_num)`; no user, identity, bucket, object,
queue or namespace rows are read. Statement timeout is 30 seconds, lock timeout
3 seconds, idle-in-transaction timeout 60 seconds. All settings are transaction-local.
The read-only transaction is a procedural guard for an elevated operator, not a
claim that this identity lacks write authority.

Review the JSON sections as follows:

- `context`: expected database/operator/version and read-only transaction. The
  project string is an intended target label, not a server-side identity check.
- `revision`: exactly one recognized candidate revision through 0027 is required.
  Zero/multiple/unknown rows, or 0028, are STOP. Missing roles/relations appear as
  absent/null; this is not proof of readiness. Missing future objects may be
  expected at the observed earlier revision.
- `roles`, `memberships`, `effective_capability_holders`, schema/relation/column/
  sequence grants: compare with the frozen candidate migrations. The revision
  table's owner is only an OBSERVED candidate migration principal, not approval
  to use that role. Confirm the intended migration operator separately. OIDs
  correlate ownership/role metadata. In particular, do not assume the elevated
  `postgres` role satisfies the migration's restricted-role requirements.
- `rls_policies` and `constraints`: flags, applicable role OIDs and fingerprints
  only. No policy/constraint expressions are exported. Fingerprints need trusted
  comparison or separately reviewed metadata evidence; they alone cannot certify
  semantics. `uses_custom_function` is a dependency indicator, not a complete
  proof that every indirect policy dependency is safe. No policy is evaluated
  against application records by this script.
- `routines` and `reference_guards`: structural owner/SECURITY DEFINER/search-path/
  execution metadata and trigger identity only. No function source or invocation.
  At 0027, require the expected three enabled reference guards and forced storage
  RLS. `forbidden_0028_routines` must be zero.
- `fresh_0027_capability_prerequisites`: the migration's checks span non-system
  schemas and PUBLIC/default ACLs, including Supabase-managed objects. Before
  0027, existing storage capability roles must pass those zero-exposure checks.
  Missing capability roles are a separate provisioning prerequisite, not zero-risk
  success. At installed 0027, intended ownership/privileges already exist, so do
  not apply the pre-migration zero rule unchanged. No grants are corrected here.

Safe to share **with the authorized release reviewers**: the generated
`catalog_report` JSON, script hash, execution timestamp, expected project reference
and any generic STOP classification. The report is limited to application schema
names, role metadata, OIDs, privilege/ownership/RLS flags, counts, policy/constraint
fingerprints and recognized Alembic revision identifiers. These remain internal
security metadata; do not post them publicly. Review output before sharing.

Do not share SQL Editor screenshots with account/session details, connection
strings, keys, credentials, raw error diagnostics, user/object records or function
source. Unexpected diagnostics should be reviewed privately and summarized.

Validation performed locally: static transaction/statement/function/relation
allowlist review, checks that psql commands and unresolved substitutions are
absent, Python validation-script syntax, and SHA-256 generation. **No SQL was
executed**, locally or remotely; PostgreSQL grammar/runtime/permission validation
is not claimed. The explicit instruction not to execute SQL takes precedence over
runtime testing. `validation.json` records this limit.

This is a separate operator procedure. The existing restricted-inspector runner,
its contract, the release candidate and previous manifests were not modified.
Nothing here authorizes migrations, permissions changes, deployment or OAuth.
