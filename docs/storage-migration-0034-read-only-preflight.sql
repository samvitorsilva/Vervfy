-- Vervfy 0034 production preflight — READ ONLY.
-- Run each SELECT separately in Supabase SQL Editor and retain the results.
-- Stop on missing rows, mismatches, unexpected grants/policies, or an unsupported
-- revision. This supplements; it does not replace the restricted runner checks.
--
-- SQL Editor commonly runs with a privileged postgres identity. These queries
-- cannot prove the runner's login, TLS/CA validation, project URL binding,
-- local migration-chain digest, or execution-time authorization. Do not treat
-- a clean result here as production approval.
--
-- 0034 is forward-only. Existing objects receive reserved_bytes = NULL and
-- block new reservations until a separately approved, complete inventory
-- reconciliation. SQL cannot enumerate provider-side orphans/shared objects.

-- 1. Session identity and server version. The runner requires PostgreSQL 16+,
-- public schema, and its own restricted migration login.
SELECT
    current_database() AS database_name,
    session_user,
    current_user,
    current_schema(),
    current_setting('server_version_num')::integer AS server_version_num,
    current_setting('server_version_num')::integer >= 160000
        AS postgres_16_or_newer;

-- 2. Exactly one approved starting revision is required: 0031 or 0033.
SELECT
    count(*) AS revision_rows,
    array_agg(version_num ORDER BY version_num) AS revisions,
    count(*) = 1
        AND bool_and(version_num IN (
            '0031_cleanup_retry_limits',
            '0033_cleanup_claims_disabled'
        )) AS supported_start_revision
FROM public.alembic_version;

-- 3. Role attributes. Expected: migration LOGIN without elevated attributes;
-- lifecycle owner and cleanup executor NOLOGIN/NOINHERIT; worker LOGIN/
-- NOINHERIT; app_runtime LOGIN/INHERIT. No listed role may be superuser,
-- BYPASSRLS, CREATE privilege, or replication-enabled.
WITH expected(role_name, expected_login, expected_inherit) AS (
    VALUES
        ('vervfy_prod_migrator', true, NULL::boolean),
        ('vervfy_storage_lifecycle_owner', false, false),
        ('vervfy_storage_cleanup', false, false),
        ('storage_cleanup_worker', true, false),
        ('app_runtime', true, true)
)
SELECT
    e.role_name,
    r.rolname IS NOT NULL AS role_exists,
    r.rolcanlogin,
    r.rolinherit,
    r.rolsuper,
    r.rolbypassrls,
    r.rolcreatedb,
    r.rolcreaterole,
    r.rolreplication,
    r.rolcanlogin IS NOT DISTINCT FROM e.expected_login
        AND (e.expected_inherit IS NULL
             OR r.rolinherit IS NOT DISTINCT FROM e.expected_inherit)
        AND NOT COALESCE(r.rolsuper, true)
        AND NOT COALESCE(r.rolbypassrls, true)
        AND NOT COALESCE(r.rolcreatedb, true)
        AND NOT COALESCE(r.rolcreaterole, true)
        AND NOT COALESCE(r.rolreplication, true) AS attributes_match
FROM expected e
LEFT JOIN pg_catalog.pg_roles r ON r.rolname = e.role_name
ORDER BY e.role_name;

-- The runner's migration role additionally needs CONNECT/CREATE on the
-- database and USAGE/CREATE on public. These are effective privilege checks,
-- not proof that SQL Editor is connected as that role.
SELECT
    has_database_privilege(
        'vervfy_prod_migrator', current_database(), 'CONNECT'
    ) AS migrator_database_connect,
    has_database_privilege(
        'vervfy_prod_migrator', current_database(), 'CREATE'
    ) AS migrator_database_create,
    has_schema_privilege(
        'vervfy_prod_migrator', 'public', 'USAGE'
    ) AS migrator_public_usage,
    has_schema_privilege(
        'vervfy_prod_migrator', 'public', 'CREATE'
    ) AS migrator_public_create;

