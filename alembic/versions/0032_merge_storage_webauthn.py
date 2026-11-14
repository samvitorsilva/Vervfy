"""Reconcile the independently preserved storage and WebAuthn histories."""

revision = "0032_merge_storage_webauthn"
down_revision = ("0028_webauthn_enrollment", "0031_operator_revocation")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError("The reconciled security migration history is forward-only")
