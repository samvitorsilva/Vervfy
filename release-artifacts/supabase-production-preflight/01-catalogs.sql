-- REVIEW PACKAGE ONLY. No SQL has been executed.
-- Read-only transaction; built-in catalog functions only; no application rows.
\set ON_ERROR_STOP on
\pset pager off
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '3s';

SELECT pg_catalog.current_setting('server_version') AS postgres_version,
       pg_catalog.current_setting('server_version_num')::integer AS postgres_version_num,
       pg_catalog.current_setting('transaction_read_only') = 'on' AS transaction_read_only,
       current_database() = :'database_name' AS database_matches,
       session_user = :'inspection_role' AND current_user = :'inspection_role' AS identity_matches,
       EXISTS (SELECT 1 FROM pg_catalog.pg_stat_ssl
               WHERE pid = pg_catalog.pg_backend_pid() AND ssl) AS tls_enabled;
SELECT pg_catalog.current_setting('server_version_num')::integer BETWEEN 160000 AND 189999
       AND current_database() = :'database_name'
       AND session_user = :'inspection_role' AND current_user = :'inspection_role'
       AND EXISTS (SELECT 1 FROM pg_catalog.pg_stat_ssl
                   WHERE pid = pg_catalog.pg_backend_pid() AND ssl) AS connection_gate \gset
\if :connection_gate
\else
\echo 'STOP: version, database, identity or TLS mismatch; no further queries.'
\quit 3
\endif

SELECT rolcanlogin AND NOT (rolinherit OR rolsuper OR rolbypassrls OR rolcreatedb
       OR rolcreaterole OR rolreplication)
       AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members
                       WHERE member = r.oid OR roleid = r.oid)
       AND NOT pg_catalog.has_database_privilege(r.oid, current_database(), 'CREATE')
       AND NOT pg_catalog.has_database_privilege(r.oid, current_database(), 'TEMP')
       AS inspection_identity_gate
FROM pg_catalog.pg_roles r WHERE rolname = :'inspection_role' \gset
\if :inspection_identity_gate
\else
\echo 'STOP: inspection identity is not the approved restricted login.'
\quit 3
\endif

SELECT pg_catalog.to_regclass('public.alembic_version') IS NOT NULL AS has_revision \gset
\if :has_revision
-- This is release metadata, not an application-user table.
SELECT CASE WHEN version_num = ANY(pg_catalog.string_to_array(:'allowed_revisions', ','))
            THEN version_num ELSE '<unrecognized-revision>' END AS alembic_revision
FROM ONLY public.alembic_version;
SELECT count(*) = 1 AND coalesce(bool_and(
 version_num = ANY(pg_catalog.string_to_array(:'allowed_revisions', ','))
 AND (:'expected_revision'='DISCOVER' OR version_num=:'expected_revision')), false)
       AS revision_gate FROM ONLY public.alembic_version \gset
\if :revision_gate
\else
\echo 'STOP: revision differs from approved current revision, or is ambiguous.'
\quit 3
\endif
\else
\echo 'STOP: missing Alembic metadata on reported populated production database.'
\quit 3
\endif

-- Known application/capability names only. Missing rows remain explicit NULLs.
WITH expected(name) AS (VALUES
 (:'migration_role'), (:'inspection_role'), ('app_runtime'), ('google_auth_lookup'),
 ('vervfy_identity_lookup_owner'), ('vervfy_identity_lookup'),
 ('vervfy_storage_lifecycle_owner'), ('vervfy_storage_cleanup'), ('storage_cleanup_worker'))
SELECT e.name AS expected_role, r.oid IS NOT NULL AS present,
 r.rolcanlogin, r.rolinherit, r.rolsuper, r.rolbypassrls, r.rolcreatedb,
 r.rolcreaterole, r.rolreplication,
 pg_catalog.has_database_privilege(r.oid, current_database(), 'CONNECT') AS db_connect,
 pg_catalog.has_database_privilege(r.oid, current_database(), 'CREATE') AS db_create,
 pg_catalog.has_database_privilege(r.oid, current_database(), 'TEMP') AS db_temp,
 pg_catalog.has_schema_privilege(r.oid, 'public', 'USAGE') AS public_usage,
 pg_catalog.has_schema_privilege(r.oid, 'public', 'CREATE') AS public_create
FROM expected e LEFT JOIN pg_catalog.pg_roles r ON r.rolname = e.name ORDER BY e.name;

