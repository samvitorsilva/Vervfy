-- APPROVAL C: authenticate directly as inspector. No SET ROLE from postgres.
-- psql -X --no-password --set=ON_ERROR_STOP=1 --file this-file.sql
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '30s';
SELECT session_user='vervfy_prod_inspector' AND current_user=session_user
       AND current_database()='postgres'
       AND current_setting('transaction_read_only')='on' AS identity_gate \gset
\if :identity_gate
\else
\echo 'STOP: wrong inspection identity/database/transaction mode.'
\quit 3
\endif
SELECT current_setting('server_version') AS server_version,
       current_setting('transaction_read_only')='on' AS read_only_transaction,
       (SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls_enabled;
SELECT CASE WHEN version_num ~ '^00(0[1-9]|1[0-9]|2[0-7])_[a-z0-9_]+$'
       THEN version_num ELSE '<unexpected-revision-STOP>' END AS revision
FROM ONLY public.alembic_version;
SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,
 (SELECT count(*) FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid OR m.roleid=r.oid) AS membership_edges,
 has_database_privilege(r.oid,current_database(),'CREATE,TEMP') AS database_create_or_temp
FROM pg_catalog.pg_roles r WHERE r.rolname=current_user;
-- Recheck the full effective privilege contract using catalogs only.
DO $verify$
DECLARE inspector oid;
BEGIN
 SELECT oid INTO STRICT inspector FROM pg_catalog.pg_roles WHERE rolname='vervfy_prod_inspector';
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE oid=inspector AND
   (NOT rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)) THEN
   RAISE EXCEPTION 'STOP: unsafe inspector attributes';
 END IF;
 -- The existing runner rejects inbound as well as outbound membership. A
 -- non-superuser creator can receive an automatic ADMIN membership in PG17;
 -- that case must roll back too. Do not silently relax the runner contract.
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=inspector OR roleid=inspector) THEN
   RAISE EXCEPTION 'STOP: inspector membership conflicts with approved contract';
 END IF;
 IF pg_catalog.has_database_privilege(inspector,current_database(),'CREATE,TEMP') THEN
   RAISE EXCEPTION 'STOP: PUBLIC or effective database CREATE/TEMP prevents strict isolation';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_database d WHERE d.datallowconn AND d.datname<>current_database()
   AND pg_catalog.has_database_privilege(inspector,d.oid,'CONNECT')) THEN
   RAISE EXCEPTION 'STOP: unreviewed access to another database';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_namespace n WHERE n.nspowner=inspector
   OR (n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
     AND pg_catalog.has_schema_privilege(inspector,n.oid,'CREATE'))) THEN
   RAISE EXCEPTION 'STOP: effective schema CREATE/ownership';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','v','m','f')
   AND (c.relowner=inspector
    OR pg_catalog.has_table_privilege(inspector,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
    OR pg_catalog.has_any_column_privilege(inspector,c.oid,'INSERT,UPDATE,REFERENCES')
    OR (NOT (n.nspname='public' AND c.relname='alembic_version')
       AND (pg_catalog.has_table_privilege(inspector,c.oid,'SELECT')
         OR pg_catalog.has_any_column_privilege(inspector,c.oid,'SELECT'))))) THEN
   RAISE EXCEPTION 'STOP: effective access to non-release records or write/ownership privilege';
 END IF;
 IF pg_catalog.has_table_privilege(inspector,'public.alembic_version','SELECT')
 OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid='public.alembic_version'::regclass
   AND a.attnum>0 AND NOT a.attisdropped AND a.attname<>'version_num'
   AND pg_catalog.has_column_privilege(inspector,a.attrelid,a.attnum,'SELECT')) THEN
   RAISE EXCEPTION 'STOP: revision grant is broader than version_num';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind='S'
   AND (c.relowner=inspector OR pg_catalog.has_sequence_privilege(inspector,c.oid,'USAGE,SELECT,UPDATE'))) THEN
   RAISE EXCEPTION 'STOP: effective sequence access';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
   WHERE (p.proowner=inspector OR
      (n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
       AND pg_catalog.has_schema_privilege(inspector,n.oid,'USAGE')
       AND pg_catalog.has_function_privilege(inspector,p.oid,'EXECUTE')))
    OR (n.nspname='pg_catalog'
       AND p.proname IN ('lo_create','lo_creat','lo_from_bytea','lo_import','lo_put',
                         'lo_unlink','lowrite','lo_truncate','lo_truncate64')
       AND pg_catalog.has_function_privilege(inspector,p.oid,'EXECUTE'))) THEN
   RAISE EXCEPTION 'STOP: callable non-catalog or large-object write routine';
 END IF;
 IF NOT pg_catalog.has_column_privilege(inspector,'public.alembic_version','version_num','SELECT') THEN
   RAISE EXCEPTION 'STOP: missing revision metadata permission';
 END IF;
END
$verify$;
ROLLBACK;
-- After signoff, the existing 01-catalogs.sql collects the full approved catalog
-- inventory using the same login, without adding Storage/user-record grants.
