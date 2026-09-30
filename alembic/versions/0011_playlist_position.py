"""Add a stable display position to playlists."""
from alembic import op
import sqlalchemy as sa

revision = "0011_playlist_position"
down_revision = "0010_verified_account_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("playlists")}
    if "position" not in columns:
        op.add_column(
            "playlists",
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("playlists", "position")