-- Include direct edges AND effective inherited/SET reachability, including
-- provider-managed roles. Do not exempt Supabase roles from migration guards.
WITH targets(name) AS (VALUES (:'migration_role'), (:'inspection_role'),
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
GROUP BY 1,2,3,4,5 ORDER BY 1,2;
WITH caps(name,allowed_member) AS (VALUES
 ('vervfy_identity_lookup_owner', :'migration_role'),
 ('vervfy_identity_lookup', 'google_auth_lookup'),
 ('vervfy_storage_lifecycle_owner', :'migration_role'),
 ('vervfy_storage_cleanup', 'storage_cleanup_worker'))
SELECT caps.name, cap.oid IS NOT NULL AS present,
 count(r.oid) FILTER (WHERE NOT r.rolsuper
   AND r.rolname NOT IN (caps.name, caps.allowed_member)
   AND (pg_catalog.pg_has_role(r.oid,cap.oid,'USAGE')
        OR pg_catalog.pg_has_role(r.oid,cap.oid,'SET'))) AS unexpected_effective_holders,
 count(r.oid) FILTER (WHERE r.rolsuper AND r.oid <> cap.oid) AS superuser_holders
FROM caps LEFT JOIN pg_catalog.pg_roles cap ON cap.rolname=caps.name
LEFT JOIN pg_catalog.pg_roles r ON true GROUP BY caps.name,cap.oid ORDER BY caps.name;

-- Effective database/schema privileges include PUBLIC and inherited grants.
WITH subjects(name) AS (VALUES (:'migration_role'), (:'inspection_role'),
 ('app_runtime'), ('google_auth_lookup'), ('vervfy_identity_lookup_owner'),
 ('vervfy_identity_lookup'), ('vervfy_storage_lifecycle_owner'),
 ('vervfy_storage_cleanup'), ('storage_cleanup_worker'))
SELECT s.name AS role_name, n.nspname AS schema_name,
 n.nspowner = r.oid AS owns_schema,
 pg_catalog.has_schema_privilege(r.oid,n.oid,'USAGE') AS usage,
 pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE') AS create_privilege
FROM subjects s LEFT JOIN pg_catalog.pg_roles r ON r.rolname=s.name
CROSS JOIN pg_catalog.pg_namespace n
WHERE n.nspname IN ('public','vervfy_auth','vervfy_storage','storage') ORDER BY 1,2;

-- Application tables, migration metadata, storage bucket configuration and
-- lifecycle tables only. Relation names are fixed; no relation data is read.
WITH expected(schema_name,table_name) AS (VALUES
 ('public','alembic_version'),('public','users'),('public','tracks'),
 ('public','favorites'),('public','playlists'),('public','playlist_tracks'),
 ('public','upload_jobs'),('public','artist_photos'),('public','track_listens'),
 ('public','provider_identities'),('public','artist_images'),('public','track_cover_cache'),
 ('storage','buckets'),('storage','objects'),('vervfy_storage','namespaces'),
 ('vervfy_storage','objects'),('vervfy_storage','cleanup_jobs'))
SELECT e.schema_name,e.table_name,c.oid IS NOT NULL AS present,c.relkind,
 CASE WHEN owner_role.rolname = :'migration_role' THEN '<approved-migration-role>'
      WHEN owner_role.rolname IN ('supabase_storage_admin','supabase_admin','postgres')
      THEN owner_role.rolname ELSE '<other-owner>' END AS owner_class,
 c.relrowsecurity,c.relforcerowsecurity,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'SELECT') AS runtime_select,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'INSERT') AS runtime_insert,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'UPDATE') AS runtime_update,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'DELETE') AS runtime_delete,
 pg_catalog.has_table_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'TRUNCATE,REFERENCES,TRIGGER') AS runtime_extra,
 pg_catalog.has_any_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,'INSERT,UPDATE,REFERENCES') AS runtime_any_column_write
FROM expected e LEFT JOIN pg_catalog.pg_namespace n ON n.nspname=e.schema_name
LEFT JOIN pg_catalog.pg_class c ON c.relnamespace=n.oid AND c.relname=e.table_name
LEFT JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=c.relowner ORDER BY 1,2;

