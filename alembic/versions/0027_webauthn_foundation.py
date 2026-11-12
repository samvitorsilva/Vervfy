"""Add dormant WebAuthn foundation; downgrade refuses any retained security data."""

import sqlalchemy as sa

from alembic import op

metadata = sa.MetaData()
users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("session_version", sa.Integer, nullable=False),
)

handles = sa.Table(
    "webauthn_handles",
    metadata,
    sa.Column(
        "user_id",
        sa.String(32),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("handle", sa.LargeBinary, nullable=False, unique=True),
    sa.CheckConstraint("length(handle) = 32", name="ck_webauthn_handle_length"),
)
credentials = sa.Table(
    "webauthn_credentials",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column(
        "user_id",
        sa.String(32),
        sa.ForeignKey("webauthn_handles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("credential_id", sa.LargeBinary, nullable=False, unique=True),
    sa.Column("public_key", sa.LargeBinary, nullable=False),
    sa.Column("algorithm", sa.Integer, nullable=False),
    sa.Column("sign_count", sa.BigInteger, nullable=False),
    sa.Column("backup_eligible", sa.Boolean, nullable=False),
    sa.Column("backed_up", sa.Boolean, nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("last_used_at", sa.BigInteger),
    sa.Column("revoked_at", sa.BigInteger),
    sa.UniqueConstraint("id", "user_id"),
    sa.CheckConstraint(
        "length(credential_id) BETWEEN 1 AND 1023", name="ck_webauthn_credential_length"
    ),
    sa.CheckConstraint(
        "length(public_key) BETWEEN 1 AND 4096", name="ck_webauthn_key_length"
    ),
    sa.CheckConstraint("algorithm IN (-7, -257, -8)", name="ck_webauthn_algorithm"),
    sa.CheckConstraint(
        "sign_count BETWEEN 0 AND 4294967295", name="ck_webauthn_counter"
    ),
    sa.CheckConstraint("NOT backed_up OR backup_eligible", name="ck_webauthn_backup"),
)
intents = sa.Table(
    "account_action_intents",
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
    sa.Column("action", sa.String(32), nullable=False),
    sa.Column("payload_digest", sa.String(64), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    sa.Column("consumed_at", sa.BigInteger),
    sa.UniqueConstraint("id", "user_id"),
    sa.CheckConstraint(
        "action IN ('password_add','email_change','logout_all','account_delete','passkey_add','passkey_remove','recovery_rotate')",
        name="ck_action_intent_action",
    ),
    sa.CheckConstraint(
        "expires_at > created_at AND expires_at <= created_at + 300",
        name="ck_action_intent_expiry",
    ),
)
proofs = sa.Table(
    "account_verification_proofs",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column(
        "user_id",
        sa.String(32),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("intent_id", sa.String(64), nullable=False, unique=True),
    sa.Column("credential_id", sa.String(64), nullable=False),
    sa.Column("verified_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    sa.Column("consumed_at", sa.BigInteger),
    sa.ForeignKeyConstraint(
        ["intent_id", "user_id"],
        ["account_action_intents.id", "account_action_intents.user_id"],
        ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
        ["credential_id", "user_id"],
        ["webauthn_credentials.id", "webauthn_credentials.user_id"],
        ondelete="CASCADE",
    ),
    sa.CheckConstraint(
        "expires_at > verified_at AND expires_at <= verified_at + 300",
        name="ck_verification_proof_expiry",
    ),
)
recovery_codes = sa.Table(
    "account_recovery_codes",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column(
        "user_id",
        sa.String(32),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("code_hash", sa.LargeBinary, nullable=False, unique=True),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("consumed_at", sa.BigInteger),
    sa.CheckConstraint("length(code_hash) = 32", name="ck_recovery_hash_length"),
)
recovery_states = sa.Table(
    "account_recovery_states",
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
    sa.Column("status", sa.String(24), nullable=False),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    sa.CheckConstraint(
        "status IN ('pending','cancelled','completed')", name="ck_recovery_state_status"
    ),
    sa.CheckConstraint("expires_at > created_at", name="ck_recovery_state_expiry"),
)
TABLES = (handles, credentials, intents, proofs, recovery_codes, recovery_states)

revision = "0027_webauthn_foundation"
down_revision = "0026_application_runtime_grants"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind)
        if bind.dialect.name == "postgresql":
            name = table.name
            # Remove deployment default ACLs before granting exact capabilities.
            # Otherwise ALTER DEFAULT PRIVILEGES could silently expose new tables.
            grantees = (
                bind.execute(
                    sa.text("""
                SELECT DISTINCT r.rolname
                FROM pg_class c
                CROSS JOIN LATERAL aclexplode(c.relacl) a
                JOIN pg_roles r ON r.oid = a.grantee
                WHERE c.oid = to_regclass(:name) AND a.grantee <> c.relowner
            """),
                    {"name": name},
                )
                .scalars()
                .all()
            )
            quote = bind.dialect.identifier_preparer.quote
            for role in grantees:
                op.execute(f"REVOKE ALL ON TABLE {name} FROM {quote(role)}")
            op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
            op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
            op.execute(f"""CREATE POLICY {name}_tenant ON {name}
                USING (user_id = current_setting('app.current_user_id', true))
                WITH CHECK (user_id = current_setting('app.current_user_id', true))""")
            # No enrollment/recovery writes granted in Phase 2.
            grants = {
                "webauthn_handles": "SELECT",
                "webauthn_credentials": "SELECT",
                "account_action_intents": "SELECT, INSERT",
                "account_verification_proofs": "SELECT, INSERT",
            }
            op.execute(f"REVOKE ALL ON TABLE {name} FROM app_runtime")
            if name in grants:
                op.execute(f"GRANT {grants[name]} ON TABLE {name} TO app_runtime")
    if bind.dialect.name == "postgresql":
        op.execute(
            "GRANT UPDATE (sign_count, backed_up, last_used_at) ON webauthn_credentials TO app_runtime"
        )
        op.execute(
            "GRANT UPDATE (consumed_at) ON account_action_intents, account_verification_proofs TO app_runtime"
        )


def downgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    if postgres:
        op.execute(
            "LOCK TABLE "
            + ", ".join(t.name for t in TABLES)
            + " IN ACCESS EXCLUSIVE MODE"
        )
    for table in TABLES:
        if postgres:
            op.execute(f"ALTER TABLE {table.name} NO FORCE ROW LEVEL SECURITY")
        try:
            occupied = bind.execute(
                sa.select(sa.literal(1)).select_from(table).limit(1)
            ).first()
        finally:
            if postgres:
                op.execute(f"ALTER TABLE {table.name} FORCE ROW LEVEL SECURITY")
        if occupied:
            raise RuntimeError("Cannot downgrade while WebAuthn security data exists")
    for table in reversed(TABLES):
        table.drop(bind)
