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

-- Catalog-only delta. No application rows, expression text, function bodies or credentials.
WITH
acl_provenance AS (
SELECT n.nspname, c.relname, c.relowner AS owner_oid,
 pg_get_userbyid(c.relowner) AS owner_name, x.column_name,
 a.grantor, pg_get_userbyid(a.grantor) AS grantor_name,
 a.grantee, CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee_name,
 a.privilege_type, a.is_grantable,
 CASE WHEN a.grantee=0 THEN true ELSE pg_has_role('app_runtime',a.grantee,'USAGE') END AS runtime_inherits,
 CASE WHEN a.grantee=0 THEN false ELSE pg_has_role('app_runtime',a.grantee,'SET') END AS runtime_can_set
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
CROSS JOIN LATERAL (
 SELECT NULL::name AS column_name, coalesce(c.relacl,acldefault('r',c.relowner)) AS acl
 UNION ALL SELECT attname, attacl FROM pg_attribute
 WHERE attrelid=c.oid AND attnum>0 AND NOT attisdropped AND attacl IS NOT NULL
) x CROSS JOIN LATERAL aclexplode(x.acl) a
WHERE n.nspname='public' AND c.relname IN ('alembic_version','artist_images','track_cover_cache')
),
default_acl_provenance AS (
SELECT pg_get_userbyid(d.defaclrole) AS creator, coalesce(n.nspname,'<global>') AS schema_name,
 d.defaclobjtype, a.grantor, a.grantee,
 CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee_name,
 a.privilege_type, a.is_grantable, r.rolsuper, r.rolbypassrls, r.rolcanlogin
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
CROSS JOIN LATERAL aclexplode(d.defaclacl) a LEFT JOIN pg_roles r ON r.oid=a.grantee
WHERE (d.defaclrole='postgres'::regrole AND (d.defaclnamespace=0 OR n.nspname='public'))
 OR a.grantee=0
),
relevant_memberships AS (
SELECT pg_get_userbyid(m.roleid) AS granted_role, pg_get_userbyid(m.member) AS member,
 pg_get_userbyid(m.grantor) AS grantor, m.admin_option,m.inherit_option,m.set_option
FROM pg_auth_members m
WHERE m.member IN ('postgres'::regrole,'app_runtime'::regrole)
 OR m.roleid IN ('postgres'::regrole,'app_runtime'::regrole)
 OR m.roleid IN (SELECT a.grantee FROM pg_default_acl d
 CROSS JOIN LATERAL aclexplode(d.defaclacl) a
 WHERE d.defaclrole='postgres'::regrole AND d.defaclnamespace IN (0,'public'::regnamespace))
),
column_types AS (
SELECT t.table_name,t.column_name,a.attnum IS NOT NULL AS present,
 format_type(a.atttypid,a.atttypmod) AS data_type,a.attnotnull,
 tn.nspname AS type_schema, ty.typtype
FROM (VALUES ('playlists','last_played_at'),('tracks','cover_url'),('upload_jobs','cover_data'),
 ('tracks','cover_source'),('users','password_hash')) t(table_name,column_name)
LEFT JOIN pg_class c ON c.relnamespace='public'::regnamespace AND c.relname=t.table_name
LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attname=t.column_name AND a.attnum>0 AND NOT a.attisdropped
LEFT JOIN pg_type ty ON ty.oid=a.atttypid LEFT JOIN pg_namespace tn ON tn.oid=ty.typnamespace
),
cover_constraint AS (
SELECT conname,contype,convalidated,connoinherit,
 md5(pg_get_constraintdef(oid)) AS definition_fingerprint,
 conname='ck_tracks_cover_source' AS expected_name,
 pg_get_constraintdef(oid) = 'CHECK (((cover_source)::text = ANY ((ARRAY[''embedded''::character varying, ''user''::character varying, ''placeholder''::character varying, ''unknown''::character varying])::text[])))' AS matches_legacy_candidate_form
FROM pg_constraint WHERE conrelid='public.tracks'::regclass AND contype='c'
),
rls_fingerprints AS (
SELECT c.relname,p.polname,p.polcmd,p.polpermissive,p.polroles,
 md5(pg_get_expr(p.polqual,p.polrelid)) AS using_fingerprint,
 md5(pg_get_expr(p.polwithcheck,p.polrelid)) AS check_fingerprint,
 pg_get_expr(p.polqual,p.polrelid)=pg_get_expr(p.polwithcheck,p.polrelid) AS using_equals_check,
 regexp_replace(pg_get_expr(p.polqual,p.polrelid),'[[:space:]]','','g') IN
 ('(user_id=current_setting(''app.current_user_id''::text,true))',
 '((user_id)::text=current_setting(''app.current_user_id''::text,true))') AS matches_simple_tenant_predicate,
 regexp_replace(pg_get_expr(p.polqual,p.polrelid),'[[:space:]]','','g') =
 '(EXISTS(SELECT1FROMpublic.playlistsWHERE(((playlists.id)::text=(playlist_tracks.playlist_id)::text)AND((playlists.user_id)::text=current_setting(''app.current_user_id''::text,true)))))'
 AS matches_playlist_tenant_predicate
FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid
WHERE c.relnamespace='public'::regnamespace AND c.relname IN
 ('tracks','favorites','playlists','playlist_tracks','upload_jobs','artist_photos','track_listens')
),
public_fresh_role_obstacles AS (
SELECT 'relation' AS object_kind,n.nspname AS schema_name,c.relname::text AS object_name,a.privilege_type
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::"char" ELSE 'r'::"char" END,c.relowner))) a
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','v','m','f','S')
 AND a.grantee=0 AND a.privilege_type IN ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','USAGE')
UNION ALL
SELECT 'column',n.nspname,c.relname::text || '.' || t.attname,a.privilege_type
FROM pg_attribute t JOIN pg_class c ON c.oid=t.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
CROSS JOIN LATERAL aclexplode(t.attacl) a
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND t.attnum>0 AND NOT t.attisdropped
 AND a.grantee=0 AND a.privilege_type IN ('SELECT','INSERT','UPDATE','REFERENCES')
UNION ALL
SELECT 'schema',n.nspname,n.nspname::text,a.privilege_type
FROM pg_namespace n CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND a.grantee=0 AND a.privilege_type='CREATE'
UNION ALL
SELECT 'routine',n.nspname,p.proname::text || '#' || p.oid::text,'EXECUTE'
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
 AND EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')
 AND EXISTS (SELECT 1 FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE a.grantee=0 AND a.privilege_type='USAGE')
)
SELECT jsonb_build_object(
  'acl_provenance',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM acl_provenance s),'[]'::jsonb),
  'default_acl_provenance',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM default_acl_provenance s),'[]'::jsonb),
  'relevant_memberships',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM relevant_memberships s),'[]'::jsonb),
  'column_types',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM column_types s),'[]'::jsonb),
  'cover_constraint',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM cover_constraint s),'[]'::jsonb),
  'rls_fingerprints',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM rls_fingerprints s),'[]'::jsonb),
  'public_fresh_role_obstacles',coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM public_fresh_role_obstacles s),'[]'::jsonb)
) AS followup_report;
ROLLBACK;
