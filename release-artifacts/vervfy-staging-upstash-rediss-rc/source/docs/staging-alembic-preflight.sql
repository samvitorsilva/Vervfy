-- Supabase PG17 staging only. Run through staging_guard.py with TLS
-- sslmode=verify-full, the independently approved CA, and the pinned project ref.
-- pg_stat_ssl describes the pooler-to-server leg, not client TLS; do not use it
-- as a substitute for the client-side libpq verify-full check.
\set ON_ERROR_STOP on
BEGIN READ ONLY;

SELECT current_database(), session_user, current_user, current_schema(),
       current_setting('server_version'), current_setting('search_path'),
       inet_server_addr(), inet_server_port();

DO $preflight$
DECLARE
    expected_role_count integer;
BEGIN
    IF current_database() <> 'postgres'
       OR session_user <> 'vervfy_oauth_staging_user'
       OR current_user <> 'vervfy_oauth_staging_user'
       OR current_schema() IS DISTINCT FROM 'public'
       OR current_setting('server_version_num')::integer < 170011
       OR current_setting('server_version_num')::integer >= 180000
    THEN
        RAISE EXCEPTION 'Wrong Supabase staging database, role, schema, or PostgreSQL version';
    END IF;

    IF to_regclass('public.alembic_version') IS NOT NULL
       OR to_regnamespace('vervfy_auth') IS NOT NULL
       OR to_regnamespace('vervfy_storage') IS NOT NULL
    THEN
        RAISE EXCEPTION 'Vervfy objects already exist; inspect exact migration state';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='auth')
       OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='storage')
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.pg_namespace n
           WHERE n.nspname !~ '^pg_'
             AND n.nspname <> 'information_schema'
             AND n.nspname NOT IN (
                 'public', 'auth', 'extensions', 'graphql', 'graphql_public',
                 'pgbouncer', 'realtime', 'storage', 'vault'
             )
       )
    THEN
        RAISE EXCEPTION 'Unexpected schema set; provider schemas require explicit review';
    END IF;

    -- Existing Supabase-owned relations are allowed in the enumerated provider
    -- schemas. public may contain extension-owned objects, but no user tables.
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public'
          AND c.relkind IN ('r','p','v','m','S','f')
          AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_depend d
              WHERE d.classid='pg_catalog.pg_class'::regclass
                AND d.objid=c.oid AND d.deptype='e'
          )
    ) THEN
        RAISE EXCEPTION 'Unexpected non-extension objects in public schema';
    END IF;

    IF NOT has_database_privilege(current_user, current_database(), 'CONNECT')
       OR NOT has_database_privilege(current_user, current_database(), 'CREATE')
       OR NOT has_schema_privilege(current_user, 'public', 'USAGE')
       OR NOT has_schema_privilege(current_user, 'public', 'CREATE')
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.pg_namespace n
           CROSS JOIN LATERAL pg_catalog.aclexplode(n.nspacl) a
           WHERE n.nspname='public'
             AND a.grantee=0 AND a.privilege_type='CREATE'
       )
    THEN
        RAISE EXCEPTION 'Database/schema capability boundary is not restricted';
    END IF;

    IF (SELECT count(*) FROM pg_catalog.pg_roles
        WHERE rolname IN (
            'anon','authenticated','service_role','postgres','supabase_admin'
        )) <> 5
    THEN
        RAISE EXCEPTION 'Supabase API/bootstrap roles are missing';
    END IF;

    SELECT count(*) INTO expected_role_count
    FROM pg_catalog.pg_roles r
    WHERE (
           (r.rolname='vervfy_oauth_staging_user' AND r.rolcanlogin AND NOT r.rolinherit)
        OR (r.rolname='app_runtime' AND r.rolcanlogin AND NOT r.rolinherit)
        OR (r.rolname='google_auth_lookup' AND r.rolcanlogin AND NOT r.rolinherit)
        OR (r.rolname='storage_cleanup_worker' AND r.rolcanlogin AND NOT r.rolinherit)
        OR (r.rolname IN (
              'vervfy_identity_lookup_owner','vervfy_identity_lookup',
              'vervfy_storage_lifecycle_owner','vervfy_storage_cleanup'
          ) AND NOT r.rolcanlogin AND NOT r.rolinherit)
    )
      AND NOT r.rolsuper AND NOT r.rolbypassrls AND NOT r.rolcreatedb
      AND NOT r.rolcreaterole AND NOT r.rolreplication;

    IF expected_role_count <> 8 THEN
        RAISE EXCEPTION 'Vervfy role attributes are unsafe or incomplete';
    END IF;

    IF EXISTS (
           SELECT 1 FROM pg_catalog.pg_roles r
           WHERE r.rolname IN ('app_runtime','google_auth_lookup')
             AND (
                 NOT has_database_privilege(r.oid,current_database(),'CONNECT')
                 OR has_database_privilege(r.oid,current_database(),'CREATE')
                 OR has_schema_privilege(r.oid,'public','CREATE')
             )
       )
       OR NOT has_schema_privilege('app_runtime','public','USAGE')
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.pg_namespace n
           CROSS JOIN LATERAL pg_catalog.aclexplode(n.nspacl) a
           WHERE n.nspname='public'
             AND a.grantee='google_auth_lookup'::regrole
             AND a.privilege_type IN ('USAGE','CREATE')
       )
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_roles r
           WHERE r.rolname='vervfy_oauth_staging_user'
             AND (r.rolsuper OR r.rolbypassrls)
       )
       OR NOT has_database_privilege(
           'app_runtime',current_database(),'TEMP'
       )
       OR NOT has_database_privilege(
           'google_auth_lookup',current_database(),'TEMP'
       )
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.pg_database d
           CROSS JOIN LATERAL pg_catalog.aclexplode(d.datacl) a
           WHERE d.datname=current_database()
             AND a.grantee IN (
                 'app_runtime'::regrole,'google_auth_lookup'::regrole
             )
             AND a.privilege_type='TEMPORARY'
       )
    THEN
        RAISE EXCEPTION 'Role attributes or Supabase PUBLIC TEMP inheritance are unsafe';
    END IF;

    -- Exact graph: every bootstrapped role has only the known Supabase creator
    -- edge plus its one reviewed Vervfy membership, if any. This rejects extra
    -- grantors, altered options, nested paths, and unrelated memberships.
    IF EXISTS (
        WITH targets(roleid) AS (
            VALUES
                ('vervfy_oauth_staging_user'::regrole::oid),
                ('app_runtime'::regrole::oid),
                ('google_auth_lookup'::regrole::oid),
                ('vervfy_identity_lookup_owner'::regrole::oid),
                ('vervfy_identity_lookup'::regrole::oid),
                ('vervfy_storage_lifecycle_owner'::regrole::oid),
                ('vervfy_storage_cleanup'::regrole::oid),
                ('storage_cleanup_worker'::regrole::oid)
        ),
        expected(roleid,member,grantor,admin_option,inherit_option,set_option) AS (
            SELECT roleid, 'postgres'::regrole::oid, 'supabase_admin'::regrole::oid,
                   true, false, false
            FROM targets
            UNION ALL
            SELECT 'vervfy_identity_lookup_owner'::regrole::oid,
                   'vervfy_oauth_staging_user'::regrole::oid,
                   'postgres'::regrole::oid, false, false, true
            UNION ALL
            SELECT 'vervfy_identity_lookup'::regrole::oid,
                   'google_auth_lookup'::regrole::oid,
                   'postgres'::regrole::oid, false, true, false
            UNION ALL
            SELECT 'vervfy_storage_lifecycle_owner'::regrole::oid,
                   'vervfy_oauth_staging_user'::regrole::oid,
                   'postgres'::regrole::oid, false, false, true
            UNION ALL
            SELECT 'vervfy_storage_cleanup'::regrole::oid,
                   'storage_cleanup_worker'::regrole::oid,
                   'postgres'::regrole::oid, false, true, false
        ),
        actual(roleid,member,grantor,admin_option,inherit_option,set_option) AS (
            SELECT roleid,member,grantor,admin_option,inherit_option,set_option
            FROM pg_catalog.pg_auth_members
            WHERE roleid IN (SELECT roleid FROM targets)
               OR member IN (SELECT roleid FROM targets)
        ),
        differences AS (
            (SELECT * FROM actual EXCEPT SELECT * FROM expected)
            UNION ALL
            (SELECT * FROM expected EXCEPT SELECT * FROM actual)
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Role memberships differ from the exact Supabase/Vervfy graph';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_default_acl d
        CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
        WHERE d.defaclrole='vervfy_oauth_staging_user'::regrole
          AND a.grantee IN (
              0, 'anon'::regrole, 'authenticated'::regrole, 'service_role'::regrole
          )
    ) THEN
        RAISE EXCEPTION 'Migration role has API/PUBLIC default object grants';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_default_acl d
        WHERE d.defaclrole='vervfy_oauth_staging_user'::regrole
          AND d.defaclobjtype='f'
          AND d.defaclnamespace=0
    ) THEN
        RAISE EXCEPTION 'Migration role function defaults are not explicitly hardened';
    END IF;
