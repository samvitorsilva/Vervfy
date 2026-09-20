"""Add session versioning for revocable sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0004_session_version"
down_revision = "0003_track_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("users", "session_version")
