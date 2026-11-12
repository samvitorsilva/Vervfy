-- DBA-only, one-time prerequisites for scripts.production_migration.
-- Run against the approved production project's direct `postgres` database
-- as Supabase's `postgres` administrator. This script is transactional.
-- It never reads, rewrites, deletes, or backfills application rows. It changes
-- ownership only for the existing relations the migration runner explicitly
-- requires, and for sequences owned by those relations.
--
-- Set the LOGIN passwords out of band using the approved secret-management
-- process. Do not put passwords in this file, SQL history, or command-line
-- arguments.

BEGIN;
SET LOCAL search_path TO pg_catalog, public;

DO $$
DECLARE
    table_name text;
    relkind "char";
    revision_count integer;
    revision_value text;
BEGIN
    IF current_database() <> 'postgres'
       OR session_user <> 'postgres'
       OR current_user <> 'postgres' THEN
        RAISE EXCEPTION 'Connect to the approved postgres database as postgres';
    END IF;

    IF current_setting('server_version_num')::integer < 160000 THEN
        RAISE EXCEPTION 'PostgreSQL 16 or newer is required';
    END IF;

    IF to_regclass('public.alembic_version') IS NULL THEN
        RAISE EXCEPTION 'public.alembic_version is missing';
    END IF;
    SELECT count(*), min(version_num)
      INTO revision_count, revision_value
      FROM public.alembic_version;
    IF revision_count <> 1 OR revision_value <> '0019_track_listens' THEN
        RAISE EXCEPTION
            'Expected exactly revision 0019_track_listens; found % row(s), revision %',
            revision_count, revision_value;
    END IF;

    FOREACH table_name IN ARRAY ARRAY[
        'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
        'upload_jobs', 'artist_photos', 'track_listens', 'artist_images',
        'track_cover_cache'
    ]
    LOOP
        SELECT c.relkind INTO relkind
          FROM pg_catalog.pg_class AS c
          JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname = table_name;
        IF relkind IS NULL OR relkind NOT IN ('r', 'p') THEN
            RAISE EXCEPTION 'Required public table % is missing or not a table', table_name;
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_inherits AS i
              JOIN pg_catalog.pg_class AS parent ON parent.oid = i.inhparent
              JOIN pg_catalog.pg_namespace AS parent_ns
                ON parent_ns.oid = parent.relnamespace
             WHERE parent_ns.nspname = 'public'
               AND parent.relname = table_name
        ) THEN
            RAISE EXCEPTION
                'Required table % has partitions/inheritance requiring separate review',
                table_name;
        END IF;
    END LOOP;

    IF to_regclass('public.provider_identities') IS NOT NULL
       OR to_regnamespace('vervfy_auth') IS NOT NULL
       OR EXISTS (
           SELECT 1
             FROM unnest(ARRAY[
                 'webauthn_handles', 'webauthn_credentials',
                 'account_action_intents', 'account_verification_proofs',
                 'account_recovery_codes', 'account_recovery_states',
                 'webauthn_enrollments'
             ]) AS objects(object_name)
            WHERE to_regclass('public.' || object_name) IS NOT NULL
       ) THEN
        RAISE EXCEPTION
            'Objects expected to be created by revisions 0021-0028 already exist';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
         WHERE attrelid = 'public.users'::regclass
           AND attname = 'session_version' AND NOT attisdropped
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
         WHERE attrelid = 'public.tracks'::regclass
           AND attname = 'cover_source' AND NOT attisdropped
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.tracks'::regclass
           AND conname = 'ck_tracks_cover_source'
           AND contype = 'c' AND convalidated
    ) THEN
        RAISE EXCEPTION
            'Baseline schema lacks session_version or the validated cover-source constraint';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.tracks
         WHERE cover_source IS NOT NULL
           AND cover_source NOT IN (
               'embedded', 'upload', 'user', 'musicbrainz', 'audiodb',
               'generated', 'placeholder', 'unknown'
           )
    ) THEN
        RAISE EXCEPTION
            'Existing cover_source values are incompatible with revision 0025';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'vervfy_prod_migrator'
    ) THEN
        CREATE ROLE vervfy_prod_migrator
            LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB
            NOCREATEROLE NOREPLICATION;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'app_runtime'
    ) THEN
        CREATE ROLE app_runtime
            NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB
            NOCREATEROLE NOREPLICATION;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'google_auth_lookup'
    ) THEN
        CREATE ROLE google_auth_lookup
            LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB
            NOCREATEROLE NOREPLICATION;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'vervfy_identity_lookup_owner'
    ) THEN
        CREATE ROLE vervfy_identity_lookup_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB
            NOCREATEROLE NOREPLICATION;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'vervfy_identity_lookup'
    ) THEN
        CREATE ROLE vervfy_identity_lookup
            NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB
            NOCREATEROLE NOREPLICATION;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles
         WHERE rolname IN (
             'vervfy_prod_migrator', 'google_auth_lookup',
             'vervfy_identity_lookup_owner', 'vervfy_identity_lookup',
             'app_runtime'
         )
           AND (
               rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolinherit
           )
           AND rolname <> 'app_runtime'
    ) THEN
        RAISE EXCEPTION 'A migration or lookup role has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'vervfy_prod_migrator' AND rolcanlogin
           AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'google_auth_lookup' AND rolcanlogin
           AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'vervfy_identity_lookup_owner' AND NOT rolcanlogin
           AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'vervfy_identity_lookup' AND NOT rolcanlogin
           AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'app_runtime'
           AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication
    ) THEN
        RAISE EXCEPTION 'A required role is missing or has incompatible attributes';
    END IF;
