-- APPROVAL A: targeted read-only existence check only. SQL Editor compatible.
-- Select project llxmskxxchpmeavorusj in the dashboard before running.
-- PREPARED ONLY; never executed against production. One metadata-only result.
BEGIN READ ONLY;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '10s';
WITH public_database AS (
 SELECT coalesce(bool_or(a.privilege_type='TEMPORARY'),false) AS public_database_temp,
        coalesce(bool_or(a.privilege_type='CREATE'),false) AS public_database_create
 FROM pg_catalog.pg_database d
 CROSS JOIN LATERAL pg_catalog.aclexplode(coalesce(d.datacl,pg_catalog.acldefault('d',d.datdba))) a
 WHERE d.datname=current_database() AND a.grantee=0
), public_lob AS (
 SELECT count(*) AS public_large_object_write_routines
 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
 CROSS JOIN LATERAL pg_catalog.aclexplode(coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
 WHERE n.nspname='pg_catalog' AND a.grantee=0 AND a.privilege_type='EXECUTE'
  AND p.proname IN ('lo_create','lo_creat','lo_from_bytea','lo_import','lo_put',
                   'lo_unlink','lowrite','lo_truncate','lo_truncate64')
)
SELECT current_database()='postgres' AS expected_database,
 current_setting('server_version_num')::integer=170011 AS expected_pg_17_11,
 EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='vervfy_prod_inspector') AS inspector_exists,
 EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=current_user AND (rolcreaterole OR rolsuper)) AS operator_can_create_roles,
 EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=current_user AND rolcreaterole AND NOT rolsuper) AS automatic_creator_admin_edge_expected,
 public_database_temp,public_database_create,public_large_object_write_routines
FROM public_database CROSS JOIN public_lob;
ROLLBACK;
