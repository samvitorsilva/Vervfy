"""Create the shared artist image cache."""
from alembic import op
import sqlalchemy as sa


revision = "0012_artist_image_cache"
down_revision = "0011_playlist_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artist_image_cache",
        sa.Column("normalized_name", sa.String(200), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("looked_up_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('deezer', 'none')", name="ck_artist_image_cache_source"),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "GRANT SELECT, INSERT, UPDATE ON TABLE artist_image_cache TO app_runtime"
        )


def downgrade() -> None:
    op.drop_table("artist_image_cache")
