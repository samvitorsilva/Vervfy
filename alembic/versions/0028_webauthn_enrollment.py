"""Dormant registration/recovery capabilities; no account/session backfill."""

import sqlalchemy as sa

from alembic import op

revision = "0028_webauthn_enrollment"
down_revision = "0027_webauthn_foundation"
branch_labels = None
depends_on = None
metadata = sa.MetaData()
sa.Table("users", metadata, sa.Column("id", sa.String(32), primary_key=True))
enrollments = sa.Table(
    "webauthn_enrollments",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column(
        "user_id",
        sa.String(32),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("session_binding", sa.String(64), nullable=False),
    sa.Column("session_version", sa.Integer, nullable=False),
    sa.Column("method", sa.String(24), nullable=False),
    sa.Column("signup_transaction", sa.String(64), unique=True),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    sa.Column("consumed_at", sa.BigInteger),
    sa.CheckConstraint(
        "method IN ('google_signup','password')", name="ck_enrollment_method"
    ),
    sa.CheckConstraint(
        "(method = 'google_signup' AND signup_transaction IS NOT NULL) OR (method = 'password' AND signup_transaction IS NULL)",
        name="ck_enrollment_source",
    ),
    sa.CheckConstraint(
        "expires_at > created_at AND expires_at <= created_at + 300",
        name="ck_enrollment_expiry",
    ),
)
sa.Index(
    "uq_signup_enrollment_user",
    enrollments.c.user_id,
    unique=True,
    postgresql_where=enrollments.c.method == "google_signup",
    sqlite_where=enrollments.c.method == "google_signup",
)


def upgrade():
    bind = op.get_bind()
    enrollments.create(bind)
    if bind.dialect.name != "postgresql":
        return
    grantees = (
        bind.execute(
            sa.text("""
        SELECT DISTINCT r.rolname FROM pg_class c
        CROSS JOIN LATERAL aclexplode(c.relacl) a
        JOIN pg_roles r ON r.oid=a.grantee
        WHERE c.oid='webauthn_enrollments'::regclass AND a.grantee<>c.relowner
    """)
        )
        .scalars()
        .all()
    )
    quote = bind.dialect.identifier_preparer.quote
    for role in grantees:
        op.execute(f"REVOKE ALL ON webauthn_enrollments FROM {quote(role)}")
    op.execute("REVOKE ALL ON webauthn_enrollments FROM PUBLIC")
    op.execute("ALTER TABLE webauthn_enrollments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webauthn_enrollments FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY webauthn_enrollments_tenant ON webauthn_enrollments
        USING (user_id=current_setting('app.current_user_id',true))
        WITH CHECK (user_id=current_setting('app.current_user_id',true))""")
    op.execute("GRANT SELECT, INSERT ON webauthn_enrollments TO app_runtime")
    op.execute("GRANT UPDATE (consumed_at) ON webauthn_enrollments TO app_runtime")
    op.execute("GRANT INSERT ON webauthn_handles, webauthn_credentials TO app_runtime")
    op.execute(
        "GRANT SELECT, INSERT ON account_recovery_codes, account_recovery_states TO app_runtime"
    )
    op.execute("GRANT UPDATE (consumed_at) ON account_recovery_codes TO app_runtime")


def downgrade():
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"
    names = (
        "webauthn_enrollments",
        "webauthn_handles",
        "webauthn_credentials",
        "account_recovery_codes",
        "account_recovery_states",
    )
    if pg:
        op.execute("LOCK TABLE " + ", ".join(names) + " IN ACCESS EXCLUSIVE MODE")
    for name in names:
        if pg:
            op.execute(f"ALTER TABLE {name} NO FORCE ROW LEVEL SECURITY")
        try:
            occupied = bind.execute(sa.text(f"SELECT 1 FROM {name} LIMIT 1")).first()
        finally:
            if pg:
                op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        if occupied:
            raise RuntimeError(
                "Cannot downgrade retained enrollment/recovery security data"
            )
    if pg:
        op.execute(
            "REVOKE INSERT ON webauthn_handles, webauthn_credentials FROM app_runtime"
        )
        op.execute(
            "REVOKE SELECT, INSERT ON account_recovery_codes, account_recovery_states FROM app_runtime"
        )
        op.execute(
            "REVOKE UPDATE (consumed_at) ON account_recovery_codes FROM app_runtime"
        )
    enrollments.drop(bind)
