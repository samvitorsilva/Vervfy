"""Supabase-like catalog setup for disposable PostgreSQL 17 tests only."""

import sqlalchemy as sa

PROVIDER_SCHEMAS = (
    "auth",
    "extensions",
    "graphql",
    "graphql_public",
    "pgbouncer",
    "realtime",
    "storage",
    "vault",
)

VERVFY_ROLES = (
    "vervfy_oauth_staging_user",
    "app_runtime",
    "google_auth_lookup",
    "vervfy_identity_lookup_owner",
    "vervfy_identity_lookup",
    "vervfy_storage_lifecycle_owner",
    "vervfy_storage_cleanup",
    "storage_cleanup_worker",
)


def provision_supabase_catalog(connection):
    """Model provider roles/default ACLs without connecting to any hosted project."""
    connection.exec_driver_sql(
        "CREATE ROLE postgres LOGIN CREATEROLE BYPASSRLS"
    )
    connection.exec_driver_sql(
        "CREATE ROLE supabase_admin NOLOGIN CREATEROLE"
    )
    connection.exec_driver_sql("CREATE ROLE anon NOLOGIN")
    connection.exec_driver_sql("CREATE ROLE authenticated NOLOGIN")
    connection.exec_driver_sql("CREATE ROLE service_role NOLOGIN BYPASSRLS")
    connection.exec_driver_sql("ALTER DATABASE postgres OWNER TO postgres")

    for schema in PROVIDER_SCHEMAS:
        connection.exec_driver_sql(
            f"CREATE SCHEMA {schema} AUTHORIZATION supabase_admin"
        )

    connection.exec_driver_sql("SET ROLE supabase_admin")
    try:
        connection.exec_driver_sql("CREATE TABLE auth.provider_probe(id integer)")
        connection.exec_driver_sql("CREATE TABLE storage.provider_probe(id integer)")
        connection.exec_driver_sql(
            "CREATE VIEW extensions.pg_stat_statements AS SELECT 1::bigint AS calls"
        )
        connection.exec_driver_sql(
            "CREATE VIEW extensions.pg_stat_statements_info AS "
            "SELECT 1::bigint AS dealloc"
        )
        connection.exec_driver_sql(
            "GRANT SELECT ON extensions.pg_stat_statements, "
            "extensions.pg_stat_statements_info TO PUBLIC"
        )
    finally:
        connection.exec_driver_sql("RESET ROLE")

    for creator in ("postgres", "supabase_admin"):
        for object_type, grantee in (
            ("TABLES", "anon, authenticated, service_role"),
            ("SEQUENCES", "anon, authenticated, service_role"),
            ("FUNCTIONS", "anon, authenticated, service_role"),
        ):
            connection.exec_driver_sql(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {creator} "
                f"IN SCHEMA public GRANT ALL ON {object_type} TO {grantee}"
            )

    connection.exec_driver_sql("REVOKE CREATE ON SCHEMA public FROM PUBLIC")


def grant_creator_edges(connection, role_names=VERVFY_ROLES):
    """Model the provider-generated tuple in a local cluster with catalog edits."""
    for role in role_names:
        connection.exec_driver_sql(
            f"GRANT {role} TO postgres "
            "WITH ADMIN TRUE, INHERIT FALSE, SET FALSE"
        )
        result = connection.execute(
            sa.text(
            """
            UPDATE pg_catalog.pg_auth_members
            SET grantor='supabase_admin'::regrole
            WHERE roleid=CAST(:role AS regrole) AND member='postgres'::regrole
              AND grantor=current_user::regrole
              AND admin_option AND NOT inherit_option AND NOT set_option
            """
            ),
            {"role": role},
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Could not model provider creator edge for {role}")


def grant_capabilities(connection, migration_role):
    """Create the reviewed Vervfy graph with postgres as the grantor."""
    connection.exec_driver_sql("SET ROLE postgres")
    try:
        connection.exec_driver_sql(
            f"GRANT vervfy_identity_lookup_owner TO {migration_role} "
            "WITH ADMIN FALSE, INHERIT FALSE, SET TRUE"
        )
        connection.exec_driver_sql(
            "GRANT vervfy_identity_lookup TO google_auth_lookup "
            "WITH ADMIN FALSE, INHERIT TRUE, SET FALSE"
        )
        connection.exec_driver_sql(
            f"GRANT vervfy_storage_lifecycle_owner TO {migration_role} "
            "WITH ADMIN FALSE, INHERIT FALSE, SET TRUE"
        )
        connection.exec_driver_sql(
            "GRANT vervfy_storage_cleanup TO storage_cleanup_worker "
            "WITH ADMIN FALSE, INHERIT TRUE, SET FALSE"
        )
    finally:
        connection.exec_driver_sql("RESET ROLE")
