"""Audio moves to Supabase Storage: add tracks.storage_path, allow empty audio_data.

Idempotent on purpose — the app's startup shim may already have added the column.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_storage_path"
down_revision = "0004_session_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("tracks")}
    if "storage_path" not in columns:
        op.add_column("tracks", sa.Column("storage_path", sa.String(600), nullable=True))
    op.alter_column("tracks", "audio_data", existing_type=sa.LargeBinary(), nullable=True)


def downgrade() -> None:
    # Only safe before scripts/move_audio_to_storage.py has run: rows whose audio
    # already lives in Storage would lose their only reference to it.
    op.drop_column("tracks", "storage_path")
