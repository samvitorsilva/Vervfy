-- READ-ONLY METADATA PROPOSAL — NOT RUN AGAINST A HOSTED DATABASE.
-- Expected target is 0027_storage_lifecycle. No user rows, object paths,
-- secrets, function definitions, or namespace bindings are selected.
\set ON_ERROR_STOP on
BEGIN READ ONLY;

SELECT current_setting('server_version') AS server_version,
       current_database() AS database_name,
       session_user AS session_role,
       current_user AS effective_role,
       (SELECT ssl
          FROM pg_catalog.pg_stat_ssl
         WHERE pid = pg_catalog.pg_backend_pid()) AS tls_enabled;

SELECT version_num AS alembic_revision,
       version_num = '0027_storage_lifecycle' AS expected_pinned_revision
  FROM public.alembic_version;

WITH expected(schema_name, relation_name) AS (
    VALUES
      ('public', 'tracks'),
      ('public', 'favorites'),
      ('public', 'playlists'),
      ('public', 'playlist_tracks'),
      ('public', 'upload_jobs'),
      ('public', 'artist_photos'),
      ('public', 'track_listens'),
      ('public', 'provider_identities'),
      ('vervfy_storage', 'namespaces'),
      ('vervfy_storage', 'objects'),
      ('vervfy_storage', 'cleanup_jobs')
)
SELECT expected.schema_name,
       expected.relation_name,
       relation.relrowsecurity AS row_security_enabled,
       relation.relforcerowsecurity AS row_security_forced
  FROM expected
  LEFT JOIN pg_catalog.pg_namespace AS namespace
    ON namespace.nspname = expected.schema_name
  LEFT JOIN pg_catalog.pg_class AS relation
    ON relation.relnamespace = namespace.oid
   AND relation.relname = expected.relation_name
 ORDER BY expected.schema_name, expected.relation_name;

SELECT count(*) AS reference_guard_triggers,
       count(*) FILTER (
           WHERE trigger.tgenabled = 'O'
             AND trigger.tgtype = 31
             AND trigger.tgfoid =
                 to_regprocedure('vervfy_storage.guard_references()')
       ) AS enabled_expected_reference_guards
  FROM pg_catalog.pg_trigger AS trigger
  JOIN pg_catalog.pg_class AS relation ON relation.oid = trigger.tgrelid
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
 WHERE namespace.nspname = 'public'
   AND relation.relname IN ('tracks', 'artist_photos', 'upload_jobs')
   AND trigger.tgname = 'storage_reference_guard'
   AND NOT trigger.tgisinternal;

SELECT to_regprocedure('vervfy_storage.claim_cleanup(uuid)') IS NOT NULL
           AS disabled_0027_cleanup_stub_present,
       to_regprocedure('vervfy_storage.claim_next_cleanup()') IS NOT NULL
           AS cleanup_0028_claim_function_present;

ROLLBACK;
