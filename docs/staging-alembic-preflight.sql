-- Expected repository head: 0026_application_runtime_grants (26 linear revisions).
-- Audit PUBLIC/inherited/default grants: 0026 only normalizes direct runtime ACLs
-- on allowlisted application objects; it cannot neutralize inherited privileges.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SELECT current_database(), session_user, current_user, current_schema(),
       current_setting('server_version'), current_setting('search_path'),
       inet_server_addr(), inet_server_port(),
       (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls;
DO $$ BEGIN
 IF current_database() <> 'vervfy_oauth_staging'
 OR session_user <> 'vervfy_oauth_staging_user'
 OR current_user <> 'vervfy_oauth_staging_user'
 OR current_schema() IS DISTINCT FROM 'public'
 OR current_setting('server_version_num')::integer / 10000 <> 18
 OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
 THEN RAISE EXCEPTION 'Wrong staging identity/schema/version/TLS'; END IF;
 IF to_regnamespace('vervfy_auth') IS NOT NULL OR EXISTS (
 SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname NOT IN ('pg_catalog','information_schema')
 AND n.nspname !~ '^pg_' AND c.relkind IN ('r','p','v','m','S','f'))
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
 IF EXISTS (SELECT 1 FROM pg_auth_members WHERE
 member='vervfy_identity_lookup_owner'::regrole OR
 (roleid='vervfy_identity_lookup_owner'::regrole AND member<>current_user::regrole))
 OR NOT pg_has_role(current_user,'vervfy_identity_lookup_owner','SET')
 OR NOT pg_has_role(current_user,'vervfy_identity_lookup_owner','MEMBER')
 OR pg_has_role(current_user,'vervfy_identity_lookup_owner','USAGE')
 THEN RAISE EXCEPTION 'Unsafe owner membership or missing SET capability'; END IF;
 IF (SELECT count(*) FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup'::regrole) <> 1
 OR NOT EXISTS (SELECT 1 FROM pg_auth_members
     WHERE roleid='vervfy_identity_lookup'::regrole
       AND member='google_auth_lookup'::regrole
       AND inherit_option AND NOT set_option AND NOT admin_option)
 OR EXISTS (SELECT 1 FROM pg_auth_members
     WHERE (member='google_auth_lookup'::regrole
            AND roleid<>'vervfy_identity_lookup'::regrole)
        OR roleid='google_auth_lookup'::regrole)
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
 OR has_database_privilege(r.oid,current_database(),'TEMP')
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
