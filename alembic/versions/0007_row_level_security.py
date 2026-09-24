"""Enable tenant isolation for application-owned PostgreSQL tables."""
from alembic import op
import sqlalchemy as sa

revision = "0007_row_level_security"
down_revision = "0006_tenant_integrity"
branch_labels = None
depends_on = None


TABLES = ("tracks", "favorites", "playlists", "playlist_tracks")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text("""
        CREATE POLICY tracks_tenant_isolation ON tracks
        USING (user_id = current_setting('app.current_user_id', true))
        WITH CHECK (user_id = current_setting('app.current_user_id', true))
    """))
    op.execute(sa.text("""
        CREATE POLICY favorites_tenant_isolation ON favorites
        USING (user_id = current_setting('app.current_user_id', true))
        WITH CHECK (user_id = current_setting('app.current_user_id', true))
    """))
    op.execute(sa.text("""
        CREATE POLICY playlists_tenant_isolation ON playlists
        USING (user_id = current_setting('app.current_user_id', true))
        WITH CHECK (user_id = current_setting('app.current_user_id', true))
    """))
    op.execute(sa.text("""
        CREATE POLICY playlist_tracks_tenant_isolation ON playlist_tracks
        USING (
            EXISTS (
                SELECT 1 FROM playlists
                WHERE playlists.id = playlist_tracks.playlist_id
                  AND playlists.user_id = current_setting('app.current_user_id', true)
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM playlists
                WHERE playlists.id = playlist_tracks.playlist_id
                  AND playlists.user_id = current_setting('app.current_user_id', true)
            )
        )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
