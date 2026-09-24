"""Enforce tenant-owned favorite references and add common lookup indexes."""
from alembic import op
import sqlalchemy as sa

revision = "0006_tenant_integrity"
down_revision = "0005_storage_path"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.create_foreign_key(
        "fk_favorites_track_owner",
        "favorites",
        "tracks",
        ["user_id", "track_id"],
        ["user_id", "id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tracks_user_id", "tracks", ["user_id"])
    op.create_index("ix_favorites_track_id", "favorites", ["track_id"])
    op.create_index("ix_playlist_tracks_track_id", "playlist_tracks", ["track_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_index("ix_playlist_tracks_track_id", table_name="playlist_tracks")
    op.drop_index("ix_favorites_track_id", table_name="favorites")
    op.drop_index("ix_tracks_user_id", table_name="tracks")
    op.drop_constraint("fk_favorites_track_owner", "favorites", type_="foreignkey")
