"""Add media columns missing from the historical PostgreSQL schema."""
import sqlalchemy as sa

from alembic import op

revision = "0023_missing_media_columns"
down_revision = "0022_provider_identity_lookup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    track_columns = {column["name"] for column in sa.inspect(bind).get_columns("tracks")}
    if "cover_url" not in track_columns:
        op.add_column("tracks", sa.Column("cover_url", sa.Text(), nullable=True))

    upload_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("upload_jobs")
    }
    if "cover_data" not in upload_columns:
        op.add_column(
            "upload_jobs",
            sa.Column("cover_data", sa.LargeBinary(), nullable=True),
        )


def downgrade() -> None:
    raise RuntimeError(
        "0023_missing_media_columns is forward-only; dropping these columns could discard media data"
    )
