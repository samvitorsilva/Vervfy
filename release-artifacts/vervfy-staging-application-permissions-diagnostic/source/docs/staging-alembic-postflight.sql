\set ON_ERROR_STOP on
BEGIN READ ONLY;
DO $postflight$
BEGIN
 IF current_database()<>'postgres'
 OR session_user<>'vervfy_oauth_staging_user'
 OR current_user<>'vervfy_oauth_staging_user'
 OR current_setting('server_version_num')::integer < 170011
 OR current_setting('server_version_num')::integer >= 180000
 THEN RAISE EXCEPTION 'Wrong Supabase staging identity or PostgreSQL version'; END IF;
 IF (SELECT version_num FROM public.alembic_version)
 IS DISTINCT FROM '0027_storage_lifecycle'
 THEN RAISE EXCEPTION 'Unexpected Alembic revision'; END IF;

 IF EXISTS (
   SELECT 1
   FROM pg_class c
   JOIN pg_namespace n ON n.oid=c.relnamespace
   CROSS JOIN pg_roles r
   WHERE r.rolname IN ('anon','authenticated','service_role')
     AND (
       n.nspname IN ('vervfy_auth','vervfy_storage')
       OR c.relowner='vervfy_oauth_staging_user'::regrole
     )
     AND c.relkind IN ('r','p','v','m','f')
     AND (
       has_table_privilege(r.oid,c.oid,'SELECT')
       OR has_table_privilege(r.oid,c.oid,'INSERT')
       OR has_table_privilege(r.oid,c.oid,'UPDATE')
       OR has_table_privilege(r.oid,c.oid,'DELETE')
       OR has_table_privilege(r.oid,c.oid,'TRUNCATE')
       OR has_table_privilege(r.oid,c.oid,'REFERENCES')
       OR has_table_privilege(r.oid,c.oid,'TRIGGER')
     )
 ) OR EXISTS (
   SELECT 1
   FROM pg_class c
   JOIN pg_namespace n ON n.oid=c.relnamespace
   CROSS JOIN pg_roles r
   WHERE r.rolname IN ('anon','authenticated','service_role')
     AND (
       n.nspname IN ('vervfy_auth','vervfy_storage')
       OR c.relowner='vervfy_oauth_staging_user'::regrole
     )
     AND c.relkind='S'
     AND (
       has_sequence_privilege(r.oid,c.oid,'USAGE')
       OR has_sequence_privilege(r.oid,c.oid,'SELECT')
       OR has_sequence_privilege(r.oid,c.oid,'UPDATE')
     )
 ) OR EXISTS (
   SELECT 1
   FROM pg_proc p
   JOIN pg_namespace n ON n.oid=p.pronamespace
   CROSS JOIN pg_roles r
   WHERE r.rolname IN ('anon','authenticated','service_role')
     AND (
       n.nspname IN ('vervfy_auth','vervfy_storage')
       OR p.proowner='vervfy_oauth_staging_user'::regrole
     )
     AND has_function_privilege(r.oid,p.oid,'EXECUTE')
 ) OR EXISTS (
   SELECT 1
   FROM pg_namespace n
   CROSS JOIN pg_roles r
   WHERE n.nspname IN ('vervfy_auth','vervfy_storage')
     AND r.rolname IN ('anon','authenticated','service_role')
     AND (
       has_schema_privilege(r.oid,n.oid,'USAGE')
       OR has_schema_privilege(r.oid,n.oid,'CREATE')
     )
 ) THEN
   RAISE EXCEPTION 'Supabase API role can access a Vervfy namespace or object';
 END IF;

 IF EXISTS (
   SELECT 1
   FROM pg_class c
   JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE (
       (n.nspname='public' AND c.relname IN (
         'tracks','favorites','playlists','playlist_tracks','upload_jobs',
         'artist_photos','track_listens','provider_identities'
       ))
       OR n.nspname='vervfy_storage'
     )
     AND c.relkind IN ('r','p')
     AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
 ) THEN
   RAISE EXCEPTION 'A tenant-scoped Vervfy table does not enforce forced RLS';
 END IF;

 IF EXISTS (
   SELECT 1
   FROM pg_default_acl d
   CROSS JOIN LATERAL aclexplode(d.defaclacl) a
   WHERE d.defaclrole IN (
     'vervfy_oauth_staging_user'::regrole,
     'vervfy_identity_lookup_owner'::regrole,
     'vervfy_storage_lifecycle_owner'::regrole,
     'vervfy_storage_cleanup'::regrole
   )
   AND a.grantee IN (0,'anon'::regrole,'authenticated'::regrole,'service_role'::regrole)
 ) THEN
   RAISE EXCEPTION 'A Vervfy creator has unsafe API/PUBLIC default privileges';
 END IF;

 IF has_schema_privilege('postgres','vervfy_storage','USAGE')
    OR has_table_privilege('postgres','vervfy_storage.namespaces','SELECT')
    OR has_table_privilege('postgres','vervfy_storage.namespaces','INSERT')
    OR has_table_privilege('postgres','vervfy_storage.namespaces','MAINTAIN')
    OR has_table_privilege('postgres','public.alembic_version','SELECT')
 THEN
   RAISE EXCEPTION 'Temporary namespace bootstrap privileges remain granted';
 END IF;
