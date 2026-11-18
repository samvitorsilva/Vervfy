"""Charge retained storage before I/O; never release charges automatically."""

import sqlalchemy as sa

from alembic import op

revision = "0034_storage_byte_reservations"
down_revision = "0033_cleanup_claims_disabled"
branch_labels = None
depends_on = None
OWNER = "vervfy_storage_lifecycle_owner"


def _clear_function_acl(signature):
    bind = op.get_bind()
    name = "vervfy_storage." + signature
    op.execute(f"REVOKE ALL ON FUNCTION {name} FROM PUBLIC")
    roles = (
        bind.execute(
            sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p
        CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE p.oid=pg_catalog.to_regprocedure(:name) AND a.grantee<>p.proowner
    """),
            {"name": name},
        )
        .scalars()
        .all()
    )
    for role in roles:
        quoted = bind.dialect.identifier_preparer.quote(role)
        op.execute(f"REVOKE ALL ON FUNCTION {name} FROM {quoted}")


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if bind.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("0034 requires the public application schema")
    # NULL means unknown, never zero. Existing objects require separately
    # reviewed inventory reconciliation before further allocations are admitted.
    op.execute("""ALTER TABLE vervfy_storage.objects ADD COLUMN reserved_bytes bigint
        CHECK(reserved_bytes IS NULL OR reserved_bytes > 0)""")
    op.execute("""CREATE TABLE vervfy_storage.quota_policy (
        id smallint PRIMARY KEY CHECK(id=1),
        tenant_limit_bytes bigint NOT NULL CHECK(tenant_limit_bytes>0),
        total_limit_bytes bigint NOT NULL CHECK(total_limit_bytes>0)
    )""")
    # Conservative installation ceilings. Only the migration administrator can
    # configure them; application callers may request a LOWER tenant limit.
    op.execute(
        "INSERT INTO vervfy_storage.quota_policy VALUES (1,157286400,10737418240)"
    )
    op.execute("REVOKE ALL ON vervfy_storage.quota_policy FROM PUBLIC")
    roles = (
        bind.execute(
            sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_class c
        CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE c.oid='vervfy_storage.quota_policy'::regclass AND a.grantee<>c.relowner
    """)
        )
        .scalars()
        .all()
    )
    for role in roles:
        op.execute(
            "REVOKE ALL ON vervfy_storage.quota_policy FROM "
            + bind.dialect.identifier_preparer.quote(role)
        )
    op.execute("ALTER TABLE vervfy_storage.quota_policy ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vervfy_storage.quota_policy FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY quota_owner ON vervfy_storage.quota_policy TO {OWNER} USING(true) WITH CHECK(true)"
    )
    op.execute(f"GRANT SELECT, UPDATE ON vervfy_storage.quota_policy TO {OWNER}")
    op.execute(f"GRANT CREATE ON SCHEMA vervfy_storage TO {OWNER}")
    op.execute(f"SET LOCAL ROLE {OWNER}")
    _clear_function_acl("reserve_object(text,text)")
    op.execute("""
        CREATE FUNCTION vervfy_storage.reserve_sized_object(
            p_kind text, p_extension text, p_bytes bigint, p_limit bigint
        ) RETURNS TABLE(object_id uuid,object_path text,upload_token uuid)
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE actor text:=current_setting('app.current_user_id',true);
                tenant_cap bigint; total_cap bigint; tenant_used numeric; total_used numeric;
                new_id uuid; new_path text; new_token uuid;
        BEGIN
            IF actor IS NULL OR actor !~ '^[A-Za-z0-9_-]{1,32}$'
               OR NOT EXISTS(SELECT 1 FROM public.users WHERE id=actor) THEN
                RAISE EXCEPTION 'Storage account context required' USING ERRCODE='42501';
            END IF;
            IF p_bytes IS NULL OR p_bytes<=0 OR p_limit IS NULL OR p_limit<=0 THEN
                RAISE EXCEPTION 'Positive storage reservation required' USING ERRCODE='22023';
            END IF;
            IF current_setting('transaction_isolation')<>'read committed' THEN
                RAISE EXCEPTION 'Storage quota requires READ COMMITTED' USING ERRCODE='55000';
            END IF;
            -- One namespace-wide lock serializes admission across all tenants.
            -- Subsequent statements take fresh snapshots after a waiting lock.
            SELECT tenant_limit_bytes,total_limit_bytes INTO STRICT tenant_cap,total_cap
                FROM vervfy_storage.quota_policy WHERE id=1 FOR UPDATE;
            IF EXISTS(SELECT 1 FROM vervfy_storage.objects WHERE reserved_bytes IS NULL) THEN
                RAISE EXCEPTION 'Storage inventory requires reconciliation' USING ERRCODE='55000';
            END IF;
            SELECT coalesce(sum(reserved_bytes),0),
                   coalesce(sum(reserved_bytes) FILTER (WHERE tenant_id=actor),0)
                INTO total_used,tenant_used FROM vervfy_storage.objects;
            IF tenant_used+p_bytes>least(tenant_cap,p_limit) OR total_used+p_bytes>total_cap THEN
                RAISE EXCEPTION 'Retained storage quota exceeded' USING ERRCODE='54000';
            END IF;
            SELECT r.object_id,r.object_path,r.upload_token INTO STRICT new_id,new_path,new_token
                FROM vervfy_storage.reserve_object(p_kind,p_extension) r;
            UPDATE vervfy_storage.objects SET reserved_bytes=p_bytes WHERE id=new_id;
            RETURN QUERY SELECT new_id,new_path,new_token;
        END $$
    """)
    _clear_function_acl("reserve_sized_object(text,text,bigint,bigint)")
    op.execute(
        "GRANT EXECUTE ON FUNCTION vervfy_storage.reserve_sized_object(text,text,bigint,bigint) TO app_runtime"
    )
    op.execute("""
        CREATE FUNCTION vervfy_storage.retained_bytes() RETURNS bigint
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE actor text:=current_setting('app.current_user_id',true); used numeric;
        BEGIN
            IF actor IS NULL OR actor !~ '^[A-Za-z0-9_-]{1,32}$'
               OR NOT EXISTS(SELECT 1 FROM public.users WHERE id=actor) THEN
                RAISE EXCEPTION 'Storage account context required' USING ERRCODE='42501';
            END IF;
            IF EXISTS(SELECT 1 FROM vervfy_storage.objects
                      WHERE tenant_id=actor AND reserved_bytes IS NULL) THEN
                RAISE EXCEPTION 'Storage inventory requires reconciliation' USING ERRCODE='55000';
            END IF;
            SELECT coalesce(sum(reserved_bytes),0) INTO used
                FROM vervfy_storage.objects WHERE tenant_id=actor;
            RETURN used::bigint;
        END $$
    """)
    _clear_function_acl("retained_bytes()")
    op.execute(
        "GRANT EXECUTE ON FUNCTION vervfy_storage.retained_bytes() TO app_runtime"
    )
    op.execute("RESET ROLE")
    op.execute(f"REVOKE CREATE ON SCHEMA vervfy_storage FROM {OWNER}")
    # No changes to cleanup functions, claims, deletion grants or namespace guard.


def downgrade():
    raise RuntimeError("0034 is forward-only: retained storage charges must survive")
