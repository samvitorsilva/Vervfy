\set ON_ERROR_STOP on

-- Fail before setup unless this is the expected empty staging target.
SELECT current_database() = 'vervfy_oauth_staging'
   AND session_user = 'vervfy_oauth_staging_user'
   AND current_user = 'vervfy_oauth_staging_user'
   AND current_schema() = 'public'
   AND current_setting('server_version_num')::integer / 10000 = 18
   AND to_regclass('public.alembic_version') IS NULL
   AND NOT EXISTS (
       SELECT 1
       FROM pg_tables
       WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
         AND schemaname !~ '^pg_'
   ) AS staging_target_ok
\gset

\if :staging_target_ok
\else
  \echo Refusing to run: staging identity, PostgreSQL version, or empty-schema check failed.
  \quit 3
\endif

-- Session-local snapshot; survives the test transaction's ROLLBACK.
CREATE TEMP TABLE oauth_role_test_acl_baseline
ON COMMIT PRESERVE ROWS AS
SELECT d.datacl AS database_acl, n.nspacl AS public_schema_acl
FROM pg_database d
CROSS JOIN pg_namespace n
WHERE d.datname = current_database()
  AND n.nspname = 'public';

-- Preserve a success/failure result outside the guarded subtransaction.
CREATE TEMP TABLE oauth_role_test_status (
    succeeded boolean NOT NULL,
    failure text
) ON COMMIT PRESERVE ROWS;

INSERT INTO oauth_role_test_status VALUES (false, NULL);

-- Record the exact ACL baseline for comparison after rollback.
TABLE pg_temp.oauth_role_test_acl_baseline;

BEGIN;

-- Any provisioning/assertion failure is caught here. The inner exception
-- block rolls back its changes; status records failure for the final verdict.
DO $$
DECLARE
    migration_oid oid;
    runtime_oid oid;
    lookup_login_oid oid;
    owner_oid oid;
    executor_oid oid;
    failure_message text;
