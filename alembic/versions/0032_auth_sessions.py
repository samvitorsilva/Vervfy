"""Persist login session allowlist in Postgres across Redis restarts."""

import sqlalchemy as sa

from alembic import op

revision = "0032_auth_sessions"
down_revision = "0031_cleanup_retry_limits"
branch_labels = None
depends_on = None

metadata = sa.MetaData()
sa.Table("users", metadata, sa.Column("id", sa.String(32), primary_key=True))
auth_sessions = sa.Table(
    "auth_sessions",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column(
        "user_id",
        sa.String(32),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("expires_at", sa.Float, nullable=False, index=True),
)


def upgrade() -> None:
    bind = op.get_bind()
    auth_sessions.create(bind)
    if bind.dialect.name != "postgresql":
        return
    grantees = (
        bind.execute(
            sa.text("""
            SELECT DISTINCT r.rolname
            FROM pg_class c
            CROSS JOIN LATERAL aclexplode(c.relacl) a
            JOIN pg_roles r ON r.oid = a.grantee
            WHERE c.oid = to_regclass('auth_sessions') AND a.grantee <> c.relowner
            """)
        )
        .scalars()
        .all()
    )
    quote = bind.dialect.identifier_preparer.quote
    for role in grantees:
        op.execute(f"REVOKE ALL ON TABLE auth_sessions FROM {quote(role)}")
    op.execute("REVOKE ALL ON TABLE auth_sessions FROM PUBLIC")
    # Session IDs are unguessable capabilities (same trust model as the old
    # Redis allowlist). No tenant RLS: revoke(session_id) must work without a
    # prior user_id, and UserStore auth lookups already use SessionLocal().
    op.execute("REVOKE ALL ON TABLE auth_sessions FROM app_runtime")
    op.execute(
        "GRANT SELECT, INSERT, DELETE ON TABLE auth_sessions TO app_runtime"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("LOCK TABLE auth_sessions IN ACCESS EXCLUSIVE MODE")
        occupied = bind.execute(
            sa.select(sa.literal(1)).select_from(auth_sessions).limit(1)
        ).first()
        if occupied:
            raise RuntimeError("Cannot downgrade while auth sessions exist")
    auth_sessions.drop(bind)
