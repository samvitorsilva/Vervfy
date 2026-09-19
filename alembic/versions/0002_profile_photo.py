"""Add profile photos to users."""
from alembic import op
import sqlalchemy as sa

revision = "0002_profile_photo"
down_revision = "0001_postgres_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_data", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("photo_mime", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "photo_mime")
    op.drop_column("users", "photo_data")
