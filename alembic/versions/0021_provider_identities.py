"""Prepare provider identities and optional password credentials.

Downgrade refuses to discard identities or strand passwordless accounts.
SQLite batch alteration requires foreign_keys=OFF on the migration connection;
run SQLite migrations offline from application traffic, with integrity checks.
"""
import sqlalchemy as sa

from alembic import op

revision = "0021_provider_identities"
down_revision = "0020_playlist_last_played"
branch_labels = None
depends_on = None


def _alter_password(nullable: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        if bind.exec_driver_sql("PRAGMA foreign_keys").scalar():
            raise RuntimeError("SQLite batch migration requires foreign_keys=OFF before the transaction")
        with op.batch_alter_table("users") as batch:
            batch.alter_column("password_hash", existing_type=sa.String(128), nullable=nullable)
    else:
        op.alter_column("users", "password_hash", existing_type=sa.String(128), nullable=nullable)


def upgrade() -> None:
    _alter_password(True)
    op.create_table(
        "provider_identities",
        sa.Column("issuer", sa.String(255), primary_key=True),
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_provider_identities_user_id", "provider_identities", ["user_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE provider_identities ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE provider_identities FORCE ROW LEVEL SECURITY")
        op.execute("""CREATE POLICY provider_identities_tenant_isolation ON provider_identities
            USING (user_id = current_setting('app.current_user_id', true))
            WITH CHECK (user_id = current_setting('app.current_user_id', true))""")


def downgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    if postgres:
        # Keep credential/identity writes from racing the guards and table drop.
        # The migration role must own these tables; application roles need no
        # BYPASSRLS privilege. Locks remain held until transaction completion.
        op.execute("LOCK TABLE users, provider_identities IN ACCESS EXCLUSIVE MODE")
    if bind.execute(sa.text("SELECT 1 FROM users WHERE password_hash IS NULL LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while passwordless accounts exist")
    if postgres:
        # Only the table owner can do this; it can now inspect every identity.
        # Other connections cannot observe the change under the exclusive lock.
        op.execute("ALTER TABLE provider_identities NO FORCE ROW LEVEL SECURITY")
    try:
        has_identities = bind.execute(sa.text("SELECT 1 FROM provider_identities LIMIT 1")).first()
    finally:
        if postgres:
            op.execute("ALTER TABLE provider_identities FORCE ROW LEVEL SECURITY")
    if has_identities:
        raise RuntimeError("Cannot downgrade while provider identities exist")
    _alter_password(False)
    op.drop_index("ix_provider_identities_user_id", table_name="provider_identities")
    op.drop_table("provider_identities")
