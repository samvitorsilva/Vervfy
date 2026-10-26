"""Persist qualified track listens for monthly and yearly recaps."""
from alembic import op
import sqlalchemy as sa


revision = "0019_track_listens"
down_revision = "0018_cover_checked_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_listens",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("track_id", sa.String(length=64), nullable=False),
        sa.Column("played_at", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "track_id"],
            ["tracks.user_id", "tracks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_track_listens_user_played",
        "track_listens",
        ["user_id", "played_at"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE track_listens ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE track_listens FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("""
            CREATE POLICY track_listens_tenant_isolation ON track_listens
            USING (user_id = current_setting('app.current_user_id', true))
            WITH CHECK (user_id = current_setting('app.current_user_id', true))
        """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "DROP POLICY IF EXISTS track_listens_tenant_isolation ON track_listens"
            )
        )
    op.drop_index("ix_track_listens_user_played", table_name="track_listens")
    op.drop_table("track_listens")
