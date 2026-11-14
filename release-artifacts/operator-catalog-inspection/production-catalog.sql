-- One-time authorized project-owner inspection, Supabase SQL Editor only.
-- Project llxmskxxchpmeavorusj; reported baseline dd22f18b92e26a59d342a98e06dfc2888c58905b.
-- Review artifact only. No SQL execution was used during preparation.
-- Run the ENTIRE script. Missing/incompatible metadata aborts; never repair here.
BEGIN READ ONLY;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '3s';
SET LOCAL idle_in_transaction_session_timeout = '60s';
-- Anonymous guard reads catalogs only. No persistent function or object is created.
DO $guard$
BEGIN
 IF current_database()<>'postgres' OR current_user<>'postgres'
    OR current_setting('server_version_num')::integer<>170011 THEN
  RAISE EXCEPTION 'STOP: unexpected database, operator role or PostgreSQL version';
 END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
  WHERE n.nspname='public' AND c.relname='alembic_version'
    AND c.relkind='r' AND NOT c.relrowsecurity AND NOT c.relforcerowsecurity
    AND a.attname='version_num' AND a.attnum>0 AND NOT a.attisdropped
    AND a.atttypid IN ('pg_catalog.text'::regtype,'pg_catalog.varchar'::regtype)
 ) THEN
  RAISE EXCEPTION 'STOP: revision metadata absent or incompatible; no inspection performed';
 END IF;
END
$guard$;