-- 4. Direct role memberships. Review against the production runner's exact
-- graph: migrator may SET (not inherit/admin) lifecycle owner; worker may
-- inherit (not SET/admin) cleanup executor; app_runtime has no memberships.
-- An inert postgres ADMIN-only membership may exist on lifecycle owner or
-- cleanup executor. No other memberships are accepted.
SELECT
    granted.rolname AS granted_role,
    member.rolname AS member_role,
    grantor.rolname AS grantor_role,
    m.inherit_option,
    m.set_option,
    m.admin_option
FROM pg_catalog.pg_auth_members m
JOIN pg_catalog.pg_roles granted ON granted.oid = m.roleid
JOIN pg_catalog.pg_roles member ON member.oid = m.member
JOIN pg_catalog.pg_roles grantor ON grantor.oid = m.grantor
WHERE granted.rolname IN (
        'vervfy_storage_lifecycle_owner',
        'vervfy_storage_cleanup'
    )
   OR member.rolname IN (
        'vervfy_prod_migrator',
        'storage_cleanup_worker',
        'app_runtime'
    )
ORDER BY granted.rolname, member.rolname;

-- 5. Required public table ownership and application RLS. Every required
-- relation must exist and be owned by vervfy_prod_migrator. The four original
-- tenant tables should have ENABLE+FORCE RLS and tenant-isolation policies.
WITH expected(table_name) AS (
    VALUES
        ('users'), ('tracks'), ('favorites'), ('playlists'),
        ('playlist_tracks'), ('upload_jobs'), ('artist_photos'),
        ('track_listens'), ('artist_images'), ('track_cover_cache')
)
SELECT
    e.table_name,
    c.oid IS NOT NULL AS relation_exists,
    pg_catalog.pg_get_userbyid(c.relowner) AS table_owner,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced,
    COALESCE((
        SELECT string_agg(p.policyname, ', ' ORDER BY p.policyname)
        FROM pg_catalog.pg_policies p
        WHERE p.schemaname = 'public' AND p.tablename = e.table_name
    ), '') AS policies,
    pg_catalog.pg_get_userbyid(c.relowner) = 'vervfy_prod_migrator'
        AS expected_owner
FROM expected e
LEFT JOIN pg_catalog.pg_class c
    ON c.relnamespace = pg_catalog.to_regnamespace('public')
   AND c.relname = e.table_name
   AND c.relkind IN ('r', 'p')
ORDER BY e.table_name;

-- Original tenant-table policy details; inspect both USING and WITH CHECK.
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('tracks', 'favorites', 'playlists', 'playlist_tracks')
ORDER BY tablename, policyname;

-- 6. Storage lifecycle ownership, forced RLS, and policies. Inspect every
-- lifecycle table; do not accept unexpected owners or missing forced RLS.
SELECT
    c.relname AS table_name,
    pg_catalog.pg_get_userbyid(c.relowner) AS table_owner,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced,
    COALESCE((
        SELECT string_agg(p.policyname, ', ' ORDER BY p.policyname)
        FROM pg_catalog.pg_policies p
        WHERE p.schemaname = n.nspname AND p.tablename = c.relname
    ), '') AS policies
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'vervfy_storage'
  AND c.relkind IN ('r', 'p')
ORDER BY c.relname;

-- Direct lifecycle-schema grants to the three restricted capability roles.
-- Compare against the runner's reviewed 0029-0031 ACL allowlist; do not infer
-- safety from role names alone.
SELECT
    r.rolname AS grantee,
    'SCHEMA' AS object_type,
    n.nspname::text AS object_name,
    a.privilege_type,
    a.is_grantable
FROM pg_catalog.pg_namespace n
CROSS JOIN LATERAL pg_catalog.aclexplode(
    COALESCE(n.nspacl, pg_catalog.acldefault('n'::"char", n.nspowner))
) a
JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
WHERE n.nspname = 'vervfy_storage'
  AND r.rolname IN (
      'vervfy_storage_lifecycle_owner',
      'vervfy_storage_cleanup',
      'storage_cleanup_worker'
  )
