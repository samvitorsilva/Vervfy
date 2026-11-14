"""PostgreSQL storage lifecycle foundation; physical cleanup is unavailable.

Requires separately provisioned capability roles; see docs/storage-lifecycle.md.
No storage requests, object moves, legacy rewrites, or cleanup activation occur.
"""

import sqlalchemy as sa

from alembic import op
from supabase_role_memberships import (
    assert_member_memberships,
    assert_role_memberships,
)

revision = "0027_storage_lifecycle"
down_revision = "0026_application_runtime_grants"
branch_labels = None
depends_on = None
OWNER = "vervfy_storage_lifecycle_owner"
EXECUTOR = "vervfy_storage_cleanup"
WORKER = "storage_cleanup_worker"


def _fresh_privileges(bind, role_ids):
    """Capabilities must not arrive with unrelated application privileges."""
    for role in role_ids:
        unsafe = bind.execute(
            sa.text("""
            SELECT 1 FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
              AND (c.relowner=:role OR
                CASE WHEN c.relkind='S' THEN pg_catalog.has_sequence_privilege(:role,c.oid,'USAGE,SELECT,UPDATE')
                     WHEN c.relkind IN ('r','p','v','m','f')
                       AND n.nspname='extensions'
                       AND c.relname IN ('pg_stat_statements','pg_stat_statements_info') THEN
                       c.relkind<>'v'
                       OR pg_catalog.has_schema_privilege(:role,n.oid,'USAGE')
                       OR NOT EXISTS (
                           SELECT 1 FROM pg_catalog.aclexplode(c.relacl) a
                           WHERE a.grantee=0 AND a.privilege_type='SELECT'
                       )
                       OR EXISTS (
                           SELECT 1 FROM pg_catalog.aclexplode(c.relacl) a
                           WHERE a.grantee<>c.relowner
                             AND (a.grantee<>0 OR a.privilege_type<>'SELECT')
                       )
                       OR pg_catalog.has_table_privilege(
                           :role,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
                       )
                       OR pg_catalog.has_any_column_privilege(
                           :role,c.oid,'INSERT,UPDATE,REFERENCES'
                       )
                     WHEN c.relkind IN ('r','p','v','m','f') THEN
                       pg_catalog.has_table_privilege(:role,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                       OR pg_catalog.has_any_column_privilege(:role,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')
                     ELSE false END)
            UNION ALL
            SELECT 1 FROM pg_catalog.pg_namespace n
            WHERE n.nspowner=:role OR
              (n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
               AND pg_catalog.has_schema_privilege(:role,n.oid,'CREATE'))
            UNION ALL
            SELECT 1 FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
              AND (p.proowner=:role OR
                   (pg_catalog.has_schema_privilege(:role,n.oid,'USAGE')
                    AND pg_catalog.has_function_privilege(:role,p.oid,'EXECUTE')))
            UNION ALL
            SELECT 1 FROM pg_catalog.pg_default_acl d
            CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
            WHERE d.defaclrole=:role OR a.grantee=0 OR a.grantee=:role
               OR (a.grantee<>0 AND
                   (pg_catalog.pg_has_role(:role,a.grantee,'USAGE')
                    OR pg_catalog.pg_has_role(:role,a.grantee,'SET')))
            LIMIT 1
        """),
            {"role": role},
        ).first()
        if unsafe:
            raise RuntimeError(
                "Storage capability has preexisting object privileges, ownership, routines or default ACLs"
            )