-- One JSON result collects every section for the SQL Editor. No user rows.
-- The revision-table owner is OBSERVED, not an approved migration identity.
WITH
section_0 AS (
SELECT current_database()='postgres' AS database_matches, current_user='postgres' AS operator_matches, current_setting('server_version_num')::integer AS server_version_num, current_setting('transaction_read_only')='on' AS read_only, 'llxmskxxchpmeavorusj'::text AS intended_project_ref, '0027_storage_lifecycle'::text AS release_target, 'operator must verify dashboard project identity'::text AS project_identity_requirement
),
section_1 AS (
SELECT count(*) AS revision_row_count, coalesce(bool_and(version_num IN ('0001_postgres_persistence','0002_profile_photo','0003_track_size','0004_session_version','0005_storage_path','0006_tenant_integrity','0007_row_level_security','0008_upload_jobs','0009_upload_retry_count','0010_verified_account_email','0011_playlist_position','0012_artist_image_cache','0013_artist_catalog','0014_user_covers','0015_artist_photos','0016_audiodb_artist_images','0017_track_covers','0018_cover_checked_at','0019_track_listens','0020_playlist_last_played','0021_provider_identities','0022_provider_identity_lookup','0023_missing_media_columns','0024_provider_identity_access','0025_track_cover_sources','0026_application_runtime_grants','0027_storage_lifecycle')),false) AS recognized_at_or_before_0027, jsonb_agg(CASE WHEN version_num IN ('0001_postgres_persistence','0002_profile_photo','0003_track_size','0004_session_version','0005_storage_path','0006_tenant_integrity','0007_row_level_security','0008_upload_jobs','0009_upload_retry_count','0010_verified_account_email','0011_playlist_position','0012_artist_image_cache','0013_artist_catalog','0014_user_covers','0015_artist_photos','0016_audiodb_artist_images','0017_track_covers','0018_cover_checked_at','0019_track_listens','0020_playlist_last_played','0021_provider_identities','0022_provider_identity_lookup','0023_missing_media_columns','0024_provider_identity_access','0025_track_cover_sources','0026_application_runtime_grants','0027_storage_lifecycle','0028_storage_cleanup_leases') THEN version_num ELSE '<unrecognized-revision>' END) AS revisions FROM ONLY public.alembic_version
),
section_2 AS (
WITH expected(name) AS (VALUES
 ((SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass)),  ('app_runtime'), ('google_auth_lookup'),
 ('vervfy_identity_lookup_owner'), ('vervfy_identity_lookup'),
 ('vervfy_storage_lifecycle_owner'), ('vervfy_storage_cleanup'), ('storage_cleanup_worker'))
SELECT CASE WHEN e.name IN ('app_runtime','google_auth_lookup','vervfy_identity_lookup_owner','vervfy_identity_lookup','vervfy_storage_lifecycle_owner','vervfy_storage_cleanup','storage_cleanup_worker','postgres') THEN e.name ELSE '<revision-table-owner>' END AS expected_role, r.oid AS role_oid, r.oid IS NOT NULL AS present,
 r.rolcanlogin, r.rolinherit, r.rolsuper, r.rolbypassrls, r.rolcreatedb,
 r.rolcreaterole, r.rolreplication,
 pg_catalog.has_database_privilege(r.oid, current_database(), 'CONNECT') AS db_connect,
 pg_catalog.has_database_privilege(r.oid, current_database(), 'CREATE') AS db_create,
 pg_catalog.has_database_privilege(r.oid, current_database(), 'TEMP') AS db_temp,
 pg_catalog.has_schema_privilege(r.oid, 'public', 'USAGE') AS public_usage,
 pg_catalog.has_schema_privilege(r.oid, 'public', 'CREATE') AS public_create
FROM expected e LEFT JOIN pg_catalog.pg_roles r ON r.rolname = e.name ORDER BY e.name
),
section_3 AS (
WITH targets(name) AS (VALUES ((SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass)), 
 ('app_runtime'), ('google_auth_lookup'), ('vervfy_identity_lookup_owner'),
 ('vervfy_identity_lookup'), ('vervfy_storage_lifecycle_owner'),
 ('vervfy_storage_cleanup'), ('storage_cleanup_worker'))
SELECT CASE WHEN granted.rolname IN (SELECT name FROM targets)
 THEN granted.rolname ELSE '<other-role>' END AS capability,
 CASE WHEN member.rolname IN (SELECT name FROM targets)
      THEN member.rolname ELSE '<other-role>' END AS member_class,
 m.inherit_option, m.set_option, m.admin_option, count(*) AS edges
FROM pg_catalog.pg_auth_members m
JOIN pg_catalog.pg_roles granted ON granted.oid = m.roleid
JOIN pg_catalog.pg_roles member ON member.oid = m.member
WHERE granted.rolname IN (SELECT name FROM targets)
 OR member.rolname IN (SELECT name FROM targets)
GROUP BY 1,2,3,4,5 ORDER BY 1,2
),
section_4 AS (
WITH caps(name,allowed_member) AS (VALUES
 ('vervfy_identity_lookup_owner', (SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass)),
 ('vervfy_identity_lookup', 'google_auth_lookup'),
 ('vervfy_storage_lifecycle_owner', (SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass)),
 ('vervfy_storage_cleanup', 'storage_cleanup_worker'))
SELECT caps.name, cap.oid IS NOT NULL AS present,
 count(r.oid) FILTER (WHERE NOT r.rolsuper
   AND r.rolname NOT IN (caps.name, caps.allowed_member)
   AND (pg_catalog.pg_has_role(r.oid,cap.oid,'USAGE')
        OR pg_catalog.pg_has_role(r.oid,cap.oid,'SET'))) AS unexpected_effective_holders,
 count(r.oid) FILTER (WHERE r.rolsuper AND r.oid <> cap.oid) AS superuser_holders
FROM caps LEFT JOIN pg_catalog.pg_roles cap ON cap.rolname=caps.name
LEFT JOIN pg_catalog.pg_roles r ON true GROUP BY caps.name,cap.oid ORDER BY caps.name
),
section_5 AS (
WITH subjects(name) AS (VALUES ((SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass)), 
 ('app_runtime'), ('google_auth_lookup'), ('vervfy_identity_lookup_owner'),
 ('vervfy_identity_lookup'), ('vervfy_storage_lifecycle_owner'),
 ('vervfy_storage_cleanup'), ('storage_cleanup_worker'))
SELECT CASE WHEN s.name IN ('app_runtime','google_auth_lookup','vervfy_identity_lookup_owner','vervfy_identity_lookup','vervfy_storage_lifecycle_owner','vervfy_storage_cleanup','storage_cleanup_worker','postgres') THEN s.name ELSE '<revision-table-owner>' END AS role_name, n.nspname AS schema_name,
 n.nspowner = r.oid AS owns_schema,
 pg_catalog.has_schema_privilege(r.oid,n.oid,'USAGE') AS usage,
 pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE') AS create_privilege
FROM subjects s LEFT JOIN pg_catalog.pg_roles r ON r.rolname=s.name
CROSS JOIN pg_catalog.pg_namespace n
WHERE n.nspname IN ('public','vervfy_auth','vervfy_storage','storage') ORDER BY 1,2
),
section_6 AS (
WITH expected(schema_name,table_name) AS (VALUES
 ('public','alembic_version'),('public','users'),('public','tracks'),
 ('public','favorites'),('public','playlists'),('public','playlist_tracks'),
 ('public','upload_jobs'),('public','artist_photos'),('public','track_listens'),
 ('public','provider_identities'),('public','artist_images'),('public','track_cover_cache'),
 ('storage','buckets'),('storage','objects'),('vervfy_storage','namespaces'),
 ('vervfy_storage','objects'),('vervfy_storage','cleanup_jobs'))
SELECT e.schema_name,e.table_name,c.oid IS NOT NULL AS present,c.relkind,
 CASE WHEN owner_role.rolname = (SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass) THEN '<revision-table-owner>'
      WHEN owner_role.rolname IN ('supabase_storage_admin','supabase_admin','postgres')
      THEN owner_role.rolname ELSE '<other-owner>' END AS owner_class,
 c.relowner AS owner_oid,c.relrowsecurity,c.relforcerowsecurity,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'SELECT') AS runtime_select,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'INSERT') AS runtime_insert,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'UPDATE') AS runtime_update,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'DELETE') AS runtime_delete,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'TRUNCATE,REFERENCES,TRIGGER') AS runtime_extra,
 pg_catalog.has_any_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'INSERT,UPDATE,REFERENCES') AS runtime_any_column_write
