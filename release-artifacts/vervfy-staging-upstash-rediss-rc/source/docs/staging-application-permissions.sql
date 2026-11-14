\set ON_ERROR_STOP on
BEGIN TRANSACTION READ ONLY;

DO $diagnostic_guard$
BEGIN
    IF current_database() <> 'postgres'
       OR session_user <> 'vervfy_oauth_staging_user'
       OR current_user <> 'vervfy_oauth_staging_user'
       OR current_schema() IS DISTINCT FROM 'public'
       OR current_setting('server_version_num')::integer < 170011
       OR current_setting('server_version_num')::integer >= 180000
    THEN
        RAISE EXCEPTION
            'Wrong Supabase staging database, role, schema, or PostgreSQL version';
    END IF;
END
$diagnostic_guard$;

SELECT
    pg_catalog.has_database_privilege(
        current_user, pg_catalog.current_database(), 'CREATE'
    ) AS migration_database_create,
    pg_catalog.has_schema_privilege(
        current_user, 'public', 'USAGE'
    ) AS migration_public_usage,
    pg_catalog.has_schema_privilege(
        current_user, 'public', 'CREATE'
    ) AS migration_public_create,
    app.oid IS NOT NULL AS app_runtime_role_present,
    CASE WHEN app.oid IS NOT NULL THEN pg_catalog.has_database_privilege(
        app.oid, pg_catalog.current_database(), 'CONNECT'
    ) END AS app_runtime_database_connect,
    CASE WHEN app.oid IS NOT NULL THEN pg_catalog.has_database_privilege(
        app.oid, pg_catalog.current_database(), 'CREATE'
    ) END AS app_runtime_database_create,
    CASE WHEN app.oid IS NOT NULL THEN pg_catalog.has_database_privilege(
        app.oid, pg_catalog.current_database(), 'TEMP'
    ) END AS app_runtime_database_temp,
    CASE WHEN app.oid IS NOT NULL THEN pg_catalog.has_schema_privilege(
        app.oid, 'public', 'USAGE'
    ) END AS app_runtime_public_usage,
    CASE WHEN app.oid IS NOT NULL THEN pg_catalog.has_schema_privilege(
        app.oid, 'public', 'CREATE'
    ) END AS app_runtime_public_create,
    lookup.oid IS NOT NULL AS google_auth_lookup_role_present,
    CASE WHEN lookup.oid IS NOT NULL THEN pg_catalog.has_database_privilege(
        lookup.oid, pg_catalog.current_database(), 'CONNECT'
    ) END AS google_auth_lookup_database_connect,
    CASE WHEN lookup.oid IS NOT NULL THEN pg_catalog.has_database_privilege(
        lookup.oid, pg_catalog.current_database(), 'CREATE'
    ) END AS google_auth_lookup_database_create,
    CASE WHEN lookup.oid IS NOT NULL THEN pg_catalog.has_database_privilege(
        lookup.oid, pg_catalog.current_database(), 'TEMP'
    ) END AS google_auth_lookup_database_temp,
    CASE WHEN lookup.oid IS NOT NULL THEN pg_catalog.has_schema_privilege(
        lookup.oid, 'public', 'USAGE'
    ) END AS google_auth_lookup_public_usage,
    CASE WHEN lookup.oid IS NOT NULL THEN pg_catalog.has_schema_privilege(
        lookup.oid, 'public', 'CREATE'
    ) END AS google_auth_lookup_public_create
FROM (SELECT 1) AS singleton
LEFT JOIN pg_catalog.pg_roles AS app
    ON app.rolname = 'app_runtime'
LEFT JOIN pg_catalog.pg_roles AS lookup
    ON lookup.rolname = 'google_auth_lookup';

ROLLBACK;
