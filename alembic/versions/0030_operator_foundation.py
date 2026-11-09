"""Private operator identity and audit schema; no authentication path is enabled."""

import sqlalchemy as sa

from alembic import op

revision = "0030_operator_foundation"
down_revision = "0029_cleanup_retry_limits"
branch_labels = None
depends_on = None

OWNER = "vervfy_operator_foundation_owner"
SCHEMA = "vervfy_operator"
TABLES = (
    "operator_identities",
    "operator_credentials",
    "operator_role_assignments",
    "operator_sessions",
    "storage_operator_audit",
)


def _validate_owner(bind) -> None:
    owner = bind.execute(
        sa.text("""
        SELECT oid,rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,
               rolcreaterole,rolreplication,rolinherit
        FROM pg_catalog.pg_roles WHERE rolname=:name
        """),
        {"name": OWNER},
    ).first()
    migration_role = bind.execute(
        sa.text("""
        SELECT oid,rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,
               rolcreaterole,rolreplication
        FROM pg_catalog.pg_roles WHERE rolname=current_user
        """)
    ).first()
    if (
        owner is None
        or owner.rolcanlogin
        or any(owner[2:])
        or migration_role is None
        or not migration_role.rolcanlogin
        or any(migration_role[2:])
    ):
        raise RuntimeError(
            f"Provision restricted NOLOGIN role {OWNER} and use a restricted migration login"
        )

    memberships = bind.execute(
        sa.text("""
        SELECT member,inherit_option,set_option,admin_option
        FROM pg_catalog.pg_auth_members WHERE roleid=:owner
        """),
        {"owner": owner.oid},
    ).all()
    current_oid = migration_role.oid
    if (
        len(memberships) != 1
        or memberships[0].member != current_oid
        or memberships[0].inherit_option
        or not memberships[0].set_option
        or memberships[0].admin_option
    ):
        raise RuntimeError(
            f"Only the migration login may SET {OWNER}; inheritance and ADMIN are forbidden"
        )
    if bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_auth_members
        WHERE member=:owner
        LIMIT 1
        """),
        {"owner": owner.oid},
    ).first():
        raise RuntimeError(f"{OWNER} must not inherit any other database role")

    unexpected_member = bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_roles r
        WHERE NOT r.rolsuper AND r.oid NOT IN (:owner,:migration)
          AND (pg_catalog.pg_has_role(r.oid,:owner,'USAGE')
               OR pg_catalog.pg_has_role(r.oid,:owner,'SET'))
        LIMIT 1
        """),
        {"owner": owner.oid, "migration": current_oid},
    ).first()
    if unexpected_member:
        raise RuntimeError(f"Unexpected effective membership in {OWNER}")

    unsafe_privilege = bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
          AND (c.relowner=:owner OR
            CASE WHEN c.relkind='S' THEN
                pg_catalog.has_sequence_privilege(:owner,c.oid,'USAGE,SELECT,UPDATE')
            WHEN c.relkind IN ('r','p','v','m','f') THEN
                pg_catalog.has_table_privilege(
                    :owner,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
                )
                OR pg_catalog.has_any_column_privilege(
                    :owner,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'
                )
            ELSE false END)
        UNION ALL
        SELECT 1 FROM pg_catalog.pg_namespace n
        WHERE n.nspowner=:owner
           OR (n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
               AND pg_catalog.has_schema_privilege(:owner,n.oid,'CREATE'))
        UNION ALL
        SELECT 1 FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
          AND (p.proowner=:owner OR
              (pg_catalog.has_schema_privilege(:owner,n.oid,'USAGE')
               AND pg_catalog.has_function_privilege(:owner,p.oid,'EXECUTE')))
        UNION ALL
        SELECT 1 FROM pg_catalog.pg_default_acl d
        CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
        WHERE d.defaclrole=:owner OR a.grantee=0 OR a.grantee=:owner
           OR (a.grantee<>0 AND
               (pg_catalog.pg_has_role(:owner,a.grantee,'USAGE')
                OR pg_catalog.pg_has_role(:owner,a.grantee,'SET')))
        LIMIT 1
        """),
        {"owner": owner.oid},
    ).first()
    if unsafe_privilege:
        raise RuntimeError(
            f"{OWNER} has pre-existing ownership, privileges, routines, or default ACLs"
        )


def _revoke_schema_grants(bind) -> None:
    op.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC")
    grantees = bind.execute(
        sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_namespace n
        CROSS JOIN LATERAL pg_catalog.aclexplode(n.nspacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE n.nspname=:schema AND r.rolname<>current_user
        """),
        {"schema": SCHEMA},
    ).scalars()
    for role in grantees:
        op.execute(
            f"REVOKE ALL ON SCHEMA {SCHEMA} FROM "
            f"{bind.dialect.identifier_preparer.quote(role)}"
        )