-- Attribute ACLs, owned-sequence privileges and constraints are catalog metadata.
SELECT c.relname AS table_name,a.attname AS column_name,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'SELECT') AS runtime_select,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'INSERT') AS runtime_insert,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'UPDATE') AS runtime_update,
 pg_catalog.has_column_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),c.oid,a.attnum,'REFERENCES') AS runtime_references
FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('users','tracks','favorites','playlists',
 'playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities',
 'artist_images','track_cover_cache') AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2;
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
 'artist_images','track_cover_cache') GROUP BY tbl.relname ORDER BY 1;
SELECT c.relname AS table_name,k.contype,k.convalidated,
 pg_catalog.md5(pg_catalog.pg_get_constraintdef(k.oid)) AS definition_fingerprint
FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('tracks','favorites','playlists',
 'playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities') ORDER BY 1,2,4;

-- Fingerprints avoid exporting expression literals. Compare to the candidate
-- migrations and existing reviewed policy evidence; existence alone is not PASS.
SELECT n.nspname,c.relname,p.polcmd,p.polpermissive,
 pg_catalog.md5(p.polname) AS policy_name_fingerprint,
 pg_catalog.md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid)) AS using_fingerprint,
 pg_catalog.md5(pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)) AS check_fingerprint,
 coalesce(0 = ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles
          WHERE rolname=:'inspection_role') = ANY(p.polroles),false) AS applies_to_inspector,
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
 OR (n.nspname='storage' AND c.relname IN ('buckets','objects')) ORDER BY 1,2,5;

-- Function definitions/configuration values are never emitted. Only a known
-- search_path boolean, built-in hash and effective execution privileges appear.
SELECT n.nspname,p.proname,p.pronargs,p.prosecdef,p.provolatile,
 CASE WHEN owner_role.rolname IN ('vervfy_identity_lookup_owner','vervfy_storage_lifecycle_owner')
      THEN owner_role.rolname ELSE '<other-owner>' END AS owner_class,
 coalesce(p.proconfig @> ARRAY['search_path=pg_catalog, pg_temp'],false) AS pinned_search_path,
 pg_catalog.md5(p.prosrc) AS body_fingerprint,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(coalesce(p.proacl,
     pg_catalog.acldefault('f',p.proowner))) a WHERE a.grantee=0
     AND a.privilege_type='EXECUTE') AS public_execute,
 pg_catalog.has_function_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='app_runtime'),p.oid,'EXECUTE') AS runtime_execute,
 pg_catalog.has_function_privilege((SELECT oid FROM pg_catalog.pg_roles WHERE rolname='google_auth_lookup'),p.oid,'EXECUTE') AS lookup_execute
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=p.proowner
WHERE n.nspname IN ('vervfy_auth','vervfy_storage') ORDER BY 1,2,3;
SELECT count(*) FILTER (WHERE p.proname IN ('claim_next_cleanup','complete_cleanup','retry_cleanup'))
       AS forbidden_0028_routines
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='vervfy_storage';
SELECT c.relname,t.tgenabled,t.tgtype,
 t.tgfoid = pg_catalog.to_regprocedure('vervfy_storage.guard_references()') AS correct_guard_function
FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('tracks','artist_photos','upload_jobs')
 AND t.tgname='storage_reference_guard' AND NOT t.tgisinternal ORDER BY 1;

-- Normalized default ACLs: owner/grantee categories, never raw ACL strings.
SELECT CASE WHEN owner_role.rolname=:'migration_role' THEN '<migration-role>' ELSE '<other-role>' END AS owner_class,
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
GROUP BY 1,2,3,4,5,6,7 ORDER BY 1,2,3,4,7;

-- Stage 02 is forbidden unless these inspection scope counts are all zero.
-- Allowed metadata relations have COLUMN grants only; inspect those separately.
SELECT count(*) FILTER (WHERE pg_catalog.has_table_privilege(current_user,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 OR pg_catalog.has_any_column_privilege(current_user,c.oid,'INSERT,UPDATE,REFERENCES')) AS writable_relations,
 count(*) FILTER (WHERE NOT ((n.nspname='public' AND c.relname='alembic_version')
 OR (n.nspname='storage' AND c.relname='buckets')
 OR (n.nspname='vervfy_storage' AND c.relname='namespaces'))
 AND (pg_catalog.has_table_privilege(current_user,c.oid,'SELECT')
 OR pg_catalog.has_any_column_privilege(current_user,c.oid,'SELECT'))) AS other_readable_relations,
 count(*) FILTER (WHERE c.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)) AS owned_relations
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','v','m','f');
SELECT count(*) AS inspector_accessible_or_owned_sequences
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind='S'
 AND (pg_catalog.has_sequence_privilege(current_user,c.oid,'USAGE,SELECT,UPDATE')
 OR c.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user));