END
$$;

-- Preserve provider-managed grants (including their grantor and ADMIN option).
-- ADMIN alone does not permit SET ROLE on PostgreSQL 16+. Record this grant
-- as postgres, separately from any supabase_admin-managed membership. Leave
-- ADMIN unspecified: a locally created role can have an automatic postgres
-- ADMIN grant which must remain available for dependent membership grants.
-- SET permits ownership transfers; INHERIT permits the subsequent ACL grants
-- as postgres after ownership has moved. This grants nothing TO the migrator.
GRANT vervfy_prod_migrator TO postgres
    WITH INHERIT TRUE, SET TRUE GRANTED BY postgres;

DO $$
BEGIN
    IF NOT pg_catalog.pg_has_role(current_user, 'vervfy_prod_migrator', 'SET')
       OR NOT pg_catalog.pg_has_role(current_user, 'vervfy_prod_migrator', 'USAGE') THEN
        RAISE EXCEPTION 'postgres lacks migration-owner SET or inherited privileges';
    END IF;
END
$$;

GRANT vervfy_identity_lookup_owner TO vervfy_prod_migrator
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT vervfy_identity_lookup TO google_auth_lookup
    WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;

GRANT CONNECT, CREATE ON DATABASE postgres TO vervfy_prod_migrator;
GRANT CONNECT ON DATABASE postgres TO app_runtime, google_auth_lookup;
GRANT USAGE, CREATE ON SCHEMA public TO vervfy_prod_migrator;
GRANT USAGE ON SCHEMA public TO app_runtime;

DO $$
DECLARE
    table_name text;
    sequence_name record;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
        'upload_jobs', 'artist_photos', 'track_listens', 'artist_images',
        'track_cover_cache', 'alembic_version'
    ]
    LOOP
        EXECUTE format(
            'ALTER TABLE public.%I OWNER TO vervfy_prod_migrator',
            table_name
        );
        IF table_name <> 'alembic_version' THEN
            EXECUTE format(
                'GRANT ALL PRIVILEGES ON TABLE public.%I TO postgres',
                table_name
            );
            EXECUTE format(
                'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO app_runtime',
                table_name
            );
        END IF;
    END LOOP;

    FOR sequence_name IN
        SELECT DISTINCT ns.nspname, seq.relname
          FROM pg_catalog.pg_class AS seq
          JOIN pg_catalog.pg_namespace AS ns ON ns.oid = seq.relnamespace
          JOIN pg_catalog.pg_depend AS d
            ON d.objid = seq.oid
           AND d.classid = 'pg_catalog.pg_class'::regclass
           AND d.refclassid = 'pg_catalog.pg_class'::regclass
           AND d.deptype IN ('a', 'i')
          JOIN pg_catalog.pg_class AS tbl ON tbl.oid = d.refobjid
          JOIN pg_catalog.pg_namespace AS tbl_ns ON tbl_ns.oid = tbl.relnamespace
         WHERE seq.relkind = 'S'
           AND tbl_ns.nspname = 'public'
           AND tbl.relname = ANY (ARRAY[
               'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
               'upload_jobs', 'artist_photos', 'track_listens', 'artist_images',
               'track_cover_cache'
           ])
    LOOP
        EXECUTE format(
            'ALTER SEQUENCE %I.%I OWNER TO vervfy_prod_migrator',
            sequence_name.nspname, sequence_name.relname
        );
        EXECUTE format(
            'GRANT ALL PRIVILEGES ON SEQUENCE %I.%I TO postgres',
            sequence_name.nspname, sequence_name.relname
        );
        EXECUTE format(
            'GRANT USAGE, SELECT, UPDATE ON SEQUENCE %I.%I TO app_runtime',
            sequence_name.nspname, sequence_name.relname
        );
    END LOOP;
