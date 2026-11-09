-- REVIEW PROPOSAL ONLY — NOT EXECUTED.
-- Fresh, independently verified disposable staging database only.
-- Run only after separate initialization approval and metadata preflight.
-- Connect as the provider bootstrap administrator to the verified database.
-- Pass the confirmed PostgreSQL database name as psql variable staging_db.
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
-- database CONNECT, or deploy a worker for OAuth-only staging.
CREATE ROLE storage_cleanup_worker LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;

-- Remove inherited PUBLIC CONNECT/TEMP and public-schema CREATE in this fresh,
-- disposable database; then grant only the reviewed connections/capabilities.
REVOKE ALL ON DATABASE :"staging_db" FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE :"staging_db" TO vervfy_oauth_staging_user;
GRANT CONNECT ON DATABASE :"staging_db" TO app_runtime, google_auth_lookup;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
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

-- Set passwords separately with psql's hidden \password prompt, after approval.
-- Do not set or deploy a storage_cleanup_worker password for OAuth-only staging.
