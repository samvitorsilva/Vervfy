"""Align persisted cover sources with the application's supported values."""
import sqlalchemy as sa
from alembic import op

revision = "0025_track_cover_sources"
down_revision = "0024_provider_identity_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve every historical value and support all current model values.
    # No data rewrite: nullable matches TrackRecord and preserves legacy NULLs.
    with op.batch_alter_table("tracks") as batch:
        batch.drop_constraint("ck_tracks_cover_source", type_="check")
        batch.alter_column("cover_source", existing_type=sa.String(20), nullable=True)
        batch.create_check_constraint(
            "ck_tracks_cover_source",
            "cover_source IS NULL OR cover_source IN "
            "('embedded', 'upload', 'user', 'musicbrainz', 'audiodb', "
            "'generated', 'placeholder', 'unknown')",
        )


def downgrade() -> None:
    raise RuntimeError("0025_track_cover_sources is forward-only; narrowing sources could reject existing data")
