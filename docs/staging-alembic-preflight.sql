-- Expected repository head: 0028_webauthn_enrollment (28 linear revisions).
-- Audit PUBLIC/inherited/default grants: 0026 only normalizes direct runtime ACLs
-- on allowlisted application objects; it cannot neutralize inherited privileges.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SELECT current_database(), session_user, current_user, current_schema(),
       current_setting('server_version'), current_setting('search_path'),
       inet_server_addr(), inet_server_port(),
       (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls;
DO $$ BEGIN
 IF current_database() <> 'postgres'
 OR session_user <> 'vervfy_oauth_staging_user'
 OR current_user <> 'vervfy_oauth_staging_user'
 OR current_schema() IS DISTINCT FROM 'public'
 OR current_setting('server_version_num')::integer / 10000 <> 17
 OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
 THEN RAISE EXCEPTION 'Wrong staging identity/schema/version/TLS'; END IF;
 -- Application emptiness only: provider schemas are not application state.
 -- BEGIN APPLICATION EMPTY PREDICATE (also exercised by local catalog tests)
 IF to_regnamespace('vervfy_auth') IS NOT NULL OR EXISTS (
 WITH expected_default_acl AS (
   -- Exact six-ACL staging baseline from the reviewed 96-row diagnostic.
   -- No owner-only or subset exemptions: grantor and grant options also match.
   SELECT owner_name, object_category,
          jsonb_agg(jsonb_build_array(grantee_name, owner_name, privilege, false)
                    ORDER BY grantee_name, owner_name, privilege) AS entries
   FROM (VALUES ('postgres'), ('supabase_admin')) owners(owner_name)
   CROSS JOIN (VALUES
     ('r', ARRAY['DELETE','INSERT','MAINTAIN','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE']),
     ('S', ARRAY['SELECT','UPDATE','USAGE']),
     ('f', ARRAY['EXECUTE'])
   ) categories(object_category, privileges)
   CROSS JOIN (VALUES ('postgres'), ('anon'), ('authenticated'), ('service_role')) grantees(grantee_name)
   CROSS JOIN LATERAL unnest(privileges) AS privileges(privilege)
   GROUP BY owner_name, object_category
 ), baseline_default_acl AS (
   SELECT d.oid FROM pg_default_acl d
   JOIN pg_roles creator ON creator.oid = d.defaclrole
   JOIN expected_default_acl expected
     ON expected.owner_name = creator.rolname
    AND expected.object_category = d.defaclobjtype::text
   WHERE d.defaclnamespace = 'public'::regnamespace
     AND expected.entries = (
       SELECT jsonb_agg(jsonb_build_array(grantee.rolname, grantor.rolname,
                                          acl.privilege_type, acl.is_grantable)
                        ORDER BY grantee.rolname, grantor.rolname, acl.privilege_type)
       FROM aclexplode(d.defaclacl) acl
       LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
       LEFT JOIN pg_roles grantor ON grantor.oid = acl.grantor
     )
 ), public_objects AS (
   SELECT 'pg_class'::regclass AS classid, c.oid AS objid
   FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace
   UNION
   SELECT 'pg_proc'::regclass, p.oid
   FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace
   UNION
   SELECT 'pg_type'::regclass, t.oid
   FROM pg_type t WHERE t.typnamespace = 'public'::regnamespace
   UNION
   -- Operators, collations, conversions, text-search objects, etc.
   SELECT d.classid, d.objid FROM pg_depend d
   WHERE d.refclassid = 'pg_namespace'::regclass
     AND d.refobjid = 'public'::regnamespace
 )
 SELECT 1 FROM public_objects o
 WHERE NOT (o.classid = 'pg_default_acl'::regclass
            AND o.objid IN (SELECT oid FROM baseline_default_acl))
 AND NOT EXISTS (
   -- Only registered routine/type members (and their generated array types) of provider-owned extensions
   -- installed in extensions/pg_catalog are exempt. No relation exemptions,
   -- name-prefix exemptions, or exemption for extensions installed in public.
   SELECT 1 FROM pg_depend d
   JOIN pg_extension e ON e.oid = d.refobjid
   JOIN pg_namespace n ON n.oid = e.extnamespace
   JOIN pg_roles r ON r.oid = e.extowner
   WHERE d.classid = o.classid AND d.objsubid = 0
     AND (d.objid = o.objid OR (
       o.classid = 'pg_type'::regclass AND EXISTS (
         SELECT 1 FROM pg_type base JOIN pg_type arr ON arr.oid = base.typarray
         WHERE arr.oid = o.objid AND arr.typelem = base.oid
           AND d.objid = base.oid
       )
     ))
     AND d.refclassid = 'pg_extension'::regclass AND d.deptype = 'e'
     AND o.classid IN ('pg_proc'::regclass, 'pg_type'::regclass)
     AND n.nspname IN ('extensions', 'pg_catalog')
     AND r.rolname IN ('postgres', 'supabase_admin')
 )) OR EXISTS (
   -- Ownership dependencies cover objects in ANY schema, including provider
   -- schemas. Only the documented migration-role global function hardening
   -- (owner EXECUTE, no PUBLIC/API grants) is an allowed Vervfy default ACL.
   SELECT 1 FROM pg_shdepend d JOIN pg_roles r ON r.oid = d.refobjid
   WHERE d.refclassid = 'pg_authid'::regclass AND d.deptype = 'o'
     AND d.dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
     AND r.rolname IN ('vervfy_oauth_staging_user', 'app_runtime',
       'google_auth_lookup', 'vervfy_identity_lookup_owner',
       'vervfy_identity_lookup', 'vervfy_storage_lifecycle_owner',
       'vervfy_storage_cleanup', 'storage_cleanup_worker')
     AND NOT (d.classid = 'pg_default_acl'::regclass AND EXISTS (
       SELECT 1 FROM pg_default_acl defaults
       WHERE defaults.oid = d.objid
         AND defaults.defaclrole = r.oid
         AND r.rolname = 'vervfy_oauth_staging_user'
         AND defaults.defaclnamespace = 0 AND defaults.defaclobjtype = 'f'
         AND cardinality(defaults.defaclacl) = 1
         AND EXISTS (SELECT 1 FROM aclexplode(defaults.defaclacl) acl
                     WHERE acl.grantee = r.oid AND acl.grantor = r.oid
                       AND acl.privilege_type = 'EXECUTE' AND NOT acl.is_grantable)
     ))
     AND NOT (d.classid = 'pg_namespace'::regclass
              AND d.objid = 'public'::regnamespace)
 )
 -- END APPLICATION EMPTY PREDICATE
 THEN RAISE EXCEPTION 'Expected empty staging database without private auth schema'; END IF;
 IF NOT has_database_privilege(current_user,current_database(),'CREATE')
 OR NOT has_schema_privilege(current_user,'public','USAGE')
 OR NOT has_schema_privilege(current_user,'public','CREATE')
 THEN RAISE EXCEPTION 'Missing migration schema/database permissions'; END IF;
 IF (SELECT count(*) FROM pg_roles WHERE rolname IN
 ('vervfy_identity_lookup_owner','vervfy_identity_lookup')
 AND NOT (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit)) <> 2
 THEN RAISE EXCEPTION 'Unsafe or missing capability roles'; END IF;
 IF (SELECT count(*) FROM pg_roles WHERE rolname IN ('app_runtime','google_auth_lookup')
 AND rolcanlogin AND NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit)) <> 2
 THEN RAISE EXCEPTION 'Unsafe or missing application logins'; END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls))
 THEN RAISE EXCEPTION 'Unsafe migration principal'; END IF;
 IF (SELECT count(*) FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup_owner'::regrole) <> 2
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup_owner'::regrole
       AND NOT (
         (member='postgres'::regrole AND grantor='supabase_admin'::regrole
          AND admin_option AND NOT inherit_option AND NOT set_option)
         OR
         (member=current_user::regrole AND grantor='postgres'::regrole
          AND NOT admin_option AND NOT inherit_option AND set_option)))
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE member='vervfy_identity_lookup_owner'::regrole)
 OR NOT pg_has_role(current_user,'vervfy_identity_lookup_owner','SET')
 OR NOT pg_has_role(current_user,'vervfy_identity_lookup_owner','MEMBER')
 OR pg_has_role(current_user,'vervfy_identity_lookup_owner','USAGE')
 THEN RAISE EXCEPTION 'Unsafe owner membership or missing SET capability'; END IF;
 IF (SELECT count(*) FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup'::regrole) <> 2
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup'::regrole
       AND NOT (
         (member='postgres'::regrole AND grantor='supabase_admin'::regrole
          AND admin_option AND NOT inherit_option AND NOT set_option)
         OR
         (member='google_auth_lookup'::regrole AND grantor='postgres'::regrole
          AND NOT admin_option AND inherit_option AND NOT set_option)))
 OR (SELECT count(*) FROM pg_auth_members
     WHERE member='google_auth_lookup'::regrole) <> 1
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE member='google_auth_lookup'::regrole
       AND (roleid<>'vervfy_identity_lookup'::regrole
            OR grantor<>'postgres'::regrole OR admin_option
            OR NOT inherit_option OR set_option))
 OR (SELECT count(*) FROM pg_auth_members
     WHERE roleid='google_auth_lookup'::regrole) <> 1
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE roleid='google_auth_lookup'::regrole
       AND NOT (member='postgres'::regrole
                AND grantor='supabase_admin'::regrole
                AND admin_option AND NOT inherit_option AND NOT set_option))
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE member='vervfy_identity_lookup'::regrole)
 OR EXISTS (SELECT 1 FROM pg_roles r
     WHERE r.oid NOT IN ('vervfy_identity_lookup'::regrole,
                         'google_auth_lookup'::regrole)
       AND NOT r.rolsuper
       AND (pg_has_role(r.oid,'vervfy_identity_lookup','USAGE')
            OR pg_has_role(r.oid,'vervfy_identity_lookup','SET')))
 OR NOT pg_has_role('google_auth_lookup','vervfy_identity_lookup','USAGE')
 OR pg_has_role('google_auth_lookup','vervfy_identity_lookup','SET')
 OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='app_runtime'::regrole)
 OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='vervfy_identity_lookup'::regrole)
 THEN RAISE EXCEPTION 'Unsafe runtime/executor role graph'; END IF;
 IF EXISTS (SELECT 1 FROM pg_roles r WHERE rolname IN ('app_runtime','google_auth_lookup')
 AND (NOT has_database_privilege(r.oid,current_database(),'CONNECT')
 OR has_database_privilege(r.oid,current_database(),'CREATE')
 OR has_schema_privilege(r.oid,'public','CREATE')))
 OR NOT has_schema_privilege('app_runtime','public','USAGE')
 OR has_schema_privilege('google_auth_lookup','public','USAGE')
 THEN RAISE EXCEPTION 'Unexpected app database/schema permissions'; END IF;
