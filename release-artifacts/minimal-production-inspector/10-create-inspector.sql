-- APPROVAL B: NEW ROLE + THREE NARROW GRANTS ONLY. Not a read-only script.
-- SQL Editor compatible. Run as an independently authorized provisioning
-- operator on project llxmskxxchpmeavorusj / database postgres only.
-- PUBLIC/provider/application ACLs, memberships and data are never modified.
-- If any statement fails, ROLLBACK the transaction. Never execute COMMIT alone.
BEGIN;
SET LOCAL search_path = pg_catalog;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '3s';
DO $preconditions$
BEGIN
 IF current_database()<>'postgres' OR current_setting('server_version_num')::integer NOT BETWEEN 170000 AND 189999 THEN
   RAISE EXCEPTION 'STOP: unreviewed database/version';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='vervfy_prod_inspector') THEN
   RAISE EXCEPTION 'STOP: inspector already exists; do not alter/reuse it';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='alembic_version'
      AND c.relkind='r' AND NOT c.relrowsecurity AND NOT c.relforcerowsecurity) THEN
   RAISE EXCEPTION 'STOP: revision metadata missing, not a plain table, or protected by RLS';
 END IF;
END
$preconditions$;

CREATE ROLE vervfy_prod_inspector
 LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
 NOREPLICATION CONNECTION LIMIT 1 PASSWORD NULL;
GRANT CONNECT ON DATABASE postgres TO vervfy_prod_inspector;
GRANT USAGE ON SCHEMA public TO vervfy_prod_inspector;
GRANT SELECT (version_num) ON TABLE public.alembic_version TO vervfy_prod_inspector;
ALTER ROLE vervfy_prod_inspector SET default_transaction_read_only = on;

-- These assertions include PUBLIC and effective grants. There is no per-role
-- DENY overriding PUBLIC. Failure aborts EVERYTHING, including CREATE ROLE.
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
COMMIT;
-- No usable password was installed. Credential activation is a separately
-- identified part of provisioning approval, performed only after full success.