END
$$;

DO $$
DECLARE
    required_table text;
    migration_oid oid;
    owner_oid oid;
    executor_oid oid;
    lookup_oid oid;
    runtime_oid oid;
    postgres_oid oid;
    admin_oid oid;
    application_table text;
BEGIN
    SELECT oid INTO migration_oid FROM pg_catalog.pg_roles
     WHERE rolname = 'vervfy_prod_migrator';
    SELECT oid INTO owner_oid FROM pg_catalog.pg_roles
     WHERE rolname = 'vervfy_identity_lookup_owner';
    SELECT oid INTO executor_oid FROM pg_catalog.pg_roles
     WHERE rolname = 'vervfy_identity_lookup';
    SELECT oid INTO lookup_oid FROM pg_catalog.pg_roles
     WHERE rolname = 'google_auth_lookup';
    SELECT oid INTO runtime_oid FROM pg_catalog.pg_roles
     WHERE rolname = 'app_runtime';
    SELECT oid INTO postgres_oid FROM pg_catalog.pg_roles WHERE rolname = 'postgres';
    SELECT oid INTO admin_oid FROM pg_catalog.pg_roles WHERE rolname = 'supabase_admin';

    FOREACH required_table IN ARRAY ARRAY[
        'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
        'upload_jobs', 'artist_photos', 'track_listens', 'artist_images',
        'track_cover_cache', 'alembic_version'
    ]
    LOOP
        IF (
            SELECT c.relowner
              FROM pg_catalog.pg_class AS c
              JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relname = required_table
        ) <> migration_oid THEN
            RAISE EXCEPTION 'Migration role does not own public.%', required_table;
        END IF;
    END LOOP;

    IF NOT pg_catalog.has_database_privilege(
           migration_oid, current_database(), 'CONNECT'
       )
       OR NOT pg_catalog.has_database_privilege(
           migration_oid, current_database(), 'CREATE'
       )
       OR NOT pg_catalog.has_schema_privilege(migration_oid, 'public', 'USAGE')
       OR NOT pg_catalog.has_schema_privilege(migration_oid, 'public', 'CREATE')
       OR NOT pg_catalog.pg_has_role(migration_oid, owner_oid, 'SET') THEN
        RAISE EXCEPTION 'Migration login lacks a runner-required grant';
    END IF;

    IF (
        SELECT count(*) FROM pg_catalog.pg_auth_members
         WHERE member = migration_oid
    ) <> 1
       OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE member = migration_oid AND roleid = owner_oid
              AND grantor = postgres_oid AND NOT admin_option
              AND NOT inherit_option AND set_option
       ) THEN
        RAISE EXCEPTION 'Migration login has an unexpected role membership';
    END IF;

    IF EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE roleid = owner_oid
              AND NOT (
                  member = migration_oid AND grantor = postgres_oid
                  AND NOT admin_option AND NOT inherit_option AND set_option
              )
              AND NOT (
                  member = postgres_oid AND grantor = postgres_oid
                  AND NOT admin_option AND NOT inherit_option AND set_option
              )
              AND NOT (
                  admin_oid IS NOT NULL AND member = postgres_oid
                  AND grantor = admin_oid AND admin_option
                  AND NOT inherit_option AND NOT set_option
              )
       )
       OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE roleid = owner_oid AND member = migration_oid
              AND grantor = postgres_oid AND NOT admin_option
              AND NOT inherit_option AND set_option
       )
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = owner_oid
       ) THEN
        RAISE EXCEPTION 'Lookup-owner membership graph does not match migration 0022';
    END IF;

    IF EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE roleid = executor_oid
              AND NOT (
                  member = lookup_oid AND grantor = postgres_oid
                  AND NOT admin_option AND inherit_option AND NOT set_option
              )
              AND NOT (
                  admin_oid IS NOT NULL AND member = postgres_oid
                  AND grantor = admin_oid AND admin_option
                  AND NOT inherit_option AND NOT set_option
              )
       )
       OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE roleid = executor_oid AND member = lookup_oid
              AND grantor = postgres_oid AND NOT admin_option
              AND inherit_option AND NOT set_option
       )
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = executor_oid
       ) THEN
        RAISE EXCEPTION 'Lookup-executor membership graph does not match migration 0022';
    END IF;

    IF EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE roleid = lookup_oid
              AND NOT (
                  admin_oid IS NOT NULL AND member = postgres_oid
                  AND grantor = admin_oid AND admin_option
                  AND NOT inherit_option AND NOT set_option
              )
       )
       OR (
           SELECT count(*) FROM pg_catalog.pg_auth_members
            WHERE member = lookup_oid
       ) <> 1
       OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
            WHERE member = lookup_oid AND roleid = executor_oid
              AND grantor = postgres_oid AND NOT admin_option
              AND inherit_option AND NOT set_option
       ) THEN
        RAISE EXCEPTION 'Lookup-login membership graph does not match migration 0022';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS r
         WHERE r.oid NOT IN (executor_oid, lookup_oid)
           AND NOT r.rolsuper
           AND (
               pg_catalog.pg_has_role(r.oid, executor_oid, 'USAGE')
               OR pg_catalog.pg_has_role(r.oid, executor_oid, 'SET')
           )
    ) THEN
        RAISE EXCEPTION 'An unexpected role can access the lookup capability';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members
         WHERE member = runtime_oid
           AND roleid IN (migration_oid, owner_oid, executor_oid, lookup_oid)
    ) OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles AS r
         WHERE r.rolbypassrls
           AND pg_catalog.pg_has_role(runtime_oid, r.oid, 'USAGE')
    ) THEN
        RAISE EXCEPTION
            'app_runtime inherits a migration, lookup, or BYPASSRLS capability';
    END IF;

    IF NOT pg_catalog.has_database_privilege(
           runtime_oid, current_database(), 'CONNECT'
       )
       OR NOT pg_catalog.has_schema_privilege(runtime_oid, 'public', 'USAGE') THEN
        RAISE EXCEPTION 'app_runtime lacks database CONNECT or public schema USAGE';
    END IF;

    FOREACH application_table IN ARRAY ARRAY[
        'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
        'upload_jobs', 'artist_photos', 'track_listens', 'artist_images',
        'track_cover_cache'
    ]
    LOOP
        IF NOT pg_catalog.has_table_privilege(
                   runtime_oid, format('public.%I', application_table), 'SELECT'
               )
           OR NOT pg_catalog.has_table_privilege(
                   runtime_oid, format('public.%I', application_table), 'INSERT'
               )
           OR NOT pg_catalog.has_table_privilege(
                   runtime_oid, format('public.%I', application_table), 'UPDATE'
               )
           OR NOT pg_catalog.has_table_privilege(
                   runtime_oid, format('public.%I', application_table), 'DELETE'
               ) THEN
            RAISE EXCEPTION
                'app_runtime lacks SELECT, INSERT, UPDATE, or DELETE on public.%',
                application_table;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS seq
          JOIN pg_catalog.pg_namespace AS ns ON ns.oid = seq.relnamespace
          JOIN pg_catalog.pg_depend AS d
            ON d.objid = seq.oid
           AND d.classid = 'pg_catalog.pg_class'::regclass
           AND d.refclassid = 'pg_catalog.pg_class'::regclass
           AND d.deptype IN ('a', 'i')
          JOIN pg_catalog.pg_class AS tbl ON tbl.oid = d.refobjid
          JOIN pg_catalog.pg_namespace AS tbl_ns ON tbl_ns.oid = tbl.relnamespace
         WHERE seq.relkind = 'S'
           AND tbl_ns.nspname = 'public'
           AND tbl.relname = ANY (ARRAY[
               'users', 'tracks', 'favorites', 'playlists', 'playlist_tracks',
               'upload_jobs', 'artist_photos', 'track_listens', 'artist_images',
               'track_cover_cache'
           ])
           AND (
               NOT pg_catalog.has_sequence_privilege(runtime_oid, seq.oid, 'USAGE')
               OR NOT pg_catalog.has_sequence_privilege(runtime_oid, seq.oid, 'SELECT')
               OR NOT pg_catalog.has_sequence_privilege(runtime_oid, seq.oid, 'UPDATE')
           )
    ) THEN
        RAISE EXCEPTION
            'app_runtime lacks USAGE, SELECT, or UPDATE on an application sequence';
    END IF;
END
$$;

COMMIT;
