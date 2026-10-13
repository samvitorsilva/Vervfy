"""Add tenant-owned and Commons artist photos."""
from alembic import op
import sqlalchemy as sa


revision = "0015_artist_photos"
down_revision = "0014_user_covers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artist_photos",
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("normalized_artist_name", sa.String(length=200), primary_key=True),
        sa.Column("jpeg_data", sa.LargeBinary(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("author", sa.Text()),
        sa.Column("license_name", sa.String(length=100)),
        sa.Column("license_url", sa.Text()),
        sa.Column("commons_page_url", sa.Text()),
        sa.Column(
            "resized_for_display",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('user', 'commons')",
            name="ck_artist_photos_source",
        ),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE artist_photos ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE artist_photos FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("""
            CREATE POLICY artist_photos_tenant_isolation ON artist_photos
            USING (user_id = current_setting('app.current_user_id', true))
            WITH CHECK (user_id = current_setting('app.current_user_id', true))
        """))
        op.execute(sa.text("REVOKE ALL ON TABLE artist_photos FROM PUBLIC"))
        op.execute(sa.text("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE ALL ON TABLE artist_photos FROM anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE ALL ON TABLE artist_photos FROM authenticated';
                END IF;
            END; $$
        """))
        op.execute(sa.text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE artist_photos TO app_runtime"
        ))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(
            "DROP POLICY IF EXISTS artist_photos_tenant_isolation ON artist_photos"
        ))
        op.execute(sa.text("ALTER TABLE artist_photos NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE artist_photos DISABLE ROW LEVEL SECURITY"))
    op.drop_table("artist_photos")
