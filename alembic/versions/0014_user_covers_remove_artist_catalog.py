"""Replace provider artwork with user-owned covers and remove artist caches."""
from alembic import op
import sqlalchemy as sa


revision = "0014_user_covers_remove_artist_catalog"
down_revision = "0013_artist_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "artist_image_cache" in tables:
        op.drop_table("artist_image_cache")
    if "artists" in tables:
        op.drop_table("artists")

    columns = {column["name"] for column in sa.inspect(bind).get_columns("tracks")}
    if "cover_source" not in columns:
        op.add_column(
            "tracks",
            sa.Column(
                "cover_source",
                sa.String(length=20),
                nullable=False,
                server_default="unknown",
            ),
        )
        op.execute("UPDATE tracks SET cover_source = 'unknown'")
    if bind.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_tracks_cover_source",
            "tracks",
            "cover_source IN ('embedded', 'user', 'placeholder', 'unknown')",
        )
    else:
        with op.batch_alter_table("tracks") as batch_op:
            batch_op.create_check_constraint(
                "ck_tracks_cover_source",
                "cover_source IN ('embedded', 'user', 'placeholder', 'unknown')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_tracks_cover_source", "tracks", type_="check")
        op.drop_column("tracks", "cover_source")
    else:
        with op.batch_alter_table("tracks") as batch_op:
            batch_op.drop_constraint("ck_tracks_cover_source", type_="check")
            batch_op.drop_column("cover_source")

    op.create_table(
        "artist_image_cache",
        sa.Column("normalized_name", sa.String(length=200), primary_key=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("looked_up_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('deezer', 'none')",
            name="ck_artist_image_cache_source",
        ),
    )
    op.create_table(
        "artists",
        sa.Column("deezer_id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("picture", sa.Text(), nullable=True),
        sa.Column("fans", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    if bind.dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_artists_lower_name ON artists (lower(name))")
        op.execute(
            "GRANT SELECT, INSERT, UPDATE ON TABLE artist_image_cache TO app_runtime"
        )
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE artists TO app_runtime"
        )
