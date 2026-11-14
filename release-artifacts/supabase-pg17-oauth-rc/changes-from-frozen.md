# Supabase PG17.11 candidate changes

Baseline: `release-artifacts/final-local-rc/vervfy-release-candidate.tar.gz`  
Baseline SHA-256: `58da2d95be04aa7077c8b5b0b76965fcbb7f99f86b210b5565d5e94285e1108d`  
Migration target: `0027_storage_lifecycle`; `0028_storage_cleanup_leases` remains unapplied.  
Passkey/WebAuthn code: excluded.

The original archive remains unchanged. The initial new source contained 254 files: 14
modified, 6 added, and 6 obsolete Render/PG18 staging runbooks removed.

**Modified:** `.env.example`,
`alembic/versions/0022_provider_identity_lookup.py`,
`alembic/versions/0027_storage_lifecycle.py`, `staging_guard.py`,
`docs/google-oauth-readiness.md`, `docs/staging-alembic-preflight.sql`,
`docs/staging-alembic-postflight.sql`,
`docs/staging-db-bootstrap-proposal.sql`,
`docs/storage-namespace-initialization.md`,
`tests/storage_lifecycle_fixture.py`, `tests/test_oauth_postgres.py`,
`tests/test_staging_guard.py`, `tests/test_staging_migrations.py`, and
`tests/test_storage_lifecycle.py`.

**Added:** `supabase_role_memberships.py`,
`tests/supabase_pg17_fixture.py`,
`docs/staging-migration-default-privileges.sql`,
`docs/staging-namespace-bootstrap-grant.sql`,
`docs/staging-namespace-bootstrap-revoke.sql`, and
`docs/supabase-staging-compatibility.md`.

**Removed as superseded and unsafe for this target:** the Render endpoint
approval, PostgreSQL 18 staging review/recovery/initialization runbooks, and
the old metadata preflight/postflight SQL.

**Compatibility/security changes:** session-pooler project-ref login and
`verify-full` TLS only; PostgreSQL 17.11 and Supabase `postgres` database
checks; exact provider-created role-membership edge; retained provider schemas,
default ACLs, `PUBLIC CONNECT`, `PUBLIC TEMP`, and public-schema USAGE; scoped
migration defaults; API-role object-access postflight; temporary namespace
`MAINTAIN` grant/revocation. Forced RLS, tenant isolation, restricted Google
identity lookup, and storage lifecycle protections remain covered by negative
tests.

**Validation:** disposable PostgreSQL 17.11 and the complete candidate test
suite: **335 passed**, including negative role/API exposure, TLS, tenant/RLS,
lookup, storage lifecycle, and namespace grant/revoke tests. No hosted SQL,
migration, or deployment was performed.

## Frontend staging isolation update

The Virginia runtime-guard candidate now contains 258 source files. The
staging Blueprint sets `VERVFY_ENVIRONMENT=staging` for the web service. Its
Next.js configuration accepts only the expected HTTPS API and web origins for
the proposed service names, rejecting production or malformed destinations
before build. Added `source/web/staging-backend-url.ts` and
`source/web/tests/staging-backend-url.spec.ts`; updated
`source/web/next.config.ts` and `source/render.staging.proposal.yaml`.

**Validation:** five focused frontend URL tests passed, targeted ESLint passed,
and a Next.js production build with the expected staging origins succeeded.
The generated rewrite manifest contained only the staging API origin. The
actual Render hostnames and Free Key Value workspace slot remain unverified.