BEGIN
    BEGIN
        IF current_database() <> 'vervfy_oauth_staging'
           OR session_user <> 'vervfy_oauth_staging_user'
           OR current_user <> 'vervfy_oauth_staging_user'
           OR current_schema() IS DISTINCT FROM 'public'
           OR current_setting('server_version_num')::integer / 10000 <> 18 THEN
            RAISE EXCEPTION 'Staging identity/schema/version mismatch';
        END IF;

        IF to_regclass('public.alembic_version') IS NOT NULL
           OR EXISTS (
               SELECT 1
               FROM pg_tables
               WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                 AND schemaname !~ '^pg_'
           ) THEN
            RAISE EXCEPTION 'Application tables or Alembic revision found';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_roles
            WHERE rolname = current_user
              AND rolcreaterole
              AND NOT rolsuper
              AND NOT rolbypassrls
        ) THEN
            RAISE EXCEPTION 'Migration login role attributes do not match';
        END IF;

        IF NOT has_database_privilege(current_user, current_database(), 'CREATE')
           OR NOT has_schema_privilege(current_user, 'public', 'CREATE') THEN
            RAISE EXCEPTION 'Migration login lacks required database/schema CREATE';
        END IF;

        IF EXISTS (
            SELECT 1
            FROM pg_roles
            WHERE rolname IN (
                'app_runtime',
                'google_auth_lookup',
                'vervfy_identity_lookup_owner',
                'vervfy_identity_lookup'
            )
        ) THEN
            RAISE EXCEPTION 'A proposed role already exists; inspect staging';
        END IF;

        EXECUTE 'CREATE ROLE app_runtime LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION';
        EXECUTE 'CREATE ROLE google_auth_lookup LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION';
        EXECUTE 'CREATE ROLE vervfy_identity_lookup_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION';
        EXECUTE 'CREATE ROLE vervfy_identity_lookup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION';

        -- Remove PostgreSQL's default PUBLIC database access, then grant
        -- CONNECT only to the staging migration and application logins.
        EXECUTE 'REVOKE CONNECT, TEMPORARY ON DATABASE vervfy_oauth_staging FROM PUBLIC';
        EXECUTE 'GRANT CONNECT ON DATABASE vervfy_oauth_staging TO vervfy_oauth_staging_user, app_runtime, google_auth_lookup';

        -- No PUBLIC privileges on public schema. Migration needs CREATE/USAGE;
        -- application runtime needs USAGE only.
        EXECUTE 'REVOKE ALL ON SCHEMA public FROM PUBLIC';
        EXECUTE 'GRANT USAGE, CREATE ON SCHEMA public TO vervfy_oauth_staging_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO app_runtime';

        -- PostgreSQL 18's creator membership is retained; this adds the
        -- separate self-granted SET-enabled membership migration 0022 needs.
        EXECUTE 'GRANT vervfy_identity_lookup_owner TO vervfy_oauth_staging_user WITH ADMIN FALSE, INHERIT FALSE, SET TRUE';

        -- Lookup login inherits EXECUTE capability but cannot SET ROLE to it.
        EXECUTE 'GRANT vervfy_identity_lookup TO google_auth_lookup WITH ADMIN FALSE, INHERIT TRUE, SET FALSE';

        SELECT oid INTO migration_oid
        FROM pg_roles WHERE rolname = 'vervfy_oauth_staging_user';
        SELECT oid INTO runtime_oid
        FROM pg_roles WHERE rolname = 'app_runtime';
        SELECT oid INTO lookup_login_oid
        FROM pg_roles WHERE rolname = 'google_auth_lookup';
        SELECT oid INTO owner_oid
        FROM pg_roles WHERE rolname = 'vervfy_identity_lookup_owner';
        SELECT oid INTO executor_oid
        FROM pg_roles WHERE rolname = 'vervfy_identity_lookup';

        -- Match migration 0022's owner-role membership guards exactly.
        IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = owner_oid) THEN
            RAISE EXCEPTION 'Lookup-owner role is itself a member of another role';
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_auth_members
            WHERE roleid = owner_oid AND member <> migration_oid
        ) THEN
            RAISE EXCEPTION 'Lookup-owner has a member other than current_user';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_auth_members
            WHERE roleid = owner_oid
              AND member = migration_oid
              AND grantor = migration_oid
              AND set_option
              AND NOT inherit_option
              AND NOT admin_option
        ) THEN
            RAISE EXCEPTION 'Self-granted owner membership options are incorrect';
        END IF;

        IF NOT pg_has_role(current_user, owner_oid, 'MEMBER')
           OR NOT pg_has_role(current_user, owner_oid, 'SET') THEN
            RAISE EXCEPTION 'Migration login lacks effective membership/SET on owner role';
        END IF;

        -- Both capability roles must satisfy migration 0022's role checks.
        IF (
            SELECT count(*) FROM pg_roles
            WHERE rolname IN (
                'vervfy_identity_lookup_owner', 'vervfy_identity_lookup'
            )
              AND NOT rolcanlogin
              AND NOT rolsuper
              AND NOT rolbypassrls
              AND NOT rolcreatedb
              AND NOT rolcreaterole
              AND NOT rolreplication
              AND NOT rolinherit
        ) <> 2 THEN
            RAISE EXCEPTION 'Capability role attributes are incorrect';
        END IF;

        -- App credentials are separate, non-privileged, non-inheriting logins.
        IF (
            SELECT count(*) FROM pg_roles
            WHERE rolname IN ('app_runtime', 'google_auth_lookup')
              AND rolcanlogin
              AND NOT rolsuper
              AND NOT rolbypassrls
              AND NOT rolcreatedb
              AND NOT rolcreaterole
              AND NOT rolreplication
              AND NOT rolinherit
        ) <> 2 THEN
            RAISE EXCEPTION 'Application login role attributes are unsafe';
        END IF;

        -- Lookup login inherits executor privileges only, without SET/admin,
        -- with no nested membership path from another login or role.
        IF (SELECT count(*) FROM pg_auth_members
            WHERE roleid = executor_oid) <> 1
           OR NOT EXISTS (
            SELECT 1 FROM pg_auth_members
            WHERE roleid = executor_oid
              AND member = lookup_login_oid
              AND inherit_option
              AND NOT set_option
              AND NOT admin_option
        )
           OR EXISTS (
            SELECT 1 FROM pg_auth_members
            WHERE (member = lookup_login_oid AND roleid <> executor_oid)
               OR roleid = lookup_login_oid
        )
           OR EXISTS (
            SELECT 1 FROM pg_roles r
            WHERE r.oid NOT IN (executor_oid, lookup_login_oid)
              AND NOT r.rolsuper
              AND (pg_has_role(r.oid, executor_oid, 'USAGE')
                   OR pg_has_role(r.oid, executor_oid, 'SET'))
        )
           OR NOT pg_has_role(lookup_login_oid, executor_oid, 'USAGE')
           OR pg_has_role(lookup_login_oid, executor_oid, 'SET')
           OR pg_has_role(lookup_login_oid, owner_oid, 'MEMBER')
           OR pg_has_role(lookup_login_oid, migration_oid, 'MEMBER') THEN
            RAISE EXCEPTION 'Google lookup login has unexpected role access';
        END IF;

        -- Runtime has no membership in the capability, migration, or lookup
        -- roles; lookup login is not a member of runtime.
        IF pg_has_role(runtime_oid, owner_oid, 'MEMBER')
           OR pg_has_role(runtime_oid, executor_oid, 'MEMBER')
           OR pg_has_role(runtime_oid, migration_oid, 'MEMBER')
           OR pg_has_role(runtime_oid, lookup_login_oid, 'MEMBER') THEN
            RAISE EXCEPTION 'app_runtime has unexpected role membership';
        END IF;

        -- Effective database/schema rights: no PUBLIC access, no app CREATE
        -- or TEMP; runtime alone has public-schema USAGE.
        IF NOT has_database_privilege(runtime_oid, current_database(), 'CONNECT')
           OR NOT has_database_privilege(lookup_login_oid, current_database(), 'CONNECT')
           OR has_database_privilege(runtime_oid, current_database(), 'CREATE')
           OR has_database_privilege(lookup_login_oid, current_database(), 'CREATE')
           OR has_database_privilege(runtime_oid, current_database(), 'TEMPORARY')
           OR has_database_privilege(lookup_login_oid, current_database(), 'TEMPORARY')
           OR has_schema_privilege(runtime_oid, 'public', 'CREATE')
           OR has_schema_privilege(lookup_login_oid, 'public', 'CREATE')
           OR NOT has_schema_privilege(runtime_oid, 'public', 'USAGE')
           OR has_schema_privilege(lookup_login_oid, 'public', 'USAGE') THEN
            RAISE EXCEPTION 'Application database/schema privileges are unexpected';
        END IF;

        IF EXISTS (
            SELECT 1
            FROM pg_database d
            CROSS JOIN LATERAL aclexplode(
                COALESCE(d.datacl, acldefault('d', d.datdba))
            ) a
            WHERE d.datname = current_database()
              AND a.grantee = 0
              AND a.privilege_type IN ('CONNECT', 'TEMPORARY')
        ) THEN
            RAISE EXCEPTION 'PUBLIC retains database CONNECT or TEMPORARY';
        END IF;

        IF EXISTS (
            SELECT 1
            FROM pg_namespace n
            CROSS JOIN LATERAL aclexplode(
                COALESCE(n.nspacl, acldefault('n', n.nspowner))
            ) a
            WHERE n.nspname = 'public'
              AND a.grantee = 0
        ) THEN
            RAISE EXCEPTION 'PUBLIC retains a public-schema privilege';
        END IF;

        UPDATE pg_temp.oauth_role_test_status
        SET succeeded = true, failure = NULL;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS failure_message = MESSAGE_TEXT;
        UPDATE pg_temp.oauth_role_test_status
        SET succeeded = false, failure = failure_message;
    END;