END
$preflight$;

-- Human-reviewed inventory: provider schemas are retained, never treated as
-- Vervfy objects. Supabase default ACLs are reported but not changed.
SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,
       rolcreaterole,rolreplication,rolconfig
FROM pg_catalog.pg_roles
WHERE rolname IN (
    'vervfy_oauth_staging_user','app_runtime','google_auth_lookup',
    'vervfy_identity_lookup_owner','vervfy_identity_lookup',
    'vervfy_storage_lifecycle_owner','vervfy_storage_cleanup',
    'storage_cleanup_worker','anon','authenticated','service_role',
    'postgres','supabase_admin'
)
ORDER BY rolname;

SELECT roleid::regrole AS granted_role,member::regrole AS member,
       grantor::regrole AS grantor,admin_option,inherit_option,set_option
FROM pg_catalog.pg_auth_members
WHERE roleid IN (
    'vervfy_oauth_staging_user'::regrole,'app_runtime'::regrole,
    'google_auth_lookup'::regrole,'vervfy_identity_lookup_owner'::regrole,
    'vervfy_identity_lookup'::regrole,'vervfy_storage_lifecycle_owner'::regrole,
    'vervfy_storage_cleanup'::regrole,'storage_cleanup_worker'::regrole
)
ORDER BY 1,2,3;

SELECT datname,pg_get_userbyid(datdba) AS owner,datacl
FROM pg_catalog.pg_database WHERE datname=current_database();

SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl
FROM pg_catalog.pg_namespace
WHERE nspname !~ '^pg_' AND nspname<>'information_schema'
ORDER BY nspname;

SELECT defaclrole::regrole AS creator,n.nspname,defaclobjtype,defaclacl
FROM pg_catalog.pg_default_acl d
LEFT JOIN pg_catalog.pg_namespace n ON n.oid=d.defaclnamespace
ORDER BY 1,2,3;

SELECT n.nspname,c.relkind,count(*) AS relations
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
GROUP BY n.nspname,c.relkind
ORDER BY 1,2;

SELECT current_setting('transaction_read_only') AS preflight_read_only,
       current_setting('default_transaction_read_only') AS default_read_only,
       current_setting('row_security') AS row_security,
       current_setting('lock_timeout') AS lock_timeout,
       current_setting('statement_timeout') AS statement_timeout;
ROLLBACK;