END
$postflight$;
SELECT version_num FROM public.alembic_version;
SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner) AS owner,
 c.relrowsecurity,c.relforcerowsecurity,c.relacl
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname IN ('public','vervfy_auth','vervfy_storage') AND c.relkind IN ('r','p')
ORDER BY 1,2;
SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check
FROM pg_policies WHERE schemaname IN ('public','vervfy_auth','vervfy_storage') ORDER BY 2,3;
SELECT p.oid::regprocedure,pg_get_userbyid(p.proowner) AS owner,
 p.prosecdef,p.proisstrict,p.provolatile,p.proconfig,p.proacl,
 pg_get_functiondef(p.oid) AS definition
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='vervfy_auth';
SELECT r.rolname,
 has_schema_privilege(r.oid,'vervfy_auth','USAGE') AS schema_usage,
 has_schema_privilege(r.oid,'vervfy_auth','CREATE') AS schema_create,
 has_function_privilege(r.oid,'vervfy_auth.lookup_provider_identity(text,text)','EXECUTE') AS execute_lookup,
 has_table_privilege(r.oid,'public.provider_identities','SELECT') AS table_select,
 has_table_privilege(r.oid,'public.provider_identities','INSERT') AS table_insert,
 has_table_privilege(r.oid,'public.provider_identities','UPDATE') AS table_update,
 has_table_privilege(r.oid,'public.provider_identities','DELETE') AS table_delete,
 has_table_privilege(r.oid,'public.provider_identities','TRUNCATE') AS table_truncate
FROM pg_roles r WHERE rolname IN ('app_runtime','google_auth_lookup',
 'vervfy_identity_lookup_owner','vervfy_identity_lookup');
SELECT r.rolname,a.attname,
 has_column_privilege(r.oid,a.attrelid,a.attnum,'SELECT') AS col_select,
 has_column_privilege(r.oid,a.attrelid,a.attnum,'INSERT') AS col_insert,
 has_column_privilege(r.oid,a.attrelid,a.attnum,'UPDATE') AS col_update,a.attacl
FROM pg_attribute a CROSS JOIN pg_roles r
WHERE a.attrelid='public.provider_identities'::regclass AND a.attnum>0 AND NOT a.attisdropped
AND r.rolname IN ('app_runtime','google_auth_lookup','vervfy_identity_lookup_owner','vervfy_identity_lookup')
ORDER BY 1,2;
SELECT c.relname,
 has_table_privilege('app_runtime',c.oid,'SELECT') AS sel,
 has_table_privilege('app_runtime',c.oid,'INSERT') AS ins,
 has_table_privilege('app_runtime',c.oid,'UPDATE') AS upd,
 has_table_privilege('app_runtime',c.oid,'DELETE') AS del
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind='r' ORDER BY 1;
SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns
WHERE table_schema='public' AND ((table_name='users' AND column_name='password_hash')
 OR (table_name='tracks' AND column_name IN ('cover_url','cover_source'))
 OR (table_name='upload_jobs' AND column_name='cover_data'));
SELECT conrelid::regclass,conname,pg_get_constraintdef(oid)
FROM pg_constraint WHERE conrelid IN ('public.provider_identities'::regclass,'public.tracks'::regclass);
SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl
FROM pg_namespace WHERE nspname IN ('public','vervfy_auth','vervfy_storage');
-- Fresh chain has no sequences. Any adopted owned sequences allow USAGE only.
SELECT n.nspname,c.relname,
 has_sequence_privilege('app_runtime',c.oid,'USAGE') AS usage,
 has_sequence_privilege('app_runtime',c.oid,'SELECT') AS sel,
 has_sequence_privilege('app_runtime',c.oid,'UPDATE') AS upd
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='S' AND n.nspname NOT LIKE 'pg_%';
-- Phase 2 gates: report only; operator review is required, not exit-status signoff.
SELECT n.nspname,c.relname,c.relrowsecurity,c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='vervfy_storage' AND c.relkind='r';
SELECT p.proname,p.prosecdef,p.provolatile,p.proconfig,pg_get_userbyid(p.proowner) AS owner,p.proacl
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='vervfy_storage';
SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolinherit,rolcreatedb,rolcreaterole,rolreplication
FROM pg_roles WHERE rolname IN ('vervfy_storage_lifecycle_owner','vervfy_storage_cleanup','storage_cleanup_worker');
-- Targeted 0027 correction: review cross-schema ownership, executable routines
-- and default ACLs. These are reports, not authorization to run hosted checks.
SELECT n.nspname,p.oid::regprocedure,pg_get_userbyid(p.proowner) AS owner,
 p.prosecdef,p.proacl
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema';
SELECT defaclrole::regrole AS creator,n.nspname,defaclobjtype,defaclacl
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace;
SELECT r.rolname,n.nspname,p.oid::regprocedure,
 has_schema_privilege(r.oid,n.oid,'USAGE') AS schema_usage,
 has_function_privilege(r.oid,p.oid,'EXECUTE') AS executable
FROM pg_roles r CROSS JOIN pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE r.rolname IN ('vervfy_storage_lifecycle_owner','vervfy_storage_cleanup',
 'storage_cleanup_worker','app_runtime','google_auth_lookup')
 AND n.nspname !~ '^pg_' AND n.nspname<>'information_schema';
ROLLBACK;