def _roles(bind):
    roles = {}
    for name, login in (
        (OWNER, False),
        (EXECUTOR, False),
        (WORKER, True),
        ("app_runtime", True),
    ):
        row = bind.execute(
            sa.text("""
            SELECT oid, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                   rolcreaterole, rolreplication, rolinherit
            FROM pg_catalog.pg_roles WHERE rolname=:name
        """),
            {"name": name},
        ).first()
        if row is None or row.rolcanlogin != login or any(row[2:]):
            raise RuntimeError(f"Provision restricted storage role {name} before 0027")
        roles[name] = row.oid
    migration_role = bind.execute(
        sa.text("SELECT current_user")
    ).scalar_one()
    assert_role_memberships(
        bind,
        OWNER,
        [(migration_role, "postgres", False, False, True)],
    )
    assert_role_memberships(
        bind,
        EXECUTOR,
        [(WORKER, "postgres", False, True, False)],
    )
    assert_role_memberships(bind, WORKER, [])
    assert_member_memberships(
        bind,
        WORKER,
        [(EXECUTOR, "postgres", False, True, False)],
    )
    assert_member_memberships(bind, "app_runtime", [])
    unsafe = bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_auth_members
        WHERE member=:owner OR member=:executor
           OR (member=:worker AND roleid<>:executor)
           OR member=:runtime
        LIMIT 1
    """),
        {
            "owner": roles[OWNER],
            "executor": roles[EXECUTOR],
            "worker": roles[WORKER],
            "runtime": roles["app_runtime"],
        },
    ).first()
    if unsafe:
        raise RuntimeError("Unsafe storage capability role graph")
    unsafe = bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_roles r
        WHERE NOT r.rolsuper AND r.oid NOT IN (:owner, current_user::regrole::oid)
          AND (pg_catalog.pg_has_role(r.oid,:owner,'USAGE') OR pg_catalog.pg_has_role(r.oid,:owner,'SET'))
        UNION ALL
        SELECT 1 FROM pg_catalog.pg_roles r
        WHERE NOT r.rolsuper AND r.oid NOT IN (:executor,:worker)
          AND (pg_catalog.pg_has_role(r.oid,:executor,'USAGE') OR pg_catalog.pg_has_role(r.oid,:executor,'SET'))
        LIMIT 1
    """),
        {"owner": roles[OWNER], "executor": roles[EXECUTOR], "worker": roles[WORKER]},
    ).first()
    if unsafe:
        raise RuntimeError("Unexpected effective storage capability membership")
    _fresh_privileges(bind, (roles[OWNER], roles[EXECUTOR], roles[WORKER]))


