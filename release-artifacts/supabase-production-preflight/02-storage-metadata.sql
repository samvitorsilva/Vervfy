-- Run only after explicit catalog-output review described in README.md.
-- No storage.objects, application tables, audio bytes, URLs with tokens or paths.
\set ON_ERROR_STOP on
\pset pager off
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '3s';
SELECT pg_catalog.current_setting('server_version_num')::integer BETWEEN 160000 AND 189999
 AND current_database()=:'database_name'
 AND session_user=:'inspection_role' AND current_user=:'inspection_role'
 AND EXISTS (SELECT 1 FROM pg_catalog.pg_stat_ssl WHERE pid=pg_catalog.pg_backend_pid() AND ssl)
 AS connection_gate \gset
\if :connection_gate
\else
\echo 'STOP: identity, database, TLS or version mismatch.'
\quit 3
\endif
SELECT count(*)=1 AND coalesce(bool_and(version_num=:'expected_revision'),false)
 AS revision_gate FROM ONLY public.alembic_version \gset
\if :revision_gate
\else
\echo 'STOP: revision changed since catalog review.'
\quit 3
\endif

-- Read only explicitly granted bucket configuration columns for the approved ID.
-- No raw bucket identifier or allowed_mime_types array is exported.
SELECT count(*)=1 AS exactly_one_visible_bucket,
 coalesce(bool_and(name=:'bucket_name'),false) AS name_matches,
 coalesce(bool_and(NOT public),false) AS bucket_private,
 coalesce(bool_and(file_size_limit IS NULL OR file_size_limit >= :'required_upload_bytes'::bigint),false)
   AS upload_size_compatible,
 coalesce(bool_and(allowed_mime_types IS NULL
   OR :'required_mime_types'::text[] <@ allowed_mime_types),false) AS mime_allowlist_compatible
FROM ONLY storage.buckets WHERE id=:'bucket_id';

SELECT pg_catalog.to_regclass('vervfy_storage.namespaces') IS NOT NULL AS has_namespace_table \gset
\if :has_namespace_table
-- Zero visible rows is UNKNOWN unless the approved, scoped inspector RLS policy
-- is known to provide complete singleton visibility. Never treat hidden rows as absent.
SELECT count(*)=1 AS exactly_one_visible_binding,
 coalesce(bool_and(id=1 AND namespace_id=:'namespace_id'::uuid
  AND environment='production' AND endpoint=:'storage_endpoint'
  AND bucket=:'bucket_id'),false) AS immutable_binding_matches,
 coalesce(bool_and(NOT physical_cleanup_enabled),false) AS physical_cleanup_disabled
FROM ONLY vervfy_storage.namespaces;
\else
\echo 'Namespace table absent: record pending 0027 and separately approved initialization; no write performed.'
\endif
ROLLBACK;