SELECT count(*) AS inspector_creatable_or_owned_schemas FROM pg_catalog.pg_namespace n
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
 AND (pg_catalog.has_schema_privilege(current_user,n.oid,'CREATE')
 OR n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user));
SELECT count(*) AS inspector_callable_non_catalog_routines
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
 AND pg_catalog.has_schema_privilege(current_user,n.oid,'USAGE')
 AND pg_catalog.has_function_privilege(current_user,p.oid,'EXECUTE');
SELECT n.nspname,c.relname,a.attname,
 pg_catalog.has_table_privilege(current_user,c.oid,'SELECT') AS broad_table_select,
 pg_catalog.has_column_privilege(current_user,c.oid,a.attnum,'SELECT') AS effective_column_select
FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE ((n.nspname='public' AND c.relname='alembic_version')
 OR (n.nspname='storage' AND c.relname='buckets')
 OR (n.nspname='vervfy_storage' AND c.relname='namespaces'))
 AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3;

-- Privileges of every narrow capability/login on relevant existing relations.
WITH subjects(name) AS (VALUES (:'migration_role'),('google_auth_lookup'),
 ('vervfy_identity_lookup_owner'),('vervfy_identity_lookup'),
 ('vervfy_storage_lifecycle_owner'),('vervfy_storage_cleanup'),('storage_cleanup_worker'))
SELECT s.name AS role_name,n.nspname,c.relname,c.relowner=r.oid AS owns_relation,
 pg_catalog.has_table_privilege(r.oid,c.oid,'SELECT') AS table_select,
 pg_catalog.has_any_column_privilege(r.oid,c.oid,'SELECT') AS any_column_select,
 pg_catalog.has_table_privilege(r.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 OR pg_catalog.has_any_column_privilege(r.oid,c.oid,'INSERT,UPDATE,REFERENCES') AS any_write
FROM subjects s LEFT JOIN pg_catalog.pg_roles r ON r.rolname=s.name
CROSS JOIN pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE (n.nspname='public' AND c.relname IN ('alembic_version','users','tracks','favorites',
 'playlists','playlist_tracks','upload_jobs','artist_photos','track_listens','provider_identities',
 'artist_images','track_cover_cache')) OR n.nspname IN ('vervfy_auth','vervfy_storage')
ORDER BY 1,2,3;

-- 0027 runs the equivalent checks across ALL non-system schemas. PUBLIC
-- privileges in Supabase-managed schemas can therefore block it. Emit counts
-- only; do not enumerate provider objects or change provider ACLs to pass.
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
FROM caps LEFT JOIN pg_catalog.pg_roles r ON r.rolname=caps.name ORDER BY caps.name;


-- Provider PUBLIC defaults are reported; they are not silently assumed safe.
SELECT a.privilege_type,a.is_grantable FROM pg_catalog.pg_database d
CROSS JOIN LATERAL pg_catalog.aclexplode(coalesce(d.datacl,
 pg_catalog.acldefault('d',d.datdba))) a
WHERE d.datname=current_database() AND a.grantee=0 ORDER BY 1;
SELECT n.nspname,a.privilege_type,a.is_grantable FROM pg_catalog.pg_namespace n
CROSS JOIN LATERAL pg_catalog.aclexplode(coalesce(n.nspacl,
 pg_catalog.acldefault('n',n.nspowner))) a
WHERE n.nspname IN ('public','storage','vervfy_auth','vervfy_storage') AND a.grantee=0 ORDER BY 1,2;
SELECT e.table_name,e.column_name,a.attnum IS NOT NULL AS present
FROM (VALUES ('tracks','storage_path'),('tracks','cover_path'),('tracks','cover_source'),
 ('artist_photos','storage_path'),('upload_jobs','storage_path'),('users','password_hash'))
 e(table_name,column_name)
LEFT JOIN pg_catalog.pg_class c ON c.relname=e.table_name
 AND c.relnamespace=pg_catalog.to_regnamespace('public')
LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid AND a.attname=e.column_name
 AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2;

ROLLBACK;
