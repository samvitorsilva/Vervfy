"""Expose the hard-disabled cleanup gate only to the cleanup worker."""

import sqlalchemy as sa

from alembic import op

revision = "0033_cleanup_activation_gate"
down_revision = "0032_merge_storage_webauthn"
branch_labels = None
depends_on = None

OWNER = "vervfy_storage_lifecycle_owner"
EXECUTOR = "vervfy_storage_cleanup"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if bind.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("0033 requires the reviewed public application schema")
    op.execute(f"GRANT CREATE ON SCHEMA vervfy_storage TO {OWNER}")
    op.execute(f"SET LOCAL ROLE {OWNER}")
    op.execute("""
        CREATE FUNCTION vervfy_storage.cleanup_enabled()
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $$
            SELECT COALESCE((
                SELECT physical_cleanup_enabled
                FROM vervfy_storage.namespaces WHERE id=1
            ),false)
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION vervfy_storage.cleanup_enabled() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION vervfy_storage.cleanup_enabled() TO "
        + EXECUTOR
    )
    op.execute("RESET ROLE")
    op.execute(f"REVOKE CREATE ON SCHEMA vervfy_storage FROM {OWNER}")


def downgrade() -> None:
    raise RuntimeError("0033 is forward-only; preserve the cleanup activation gate")
