\set ON_ERROR_STOP on
BEGIN READ ONLY;
DO $$ BEGIN
 IF current_database()<>'postgres'
 OR session_user<>'vervfy_oauth_staging_user'
 OR current_user<>'vervfy_oauth_staging_user'
 OR current_setting('server_version_num')::integer / 10000 <> 17
 OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
 THEN RAISE EXCEPTION 'Wrong staging identity/TLS'; END IF;
 IF (SELECT version_num FROM public.alembic_version)
 IS DISTINCT FROM '0028_webauthn_enrollment'
 THEN RAISE EXCEPTION 'Unexpected Alembic revision'; END IF;
END $$;
SELECT version_num FROM public.alembic_version;
SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner) AS owner,
 c.relrowsecurity,c.relforcerowsecurity,c.relacl
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname IN ('public','vervfy_auth') AND c.relkind IN ('r','p')
ORDER BY 1,2;
SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check
FROM pg_policies WHERE schemaname IN ('public','vervfy_auth') ORDER BY 2,3;
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
FROM pg_namespace WHERE nspname IN ('public','vervfy_auth');
-- Fresh chain has no sequences. Any adopted owned sequences allow USAGE only.
SELECT n.nspname,c.relname,
 has_sequence_privilege('app_runtime',c.oid,'USAGE') AS usage,
 has_sequence_privilege('app_runtime',c.oid,'SELECT') AS sel,
 has_sequence_privilege('app_runtime',c.oid,'UPDATE') AS upd
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='S' AND n.nspname NOT LIKE 'pg_%';
ROLLBACK;