END $$;
-- Review every row below before approval; passing assertions are not an ACL audit.
SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,
       rolcreaterole,rolreplication,rolconfig
FROM pg_roles WHERE rolname IN ('vervfy_oauth_staging_user','app_runtime',
 'google_auth_lookup','vervfy_identity_lookup_owner','vervfy_identity_lookup');
SELECT roleid::regrole AS capability,member::regrole AS member,
 grantor::regrole AS grantor,admin_option,inherit_option,set_option
FROM pg_auth_members ORDER BY 1,2,3;
SELECT datname,pg_get_userbyid(datdba) AS owner,datallowconn,datconnlimit,
       pg_encoding_to_char(encoding) AS encoding,datcollate,datctype,datacl
FROM pg_database WHERE datname=current_database();
SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl
FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname<>'information_schema';
SELECT defaclrole::regrole AS creator,n.nspname,defaclobjtype,defaclacl
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace;
-- Settings may affect search_path or row_security. No passwords are queried.
SELECT setdatabase,setrole::regrole,setconfig FROM pg_db_role_setting
WHERE setdatabase IN (0,(SELECT oid FROM pg_database WHERE datname=current_database()));
SELECT current_setting('transaction_read_only') AS preflight_read_only,
 current_setting('default_transaction_read_only') AS default_read_only,
 current_setting('row_security') AS row_security,
 current_setting('lock_timeout') AS lock_timeout,
 current_setting('statement_timeout') AS statement_timeout;
ROLLBACK;
