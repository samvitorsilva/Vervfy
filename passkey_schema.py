"""Phase 2 Core tables. No routes, enrollment, or implicit database connections."""

import sqlalchemy as sa

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

# Phase 3: durable one-use enrollment capability, never a login/session capability.
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
