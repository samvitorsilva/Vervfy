-- REVIEW PROPOSAL ONLY — execute after the approved namespace initializer.
-- Connect as vervfy_oauth_staging_user to database postgres.
\set ON_ERROR_STOP on

BEGIN;

DO $revoke_check$
BEGIN
    IF current_database() <> 'postgres' THEN
        RAISE EXCEPTION 'Namespace revoke requires database postgres';
    END IF;
    IF current_user <> 'vervfy_oauth_staging_user' THEN
        RAISE EXCEPTION 'Namespace revoke requires the migration role';
    END IF;
    IF (SELECT version_num FROM public.alembic_version)
         IS DISTINCT FROM '0027_storage_lifecycle' THEN
        RAISE EXCEPTION 'Namespace revoke requires revision 0027';
    END IF;
END
$revoke_check$;

REVOKE SELECT, INSERT, MAINTAIN
    ON TABLE vervfy_storage.namespaces FROM postgres;
REVOKE USAGE ON SCHEMA vervfy_storage FROM postgres;
REVOKE SELECT ON TABLE public.alembic_version FROM postgres;

COMMIT;
