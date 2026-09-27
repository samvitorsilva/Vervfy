"""Track bounded upload worker retry attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0009_upload_retry_count"
down_revision = "0008_upload_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "upload_jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("upload_jobs", "attempts")
