"""Restricted pre-login lookup; requires DBA-provisioned capability roles.

Provision vervfy_identity_lookup_owner and vervfy_identity_lookup as NOLOGIN,
NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOINHERIT.
Only the migration role may be a member of the owner role. The owner must have
no other role memberships. Grant the executor role only to google_auth_lookup, the trusted auth backend
login. No other login or nested role may inherit or SET this capability. This
migration does not manage logins.
"""
import sqlalchemy as sa

from alembic import op
from supabase_role_memberships import (
    assert_member_memberships,
    assert_role_memberships,
)

revision = "0022_provider_identity_lookup"
down_revision = "0021_provider_identities"
branch_labels = None
depends_on = None

OWNER = "vervfy_identity_lookup_owner"
EXECUTOR = "vervfy_identity_lookup"
LOOKUP_LOGIN = "google_auth_lookup"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # No insecure SQLite fallback for privileged authentication lookup.
    role_ids = {}
    for role in (OWNER, EXECUTOR):
        row = bind.execute(sa.text("""
            SELECT oid, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                   rolcreaterole, rolreplication, rolinherit
            FROM pg_catalog.pg_roles WHERE rolname = :role
        """), {"role": role}).first()
        if row is None or any(row[1:]):
            raise RuntimeError(f"Provision restricted NOLOGIN capability role {role} before migration")
        role_ids[role] = row.oid
    lookup_login = bind.execute(sa.text("""
        SELECT oid, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
               rolcreaterole, rolreplication, rolinherit
        FROM pg_catalog.pg_roles WHERE rolname = :role
    """), {"role": LOOKUP_LOGIN}).first()
    if lookup_login is None or not lookup_login.rolcanlogin or any(
        lookup_login[index] for index in range(2, 8)
    ):
        raise RuntimeError(f"Provision restricted login role {LOOKUP_LOGIN} before migration")
    role_ids[LOOKUP_LOGIN] = lookup_login.oid
    migration_role = bind.execute(
        sa.text("SELECT current_user")
    ).scalar_one()
    assert_role_memberships(
        bind,
        OWNER,
        [(migration_role, "postgres", False, False, True)],
    )
    assert_member_memberships(bind, OWNER, [])
    assert_role_memberships(
        bind,
        EXECUTOR,
        [(LOOKUP_LOGIN, "postgres", False, True, False)],
    )
    assert_role_memberships(bind, LOOKUP_LOGIN, [])
    assert_member_memberships(
        bind,
        LOOKUP_LOGIN,
        [(EXECUTOR, "postgres", False, True, False)],
    )
    unexpected_executor_access = bind.execute(sa.text("""
        SELECT r.rolname
        FROM pg_catalog.pg_roles r
        WHERE r.oid NOT IN (:executor, :lookup_login)
          AND NOT r.rolsuper
          AND (
              pg_catalog.pg_has_role(r.oid, :executor, 'USAGE')
              OR pg_catalog.pg_has_role(r.oid, :executor, 'SET')
          )
        LIMIT 1
    """), {
        "executor": role_ids[EXECUTOR],
        "lookup_login": role_ids[LOOKUP_LOGIN],
    }).first()
    if unexpected_executor_access:
        raise RuntimeError(
            f"Role {unexpected_executor_access.rolname} can inherit or SET {EXECUTOR}"
        )
    if not bind.execute(sa.text("SELECT pg_catalog.pg_has_role(current_user, :owner, 'MEMBER')"), {"owner": OWNER}).scalar():
        raise RuntimeError("Migration role requires lookup-owner membership to assign function ownership")
    schema = bind.execute(sa.text("SELECT current_schema()")).scalar_one()
    qualified_table = bind.dialect.identifier_preparer.quote_schema(schema) + '.provider_identities'
    # A new private schema avoids inherited PUBLIC EXECUTE grants or path shadowing.
    op.execute("CREATE SCHEMA vervfy_auth")
    op.execute("REVOKE ALL ON SCHEMA vervfy_auth FROM PUBLIC")
    schema_grantees = bind.execute(sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_namespace n
        CROSS JOIN LATERAL pg_catalog.aclexplode(n.nspacl) a
        JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE n.nspname = 'vervfy_auth' AND r.rolname <> current_user
    """)).scalars().all()
    for role in schema_grantees:
        quoted = bind.dialect.identifier_preparer.quote(role)
        op.execute(f"REVOKE ALL ON SCHEMA vervfy_auth FROM {quoted}")
    op.execute(f"GRANT USAGE ON SCHEMA {bind.dialect.identifier_preparer.quote_schema(schema)} TO {OWNER}")
    op.execute(f"GRANT SELECT (issuer, subject, user_id) ON {qualified_table} TO {OWNER}")
    op.execute(f"""CREATE POLICY provider_identity_lookup ON {qualified_table}
        FOR SELECT TO {OWNER} USING (true)""")
    op.execute(f"GRANT USAGE, CREATE ON SCHEMA vervfy_auth TO {OWNER}")
    op.execute(f"""
        CREATE FUNCTION vervfy_auth.lookup_provider_identity(p_issuer text, p_subject text)
        RETURNS text LANGUAGE sql STABLE STRICT SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $lookup$
            SELECT user_id::text FROM {qualified_table}
            WHERE issuer COLLATE "C" = p_issuer COLLATE "C"
              AND subject COLLATE "C" = p_subject COLLATE "C"
              AND p_issuer IN ('https://accounts.google.com', 'accounts.google.com')
              AND length(p_subject) BETWEEN 1 AND 255
        $lookup$
    """)
    op.execute("REVOKE ALL ON FUNCTION vervfy_auth.lookup_provider_identity(text, text) FROM PUBLIC")
    # Remove grants inherited from deployment-specific default privileges too.
    grantees = bind.execute(sa.text("""
        SELECT DISTINCT r.rolname FROM pg_catalog.pg_proc p
        CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
        JOIN pg_catalog.pg_roles r ON r.oid = a.grantee
        WHERE p.oid = 'vervfy_auth.lookup_provider_identity(text,text)'::regprocedure
          AND r.rolname <> current_user
    """)).scalars().all()
    for role in grantees:
        quoted = bind.dialect.identifier_preparer.quote(role)
        op.execute(f"REVOKE ALL ON FUNCTION vervfy_auth.lookup_provider_identity(text,text) FROM {quoted}")
    op.execute(f"GRANT USAGE ON SCHEMA vervfy_auth TO {EXECUTOR}")
    op.execute(f"GRANT EXECUTE ON FUNCTION vervfy_auth.lookup_provider_identity(text, text) TO {EXECUTOR}")
    # The migration principal owns the function until this point. Grant before
    # transferring ownership; afterward it is not authorized to grant EXECUTE.
    op.execute(f"ALTER FUNCTION vervfy_auth.lookup_provider_identity(text, text) OWNER TO {OWNER}")
    op.execute(f"REVOKE CREATE ON SCHEMA vervfy_auth FROM {OWNER}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    schema = bind.execute(sa.text("SELECT current_schema()")).scalar_one()
    quoted = bind.dialect.identifier_preparer.quote_schema(schema)
    op.execute("DROP FUNCTION vervfy_auth.lookup_provider_identity(text, text)")
    op.execute(f"DROP POLICY provider_identity_lookup ON {quoted}.provider_identities")
    op.execute(f"REVOKE SELECT (issuer, subject, user_id) ON {quoted}.provider_identities FROM {OWNER}")
    op.execute(f"REVOKE USAGE ON SCHEMA {quoted} FROM {OWNER}")
    op.execute("DROP SCHEMA vervfy_auth")  # Deliberately no CASCADE; preserve unexpected objects.
    # Shared capability roles and their externally managed memberships are retained.