FROM expected e LEFT JOIN pg_catalog.pg_namespace n ON n.nspname=e.schema_name
LEFT JOIN pg_catalog.pg_class c ON c.relnamespace=n.oid AND c.relname=e.table_name
LEFT JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=c.relowner ORDER BY 1,2
),
section_7 AS (
SELECT c.relname AS table_name,a.attname AS column_name,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'SELECT') AS runtime_select,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'INSERT') AS runtime_insert,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'UPDATE') AS runtime_update,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'REFERENCES') AS runtime_references
FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('users','tracks','favorites','playlists',
 'playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities',
 'artist_images','track_cover_cache') AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2
),
section_8 AS (
SELECT tbl.relname AS owned_by_table,count(*) AS sequence_count,
 bool_and(pg_catalog.has_sequence_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),seq.oid,'USAGE')) AS runtime_usage,
 bool_or(pg_catalog.has_sequence_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),seq.oid,'SELECT,UPDATE')) AS runtime_extra
FROM pg_catalog.pg_class seq JOIN pg_catalog.pg_depend d ON d.objid=seq.oid
 AND d.classid='pg_catalog.pg_class'::regclass AND d.refclassid='pg_catalog.pg_class'::regclass
 AND d.deptype IN ('a','i')
JOIN pg_catalog.pg_class tbl ON tbl.oid=d.refobjid
JOIN pg_catalog.pg_namespace n ON n.oid=tbl.relnamespace
WHERE seq.relkind='S' AND n.nspname='public' AND tbl.relname IN ('users','tracks',
 'favorites','playlists','playlist_tracks','upload_jobs','artist_photos','track_listens',
 'artist_images','track_cover_cache') GROUP BY tbl.relname ORDER BY 1
),
section_9 AS (
SELECT c.relname AS table_name,k.contype,k.convalidated,
 pg_catalog.md5(pg_catalog.pg_get_constraintdef(k.oid)) AS definition_fingerprint
FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('tracks','favorites','playlists',
 'playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities') ORDER BY 1,2,4
),
section_10 AS (
SELECT n.nspname,c.relname,p.polcmd,p.polpermissive,
 pg_catalog.md5(p.polname) AS policy_name_fingerprint,
 pg_catalog.md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid)) AS using_fingerprint,
 pg_catalog.md5(pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)) AS check_fingerprint,
 coalesce(0 = ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles
          WHERE rolname='app_runtime') = ANY(p.polroles),false) AS applies_to_runtime,
 EXISTS (SELECT 1 FROM pg_catalog.pg_depend d JOIN pg_catalog.pg_proc f ON f.oid=d.refobjid
   JOIN pg_catalog.pg_namespace fn ON fn.oid=f.pronamespace
   WHERE d.classid='pg_catalog.pg_policy'::regclass AND d.objid=p.oid
     AND d.refclassid='pg_catalog.pg_proc'::regclass AND fn.nspname<>'pg_catalog') AS uses_custom_function,
 p.polroles AS policy_role_oids
FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE (n.nspname='public' AND c.relname IN ('tracks','favorites','playlists',
 'playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities'))
 OR (n.nspname='vervfy_storage' AND c.relname IN ('namespaces','objects','cleanup_jobs'))
 OR (n.nspname='storage' AND c.relname IN ('buckets','objects')) ORDER BY 1,2,5
),
section_11 AS (
SELECT n.nspname,p.proname,p.proowner AS owner_oid,p.pronargs,p.prosecdef,p.provolatile,
 CASE WHEN owner_role.rolname IN ('vervfy_identity_lookup_owner','vervfy_storage_lifecycle_owner')
      THEN owner_role.rolname ELSE '<other-owner>' END AS owner_class,
 coalesce(p.proconfig @> ARRAY['search_path=pg_catalog, pg_temp'],false) AS pinned_search_path,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(coalesce(p.proacl,
     pg_catalog.acldefault('f',p.proowner))) a WHERE a.grantee=0
     AND a.privilege_type='EXECUTE') AS public_execute,
 pg_catalog.has_function_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),p.oid,'EXECUTE') AS runtime_execute,
 pg_catalog.has_function_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='google_auth_lookup'),p.oid,'EXECUTE') AS lookup_execute
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=p.proowner
WHERE n.nspname IN ('vervfy_auth','vervfy_storage') ORDER BY 1,2,3
),
section_12 AS (
SELECT count(*) FILTER (WHERE p.proname IN ('claim_next_cleanup','complete_cleanup','retry_cleanup'))
       AS forbidden_0028_routines
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='vervfy_storage'
),
section_13 AS (
SELECT c.relname,t.tgenabled,t.tgtype,
 t.tgfoid = pg_catalog.to_regprocedure('vervfy_storage.guard_references()') AS correct_guard_function
FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('tracks','artist_photos','upload_jobs')
 AND t.tgname='storage_reference_guard' AND NOT t.tgisinternal ORDER BY 1
),
section_14 AS (
SELECT CASE WHEN owner_role.rolname=(SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass) THEN '<revision-table-owner>' ELSE '<other-role>' END AS owner_class,
 coalesce(n.nspname IN ('public','vervfy_auth','vervfy_storage'),false) AS application_schema,
 d.defaclnamespace=0 AS global_default,d.defaclobjtype,a.privilege_type,a.is_grantable,
 CASE WHEN a.grantee=0 THEN 'PUBLIC'
      WHEN grantee.rolname IN ('app_runtime','google_auth_lookup','vervfy_identity_lookup_owner',
       'vervfy_identity_lookup','vervfy_storage_lifecycle_owner','vervfy_storage_cleanup','storage_cleanup_worker')
      THEN grantee.rolname ELSE '<other-role>' END AS grantee_class,count(*) AS entries
FROM pg_catalog.pg_default_acl d JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=d.defaclrole
LEFT JOIN pg_catalog.pg_namespace n ON n.oid=d.defaclnamespace
CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=a.grantee
GROUP BY 1,2,3,4,5,6,7 ORDER BY 1,2,3,4,7
),
section_15 AS (
WITH subjects(name) AS (VALUES ((SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.alembic_version'::regclass)),('google_auth_lookup'),
 ('vervfy_identity_lookup_owner'),('vervfy_identity_lookup'),
 ('vervfy_storage_lifecycle_owner'),('vervfy_storage_cleanup'),('storage_cleanup_worker'))
SELECT CASE WHEN s.name IN ('app_runtime','google_auth_lookup','vervfy_identity_lookup_owner','vervfy_identity_lookup','vervfy_storage_lifecycle_owner','vervfy_storage_cleanup','storage_cleanup_worker','postgres') THEN s.name ELSE '<revision-table-owner>' END AS role_name,n.nspname,c.relname,c.relowner=r.oid AS owns_relation,
 pg_catalog.has_table_privilege(r.oid,c.oid,'SELECT') AS table_select,
 pg_catalog.has_any_column_privilege(r.oid,c.oid,'SELECT') AS any_column_select,
 pg_catalog.has_table_privilege(r.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 OR pg_catalog.has_any_column_privilege(r.oid,c.oid,'INSERT,UPDATE,REFERENCES') AS any_write
FROM subjects s LEFT JOIN pg_catalog.pg_roles r ON r.rolname=s.name
CROSS JOIN pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE (n.nspname='public' AND c.relname IN ('alembic_version','users','tracks','favorites',
 'playlists','playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities',
 'artist_images','track_cover_cache')) OR n.nspname IN ('vervfy_auth','vervfy_storage')
ORDER BY 1,2,3
),
section_16 AS (
WITH caps(name) AS (VALUES ('vervfy_storage_lifecycle_owner'),
 ('vervfy_storage_cleanup'),('storage_cleanup_worker'))
SELECT caps.name,r.oid IS NOT NULL AS present,
 (SELECT count(*) FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
  AND (c.relowner=r.oid OR CASE WHEN c.relkind='S' THEN
       pg_catalog.has_sequence_privilege(r.oid,c.oid,'USAGE,SELECT,UPDATE')
       WHEN c.relkind IN ('r','p','v','m','f') THEN
       pg_catalog.has_table_privilege(r.oid,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
       OR pg_catalog.has_any_column_privilege(r.oid,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')
       ELSE false END)) AS accessible_or_owned_relations,
 (SELECT count(*) FROM pg_catalog.pg_namespace n WHERE n.nspowner=r.oid OR
   (n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
    AND pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE'))) AS owned_or_creatable_schemas,
 (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
   AND (p.proowner=r.oid OR (pg_catalog.has_schema_privilege(r.oid,n.oid,'USAGE')
    AND pg_catalog.has_function_privilege(r.oid,p.oid,'EXECUTE')))) AS accessible_or_owned_routines,
 (SELECT count(*) FROM pg_catalog.pg_default_acl d
  CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
  WHERE d.defaclrole=r.oid OR a.grantee=0 OR a.grantee=r.oid OR
   (a.grantee<>0 AND (pg_catalog.pg_has_role(r.oid,a.grantee,'USAGE')
    OR pg_catalog.pg_has_role(r.oid,a.grantee,'SET')))) AS incompatible_default_acl_entries
FROM caps LEFT JOIN pg_catalog.pg_roles r ON r.rolname=caps.name ORDER BY caps.name
),
section_17 AS (
SELECT a.privilege_type,a.is_grantable FROM pg_catalog.pg_database d
CROSS JOIN LATERAL pg_catalog.aclexplode(coalesce(d.datacl,
 pg_catalog.acldefault('d',d.datdba))) a
WHERE d.datname=current_database() AND a.grantee=0 ORDER BY 1
),
section_18 AS (
SELECT n.nspname,a.privilege_type,a.is_grantable FROM pg_catalog.pg_namespace n
CROSS JOIN LATERAL pg_catalog.aclexplode(coalesce(n.nspacl,
 pg_catalog.acldefault('n',n.nspowner))) a
WHERE n.nspname IN ('public','storage','vervfy_auth','vervfy_storage') AND a.grantee=0 ORDER BY 1,2
),
section_19 AS (
SELECT e.table_name,e.column_name,a.attnum IS NOT NULL AS present
FROM (VALUES ('tracks','storage_path'),('tracks','cover_path'),('tracks','cover_source'),
 ('artist_photos','storage_path'),('upload_jobs','storage_path'),('users','password_hash'))
 e(table_name,column_name)
LEFT JOIN pg_catalog.pg_class c ON c.relname=e.table_name
 AND c.relnamespace=pg_catalog.to_regnamespace('public')
LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid AND a.attname=e.column_name
 AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2
)
SELECT jsonb_build_object(
'context', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_0 t),
'revision', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_1 t),
'roles', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_2 t),
'memberships', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_3 t),
'effective_capability_holders', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_4 t),
'schema_privileges', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_5 t),
'relations_and_runtime_grants', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_6 t),
'column_grants', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_7 t),
'sequence_grants', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_8 t),
'constraints', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_9 t),
'rls_policies', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_10 t),
'routines', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_11 t),
'forbidden_0028_routines', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_12 t),
'reference_guards', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_13 t),
'default_acls', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_14 t),
'capability_relation_privileges', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_15 t),
'fresh_0027_capability_prerequisites', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_16 t),
'public_database_grants', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_17 t),
'public_schema_grants', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_18 t),
'required_columns', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM section_19 t)
) AS catalog_report;
ROLLBACK;
