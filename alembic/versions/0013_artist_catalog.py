"""Create the shared Deezer artist catalog cache."""
from alembic import op
import sqlalchemy as sa


revision = "0013_artist_catalog"
down_revision = "0012_artist_image_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "artists" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "artists",
        sa.Column("deezer_id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("picture", sa.Text(), nullable=True),
        sa.Column("fans", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_artists_lower_name ON artists (lower(name))"
        )
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE artists TO app_runtime"
        )


def downgrade() -> None:
    """Keep this shared cache: the migration may have adopted an existing table."""
