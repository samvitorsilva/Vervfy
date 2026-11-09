-- One SELECT of PostgreSQL catalog metadata. The guarded Python runner opens
-- a READ ONLY transaction before executing this file and emits only its
-- curated JSON result. Never run this query against production.
SELECT jsonb_build_object(
    'server_version', pg_catalog.current_setting('server_version'),
    'server_version_num', pg_catalog.current_setting('server_version_num'),
    'database', pg_catalog.current_database(),
    'session_role', session_user,
    'effective_role', current_user,
    'database_owner', (
        SELECT CASE WHEN owner.rolname IN (
            'vervfy_staging_bootstrap',
            'vervfy_oauth_staging_user',
            'app_runtime',
            'google_auth_lookup',
            'vervfy_identity_lookup_owner',
            'vervfy_identity_lookup',
            'vervfy_storage_lifecycle_owner',
            'vervfy_storage_cleanup',
            'storage_cleanup_worker'
        ) THEN owner.rolname ELSE 'OTHER' END
        FROM pg_catalog.pg_database AS database
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = database.datdba
        WHERE database.datname = pg_catalog.current_database()
    ),
    'current_schema', pg_catalog.current_schema(),
    'tls_enabled', (
        SELECT ssl
        FROM pg_catalog.pg_stat_ssl
        WHERE pid = pg_catalog.pg_backend_pid()
    ),
    'gen_random_uuid_available',
        pg_catalog.to_regprocedure('pg_catalog.gen_random_uuid()') IS NOT NULL,
    'alembic_version_exists',
        pg_catalog.to_regclass('public.alembic_version') IS NOT NULL,
    'auth_schema_exists',
        pg_catalog.to_regnamespace('vervfy_auth') IS NOT NULL,
    'storage_schema_exists',
        pg_catalog.to_regnamespace('vervfy_storage') IS NOT NULL,
    'has_non_system_relations',
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_class AS relation
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname NOT IN ('pg_catalog', 'information_schema')
              AND namespace.nspname !~ '^pg_'
              AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ),
    'roles', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'name', role.rolname,
            'login', role.rolcanlogin,
            'inherit', role.rolinherit,
            'superuser', role.rolsuper,
            'bypass_rls', role.rolbypassrls,
            'create_db', role.rolcreatedb,
            'create_role', role.rolcreaterole,
            'replication', role.rolreplication
        ) ORDER BY role.rolname)
        FROM pg_catalog.pg_roles AS role
        WHERE role.rolname IN (
            'vervfy_staging_bootstrap',
            'vervfy_oauth_staging_user',
            'app_runtime',
            'google_auth_lookup',
            'vervfy_identity_lookup_owner',
            'vervfy_identity_lookup',
            'vervfy_storage_lifecycle_owner',
            'vervfy_storage_cleanup',
            'storage_cleanup_worker'
        )
    ), '[]'::jsonb),
    'memberships', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'granted_role', CASE WHEN granted.rolname IN (
                'vervfy_staging_bootstrap',
                'vervfy_oauth_staging_user',
                'app_runtime',
                'google_auth_lookup',
                'vervfy_identity_lookup_owner',
                'vervfy_identity_lookup',
                'vervfy_storage_lifecycle_owner',
                'vervfy_storage_cleanup',
                'storage_cleanup_worker'
            ) THEN granted.rolname ELSE 'OTHER' END,
            'member_role', CASE WHEN member.rolname IN (
                'vervfy_staging_bootstrap',
                'vervfy_oauth_staging_user',
                'app_runtime',
                'google_auth_lookup',
                'vervfy_identity_lookup_owner',
                'vervfy_identity_lookup',
                'vervfy_storage_lifecycle_owner',
                'vervfy_storage_cleanup',
                'storage_cleanup_worker'
            ) THEN member.rolname ELSE 'OTHER' END,
            'inherit', membership.inherit_option,
            'set', membership.set_option,
            'admin', membership.admin_option
        ) ORDER BY granted.rolname, member.rolname)
        FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted ON granted.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
        WHERE granted.rolname IN (
            'vervfy_staging_bootstrap',
            'vervfy_oauth_staging_user',
            'app_runtime',
            'google_auth_lookup',
            'vervfy_identity_lookup_owner',
            'vervfy_identity_lookup',
            'vervfy_storage_lifecycle_owner',
            'vervfy_storage_cleanup',
            'storage_cleanup_worker'
        ) OR member.rolname IN (
            'vervfy_staging_bootstrap',
            'vervfy_oauth_staging_user',
            'app_runtime',
            'google_auth_lookup',
            'vervfy_identity_lookup_owner',
            'vervfy_identity_lookup',
            'vervfy_storage_lifecycle_owner',
            'vervfy_storage_cleanup',
            'storage_cleanup_worker'
        )
    ), '[]'::jsonb),
    'database_privileges', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'name', role.rolname,
            'connect', pg_catalog.has_database_privilege(
                role.oid, database.datname, 'CONNECT'),
            'create', pg_catalog.has_database_privilege(
                role.oid, database.datname, 'CREATE'),
            'temporary', pg_catalog.has_database_privilege(
                role.oid, database.datname, 'TEMP')
        ) ORDER BY role.rolname)
        FROM pg_catalog.pg_roles AS role
        CROSS JOIN pg_catalog.pg_database AS database
        WHERE database.datname = pg_catalog.current_database()
          AND role.rolname IN (
              'vervfy_staging_bootstrap',
              'vervfy_oauth_staging_user',
              'app_runtime',
              'google_auth_lookup',
              'vervfy_identity_lookup_owner',
              'vervfy_identity_lookup',
              'vervfy_storage_lifecycle_owner',
              'vervfy_storage_cleanup',
              'storage_cleanup_worker'
          )
    ), '[]'::jsonb),
    'schema_owners', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'schema', expected.schema_name,
            'owner', CASE WHEN owner.rolname IN (
                'vervfy_staging_bootstrap',
                'pg_database_owner',
                'vervfy_oauth_staging_user',
                'app_runtime',
                'google_auth_lookup',
                'vervfy_identity_lookup_owner',
                'vervfy_identity_lookup',
                'vervfy_storage_lifecycle_owner',
                'vervfy_storage_cleanup',
                'storage_cleanup_worker'
            ) THEN owner.rolname ELSE 'OTHER' END
        ) ORDER BY expected.schema_name)
        FROM (VALUES ('public'), ('vervfy_auth'), ('vervfy_storage'))
            AS expected(schema_name)
        LEFT JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.nspname = expected.schema_name
        LEFT JOIN pg_catalog.pg_roles AS owner ON owner.oid = namespace.nspowner
    ), '[]'::jsonb),
    'schema_privileges', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'role', role.rolname,
            'schema', expected.schema_name,
            'usage', CASE WHEN namespace.oid IS NULL THEN NULL
                ELSE pg_catalog.has_schema_privilege(
                    role.oid, namespace.oid, 'USAGE') END,
            'create', CASE WHEN namespace.oid IS NULL THEN NULL
                ELSE pg_catalog.has_schema_privilege(
                    role.oid, namespace.oid, 'CREATE') END
        ) ORDER BY role.rolname, expected.schema_name)
        FROM pg_catalog.pg_roles AS role
        CROSS JOIN (VALUES ('public'), ('vervfy_auth'), ('vervfy_storage'))
            AS expected(schema_name)
        LEFT JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.nspname = expected.schema_name
        WHERE role.rolname IN (
            'vervfy_staging_bootstrap',
            'vervfy_oauth_staging_user',
            'app_runtime',
            'google_auth_lookup',
            'vervfy_identity_lookup_owner',
            'vervfy_identity_lookup',
            'vervfy_storage_lifecycle_owner',
            'vervfy_storage_cleanup',
            'storage_cleanup_worker'
        )
    ), '[]'::jsonb),
    'public_database_privileges', COALESCE((
        SELECT jsonb_agg(DISTINCT acl.privilege_type ORDER BY acl.privilege_type)
        FROM pg_catalog.pg_database AS database
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(database.datacl, pg_catalog.acldefault('d', database.datdba))
        ) AS acl
        WHERE database.datname = pg_catalog.current_database()
          AND acl.grantee = 0
    ), '[]'::jsonb),
    'public_schema_privileges', COALESCE((
        SELECT jsonb_agg(DISTINCT acl.privilege_type ORDER BY acl.privilege_type)
        FROM pg_catalog.pg_namespace AS namespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(namespace.nspacl, pg_catalog.acldefault('n', namespace.nspowner))
        ) AS acl
        WHERE namespace.nspname = 'public'
          AND acl.grantee = 0
    ), '[]'::jsonb),
    'relations', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'schema', expected.schema_name,
            'name', expected.relation_name,
            'exists', relation.oid IS NOT NULL,
            'owner', CASE WHEN relation.oid IS NULL THEN NULL
                WHEN owner.rolname IN (
                    'vervfy_staging_bootstrap',
                    'vervfy_oauth_staging_user',
                    'app_runtime',
                    'google_auth_lookup',
                    'vervfy_identity_lookup_owner',
                    'vervfy_identity_lookup',
                    'vervfy_storage_lifecycle_owner',
                    'vervfy_storage_cleanup',
                    'storage_cleanup_worker'
                ) THEN owner.rolname ELSE 'OTHER' END,
            'row_security', relation.relrowsecurity,
            'force_row_security', relation.relforcerowsecurity
        ) ORDER BY expected.schema_name, expected.relation_name)
        FROM (VALUES
            ('public', 'tracks'),
            ('public', 'favorites'),
            ('public', 'playlists'),
            ('public', 'playlist_tracks'),
            ('public', 'upload_jobs'),
            ('public', 'artist_photos'),
            ('public', 'track_listens'),
            ('public', 'provider_identities'),
            ('vervfy_storage', 'namespaces'),
            ('vervfy_storage', 'objects'),
            ('vervfy_storage', 'cleanup_jobs')
        ) AS expected(schema_name, relation_name)
        LEFT JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.nspname = expected.schema_name
        LEFT JOIN pg_catalog.pg_class AS relation
          ON relation.relnamespace = namespace.oid
         AND relation.relname = expected.relation_name
        LEFT JOIN pg_catalog.pg_roles AS owner ON owner.oid = relation.relowner
    ), '[]'::jsonb),
    'policies', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'schema', namespace.nspname,
            'table', relation.relname,
            'name', policy.polname,
            'command', CASE policy.polcmd
                WHEN '*' THEN 'ALL'
                WHEN 'r' THEN 'SELECT'
                WHEN 'a' THEN 'INSERT'
                WHEN 'w' THEN 'UPDATE'
                WHEN 'd' THEN 'DELETE'
            END,
            'permissive', policy.polpermissive,
            'roles', ARRAY(
                SELECT CASE WHEN policy_role.role_oid = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(policy_role.role_oid) END
                FROM unnest(policy.polroles) AS policy_role(role_oid)
                ORDER BY 1
            ),
            'using_present', policy.polqual IS NOT NULL,
            'check_present', policy.polwithcheck IS NOT NULL
        ) ORDER BY namespace.nspname, relation.relname, policy.polname)
        FROM pg_catalog.pg_policy AS policy
        JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE (namespace.nspname, relation.relname) IN (
            ('public', 'tracks'),
            ('public', 'favorites'),
            ('public', 'playlists'),
            ('public', 'playlist_tracks'),
            ('public', 'upload_jobs'),
            ('public', 'artist_photos'),
            ('public', 'track_listens'),
            ('public', 'provider_identities'),
            ('vervfy_storage', 'namespaces'),
            ('vervfy_storage', 'objects'),
            ('vervfy_storage', 'cleanup_jobs')
        )
    ), '[]'::jsonb),
    'security_definer_functions', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'schema', namespace.nspname,
            'name', procedure.proname,
            'arguments', pg_catalog.pg_get_function_identity_arguments(procedure.oid),
            'owner', pg_catalog.pg_get_userbyid(procedure.proowner),
            'security_definer', procedure.prosecdef,
            'search_path', (
                SELECT split_part(config, '=', 2)
                FROM unnest(COALESCE(procedure.proconfig, ARRAY[]::text[])) AS config
                WHERE left(config, 12) = 'search_path='
                LIMIT 1
            ),
            'public_execute', EXISTS (
                SELECT 1
                FROM pg_catalog.aclexplode(COALESCE(
                    procedure.proacl,
                    pg_catalog.acldefault('f', procedure.proowner)
                )) AS acl
                WHERE acl.grantee = 0
                  AND acl.privilege_type = 'EXECUTE'
            ),
            'explicit_execute_grantees', COALESCE((
                SELECT jsonb_agg(DISTINCT grantee.rolname ORDER BY grantee.rolname)
                FROM pg_catalog.aclexplode(COALESCE(
                    procedure.proacl,
                    pg_catalog.acldefault('f', procedure.proowner)
                )) AS acl
                JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
                WHERE acl.privilege_type = 'EXECUTE'
                  AND acl.grantee <> procedure.proowner
                  AND grantee.rolname IN (
                      'vervfy_oauth_staging_user',
                      'app_runtime',
                      'google_auth_lookup',
                      'vervfy_identity_lookup_owner',
                      'vervfy_identity_lookup',
                      'vervfy_storage_lifecycle_owner',
                      'vervfy_storage_cleanup',
                      'storage_cleanup_worker'
                  )
            ), '[]'::jsonb),
            'unexpected_explicit_execute_grantee_count', (
                SELECT count(DISTINCT acl.grantee)
                FROM pg_catalog.aclexplode(COALESCE(
                    procedure.proacl,
                    pg_catalog.acldefault('f', procedure.proowner)
                )) AS acl
                JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
                WHERE acl.privilege_type = 'EXECUTE'
                  AND acl.grantee <> procedure.proowner
                  AND grantee.rolname NOT IN (
                      'vervfy_oauth_staging_user',
                      'app_runtime',
                      'google_auth_lookup',
                      'vervfy_identity_lookup_owner',
                      'vervfy_identity_lookup',
                      'vervfy_storage_lifecycle_owner',
                      'vervfy_storage_cleanup',
                      'storage_cleanup_worker'
                  )
            ),
            'effective_execute_roles', COALESCE((
                SELECT jsonb_agg(role.rolname ORDER BY role.rolname)
                FROM pg_catalog.pg_roles AS role
                WHERE role.rolname IN (
                    'vervfy_oauth_staging_user',
                    'app_runtime',
                    'google_auth_lookup',
                    'vervfy_identity_lookup_owner',
                    'vervfy_identity_lookup',
                    'vervfy_storage_lifecycle_owner',
                    'vervfy_storage_cleanup',
                    'storage_cleanup_worker'
                )
                  AND pg_catalog.has_function_privilege(
                      role.oid, procedure.oid, 'EXECUTE')
            ), '[]'::jsonb)
        ) ORDER BY namespace.nspname, procedure.proname,
                   pg_catalog.pg_get_function_identity_arguments(procedure.oid))
        FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = procedure.pronamespace
        WHERE procedure.prosecdef
          AND namespace.nspname IN ('public', 'vervfy_auth', 'vervfy_storage')
    ), '[]'::jsonb),
    'identity_column_privileges', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'role', role.rolname,
            'column', attribute.attname,
            'select', pg_catalog.has_column_privilege(
                role.oid, relation.oid, attribute.attnum, 'SELECT')
        ) ORDER BY role.rolname, attribute.attname)
        FROM pg_catalog.pg_roles AS role
        CROSS JOIN pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        JOIN pg_catalog.pg_attribute AS attribute
          ON attribute.attrelid = relation.oid
         AND attribute.attnum > 0
         AND NOT attribute.attisdropped
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'provider_identities'
          AND role.rolname IN (
              'vervfy_identity_lookup_owner',
              'google_auth_lookup',
              'app_runtime'
          )
    ), '[]'::jsonb),
    'extensions', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'name', extension.extname,
            'version', extension.extversion,
            'schema', namespace.nspname
        ) ORDER BY extension.extname)
        FROM pg_catalog.pg_extension AS extension
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = extension.extnamespace
    ), '[]'::jsonb)
);
