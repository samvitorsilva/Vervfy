"""Track when a playlist was last listened to."""
from alembic import op
import sqlalchemy as sa


revision = "0020_playlist_last_played"
down_revision = "0019_track_listens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column("last_played_at", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("playlists", "last_played_at")
