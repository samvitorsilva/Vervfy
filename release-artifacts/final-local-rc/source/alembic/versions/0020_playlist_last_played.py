"""Track when a playlist was last listened to."""
import sqlalchemy as sa

from alembic import op

revision = "0020_playlist_last_played"
down_revision = "0019_track_listens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("playlists")}
    if "last_played_at" not in columns:
        op.add_column(
            "playlists",
            sa.Column("last_played_at", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("playlists")}
    if "last_played_at" in columns:
        op.drop_column("playlists", "last_played_at")
