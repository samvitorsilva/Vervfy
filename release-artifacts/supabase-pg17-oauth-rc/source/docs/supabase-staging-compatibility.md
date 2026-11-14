# Supabase PostgreSQL 17.11 Google OAuth candidate

This candidate is based only on the verified frozen Google OAuth archive
`release-artifacts/final-local-rc/vervfy-release-candidate.tar.gz`
(SHA-256 `58da2d95be04aa7077c8b5b0b76965fcbb7f99f86b210b5565d5e94285e1108d`).
The original archive is preserved. The candidate targets the isolated Supabase
project verified in the prior read-only review, database `postgres`, PostgreSQL
17.11, and its session pooler. It has not been run against any hosted database.

## Compatibility changes

- The staging guards accept PostgreSQL 17.11 through 17.x, database `postgres`,
  Supabase provider schemas, and the session-pooler user form
  `<vervfy-role>.<project-ref>`. Client TLS is always `verify-full` with the
  independently verified CA; no TLS downgrade or `pg_stat_ssl` substitute is
  accepted.
- The role checks require the exact provider-created membership tuple
  (`member=postgres`, `grantor=supabase_admin`, `ADMIN`, not `INHERIT`, not
  `SET`) plus only reviewed Vervfy memberships. Test-only catalog edits model
  that provider tuple in disposable PostgreSQL; never use them on Supabase.
- Supabase-owned schemas and default ACLs are retained. The migration login's
  defaults are explicitly hardened before migration; postflight checks
  effective access so `anon`, `authenticated`, and `service_role` cannot access
  Vervfy tables, sequences, functions, or private schemas.
- `PUBLIC TEMP` is preserved, rather than revoked across the shared database.
  The equivalent security invariant is tested: Vervfy roles receive no direct
  TEMP grant, tenant tables retain forced RLS, and security-definer routines
  pin `search_path` and qualify protected relations. Temp-object shadowing is
  covered by disposable negative tests.
- Namespace initialization is a separate approved step. A temporary grant of
  `USAGE`, `SELECT`, `INSERT`, and PostgreSQL 17 `MAINTAIN` to `postgres` is
  required; `MAINTAIN` permits the initializer's `EXCLUSIVE` lock without
  granting row updates or deletion. The revocation script is to be run
  immediately after initialization, even if initialization fails.

## Controlled staging sequence

1. Independently confirm the isolated project ref, exact session-pooler
   hostname, role suffix, database `postgres`, and approved CA fingerprint.
   The verified dashboard CA fingerprint recorded in the prior review is
   `80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA`.
   Keep credentials out of this checkout and approval record.
2. With separate explicit approval, run
   `docs/staging-db-bootstrap-proposal.sql` as the staging `postgres` role.
   Set login passwords through a protected secret workflow; do not activate
   Google OAuth or deploy the cleanup worker.
3. Connect as `vervfy_oauth_staging_user` and run
   `docs/staging-migration-default-privileges.sql`, then the guarded read-only
   preflight. Stop on any role, schema, ACL, membership, version, or identity
   mismatch.
4. Only after a new explicit migration approval, run the guarded Alembic
   upgrade to `0027_storage_lifecycle` and the read-only postflight. Keep
   `0028_storage_cleanup_leases` unapplied and OAuth disabled.
5. After postflight, separately approve the namespace binding. Run
   `docs/staging-namespace-bootstrap-grant.sql` as the migration role; call
   `storage_namespace.initialize_namespace` in one transaction as Supabase
   `postgres`; verify the exact immutable tuple and
   `physical_cleanup_enabled=false`; then run
   `docs/staging-namespace-bootstrap-revoke.sql` as the migration role.
   Re-run postflight to verify all temporary privileges are gone.
6. Retain the staging database if any step fails. A failed initialization is
   not a reason to downgrade or drop schemas. Run the revoke script after a
   failed initializer, then inspect state and obtain separate recovery approval.

All hosted SQL above is proposal-only and was not executed. The migration and
namespace sequence was exercised only on disposable PostgreSQL 17.11. See the
candidate manifest and checksum files alongside this document for the exact
reviewed contents.