def _clear_acl(bind, kind, name, catalog_query):
    op.execute(f"REVOKE ALL ON {kind} {name} FROM PUBLIC")
    for role in bind.execute(sa.text(catalog_query), {"name": name}).scalars():
        op.execute(
            f"REVOKE ALL ON {kind} {name} FROM {bind.dialect.identifier_preparer.quote(role)}"
        )


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # No SQLite substitute for PostgreSQL concurrency/privilege controls.
    if bind.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("0027 requires the reviewed public application schema")
    _roles(bind)
    # DDL transaction freezes reference writers; existing path strings are unchanged.
    op.execute(
        "LOCK TABLE public.users, public.tracks, public.artist_photos, public.upload_jobs IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute("CREATE SCHEMA vervfy_storage")
    _clear_acl(
        bind,
        "SCHEMA",
        "vervfy_storage",
        """
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_namespace n
        CROSS JOIN LATERAL pg_catalog.aclexplode(n.nspacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE n.nspname=:name AND r.rolname<>current_user
    """,
    )
    op.execute("""
        CREATE TABLE vervfy_storage.namespaces (
            id smallint PRIMARY KEY CHECK(id=1),
            namespace_id uuid NOT NULL UNIQUE,
            environment text NOT NULL CHECK(environment ~ '^[a-z][a-z0-9_-]{0,39}$'),
            endpoint text NOT NULL CHECK(endpoint ~ '^https://[a-z0-9]([a-z0-9.-]*[a-z0-9])?$' AND length(endpoint)<300),
            bucket text NOT NULL CHECK(bucket ~ '^[a-z0-9][a-z0-9_-]{0,99}$'),
            physical_cleanup_enabled boolean NOT NULL DEFAULT false CHECK(NOT physical_cleanup_enabled)
        )
    """)
    op.execute("""
        CREATE TABLE vervfy_storage.objects (
            id uuid PRIMARY KEY,
            namespace_id smallint NOT NULL REFERENCES vervfy_storage.namespaces(id),
            tenant_id varchar(32) COLLATE "C",
            path varchar(600) COLLATE "C" NOT NULL,
            kind text NOT NULL CHECK(kind IN ('audio','track-cover','album-cover','artist-photo','staged-audio','legacy')),
            classification text NOT NULL CHECK(classification IN ('managed','legacy')),
            state text NOT NULL CHECK(state IN ('reserved','uploading','ready','live','retired','deleting','deleted','hold')),
            reservation_token uuid,
            upload_verified boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE(namespace_id,path),
            CHECK(classification='legacy' OR (tenant_id IS NOT NULL AND reservation_token IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE TABLE vervfy_storage.cleanup_jobs (
            object_id uuid PRIMARY KEY REFERENCES vervfy_storage.objects(id),
            requested_by varchar(32),
            state text NOT NULL CHECK(state IN ('pending','held','claimed','done')),
            attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
            available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            claim_token uuid,
            lease_until timestamptz,
            error_code varchar(100)
        )
    """)
    for table in ("namespaces", "objects", "cleanup_jobs"):
        name = "vervfy_storage." + table
        _clear_acl(
            bind,
            "TABLE",
            name,
            """
            SELECT DISTINCT r.rolname FROM pg_catalog.pg_class c
            CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) a
            JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
            WHERE c.oid=to_regclass(:name) AND r.rolname<>current_user
        """,
        )
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY storage_owner ON {name} TO {OWNER} USING(true) WITH CHECK(true)"
        )
        op.execute(f"GRANT SELECT ON {name} TO {OWNER}")
    op.execute(
        f"GRANT INSERT, UPDATE ON vervfy_storage.objects, vervfy_storage.cleanup_jobs TO {OWNER}"
    )
    op.execute(
        "GRANT USAGE ON SCHEMA vervfy_storage TO app_runtime, vervfy_storage_cleanup"
    )
    op.execute(f"GRANT USAGE, CREATE ON SCHEMA vervfy_storage TO {OWNER}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {OWNER}")
    op.execute(f"GRANT SELECT(id) ON public.users TO {OWNER}")
    for table, columns in (
        ("tracks", "storage_path,cover_path"),
        ("artist_photos", "storage_path"),
        ("upload_jobs", "storage_path"),
    ):
        op.execute(f"GRANT SELECT({columns}) ON public.{table} TO {OWNER}")
        op.execute(
            f"CREATE POLICY storage_reference_read ON public.{table} FOR SELECT TO {OWNER} USING(true)"
        )
    op.execute(
        "CREATE POLICY storage_tenant_read ON vervfy_storage.objects FOR SELECT TO app_runtime USING(tenant_id=current_setting('app.current_user_id',true))"
    )
    op.execute(
        "GRANT SELECT(id,tenant_id,path,kind,classification,state,upload_verified) ON vervfy_storage.objects TO app_runtime"
    )
    for table, column in (
        ("tracks", "storage_path"),
        ("tracks", "cover_path"),
        ("artist_photos", "storage_path"),
        ("upload_jobs", "storage_path"),
    ):
        op.execute(
            f'CREATE INDEX ix_storage_ref_{table}_{column} ON public.{table}(({column} COLLATE "C")) WHERE {column} IS NOT NULL'
        )
    op.execute(
        "ALTER TABLE public.tracks ADD COLUMN media_version uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid()"
    )
    op.execute(
        "ALTER TABLE public.artist_photos ADD COLUMN media_version uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid()"
    )
    op.execute("ALTER TABLE public.upload_jobs ADD COLUMN processing_token uuid")
    op.execute("ALTER TABLE public.upload_jobs ALTER COLUMN storage_path DROP NOT NULL")

    functions = [
        (
            "guard_namespace()",
            "",
            """
            CREATE FUNCTION vervfy_storage.guard_namespace() RETURNS trigger
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            BEGIN
                RAISE EXCEPTION 'Storage namespace is immutable; reviewed recovery required' USING ERRCODE='55000';
            END $$
            """,
        ),
        (
            "validate_namespace(uuid,text,text,text)",
            "app_runtime, vervfy_storage_cleanup",
            """
            CREATE FUNCTION vervfy_storage.validate_namespace(p_id uuid,p_environment text,p_endpoint text,p_bucket text)
            RETURNS void LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            BEGIN
                IF NOT EXISTS(SELECT 1 FROM vervfy_storage.namespaces
                    WHERE id=1 AND namespace_id=p_id AND environment=p_environment
                    AND endpoint=p_endpoint AND bucket=p_bucket) THEN
                    RAISE EXCEPTION 'Storage namespace binding unavailable or mismatched' USING ERRCODE='55000';
                END IF;
            END $$
            """,
        ),
        (
            "_has_references(text)",
            "",
            """
            CREATE FUNCTION vervfy_storage._has_references(p_path text) RETURNS boolean
            LANGUAGE sql VOLATILE STRICT SECURITY DEFINER SET search_path=pg_catalog,pg_temp
            AS $$ SELECT EXISTS(SELECT 1 FROM public.tracks WHERE storage_path COLLATE "C"=p_path COLLATE "C" OR cover_path COLLATE "C"=p_path COLLATE "C")
                   OR EXISTS(SELECT 1 FROM public.artist_photos WHERE storage_path COLLATE "C"=p_path COLLATE "C")
                   OR EXISTS(SELECT 1 FROM public.upload_jobs WHERE storage_path COLLATE "C"=p_path COLLATE "C") $$
        """,
        ),
        (
            "_queue(uuid,text)",
            "",
            """
            CREATE FUNCTION vervfy_storage._queue(p_object uuid,p_actor text) RETURNS void
            LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp
            AS $$ INSERT INTO vervfy_storage.cleanup_jobs(object_id,requested_by,state)
                  SELECT id,p_actor,CASE WHEN classification='legacy' OR state IN ('reserved','uploading','hold')
                                        THEN 'held' ELSE 'pending' END
                  FROM vervfy_storage.objects WHERE id=p_object
                  ON CONFLICT(object_id) DO NOTHING $$
        """,
        ),
        (
            "reserve_object(text,text)",
            "app_runtime",
            """
            CREATE FUNCTION vervfy_storage.reserve_object(p_kind text,p_extension text)
            RETURNS TABLE(object_id uuid,object_path text,upload_token uuid)
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            DECLARE actor text:=current_setting('app.current_user_id',true); ns uuid;
                    oid uuid:=pg_catalog.gen_random_uuid(); token uuid:=pg_catalog.gen_random_uuid(); key text;
            BEGIN
                IF actor IS NULL OR actor !~ '^[A-Za-z0-9_-]{1,32}$'
                   OR NOT EXISTS(SELECT 1 FROM public.users WHERE id=actor) THEN
                    RAISE EXCEPTION 'Storage account context required' USING ERRCODE='42501'; END IF;
                IF p_kind IS NULL OR p_kind NOT IN ('audio','track-cover','album-cover','artist-photo','staged-audio')
                   OR p_extension IS NULL OR p_extension !~ '^[a-z0-9]{1,5}$' THEN
                    RAISE EXCEPTION 'Invalid storage object type'; END IF;
                SELECT namespace_id INTO STRICT ns FROM vervfy_storage.namespaces WHERE id=1;
                key:='v2/'||ns::text||'/'||actor||'/'||p_kind||'/'||oid::text||'.'||p_extension;
                INSERT INTO vervfy_storage.objects(id,namespace_id,tenant_id,path,kind,classification,state,reservation_token)
                    VALUES(oid,1,actor,key,p_kind,'managed','reserved',token);
                RETURN QUERY SELECT oid,key,token;
            END $$
        """,
        ),
        (
            "advance_upload(uuid,uuid,text)",
            "app_runtime",
            """
            CREATE FUNCTION vervfy_storage.advance_upload(p_object uuid,p_token uuid,p_next text) RETURNS void
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            DECLARE obj vervfy_storage.objects%ROWTYPE;
            BEGIN
                SELECT * INTO STRICT obj FROM vervfy_storage.objects WHERE id=p_object FOR UPDATE;
                IF obj.tenant_id IS DISTINCT FROM current_setting('app.current_user_id',true)
                   OR p_token IS NULL OR obj.reservation_token IS DISTINCT FROM p_token
                   OR obj.classification<>'managed' THEN
                    RAISE EXCEPTION 'Storage reservation denied' USING ERRCODE='42501'; END IF;
                IF p_next='uploading' AND obj.state='reserved' THEN
                    UPDATE vervfy_storage.objects SET state='uploading' WHERE id=p_object;
                ELSIF p_next='ready' AND obj.state='uploading' THEN
                    UPDATE vervfy_storage.objects SET state='ready',upload_verified=true WHERE id=p_object;
                ELSIF p_next='hold' AND obj.state IN ('reserved','uploading') THEN
                    UPDATE vervfy_storage.objects SET state='hold' WHERE id=p_object;
                    PERFORM vervfy_storage._queue(p_object,obj.tenant_id);
                ELSE RAISE EXCEPTION 'Storage transition denied' USING ERRCODE='55000'; END IF;
            END $$
        """,
        ),
        (
            "request_cleanup(uuid)",
            "app_runtime",
            """
            CREATE FUNCTION vervfy_storage.request_cleanup(p_object uuid) RETURNS void
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            DECLARE actor text;
            BEGIN
                SELECT tenant_id INTO STRICT actor FROM vervfy_storage.objects WHERE id=p_object FOR UPDATE;
                IF actor IS NULL OR actor IS DISTINCT FROM current_setting('app.current_user_id',true) THEN
                    RAISE EXCEPTION 'Storage cleanup request denied' USING ERRCODE='42501'; END IF;
                PERFORM vervfy_storage._queue(p_object,actor);
            END $$
        """,
        ),
        (
            "guard_references()",
            "",
            """
            CREATE FUNCTION vervfy_storage.guard_references() RETURNS trigger
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            DECLARE old_data jsonb; new_data jsonb; fields text[]; field text;
                    old_path text; new_path text; actor text; key text; changed text[]:=ARRAY[]::text[]; obj vervfy_storage.objects%ROWTYPE;
            BEGIN
                IF TG_TABLE_SCHEMA<>'public' OR TG_TABLE_NAME NOT IN ('tracks','artist_photos','upload_jobs') THEN
                    RAISE EXCEPTION 'Invalid storage trigger target'; END IF;
                old_data:=CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE to_jsonb(OLD) END;
                new_data:=CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE to_jsonb(NEW) END;
                actor:=COALESCE(new_data->>'user_id',old_data->>'user_id');
                IF TG_OP='UPDATE' AND old_data->>'user_id' IS DISTINCT FROM new_data->>'user_id' THEN
                    RAISE EXCEPTION 'Reference ownership is immutable' USING ERRCODE='42501'; END IF;
                fields:=CASE WHEN TG_TABLE_NAME='tracks' THEN ARRAY['storage_path','cover_path'] ELSE ARRAY['storage_path'] END;
                FOREACH field IN ARRAY fields LOOP
                    IF old_data->>field COLLATE "C" IS DISTINCT FROM new_data->>field COLLATE "C" THEN
                        changed:=array_append(changed,field);
                    END IF;
                END LOOP;
                -- Metadata-only operations need neither binding nor legacy registration.
                IF cardinality(changed)=0 THEN
                    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
                    RETURN NEW;
                END IF;
                -- Lock only changed references, in byte-exact order across destinations.
                FOR key IN SELECT DISTINCT v COLLATE "C"
                    FROM unnest(changed) AS f
                    CROSS JOIN LATERAL (VALUES(old_data->>f),(new_data->>f)) AS paths(v)
                    WHERE v IS NOT NULL ORDER BY v COLLATE "C"
                LOOP
                    INSERT INTO vervfy_storage.objects(id,namespace_id,path,kind,classification,state)
                        VALUES(pg_catalog.gen_random_uuid(),1,key,'legacy','legacy','hold') ON CONFLICT(namespace_id,path) DO NOTHING;
                    PERFORM 1 FROM vervfy_storage.objects WHERE namespace_id=1 AND path=key FOR UPDATE;
                END LOOP;
                FOREACH field IN ARRAY changed LOOP
                    old_path:=old_data->>field; new_path:=new_data->>field;
                    IF old_path COLLATE "C" IS NOT DISTINCT FROM new_path COLLATE "C" THEN CONTINUE; END IF;
                    IF new_path IS NOT NULL THEN
                        SELECT * INTO STRICT obj FROM vervfy_storage.objects WHERE namespace_id=1 AND path=new_path;
                        IF actor IS DISTINCT FROM current_setting('app.current_user_id',true)
                           OR obj.tenant_id IS DISTINCT FROM actor OR obj.classification<>'managed'
                           OR NOT obj.upload_verified OR obj.state NOT IN ('ready','live')
                           OR NOT (CASE
                               WHEN TG_TABLE_NAME='tracks' AND field='storage_path' THEN obj.kind='audio'
                               WHEN TG_TABLE_NAME='tracks' AND field='cover_path' THEN obj.kind IN ('track-cover','album-cover')
                               WHEN TG_TABLE_NAME='artist_photos' THEN obj.kind='artist-photo'
                               WHEN TG_TABLE_NAME='upload_jobs' THEN obj.kind='staged-audio'
                               ELSE false END) THEN
                            RAISE EXCEPTION 'Storage attachment denied' USING ERRCODE='42501'; END IF;
                        UPDATE vervfy_storage.objects SET state='live' WHERE id=obj.id;
                    END IF;
                    IF old_path IS NOT NULL THEN
                        SELECT id INTO STRICT obj.id FROM vervfy_storage.objects WHERE namespace_id=1 AND path=old_path;
                        PERFORM vervfy_storage._queue(obj.id,actor);
                    END IF;
                END LOOP;
                IF TG_OP='UPDATE' AND TG_TABLE_NAME IN ('tracks','artist_photos') THEN NEW.media_version:=pg_catalog.gen_random_uuid(); END IF;
                IF TG_OP='DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END $$
        """,
        ),
        (
            "retire_candidate(uuid)",
            EXECUTOR,
            """
            CREATE FUNCTION vervfy_storage.retire_candidate(p_object uuid) RETURNS boolean
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            DECLARE obj vervfy_storage.objects%ROWTYPE;
            BEGIN
                IF current_setting('transaction_isolation')<>'read committed' THEN
                    RAISE EXCEPTION 'Storage retirement requires READ COMMITTED'; END IF;
                SELECT * INTO STRICT obj FROM vervfy_storage.objects WHERE id=p_object FOR UPDATE;
                IF NOT EXISTS(SELECT 1 FROM vervfy_storage.cleanup_jobs WHERE object_id=p_object) THEN
                    RAISE EXCEPTION 'No authorized cleanup obligation' USING ERRCODE='42501'; END IF;
                IF obj.classification<>'managed' OR NOT obj.upload_verified OR obj.state IN ('reserved','uploading','hold') THEN RETURN false; END IF;
                IF obj.state='retired' THEN RETURN true; END IF;
                IF obj.state NOT IN ('ready','live') THEN RETURN false; END IF;
                IF vervfy_storage._has_references(obj.path) THEN RETURN false; END IF;
                UPDATE vervfy_storage.objects SET state='retired' WHERE id=p_object;
                RETURN true;
            END $$
        """,
        ),
        (
            "claim_cleanup(uuid)",
            EXECUTOR,
            """
            CREATE FUNCTION vervfy_storage.claim_cleanup(p_object uuid) RETURNS text
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            BEGIN
                RAISE EXCEPTION 'Physical cleanup unavailable until writer conversion and Phase 4 review' USING ERRCODE='55000';
            END $$
        """,
        ),
    ]
    for signature, executor, sql in functions:
        op.execute(sql)
        name = "vervfy_storage." + signature
        _clear_acl(
            bind,
            "FUNCTION",
            name,
            """
            SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p
            CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
            JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
            WHERE p.oid=to_regprocedure(:name) AND r.rolname<>current_user
        """,
        )
        if executor:
            op.execute(f"GRANT EXECUTE ON FUNCTION {name} TO {executor}")
        if signature == "guard_namespace()":
            op.execute(
                "CREATE TRIGGER storage_namespace_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON vervfy_storage.namespaces FOR EACH STATEMENT EXECUTE FUNCTION vervfy_storage.guard_namespace()"
            )
        if signature == "guard_references()":
            # Install while the migration login still owns the function; it has
            # no inherited EXECUTE after transfer to the isolated capability owner.
            for table in ("tracks", "artist_photos", "upload_jobs"):
                op.execute(
                    f"CREATE TRIGGER storage_reference_guard BEFORE INSERT OR UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION vervfy_storage.guard_references()"
                )
        op.execute(f"ALTER FUNCTION {name} OWNER TO {OWNER}")
    op.execute(f"REVOKE CREATE ON SCHEMA vervfy_storage FROM {OWNER}")


def downgrade():
    raise RuntimeError(
        "0027 is forward-only: preserve lifecycle obligations and deletion fences"
    )
