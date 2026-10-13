"""Add the shared TheAudioDB URL cache and Storage paths for artist photos."""
from alembic import op
import sqlalchemy as sa


revision = "0016_audiodb_artist_images"
down_revision = "0015_artist_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "artist_images",
        sa.Column("normalized_artist_name", sa.String(length=200), primary_key=True),
        sa.Column("audiodb_id", sa.String(length=32)),
        sa.Column("image_url", sa.Text()),
        sa.Column("banner_url", sa.Text()),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('found', 'not_found')",
            name="ck_artist_images_status",
        ),
    )
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE artist_images DISABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("REVOKE ALL ON TABLE artist_images FROM PUBLIC"))
        op.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE ON TABLE artist_images TO app_runtime"
            )
        )
    with op.batch_alter_table("artist_photos") as batch_op:
        batch_op.add_column(sa.Column("storage_path", sa.String(length=600), nullable=True))
        batch_op.alter_column(
            "jpeg_data",
            existing_type=sa.LargeBinary(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("artist_photos") as batch_op:
        batch_op.alter_column(
            "jpeg_data",
            existing_type=sa.LargeBinary(),
            nullable=False,
        )
        batch_op.drop_column("storage_path")
    op.drop_table("artist_images")
