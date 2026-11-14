"""Grant the backend only the object privileges its application operations need.

No default privileges or schema-wide grants: unrelated objects, Alembic state,
provider identities and the private authentication capability remain untouched.
"""
import sqlalchemy as sa
from alembic import op

revision = "0026_application_runtime_grants"
down_revision = "0025_track_cover_sources"
branch_labels = None
depends_on = None

CRUD_TABLES = (
    "users", "tracks", "favorites", "playlists", "playlist_tracks",
    "upload_jobs", "track_listens", "artist_photos",
)
CACHE_TABLES = ("artist_images", "track_cover_cache")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    schema = bind.execute(sa.text("SELECT current_schema()")).scalar_one()
    quote = bind.dialect.identifier_preparer.quote
    op.execute(f"GRANT USAGE ON SCHEMA {quote(schema)} TO app_runtime")
    for table in CRUD_TABLES + CACHE_TABLES:
        qualified = f"{quote(schema)}.{quote(table)}"
        op.execute(f"REVOKE ALL ON TABLE {qualified} FROM app_runtime")
        # Table-level REVOKE does not remove older column-level grants.
        for column in sa.inspect(bind).get_columns(table, schema=schema):
            name = quote(column["name"])
            op.execute(
                f"REVOKE SELECT ({name}), INSERT ({name}), UPDATE ({name}), "
                f"REFERENCES ({name}) ON TABLE {qualified} FROM app_runtime"
            )
        privileges = "SELECT, INSERT, UPDATE"
        if table in CRUD_TABLES:
            privileges += ", DELETE"
        op.execute(f"GRANT {privileges} ON TABLE {qualified} TO app_runtime")
        # Current IDs are application-generated, so fresh installs have none.
        # Accommodate serial/identity sequences owned by these tables only.
        sequences = bind.execute(sa.text("""
            SELECT DISTINCT ns.nspname, seq.relname
            FROM pg_catalog.pg_class seq
            JOIN pg_catalog.pg_namespace ns ON ns.oid = seq.relnamespace
            JOIN pg_catalog.pg_depend d ON d.objid = seq.oid
              AND d.classid = 'pg_catalog.pg_class'::regclass
              AND d.refclassid = 'pg_catalog.pg_class'::regclass
              AND d.deptype IN ('a', 'i')
            WHERE seq.relkind = 'S' AND d.refobjid = to_regclass(:table)
              AND d.refobjsubid > 0
        """), {"table": qualified}).all()
        for sequence_schema, sequence in sequences:
            qualified_sequence = f"{quote(sequence_schema)}.{quote(sequence)}"
            op.execute(f"REVOKE ALL ON SEQUENCE {qualified_sequence} FROM app_runtime")
            op.execute(f"GRANT USAGE ON SEQUENCE {qualified_sequence} TO app_runtime")


def downgrade() -> None:
    raise RuntimeError("0026_application_runtime_grants is forward-only; revocation would break application access")
