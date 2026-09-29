"""Add verified and pending account email state."""
from alembic import op
import sqlalchemy as sa

revision = "0010_verified_account_email"
down_revision = "0009_upload_retry_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("pending_email", sa.String(320), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pending_email")
    op.drop_column("users", "email_verified")