UNION ALL
SELECT
    r.rolname,
    'RELATION',
    n.nspname::text || '.' || c.relname::text,
    a.privilege_type,
    a.is_grantable
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL pg_catalog.aclexplode(
    COALESCE(
        c.relacl,
        pg_catalog.acldefault(
            CASE WHEN c.relkind = 'S' THEN 's'::"char" ELSE 'r'::"char" END,
            c.relowner
        )
    )
) a
JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
WHERE n.nspname = 'vervfy_storage'
  AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
  AND r.rolname IN (
      'vervfy_storage_lifecycle_owner',
      'vervfy_storage_cleanup',
      'storage_cleanup_worker'
  )
UNION ALL
SELECT
    r.rolname,
    'FUNCTION',
    n.nspname::text || '.' || p.proname::text || '(' ||
        pg_catalog.pg_get_function_identity_arguments(p.oid) || ')',
    a.privilege_type,
    a.is_grantable
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
CROSS JOIN LATERAL pg_catalog.aclexplode(
    COALESCE(p.proacl, pg_catalog.acldefault('f'::"char", p.proowner))
) a
JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
WHERE n.nspname = 'vervfy_storage'
  AND r.rolname IN (
      'vervfy_storage_lifecycle_owner',
      'vervfy_storage_cleanup',
      'storage_cleanup_worker'
  )
ORDER BY 1, 2, 3, 4;

-- 7. Immutable production namespace and 0031/0033 cleanup-claim permissions.
-- Namespace values must match the approved production binding exactly and
-- physical_cleanup_enabled must remain false.
SELECT namespace_id::text, environment, endpoint, bucket,
       physical_cleanup_enabled,
       namespace_id::text = '31daf7cc-8563-411f-94c7-944d607d1ef1'
           AND environment = 'production'
           AND endpoint = 'https://llxmskxxchpmeavorusj.supabase.co'
           AND bucket = 'songs'
           AND physical_cleanup_enabled = false AS approved_binding
FROM vervfy_storage.namespaces
WHERE id = 1;

SELECT
    version_num,
    has_function_privilege(
        'vervfy_storage_lifecycle_owner',
        'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
    ) AS owner_can_claim,
    has_function_privilege(
        'vervfy_storage_cleanup',
        'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
    ) AS executor_can_claim,
    has_function_privilege(
        'storage_cleanup_worker',
        'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
    ) AS worker_can_claim,
    has_function_privilege(
        'app_runtime',
        'vervfy_storage.claim_next_cleanup()', 'EXECUTE'
    ) AS app_runtime_can_claim
FROM public.alembic_version;
-- Expected claim privileges: at 0031 (true,true,true,false);
-- at 0033 (true,false,false,false).

-- 8. 0034 must not already be partially installed. Before migration, the
-- quota table and reserved_bytes column should be absent. Existing object rows
-- become unknown-size charges (NULL) after 0034; the last column below is the
-- number requiring evidence-backed reconciliation before reservations work.
SELECT
    pg_catalog.to_regclass('vervfy_storage.quota_policy') IS NULL
        AS quota_policy_absent,
    NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_attribute a
        WHERE a.attrelid = pg_catalog.to_regclass('vervfy_storage.objects')
          AND a.attname = 'reserved_bytes'
          AND a.attnum > 0
          AND NOT a.attisdropped
    ) AS reserved_bytes_absent;

SELECT
    count(*) AS existing_object_rows,
    count(*) FILTER (WHERE classification = 'managed') AS managed_rows,
    count(*) FILTER (WHERE classification = 'legacy') AS legacy_rows,
    count(*) FILTER (WHERE state IN ('reserved', 'uploading', 'deleting'))
        AS in_flight_or_deleting_rows,
    count(*) AS rows_that_will_need_size_reconciliation
FROM vervfy_storage.objects;

-- 0034 initial ceilings are 157286400 bytes (150 MiB) per tenant and
-- 10737418240 bytes (10 GiB) global. All retained rows count; charges are not
-- automatically released. Capacity and provider inventory require separate
-- review; these SQL checks do not prove bucket completeness or actual sizes.
