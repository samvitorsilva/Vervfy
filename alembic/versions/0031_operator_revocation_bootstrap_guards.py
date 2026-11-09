"""Fence credential revocation and make first-admin bootstrap one-time."""

import sqlalchemy as sa

from alembic import op

revision = "0031_operator_revocation"
down_revision = "0030_operator_foundation"
branch_labels = None
depends_on = None

OWNER = "vervfy_operator_foundation_owner"
SCHEMA = "vervfy_operator"


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
        raise RuntimeError("Unsafe operator foundation or migration role")

    members = bind.execute(
        sa.text("""
        SELECT member,inherit_option,set_option,admin_option
        FROM pg_catalog.pg_auth_members WHERE roleid=:owner
        """),
        {"owner": owner.oid},
    ).all()
    if (
        len(members) != 1
        or members[0].member != migration_role.oid
        or members[0].inherit_option
        or not members[0].set_option
        or members[0].admin_option
    ):
        raise RuntimeError("Only the migration login may SET the operator owner role")
    if bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=:owner LIMIT 1
        """),
        {"owner": owner.oid},
    ).first():
        raise RuntimeError("Operator owner must not inherit another database role")
    unexpected_member = bind.execute(
        sa.text("""
        SELECT 1 FROM pg_catalog.pg_roles r
        WHERE NOT r.rolsuper AND r.oid NOT IN (:owner,:migration)
          AND (pg_catalog.pg_has_role(r.oid,:owner,'USAGE')
               OR pg_catalog.pg_has_role(r.oid,:owner,'SET'))
        LIMIT 1
        """),
        {"owner": owner.oid, "migration": migration_role.oid},
    ).first()
    if unexpected_member:
        raise RuntimeError("Unexpected effective operator owner membership")


def _revoke_function_grants(bind, signature: str) -> None:
    qualified = f"{SCHEMA}.{signature}"
    op.execute(f"REVOKE ALL ON FUNCTION {qualified} FROM PUBLIC")
    roles = bind.execute(
        sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p
        CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
        WHERE p.oid=pg_catalog.to_regprocedure(:name) AND r.rolname<>:owner
        """),
        {"name": qualified, "owner": OWNER},
    ).scalars()
    for role in roles:
        op.execute(
            f"REVOKE ALL ON FUNCTION {qualified} FROM "
            f"{bind.dialect.identifier_preparer.quote(role)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if bind.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("0031 requires the reviewed public application schema")
    _validate_owner(bind)

    op.execute(f"GRANT CREATE ON SCHEMA {SCHEMA} TO {OWNER}")
    op.execute(f"SET LOCAL ROLE {OWNER}")
    bootstrap_count = bind.execute(
        sa.text("""
        SELECT count(*) FROM vervfy_operator.operator_role_assignments
        WHERE role='operator_admin' AND granting_admin_operator_id IS NULL
        """)
    ).scalar_one()
    if bootstrap_count > 1:
        raise RuntimeError(
            "Multiple historical bootstrap administrators require reviewed remediation"
        )

    op.execute(f"""
        DROP INDEX {SCHEMA}.uq_operator_role_assignments_bootstrap_admin
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_operator_role_assignments_bootstrap_once
        ON {SCHEMA}.operator_role_assignments(role)
        WHERE role='operator_admin' AND granting_admin_operator_id IS NULL
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_operator_role_assignments_bootstrap_reference
        ON {SCHEMA}.operator_role_assignments(bootstrap_reference)
        WHERE granting_admin_operator_id IS NULL
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.guard_operator_role_assignment()
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
                       WHERE role='operator_admin'
                         AND granting_admin_operator_id IS NULL
                   ) THEN
                    RAISE EXCEPTION 'Invalid or previously consumed first-operator bootstrap'
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
    _revoke_function_grants(bind, "guard_operator_role_assignment()")

    op.execute(f"""
        CREATE FUNCTION {SCHEMA}.guard_operator_credential_update()
        RETURNS trigger LANGUAGE plpgsql
        SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF OLD.revoked_at IS NOT NULL
               OR NEW.credential_id IS DISTINCT FROM OLD.credential_id
               OR NEW.operator_id IS DISTINCT FROM OLD.operator_id
               OR NEW.public_key IS DISTINCT FROM OLD.public_key
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'Credential identity and revocation are immutable'
                    USING ERRCODE='55000';
            END IF;

            IF NEW.revoked_at IS NOT NULL THEN
                UPDATE {SCHEMA}.operator_sessions
                SET revoked_at=pg_catalog.clock_timestamp()
                WHERE credential_id=OLD.credential_id AND revoked_at IS NULL;
            END IF;
            RETURN NEW;
        END $$
    """)
    _revoke_function_grants(bind, "guard_operator_credential_update()")
    op.execute(f"""
        CREATE TRIGGER operator_credentials_guard
        BEFORE UPDATE ON {SCHEMA}.operator_credentials
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.guard_operator_credential_update()
    """)
    op.execute("RESET ROLE")
    op.execute(f"REVOKE CREATE ON SCHEMA {SCHEMA} FROM {OWNER}")


def downgrade() -> None:
    raise RuntimeError(
        "0031 is forward-only: preserve operator credential and bootstrap history"
    )