def _revoke_object_grants(
    bind, kind: str, name: str, query: str, parameters: dict[str, str]
) -> None:
    op.execute(f"REVOKE ALL ON {kind} {name} FROM PUBLIC")
    grantees = bind.execute(sa.text(query), parameters).scalars()
    for role in grantees:
        op.execute(
            f"REVOKE ALL ON {kind} {name} FROM "
            f"{bind.dialect.identifier_preparer.quote(role)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if bind.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("0030 requires the reviewed public application schema")
    _validate_owner(bind)

    op.execute(f"CREATE SCHEMA {SCHEMA}")
    _revoke_schema_grants(bind)
    op.execute(f"GRANT USAGE,CREATE ON SCHEMA {SCHEMA} TO {OWNER}")
    op.execute(f"SET LOCAL ROLE {OWNER}")
    op.execute(f"""
        CREATE TABLE {SCHEMA}.operator_identities (
            id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
            normalized_identifier text COLLATE "C" NOT NULL UNIQUE,
            account_status text NOT NULL DEFAULT 'pending'
                CHECK(account_status IN ('pending','active','suspended','revoked')),
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            suspended_at timestamptz,
            revoked_at timestamptz,
            provisioned_by_operator_id uuid
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            provisioning_method text NOT NULL
                CHECK(provisioning_method IN ('break_glass','operator_admin')),
            provisioning_reason text NOT NULL
                CHECK(pg_catalog.length(pg_catalog.btrim(provisioning_reason))>0),
            provisioning_reference text,
            CHECK(normalized_identifier ~ '^[a-z0-9][a-z0-9._-]{{2,63}}$'),
            CHECK((account_status='suspended')=(suspended_at IS NOT NULL)),
            CHECK((account_status='revoked')=(revoked_at IS NOT NULL)),
            CHECK(provisioning_method<>'break_glass' OR provisioning_reference IS NOT NULL)
        )
    """)
    op.execute(f"""
        CREATE TABLE {SCHEMA}.operator_credentials (
            credential_id bytea PRIMARY KEY
                CHECK(pg_catalog.octet_length(credential_id) BETWEEN 1 AND 1023),
            operator_id uuid NOT NULL
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            public_key bytea NOT NULL CHECK(pg_catalog.octet_length(public_key)>0),
            credential_metadata jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK(
                    pg_catalog.jsonb_typeof(credential_metadata)='object'
                    AND credential_metadata-ARRAY[
                        'aaguid','transports','device_type','discoverable'
                    ]::text[]='{{}}'::jsonb
                    AND (NOT credential_metadata ? 'aaguid'
                         OR pg_catalog.jsonb_typeof(credential_metadata->'aaguid')='string')
                    AND (NOT credential_metadata ? 'transports'
                         OR pg_catalog.jsonb_typeof(credential_metadata->'transports')='array')
                    AND (NOT credential_metadata ? 'device_type'
                         OR pg_catalog.jsonb_typeof(credential_metadata->'device_type')='string')
                    AND (NOT credential_metadata ? 'discoverable'
                         OR pg_catalog.jsonb_typeof(credential_metadata->'discoverable')='boolean')
                ),
            signature_counter bigint NOT NULL DEFAULT 0 CHECK(signature_counter>=0),
            backup_eligible boolean NOT NULL DEFAULT false,
            backup_state boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            last_used_at timestamptz,
            revoked_at timestamptz,
            UNIQUE(credential_id,operator_id),
            CHECK(NOT backup_state OR backup_eligible)
        )
    """)
    op.execute(f"""
        CREATE TABLE {SCHEMA}.operator_role_assignments (
            id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
            operator_id uuid NOT NULL
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            role text NOT NULL CHECK(role IN ('operator_admin','storage_reviewer')),
            granting_admin_operator_id uuid
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            granted_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            revoked_at timestamptz,
            revoked_by_operator_id uuid
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            reason text NOT NULL CHECK(pg_catalog.length(pg_catalog.btrim(reason))>0),
            bootstrap_reference text,
            CHECK(granting_admin_operator_id IS NULL OR
                  granting_admin_operator_id<>operator_id),
            CHECK(granting_admin_operator_id IS NOT NULL OR bootstrap_reference IS NOT NULL),
            CHECK((revoked_at IS NULL)=(revoked_by_operator_id IS NULL))
        )
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_operator_role_assignments_active
        ON {SCHEMA}.operator_role_assignments(operator_id,role)
        WHERE revoked_at IS NULL
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_operator_role_assignments_bootstrap_admin
        ON {SCHEMA}.operator_role_assignments(role)
        WHERE role='operator_admin' AND granting_admin_operator_id IS NULL
          AND revoked_at IS NULL
    """)
    op.execute(f"""
        CREATE TABLE {SCHEMA}.operator_sessions (
            id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
            operator_id uuid NOT NULL
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            credential_id bytea NOT NULL,
            session_token_hash bytea NOT NULL UNIQUE
                CHECK(pg_catalog.octet_length(session_token_hash)=32),
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            authenticated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            last_used_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            FOREIGN KEY(credential_id,operator_id)
                REFERENCES {SCHEMA}.operator_credentials(credential_id,operator_id)
                ON DELETE RESTRICT,
            CHECK(expires_at>created_at),
            CHECK(last_used_at>=created_at)
        )
    """)
    op.execute(f"""
        CREATE TABLE {SCHEMA}.storage_operator_audit (
            id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
            operator_id uuid NOT NULL
                REFERENCES {SCHEMA}.operator_identities(id) ON DELETE RESTRICT,
            action text NOT NULL CHECK(pg_catalog.length(pg_catalog.btrim(action))>0),
            target_resource_type text NOT NULL
                CHECK(pg_catalog.length(pg_catalog.btrim(target_resource_type))>0),
            target_resource_id text NOT NULL
                CHECK(pg_catalog.length(pg_catalog.btrim(target_resource_id))>0),
            previous_state jsonb,
            resulting_state jsonb,
            reason text NOT NULL CHECK(pg_catalog.length(pg_catalog.btrim(reason))>0),
            occurred_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            request_id uuid NOT NULL
        )
    """)
    op.execute(f"""
        CREATE INDEX ix_operator_credentials_operator
        ON {SCHEMA}.operator_credentials(operator_id)
    """)
    op.execute(f"""
        CREATE INDEX ix_operator_sessions_operator_expiry
        ON {SCHEMA}.operator_sessions(operator_id,expires_at)
    """)
    op.execute(f"""
        CREATE INDEX ix_storage_operator_audit_target_time
        ON {SCHEMA}.storage_operator_audit(
            target_resource_type,target_resource_id,occurred_at
        )
    """)
    op.execute(f"""
        CREATE INDEX ix_storage_operator_audit_request
        ON {SCHEMA}.storage_operator_audit(request_id)
    """)

    op.execute(f"""
        CREATE FUNCTION {SCHEMA}.set_operator_identity_updated_at()
        RETURNS trigger LANGUAGE plpgsql
        SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF OLD.account_status='revoked'
               OR NEW.id IS DISTINCT FROM OLD.id
               OR NEW.normalized_identifier IS DISTINCT FROM OLD.normalized_identifier
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.provisioned_by_operator_id IS DISTINCT FROM OLD.provisioned_by_operator_id
               OR NEW.provisioning_method IS DISTINCT FROM OLD.provisioning_method
               OR NEW.provisioning_reason IS DISTINCT FROM OLD.provisioning_reason
               OR NEW.provisioning_reference IS DISTINCT FROM OLD.provisioning_reference THEN
                RAISE EXCEPTION 'Operator identity history is immutable'
                    USING ERRCODE='55000';
            END IF;
            IF NEW.account_status IN ('suspended','revoked')
               AND OLD.account_status IS DISTINCT FROM NEW.account_status THEN
                UPDATE {SCHEMA}.operator_sessions
                SET revoked_at=pg_catalog.clock_timestamp()
                WHERE operator_id=NEW.id AND revoked_at IS NULL;
            END IF;
            NEW.updated_at:=pg_catalog.clock_timestamp();
            RETURN NEW;
        END $$
    """)
    op.execute(f"""
        CREATE FUNCTION {SCHEMA}.reject_operator_history_mutation()
        RETURNS trigger LANGUAGE plpgsql
        SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'Operator identity and audit history are append-only'
                USING ERRCODE='55000';
            RETURN NULL;
        END $$
    """)
    op.execute(f"""
        CREATE FUNCTION {SCHEMA}.guard_operator_session()
        RETURNS trigger LANGUAGE plpgsql
        SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF TG_OP='UPDATE' THEN
                IF OLD.revoked_at IS NOT NULL
                   OR NEW.id IS DISTINCT FROM OLD.id
                   OR NEW.operator_id IS DISTINCT FROM OLD.operator_id
                   OR NEW.credential_id IS DISTINCT FROM OLD.credential_id
                   OR NEW.session_token_hash IS DISTINCT FROM OLD.session_token_hash
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.authenticated_at IS DISTINCT FROM OLD.authenticated_at
                   OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
                   OR NEW.last_used_at<OLD.last_used_at THEN
                    RAISE EXCEPTION 'Operator session history is immutable'
                        USING ERRCODE='55000';
                END IF;
                IF NEW.revoked_at IS NOT NULL THEN RETURN NEW; END IF;
            END IF;

            IF NOT EXISTS(
                SELECT 1
                FROM {SCHEMA}.operator_identities AS operator
                JOIN {SCHEMA}.operator_credentials AS credential
                  ON credential.operator_id=operator.id
                WHERE operator.id=NEW.operator_id
                  AND operator.account_status='active'
                  AND credential.credential_id=NEW.credential_id
                  AND credential.revoked_at IS NULL
                FOR SHARE OF operator,credential
            ) THEN
                RAISE EXCEPTION 'An active operator and credential are required'
                    USING ERRCODE='42501';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(f"""
        CREATE FUNCTION {SCHEMA}.guard_operator_role_assignment()
        RETURNS trigger LANGUAGE plpgsql
        SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE actor uuid;
        BEGIN
            IF TG_OP='UPDATE' THEN
                IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
                   OR NEW.operator_id IS DISTINCT FROM OLD.operator_id
                   OR NEW.role IS DISTINCT FROM OLD.role
                   OR NEW.granting_admin_operator_id IS DISTINCT FROM OLD.granting_admin_operator_id
                   OR NEW.granted_at IS DISTINCT FROM OLD.granted_at
                   OR NEW.reason IS DISTINCT FROM OLD.reason
                   OR NEW.bootstrap_reference IS DISTINCT FROM OLD.bootstrap_reference
                   OR NEW.revoked_by_operator_id IS NULL THEN
                    RAISE EXCEPTION 'Role assignment history is immutable except for revocation'
                        USING ERRCODE='55000';
                END IF;
                actor:=NEW.revoked_by_operator_id;
            ELSE
                IF NEW.revoked_at IS NOT NULL OR NEW.revoked_by_operator_id IS NOT NULL
                   OR NOT EXISTS(
                       SELECT 1 FROM {SCHEMA}.operator_identities
                       WHERE id=NEW.operator_id AND account_status='active'
                   ) THEN
                    RAISE EXCEPTION 'Role assignment requires an active operator'
                        USING ERRCODE='42501';
                END IF;
                actor:=NEW.granting_admin_operator_id;
            END IF;

            IF actor IS NULL THEN
                IF TG_OP<>'INSERT' OR NEW.role<>'operator_admin'
                   OR NEW.bootstrap_reference IS NULL
                   OR EXISTS(
                       SELECT 1 FROM {SCHEMA}.operator_role_assignments
                       WHERE role='operator_admin' AND revoked_at IS NULL
                   ) THEN
                    RAISE EXCEPTION 'Invalid first-operator bootstrap grant'
                        USING ERRCODE='42501';
                END IF;
            ELSIF NOT EXISTS(
                SELECT 1 FROM {SCHEMA}.operator_identities AS admin
                JOIN {SCHEMA}.operator_role_assignments AS assignment
                  ON assignment.operator_id=admin.id
                WHERE admin.id=actor AND admin.account_status='active'
                  AND assignment.role='operator_admin'
                  AND assignment.revoked_at IS NULL
                FOR SHARE OF admin,assignment
            ) THEN
                RAISE EXCEPTION 'An active operator administrator is required'
                    USING ERRCODE='42501';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(f"""
        CREATE TRIGGER operator_identity_updated_at
        BEFORE UPDATE ON {SCHEMA}.operator_identities
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.set_operator_identity_updated_at()
    """)
    op.execute(f"""
        CREATE TRIGGER operator_sessions_guard
        BEFORE INSERT OR UPDATE ON {SCHEMA}.operator_sessions
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.guard_operator_session()
    """)
    op.execute(f"""
        CREATE TRIGGER operator_identity_no_delete
        BEFORE DELETE OR TRUNCATE ON {SCHEMA}.operator_identities
        FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.reject_operator_history_mutation()
    """)
    op.execute(f"""
        CREATE TRIGGER operator_credentials_no_delete
        BEFORE DELETE OR TRUNCATE ON {SCHEMA}.operator_credentials
        FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.reject_operator_history_mutation()
    """)
    op.execute(f"""
        CREATE TRIGGER operator_role_assignments_guard
        BEFORE INSERT OR UPDATE ON {SCHEMA}.operator_role_assignments
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.guard_operator_role_assignment()
    """)
    op.execute(f"""
        CREATE TRIGGER operator_role_assignments_no_delete
        BEFORE DELETE OR TRUNCATE ON {SCHEMA}.operator_role_assignments
        FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.reject_operator_history_mutation()
    """)
    op.execute(f"""
        CREATE TRIGGER storage_operator_audit_immutable
        BEFORE UPDATE OR DELETE ON {SCHEMA}.storage_operator_audit
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.reject_operator_history_mutation()
    """)
    op.execute(f"""
        CREATE TRIGGER storage_operator_audit_no_truncate
        BEFORE TRUNCATE ON {SCHEMA}.storage_operator_audit
        FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.reject_operator_history_mutation()
    """)

    for table in TABLES:
        qualified = f"{SCHEMA}.{table}"
        op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY operator_foundation_owner ON {qualified} "
            f"FOR ALL TO {OWNER} USING(true) WITH CHECK(true)"
        )
        _revoke_object_grants(
            bind,
            "TABLE",
            qualified,
            """
            SELECT DISTINCT r.rolname FROM pg_catalog.pg_class c
            CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) a
            JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
            WHERE c.oid=pg_catalog.to_regclass(:name) AND r.rolname<>:owner
            """,
            {"name": qualified, "owner": OWNER},
        )
    for signature in (
        "set_operator_identity_updated_at()",
        "reject_operator_history_mutation()",
        "guard_operator_role_assignment()",
        "guard_operator_session()",
    ):
        _revoke_object_grants(
            bind,
            "FUNCTION",
            f"{SCHEMA}.{signature}",
            """
            SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p
            CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
            JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
            WHERE p.oid=pg_catalog.to_regprocedure(:name) AND r.rolname<>:owner
            """,
            {
                "name": f"{SCHEMA}.{signature}",
                "owner": OWNER,
            },
        )

    op.execute("RESET ROLE")
    op.execute(f"REVOKE CREATE ON SCHEMA {SCHEMA} FROM {OWNER}")


def downgrade() -> None:
    raise RuntimeError(
        "0030 is forward-only: preserve independent operator identities and audit history"
    )