END
$$;

-- Capture the result before rolling back the status row.
SELECT succeeded AS provisioning_succeeded,
       COALESCE(failure, '') AS provisioning_failure
FROM pg_temp.oauth_role_test_status
\gset

\echo provisioning_succeeded=:provisioning_succeeded
\echo provisioning_failure=:provisioning_failure

-- Mandatory: never replace with COMMIT.
ROLLBACK;

-- These must all be true after rollback, and the ACL arrays must exactly
-- match the session-local pre-test snapshot.
SELECT
    NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = ANY (ARRAY[
            'app_runtime', 'google_auth_lookup',
            'vervfy_identity_lookup_owner', 'vervfy_identity_lookup'
        ])
    ) AS all_four_roles_absent,
    NOT EXISTS (
        SELECT 1
        FROM pg_auth_members m
        JOIN pg_roles granted ON granted.oid = m.roleid
        JOIN pg_roles member ON member.oid = m.member
        WHERE granted.rolname = ANY (ARRAY[
            'app_runtime', 'google_auth_lookup',
            'vervfy_identity_lookup_owner', 'vervfy_identity_lookup'
        ])
           OR member.rolname = ANY (ARRAY[
            'app_runtime', 'google_auth_lookup',
            'vervfy_identity_lookup_owner', 'vervfy_identity_lookup'
        ])
    ) AS no_test_memberships_remain,
    d.datacl IS NOT DISTINCT FROM b.database_acl AS database_acl_restored,
    n.nspacl IS NOT DISTINCT FROM b.public_schema_acl AS public_schema_acl_restored
FROM pg_database d
CROSS JOIN pg_namespace n
CROSS JOIN pg_temp.oauth_role_test_acl_baseline b
WHERE d.datname = current_database()
  AND n.nspname = 'public'
\gset

\echo all_four_roles_absent=:all_four_roles_absent
\echo no_test_memberships_remain=:no_test_memberships_remain
\echo database_acl_restored=:database_acl_restored
\echo public_schema_acl_restored=:public_schema_acl_restored

-- Return nonzero unless provisioning/assertions succeeded, rollback checks
-- passed, and both ACLs are exactly back to their pre-test values.
\if :provisioning_succeeded
  \if :all_four_roles_absent
    \if :no_test_memberships_remain
      \if :database_acl_restored
        \if :public_schema_acl_restored
          \echo PASS: provisioning and assertions succeeded; rollback and restoration verified.
        \else
          \echo FAIL: public-schema ACL differs from baseline.
          \quit 1
        \endif
      \else
        \echo FAIL: database ACL differs from baseline.
        \quit 1
      \endif
    \else
      \echo FAIL: test role memberships remain.
      \quit 1
    \endif
  \else
    \echo FAIL: one or more test roles remain.
    \quit 1
  \endif
\else
  \echo FAIL: provisioning or security assertions failed; transaction was rolled back.
  \quit 1
\endif
