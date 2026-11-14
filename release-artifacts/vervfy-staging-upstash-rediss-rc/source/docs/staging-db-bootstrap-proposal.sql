-- REVIEW PROPOSAL ONLY — NOT EXECUTED.
-- Supabase PostgreSQL 17 staging only; client-side verify-full TLS is mandatory.
-- Connect as the verified staging postgres role to database "postgres".
-- This file intentionally contains no passwords, data reads, or DROP commands.
\set ON_ERROR_STOP on

BEGIN;

-- CREATE ROLE fails if any role already exists; stop and audit instead of
-- altering/reusing an existing role graph.
CREATE ROLE vervfy_oauth_staging_user LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE app_runtime LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE google_auth_lookup LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_identity_lookup_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_identity_lookup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_storage_lifecycle_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE vervfy_storage_cleanup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
-- The 0027 migration requires this role to be LOGIN. Do not assign a password,
-- explicit database CONNECT, or deploy a worker for OAuth-only staging.
-- Supabase's PUBLIC CONNECT remains an effective grant for this role.
CREATE ROLE storage_cleanup_worker LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;

-- Preserve Supabase's PUBLIC CONNECT/TEMP and public-schema USAGE defaults.
-- PUBLIC TEMP is an environment capability, not a persistent-object grant.
-- The reviewed Vervfy functions use fixed search paths and qualified objects;
-- disposable tests exercise temp-object shadowing without changing this ACL.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE postgres TO vervfy_oauth_staging_user;
GRANT CONNECT ON DATABASE postgres TO app_runtime, google_auth_lookup;

GRANT USAGE, CREATE ON SCHEMA public TO vervfy_oauth_staging_user;
GRANT USAGE ON SCHEMA public TO app_runtime;

-- PostgreSQL 16+ membership options are deliberate and required by migrations.
GRANT vervfy_identity_lookup_owner TO vervfy_oauth_staging_user
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT vervfy_identity_lookup TO google_auth_lookup
    WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT vervfy_storage_lifecycle_owner TO vervfy_oauth_staging_user
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT vervfy_storage_cleanup TO storage_cleanup_worker
    WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;

COMMIT;

-- As vervfy_oauth_staging_user, before migrations:
-- ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
-- Supabase API-role defaults belong to supabase_admin, not this creator role.
-- Postflight must still verify no Vervfy object ACL reaches anon/authenticated/service_role.

-- Set passwords separately with psql's hidden \password prompt, after approval.
-- Do not set or deploy a storage_cleanup_worker password for OAuth-only staging.
