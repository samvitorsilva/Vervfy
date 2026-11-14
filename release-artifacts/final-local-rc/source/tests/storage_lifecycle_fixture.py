"""Provision roles ONLY on caller-created disposable Unix-socket test clusters."""


def provision_storage_roles(connection):
    connection.exec_driver_sql(
        "CREATE ROLE vervfy_storage_lifecycle_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
    )
    connection.exec_driver_sql(
        "CREATE ROLE vervfy_storage_cleanup NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
    )
    connection.exec_driver_sql(
        "CREATE ROLE storage_cleanup_worker LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
    )
    connection.exec_driver_sql(
        "GRANT vervfy_storage_lifecycle_owner TO migration_owner WITH INHERIT FALSE, SET TRUE, ADMIN FALSE"
    )
    connection.exec_driver_sql(
        "GRANT vervfy_storage_cleanup TO storage_cleanup_worker WITH INHERIT TRUE, SET FALSE, ADMIN FALSE"
    )


def initialize_disposable_namespace(connection):
    """Explicit test-only initialization; refuse TCP and non-test socket locations."""
    import uuid
    from pathlib import Path

    import sqlalchemy as sa

    from storage_namespace import NamespaceBinding

    url = connection.engine.url
    host = str(url.query.get("host", ""))
    if (
        url.get_backend_name() != "postgresql"
        or not host.startswith("/tmp/")
        or not Path(host).name.startswith("vervfy-storage-pg-")
        or url.host
        or url.username != "test_admin"
    ):
        raise RuntimeError(
            "Namespace initialization is restricted to disposable test sockets"
        )
    if (
        connection.exec_driver_sql("SELECT inet_server_addr() IS NULL").scalar_one()
        is not True
    ):
        raise RuntimeError("Namespace initialization requires a Unix socket")
    binding = NamespaceBinding(
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "disposable-test",
        "https://vervfy.invalid",
        "synthetic",
    )
    connection.execute(
        sa.text("""INSERT INTO vervfy_storage.namespaces
        (id,namespace_id,environment,endpoint,bucket) VALUES(1,:id,:env,:endpoint,:bucket)"""),
        {
            "id": binding.namespace_id,
            "env": binding.environment,
            "endpoint": binding.endpoint,
            "bucket": binding.bucket,
        },
    )
    return binding
