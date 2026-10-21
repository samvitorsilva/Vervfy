"""Persist cover lookup attempts for retry cooldowns."""
from alembic import op
import sqlalchemy as sa


revision = "0018_cover_checked_at"
down_revision = "0017_track_covers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("cover_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracks", "cover_checked_at")
