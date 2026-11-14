"""Grant tenant-scoped provider identity operations to the API runtime role."""

from alembic import op

revision = "0024_provider_identity_access"
down_revision = "0023_missing_media_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "REVOKE ALL ON TABLE provider_identities FROM app_runtime"
        )
        op.execute(
            "GRANT SELECT, INSERT, DELETE "
            "ON TABLE provider_identities TO app_runtime"
        )


def downgrade() -> None:
    raise RuntimeError(
        "0024_provider_identity_runtime_access is forward-only; "
        "revoking tenant-scoped identity access would break Google account flows"
    )
