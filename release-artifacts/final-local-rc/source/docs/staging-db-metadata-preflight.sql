-- READ-ONLY METADATA PROPOSAL — NOT RUN AGAINST A HOSTED DATABASE.
-- No account rows, provider identities, object paths, secrets, or function
-- definitions are selected. Review and sanitize all output before sharing.
\set ON_ERROR_STOP on
BEGIN READ ONLY;

SELECT current_setting('server_version') AS server_version,
       current_setting('server_version_num') AS server_version_num,
       current_database() AS database_name,
       session_user AS session_role,
       current_user AS effective_role,
       current_schema() AS current_schema,
       (SELECT ssl
          FROM pg_catalog.pg_stat_ssl
         WHERE pid = pg_catalog.pg_backend_pid()) AS tls_enabled;

SELECT pg_catalog.pg_get_userbyid(d.datdba) AS database_owner,
       has_database_privilege(current_user, d.datname, 'CONNECT') AS current_role_connect,
       has_database_privilege(current_user, d.datname, 'CREATE') AS current_role_create,
       has_database_privilege(current_user, d.datname, 'TEMP') AS current_role_temp
  FROM pg_catalog.pg_database AS d
 WHERE d.datname = current_database();

SELECT to_regclass('public.alembic_version') IS NOT NULL AS alembic_version_exists,
       to_regnamespace('vervfy_auth') IS NOT NULL AS auth_schema_exists,
       to_regnamespace('vervfy_storage') IS NOT NULL AS storage_schema_exists,
       EXISTS (
           SELECT 1
             FROM pg_catalog.pg_class AS c
             JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname !~ '^pg_'
              AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
       ) AS has_non_system_relations;

SELECT to_regclass('public.alembic_version') IS NOT NULL AS has_alembic_version \gset
\if :has_alembic_version
SELECT version_num AS alembic_revision FROM public.alembic_version;
\else
\echo 'No public.alembic_version table'
\endif

WITH expected(role_name) AS (
    VALUES
      ('vervfy_oauth_staging_user'),
      ('app_runtime'),
      ('google_auth_lookup'),
      ('vervfy_identity_lookup_owner'),
      ('vervfy_identity_lookup'),
      ('vervfy_storage_lifecycle_owner'),
      ('vervfy_storage_cleanup'),
      ('storage_cleanup_worker')
)
SELECT expected.role_name,
       roles.rolcanlogin,
       roles.rolinherit,
       roles.rolsuper,
       roles.rolbypassrls,
       roles.rolcreatedb,
       roles.rolcreaterole,
       roles.rolreplication,
       CASE WHEN roles.oid IS NULL THEN NULL
            ELSE has_database_privilege(roles.oid, current_database(), 'CONNECT') END AS database_connect,
       CASE WHEN roles.oid IS NULL THEN NULL
            ELSE has_database_privilege(roles.oid, current_database(), 'CREATE') END AS database_create,
       CASE WHEN roles.oid IS NULL THEN NULL
            ELSE has_database_privilege(roles.oid, current_database(), 'TEMP') END AS database_temp,
       CASE WHEN roles.oid IS NULL THEN NULL
            ELSE has_schema_privilege(roles.oid, 'public', 'USAGE') END AS public_schema_usage,
       CASE WHEN roles.oid IS NULL THEN NULL
            ELSE has_schema_privilege(roles.oid, 'public', 'CREATE') END AS public_schema_create
  FROM expected
  LEFT JOIN pg_catalog.pg_roles AS roles ON roles.rolname = expected.role_name
 ORDER BY expected.role_name;

WITH expected(role_name) AS (
    VALUES
      ('vervfy_oauth_staging_user'),
      ('app_runtime'),
      ('google_auth_lookup'),
      ('vervfy_identity_lookup_owner'),
      ('vervfy_identity_lookup'),
      ('vervfy_storage_lifecycle_owner'),
      ('vervfy_storage_cleanup'),
      ('storage_cleanup_worker')
)
SELECT granted.rolname AS granted_role,
       member.rolname AS member_role,
       membership.inherit_option,
       membership.set_option,
       membership.admin_option
  FROM pg_catalog.pg_auth_members AS membership
  JOIN pg_catalog.pg_roles AS granted ON granted.oid = membership.roleid
  JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
 WHERE granted.rolname IN (SELECT role_name FROM expected)
    OR member.rolname IN (SELECT role_name FROM expected)
 ORDER BY granted.rolname, member.rolname;

