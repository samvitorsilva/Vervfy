-- REVIEW PROPOSAL ONLY — run as vervfy_oauth_staging_user before migrations.
-- These defaults are scoped to this creator; Supabase creator defaults remain
-- unchanged. The postflight separately verifies every created Vervfy object.
\set ON_ERROR_STOP on

BEGIN;

ALTER DEFAULT PRIVILEGES
    REVOKE ALL ON TABLES FROM anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES
    REVOKE ALL ON SEQUENCES FROM anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated, service_role;

COMMIT;
