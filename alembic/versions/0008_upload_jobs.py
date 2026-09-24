"""Add durable asynchronous upload jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0008_upload_jobs"
down_revision = "0007_row_level_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("storage_path", sa.String(600), nullable=False, unique=True),
        sa.Column("track_id", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(500)),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_upload_jobs_user_id", "upload_jobs", ["user_id"])
    op.create_index("ix_upload_jobs_status", "upload_jobs", ["status"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE upload_jobs ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE upload_jobs FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("""
            CREATE POLICY upload_jobs_tenant_isolation ON upload_jobs
            USING (user_id = current_setting('app.current_user_id', true))
            WITH CHECK (user_id = current_setting('app.current_user_id', true))
        """))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP POLICY IF EXISTS upload_jobs_tenant_isolation ON upload_jobs"))
        op.execute(sa.text("ALTER TABLE upload_jobs NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE upload_jobs DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_upload_jobs_status", table_name="upload_jobs")
    op.drop_index("ix_upload_jobs_user_id", table_name="upload_jobs")
    op.drop_table("upload_jobs")
