"""Track stored audio size for per-user quotas."""
from alembic import op
import sqlalchemy as sa

revision = "0003_track_size"
down_revision = "0002_profile_photo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.execute(sa.text("UPDATE tracks SET size_bytes = length(audio_data) WHERE size_bytes = 0"))


def downgrade() -> None:
    op.drop_column("tracks", "size_bytes")
