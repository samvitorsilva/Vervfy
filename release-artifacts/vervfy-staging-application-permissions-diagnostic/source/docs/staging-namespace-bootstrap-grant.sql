-- REVIEW PROPOSAL ONLY — execute after successful 0027 postflight.
-- Connect as vervfy_oauth_staging_user to database postgres.
\set ON_ERROR_STOP on

BEGIN;

DO $grant_check$
BEGIN
    IF current_database() <> 'postgres'
       OR current_user <> 'vervfy_oauth_staging_user'
       OR (SELECT version_num FROM public.alembic_version)
            IS DISTINCT FROM '0027_storage_lifecycle'
       OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_roles
           WHERE rolname='postgres' AND rolbypassrls AND NOT rolsuper
       )
    THEN
        RAISE EXCEPTION 'Namespace bootstrap grant preconditions failed';
    END IF;
END
$grant_check$;

GRANT USAGE ON SCHEMA vervfy_storage TO postgres;
GRANT SELECT, INSERT, MAINTAIN
    ON TABLE vervfy_storage.namespaces TO postgres;
GRANT SELECT ON TABLE public.alembic_version TO postgres;

COMMIT;
