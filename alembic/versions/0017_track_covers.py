"""Move track covers to Supabase Storage and cache TheAudioDB URLs."""
from alembic import op
import sqlalchemy as sa


revision = "0017_track_covers"
down_revision = "0016_audiodb_artist_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("tracks", sa.Column("cover_path", sa.String(length=600)))
    op.alter_column(
        "tracks",
        "cover_data",
        existing_type=sa.LargeBinary(),
        nullable=True,
    )
    op.execute(
        "UPDATE tracks SET cover_source = 'embedded' "
        "WHERE cover_source = 'unknown' AND has_cover IS TRUE"
    )
    op.create_table(
        "track_cover_cache",
        sa.Column("cache_key", sa.String(length=64), primary_key=True),
        sa.Column("normalized_artist", sa.String(length=512), nullable=False),
        sa.Column("normalized_title", sa.String(length=512), nullable=False),
        sa.Column("audiodb_album_id", sa.String(length=32)),
        sa.Column("cover_url", sa.Text()),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('found', 'not_found')",
            name="ck_track_cover_cache_status",
        ),
    )
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE track_cover_cache DISABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("REVOKE ALL ON TABLE track_cover_cache FROM PUBLIC"))
        op.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE ON TABLE track_cover_cache TO app_runtime"
            )
        )


def downgrade() -> None:
    op.drop_table("track_cover_cache")
    op.drop_column("tracks", "cover_path")
    op.alter_column(
        "tracks",
        "cover_data",
        existing_type=sa.LargeBinary(),
        nullable=False,
    )