WITH capabilities(role_name, allowed_member) AS (
    VALUES
      ('vervfy_identity_lookup_owner', 'vervfy_oauth_staging_user'),
      ('vervfy_identity_lookup', 'google_auth_lookup'),
      ('vervfy_storage_lifecycle_owner', 'vervfy_oauth_staging_user'),
      ('vervfy_storage_cleanup', 'storage_cleanup_worker')
)
SELECT capabilities.role_name,
       count(roles.oid) FILTER (
           WHERE roles.rolname <> capabilities.role_name
             AND roles.rolname <> capabilities.allowed_member
             AND NOT roles.rolsuper
             AND (pg_has_role(roles.oid, capability.oid, 'USAGE')
                  OR pg_has_role(roles.oid, capability.oid, 'SET'))
       ) AS unexpected_effective_membership_count
  FROM capabilities
  LEFT JOIN pg_catalog.pg_roles AS capability
    ON capability.rolname = capabilities.role_name
 CROSS JOIN pg_catalog.pg_roles AS roles
 GROUP BY capabilities.role_name
 ORDER BY capabilities.role_name;

-- Count only PUBLIC ACL/default-ACL exposure; do not emit unrelated ACL text.
SELECT COALESCE(bool_or(acl.privilege_type = 'CONNECT'), false) AS public_database_connect,
       COALESCE(bool_or(acl.privilege_type = 'CREATE'), false) AS public_database_create,
       COALESCE(bool_or(acl.privilege_type = 'TEMPORARY'), false) AS public_database_temp
  FROM pg_catalog.pg_database AS d
 CROSS JOIN LATERAL aclexplode(
       COALESCE(d.datacl, acldefault('d', d.datdba))
  ) AS acl
 WHERE d.datname = current_database()
   AND acl.grantee = 0;

SELECT COALESCE(bool_or(acl.privilege_type = 'USAGE'), false) AS public_schema_usage,
       COALESCE(bool_or(acl.privilege_type = 'CREATE'), false) AS public_schema_create
  FROM pg_catalog.pg_namespace AS n
 CROSS JOIN LATERAL aclexplode(
       COALESCE(n.nspacl, acldefault('n', n.nspowner))
  ) AS acl
 WHERE n.nspname = 'public'
   AND acl.grantee = 0;

SELECT count(*) FILTER (WHERE acl.grantee = 0) AS public_default_acl_entries,
       count(*) FILTER (
           WHERE roles.rolname IN (
               'vervfy_identity_lookup_owner',
               'vervfy_identity_lookup',
               'vervfy_storage_lifecycle_owner',
               'vervfy_storage_cleanup',
               'storage_cleanup_worker'
           )
       ) AS capability_default_acl_entries
  FROM pg_catalog.pg_default_acl AS defaults
 CROSS JOIN LATERAL aclexplode(defaults.defaclacl) AS acl
  LEFT JOIN pg_catalog.pg_roles AS roles ON roles.oid = acl.grantee
 WHERE acl.grantee = 0
    OR roles.rolname IN (
        'vervfy_identity_lookup_owner',
        'vervfy_identity_lookup',
        'vervfy_storage_lifecycle_owner',
        'vervfy_storage_cleanup',
        'storage_cleanup_worker'
    )
    OR defaults.defaclrole IN (
        SELECT oid FROM pg_catalog.pg_roles
         WHERE rolname IN (
             'vervfy_identity_lookup_owner',
             'vervfy_identity_lookup',
             'vervfy_storage_lifecycle_owner',
             'vervfy_storage_cleanup',
             'storage_cleanup_worker'
         )
    );

ROLLBACK;
